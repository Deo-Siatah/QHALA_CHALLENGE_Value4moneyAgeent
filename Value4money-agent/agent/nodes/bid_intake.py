# Read every bid with the tolerant extractor and keep the document's own verdict.
#
# One file per bidder, read under the run's own run_id so every read is in audit_log. A file that
# cannot be opened becomes one parse issue naming it; the other bids still run, because a tender
# often arrives with one bad scan. Each readable bid keeps the extractor's confidence, status, method
# and flagged pages, and nothing here corrects a figure: the arithmetic issues are carried through.
#
# The tender reference has to agree across the bids and, when a tender document was read, with it.
# The tender's reference wins; a bid that carries a different one stops the run. A run whose files
# describe two tenders is not evidence about either one.
#
# The description comes from the tender title when one was read, so it does not depend on the first
# bid. The model only classifies the category then. Without a title it returns to describing the
# work from the first readable bid. It never chooses what to read and never supplies a number.

import contextvars
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Tuple

from agent.state import AgentState
from agent.llm import ask_json
from agent.tools import parse_bid_pdf
from agent.tracing import record_tender

MAX_PARSE_WORKERS = 4

CATEGORIES = ("works", "goods", "services")

STOPLIST = {"the", "and", "or", "of", "in", "to", "for", "with", "by", "a", "an", "is",
            "are", "was", "were", "at", "as", "on", "that", "this", "it", "proposed"}


def _core_terms(answer: Dict[str, Any], description: str, title: str) -> List[str]:
    """Use the model's core terms or fall back to the first two work words in the title."""
    terms: List[str] = []
    raw = answer.get("core_terms")
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str) and item.strip():
                terms.append(item.strip().lower())
    if not terms:
        words = re.findall(r"[a-z0-9]+", (title or description).lower())
        terms = [word for word in words if len(word) >= 3 and word not in STOPLIST][:2]
    terms = list(dict.fromkeys(terms))[:3]
    if not terms:
        raise ValueError("intake could not name a core term for the work")
    return terms


def _tender_profile(tender_ref: str, items: List[Dict[str, Any]],
                    title: str = "") -> Dict[str, Any]:
    """Classify the work, taking the description from the tender title when one was read."""
    if title:
        answer = ask_json("intake_tender_category", {"tender_ref": tender_ref,
                                                     "title": title, "items": items})
        prompt = "intake_tender_category"
        description = title
    else:
        answer = ask_json("intake_tender_profile", {"tender_ref": tender_ref, "items": items})
        prompt = "intake_tender_profile"
        description = answer.get("description")
    category = answer.get("category")
    if category not in CATEGORIES:
        raise ValueError(f"{prompt} gave category {category!r}, "
                         f"expected one of {list(CATEGORIES)}")
    if not isinstance(description, str) or not description.strip():
        raise ValueError(f"{prompt} gave description {description!r}, expected text")
    return {"category": category, "description": description.strip(),
            "core_terms": _core_terms(answer, description.strip(), title)}


def _extract_in(context: Any, run_id: str, path: str) -> Any:
    """Read one bid inside a copy of the node's tracing context."""
    try:
        return context.copy().run(parse_bid_pdf, run_id, path)
    except ValueError as exc:
        return exc


def _extract_all(run_id: str, paths: List[str]) -> List[Tuple[str, Any]]:
    """Read every bid PDF at once and keep each result with the path it came from."""
    context = contextvars.copy_context()
    if len(paths) < 2:
        return [(path, _extract_in(context, run_id, path)) for path in paths]
    with ThreadPoolExecutor(max_workers=min(len(paths), MAX_PARSE_WORKERS)) as pool:
        read = pool.map(lambda path: _extract_in(context, run_id, path), paths)
        return list(zip(paths, read))


def bid_intake_node(state: AgentState) -> dict:
    """Read the bid PDFs and carry each document's status into state."""
    run_id = state["run_id"]
    bids: List[Dict[str, Any]] = []
    bid_status: Dict[str, str] = {}
    parse_issues: List[str] = []
    errors: List[str] = []

    for path, parsed in _extract_all(run_id, list(state.get("pdf_paths", []))):
        if isinstance(parsed, ValueError):
            parse_issues.append(f"{path}: {parsed}")
            continue
        bids.append(parsed)
        bid_status[path] = parsed.get("status", "")

    readable = [bid for bid in bids if bid.get("status") == "ok"]
    if not readable:
        errors.append(f"no bid could be read from {state.get('pdf_paths')}: {parse_issues}")
    if not bids:
        return {"bids": [], "bid_status": {}, "parse_issues": parse_issues, "errors": errors}

    first = readable[0] if readable else bids[0]
    tender_fields = state.get("tender_fields") or {}
    tender_reference = (tender_fields.get("reference") or {}).get("value") or ""
    tender_title = (tender_fields.get("title") or {}).get("value") or ""
    tender_ref = tender_reference or first.get("tender_ref") or ""
    record_tender(tender_ref)

    result: Dict[str, Any] = {
        "bids": bids,
        "bid_status": bid_status,
        "parse_issues": parse_issues,
        "tender_ref": tender_ref,
        "tender_ref_conflict": False,
    }
    if readable:
        result.update(_tender_profile(tender_ref, readable[0].get("items") or [], tender_title))

    references = sorted({bid["tender_ref"] for bid in bids if bid.get("tender_ref")})
    if tender_reference:
        conflicts = [f"{bid.get('bidder') or 'a bid'} has {bid['tender_ref']}"
                     for bid in bids
                     if bid.get("tender_ref") and bid["tender_ref"] != tender_reference]
        if conflicts:
            errors.append(f"bid tender reference does not match the tender "
                          f"{tender_reference}: " + "; ".join(conflicts))
            result["tender_ref_conflict"] = True
    elif len(references) > 1:
        errors.append(f"bids disagree on tender reference: {', '.join(references)}")
        result["tender_ref_conflict"] = True
    if errors:
        result["errors"] = errors
    return result
