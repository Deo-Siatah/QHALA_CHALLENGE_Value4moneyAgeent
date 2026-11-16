# Check the draft against the house rules before a human is asked to read it. No model, no tool.
# The report is now written by code, so this node no longer hunts for invented figures. It checks
# that every finding has a real source, that every cleaned pool award is cited, that every flagged
# bid and arithmetic failure has its own finding, and that the model's short notes obey the rules.
#
# It sets verify_ok and appends its failures. route_after_verify_sources reads verify_ok against
# max_draft_attempts to decide whether to redraft or to ask a human.

import re
from typing import Any, Dict, List

from agent.state import AgentState

NOT_ENOUGH = "Not enough comparable awards to benchmark these bids."

NUMBER_WORD = re.compile(
    r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|"
    r"fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|"
    r"eighty|ninety|hundred|thousand|million|first|second|third|half)\b", re.IGNORECASE)
FIGURE = re.compile(r"\d")
CURRENCY = re.compile(r"\b(KES|Ksh|shillings?)\b|[$€£%]", re.IGNORECASE)


def _readable(state: AgentState) -> List[Dict[str, Any]]:
    """The bids whose documents were read cleanly."""
    return [bid for bid in state.get("bids", []) if bid.get("status") == "ok"]


def _sources(finding: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalise a finding's sources, treating a bare award id as a pool source."""
    return [{"kind": "pool", "award_id": source} if isinstance(source, str) else source
            for source in finding.get("sources") or []]


def _check_sources(state: AgentState) -> List[str]:
    """Every finding needs a real source, and a bid source needs its document and page."""
    listed = {source["award_id"] for source in state.get("sources", [])}
    pooled = {row["award_id"] for row in state.get("pool", [])}
    documents = {bid["bidder"]: bid for bid in _readable(state)}
    problems: List[str] = []
    for index, finding in enumerate(state.get("findings", []), start=1):
        sources = _sources(finding)
        if not sources:
            problems.append(f"finding {index} has no source: no source, no finding")
            continue
        for source in sources:
            if source.get("kind") == "bid":
                bidder = source.get("bidder")
                document = documents.get(bidder)
                if document is None:
                    problems.append(f"finding {index} cites {bidder}, which is not a readable bid")
                    continue
                if not source.get("file") or source["file"] != document.get("file"):
                    problems.append(f"finding {index} cites {source.get('file')}, which is not the "
                                    f"parsed document for {bidder}")
                page = source.get("page")
                if not isinstance(page, int) or page < 1:
                    problems.append(f"finding {index} cites no page for {bidder}")
                elif document.get("total_page") is not None and page > document["total_page"]:
                    problems.append(f"finding {index} cites page {page} but {bidder} has "
                                    f"{document['total_page']} pages")
            else:
                award_id = source.get("award_id")
                if award_id not in listed:
                    problems.append(f"finding {index} cites {award_id}, which is not in the sources table")
                elif award_id not in pooled:
                    problems.append(f"finding {index} cites {award_id}, which is not in the "
                                    "benchmarked pool")
    return problems


def _check_coverage(state: AgentState) -> List[str]:
    """Every pooled award has to appear in at least one finding."""
    cited = {source.get("award_id") for finding in state.get("findings", [])
             for source in _sources(finding) if source.get("kind") != "bid"}
    return [f"pooled award {row['award_id']} is not cited by any finding"
            for row in state.get("pool", []) if row["award_id"] not in cited]


def _bid_cited(findings: List[Dict[str, Any]], kind: str, bidder: str) -> bool:
    """Whether a finding of the given kind cites this bid's document."""
    for finding in findings:
        if finding.get("kind") != kind:
            continue
        if any(source.get("kind") == "bid" and source.get("bidder") == bidder
               for source in _sources(finding)):
            return True
    return False


def _check_required(state: AgentState) -> List[str]:
    """A flagged bid or arithmetic failure must have its own finding."""
    findings = state.get("findings", [])
    problems = []
    for row in state.get("benchmark", {}).get("bids", []):
        if row.get("position") not in (None, "within_range"):
            if not _bid_cited(findings, "bid", row["bidder"]):
                problems.append(f"{row['bidder']} has no bid finding for its position")
    for bid in _readable(state):
        if bid.get("arithmetic_ok") is False and not _bid_cited(findings, "arithmetic", bid["bidder"]):
            problems.append(f"{bid['bidder']} has an arithmetic failure but no arithmetic finding")
    return problems


def _text_problems(text: str, where: str, bidders: List[str]) -> List[str]:
    """Refuse a note that carries a figure, a number word, a bidder name or a currency."""
    if FIGURE.search(text):
        return [f"{where} contains a figure"]
    if NUMBER_WORD.search(text):
        return [f"{where} contains a number word"]
    if CURRENCY.search(text):
        return [f"{where} contains a currency or percentage"]
    for bidder in bidders:
        if bidder.lower() in text.lower():
            return [f"{where} names a bidder"]
    return []


def _check_notes(state: AgentState) -> List[str]:
    """The model's notes must stay short and must not add facts or names."""
    if state.get("report_degraded"):
        return []
    bidders = [bid["bidder"] for bid in _readable(state)]
    summary = state.get("summary_note")
    problems = []
    if not isinstance(summary, str) or not summary.strip():
        problems.append("summary note is missing")
    elif len(summary.split()) > 40:
        problems.append("summary note is longer than 40 words")
    else:
        problems += _text_problems(summary, "summary note", bidders)
    notes = state.get("finding_notes") or {}
    for finding in state.get("findings", []):
        key = finding.get("key")
        if not key:
            continue
        note = notes.get(key)
        if not isinstance(note, str) or not note.strip():
            problems.append(f"finding note for {key} is missing")
        elif len(note.split()) > 25:
            problems.append(f"finding note for {key} is longer than 25 words")
        else:
            problems += _text_problems(note, f"finding note for {key}", bidders)
    return problems


def _check_positions(state: AgentState) -> List[str]:
    """A thin pool may not carry a percentage or a position label."""
    benchmark = state.get("benchmark", {})
    if benchmark.get("confidence") != "insufficient":
        return []
    problems = []
    for bid in benchmark.get("bids") or []:
        if bid.get("position"):
            problems.append(f"{bid.get('bidder')} is labelled {bid['position']}, but with no "
                            "comparable awards a bid cannot be labelled by position at all")
        if bid.get("pct_vs_median") is not None:
            problems.append(f"{bid.get('bidder')} is given {bid['pct_vs_median']}% against a "
                            "median that was never computed")
    return problems


def verify_sources_node(state: AgentState) -> dict:
    """Check the draft's sources and notes, and say whether a human may see it."""
    problems: List[str] = []
    markdown = state.get("review_markdown") or ""

    if not markdown.strip():
        problems.append("no review to verify: the previous draft was refused")
    problems += _check_sources(state)
    problems += _check_coverage(state)
    problems += _check_required(state)
    problems += _check_notes(state)
    problems += _check_positions(state)
    if state.get("benchmark", {}).get("confidence") == "insufficient" and NOT_ENOUGH not in markdown:
        problems.append(f"the evidence is thin but the report does not say: {NOT_ENOUGH}")

    return {"verify_ok": not problems, "verify_failures": problems}
