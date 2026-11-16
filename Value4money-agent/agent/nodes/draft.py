# Build every figure and every finding in code, then let the model supply short notes only.
#
# What this node does, in order:
#  1. It builds the findings from state: one pool finding with the median and normal range, one
#     finding for each bid outside the normal range, and one finding for each bid whose stated total
#     does not match its computed total. Every sentence is written here, from the numbers the tools
#     returned. The model never writes a figure, so it cannot write a wrong one.
#  2. It asks draft_review_wording for one summary note and one note per finding. The payload carries
#     the finding keys and positions, never money, percentages or bidder names, so the notes cannot
#     add a figure. Notes with digits, number words, bidder names or currency are refused.
#  3. It appends the notes to the code-written sentences and renders the file with draft_review_file.
#     A note that breaks the house rules sends the draft back once; on the final attempt the file is
#     rendered without notes rather than failing the run.
#  4. It lists every pooled award in the sources table, because the committee needs the whole pool
#     that produced the median, not only the awards a finding happens to mention.
#
# What it returns: the rendered markdown, the summary, the findings with typed sources, every pooled
# source, the notes, whether the report lost its notes, and the draft attempt count.

import re
from typing import Any, Dict, List, Optional

from config import settings
from agent.llm import LlmError, ask_json
from agent.state import AgentState
from agent.tools import draft_review_file
from mcp_server.tools.draft_review_file import ReviewError
from mcp_server.tools.report_format import kes, pct_phrase, position_label
from mcp_server.tools.report_model import build_report_model

SOURCE_FIELDS = ("award_id", "ocid", "data_year", "buyer_name", "title", "value_kes")

NUMBER_WORD = re.compile(
    r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|"
    r"fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|"
    r"eighty|ninety|hundred|thousand|million|first|second|third|half)\b", re.IGNORECASE)
FIGURE = re.compile(r"\d")
CURRENCY = re.compile(r"\b(KES|Ksh|shillings?)\b|[$€£%]", re.IGNORECASE)


def _readable(state: AgentState) -> List[Dict[str, Any]]:
    """The bids whose documents were read cleanly and can carry a benchmarked total."""
    return [bid for bid in state["bids"] if bid.get("status") == "ok"]


def _source_record(row: Dict[str, Any]) -> Dict[str, Any]:
    """Copy the fields the sources table needs from one pooled award."""
    return {field: row.get(field) for field in SOURCE_FIELDS}


def _pool_sources(pool: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Every pooled award as a typed pool source, in pool order."""
    return [{"kind": "pool", "award_id": row["award_id"]} for row in pool]


def _bid_source(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """One parsed bid as a typed bid source, with the file and page its total came from."""
    return {"kind": "bid", "bidder": parsed["bidder"], "file": parsed.get("file"),
            "page": parsed.get("total_page")}


def _pool_finding(state: AgentState) -> Dict[str, Any]:
    """Write the pool finding: how many awards, the median and the normal range."""
    benchmark = state["benchmark"]
    if benchmark.get("confidence") == "insufficient":
        text = (f"Only {benchmark.get('n')} comparable awards were found, too few to set a "
                "reliable median or normal range.")
    else:
        text = (f"{benchmark['n']} comparable awards have a median of {kes(benchmark['median_kes'])} "
                f"and a normal range of {kes(benchmark['q1_kes'])} to {kes(benchmark['q3_kes'])}.")
    return {"key": "pool", "kind": "pool", "text": text,
            "sources": _pool_sources(state.get("pool", [])), "note": None}


def _bid_finding(parsed: Dict[str, Any], scored: Dict[str, Any], n: int,
                 pool: List[Dict[str, Any]], key: str) -> Dict[str, Any]:
    """Write one bid finding for a total outside the normal range."""
    text = (f"{parsed['bidder']} total {kes(scored['total'])} is "
            f"{pct_phrase(scored.get('pct_vs_median'))} the median of "
            f"{n} similar awards, {position_label(scored['position'])}.")
    return {"key": key, "kind": "bid", "text": text,
            "sources": [_bid_source(parsed)] + _pool_sources(pool), "note": None}


def _arithmetic_finding(parsed: Dict[str, Any], key: str) -> Dict[str, Any]:
    """Write one arithmetic finding from the two totals the extraction already produced."""
    stated = parsed.get("stated_total")
    computed = parsed.get("computed_total")
    difference = abs(float(stated) - float(computed))
    text = (f"{parsed['bidder']} stated total {kes(stated)} does not match computed total "
            f"{kes(computed)}, a difference of {kes(difference)}.")
    return {"key": key, "kind": "arithmetic", "text": text,
            "sources": [_bid_source(parsed)], "note": None}


def build_findings(state: AgentState) -> List[Dict[str, Any]]:
    """Build every finding from state, with typed sources, before any model call."""
    findings = [_pool_finding(state)]
    scored = {row["bidder"]: row for row in state["benchmark"].get("bids", [])}
    n = state["benchmark"].get("n")
    for index, parsed in enumerate(_readable(state), start=1):
        row = scored.get(parsed["bidder"])
        if row and row.get("position") not in (None, "within_range"):
            findings.append(_bid_finding(parsed, row, n, state.get("pool", []), f"bid:{index}"))
    for index, parsed in enumerate(_readable(state), start=1):
        if parsed.get("arithmetic_ok") is False:
            findings.append(_arithmetic_finding(parsed, f"arithmetic:{index}"))
    return findings


def _note_payload(state: AgentState, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Show the model the findings it must annotate, without any figure or bidder name."""
    return {
        "tender_ref": state["tender_ref"],
        "description": state.get("description"),
        "pool_size": len(state.get("pool", [])),
        "findings": [{"key": finding["key"], "kind": finding["kind"],
                      "position": next((row.get("position") for row in state["benchmark"].get("bids", [])
                                        if row.get("bidder") == finding["sources"][0].get("bidder")),
                                       None)}
                     for finding in findings],
    }


def _words(text: str) -> int:
    """Count the words in a note."""
    return len(text.split())


def _note_problems(answer: Dict[str, Any], findings: List[Dict[str, Any]],
                   bidders: List[str]) -> List[str]:
    """Check every model note against the length, figure and naming rules."""
    summary = answer.get("summary_note")
    notes = answer.get("finding_notes") or {}
    problems: List[str] = []
    if not isinstance(summary, str) or not summary.strip():
        problems.append("summary note is missing")
    elif _words(summary) > 40:
        problems.append("summary note is longer than 40 words")
    else:
        problems += _text_problems(summary, "summary note", bidders)
    expected = [finding["key"] for finding in findings]
    for key in expected:
        note = notes.get(key)
        if not isinstance(note, str) or not note.strip():
            problems.append(f"finding note for {key} is missing")
        elif _words(note) > 25:
            problems.append(f"finding note for {key} is longer than 25 words")
        else:
            problems += _text_problems(note, f"finding note for {key}", bidders)
    return problems


def _text_problems(text: str, where: str, bidders: List[str]) -> List[str]:
    """Refuse a note that carries a figure, a number word, a bidder name or a currency."""
    lowered = text.lower()
    if FIGURE.search(text):
        return [f"{where} contains a figure"]
    if NUMBER_WORD.search(text):
        return [f"{where} contains a number word"]
    if CURRENCY.search(text):
        return [f"{where} contains a currency or percentage"]
    for bidder in bidders:
        if bidder.lower() in lowered:
            return [f"{where} names a bidder"]
    return []


def build_review(state: AgentState, findings: Optional[List[Dict[str, Any]]] = None,
                 summary_note: Optional[str] = None,
                 finding_notes: Optional[Dict[str, str]] = None,
                 sources: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Assemble what draft_review_file needs from the stored state and the accepted notes."""
    findings = state.get("findings", []) if findings is None else findings
    summary_note = state.get("summary_note") if summary_note is None else summary_note
    finding_notes = state.get("finding_notes", {}) if finding_notes is None else finding_notes
    sources = state.get("sources", []) if sources is None else sources
    return {
        "run_id": state["run_id"],
        "tender_ref": state["tender_ref"],
        "summary": summary_note or "",
        "summary_note": summary_note,
        "benchmark": state["benchmark"],
        "search": state.get("search", {}),
        "excluded": state.get("excluded", {}),
        "bids": [{"bidder": bid["bidder"], "arithmetic_issues": bid.get("issues", [])}
                 for bid in _readable(state)],
        "findings": findings,
        "sources": sources,
        "report_degraded": state.get("report_degraded", False),
    }


def _render_report(state: AgentState, review: Dict[str, Any]) -> Dict[str, str]:
    """Build the structured model and file it through the audited renderer."""
    model = build_report_model(review, state)
    carried = dict(review, report_model=model.model_dump(mode="json"))
    return draft_review_file(state["run_id"], carried)


def _degraded(state: AgentState, findings: List[Dict[str, Any]],
              sources: List[Dict[str, Any]], rounds: int, reason: str) -> Dict[str, Any]:
    """Render the code-written findings without notes after the last attempt failed."""
    result: Dict[str, Any] = {"summary": "", "summary_note": None, "finding_notes": {},
                              "bid_comments": {}, "findings": findings, "sources": sources,
                              "verify_rounds": rounds, "report_degraded": True,
                              "errors": [f"draft_review_file dropped the notes: {reason}"]}
    report_model = build_report_model(
        build_review(state, findings=findings, summary_note=None, finding_notes={}, sources=sources),
        state)
    result["report_model"] = report_model.model_dump(mode="json")
    try:
        rendered = _render_report(state, build_review(
            state, findings=findings, summary_note=None, finding_notes={}, sources=sources))
    except ReviewError as exc:
        result["review_markdown"] = ""
        result["errors"].append(f"draft_review_file refused the wording: {exc}")
        return result
    result["review_markdown"] = rendered["markdown"]
    return result


def draft_node(state: AgentState) -> dict:
    """Build the findings in code, get notes from the model, and render the committee file."""
    findings = build_findings(state)
    sources = [_source_record(row) for row in state.get("pool", [])]
    bidders = [parsed["bidder"] for parsed in _readable(state)]
    rounds = state.get("verify_rounds", 0) + 1
    final_attempt = rounds >= settings.max_draft_attempts

    try:
        answer = ask_json("draft_review_wording", _note_payload(state, findings))
        problems = _note_problems(answer, findings, bidders)
    except LlmError as exc:
        answer, problems = {}, [f"the wording model failed: {exc}"]

    if problems:
        if final_attempt:
            return _degraded(state, findings, sources, rounds, problems[0])
        return {"review_markdown": "", "findings": findings, "sources": sources,
                "verify_rounds": rounds, "errors": [f"draft notes refused: {problem}"
                                                   for problem in problems]}

    notes = answer.get("finding_notes") or {}
    for finding in findings:
        finding["note"] = notes.get(finding["key"])
        finding["text"] = f"{finding['text']} {finding['note']}"
    result: Dict[str, Any] = {
        "summary": answer["summary_note"],
        "summary_note": answer["summary_note"],
        "finding_notes": notes,
        "bid_comments": {},
        "findings": findings,
        "sources": sources,
        "verify_rounds": rounds,
        "report_degraded": False,
    }
    report_model = build_report_model(build_review(
        state, findings=findings, summary_note=answer["summary_note"],
        finding_notes=notes, sources=sources), state)
    result["report_model"] = report_model.model_dump(mode="json")

    try:
        rendered = _render_report(state, build_review(
            state, findings=findings, summary_note=answer["summary_note"],
            finding_notes=notes, sources=sources))
    except ReviewError as exc:
        if final_attempt:
            return _degraded(state, findings, sources, rounds, str(exc))
        result["review_markdown"] = ""
        result["errors"] = [f"draft_review_file refused the wording: {exc}"]
        return result

    result["review_markdown"] = rendered["markdown"]
    return result

