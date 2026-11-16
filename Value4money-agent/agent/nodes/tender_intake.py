# Read the tender document, when one was supplied, before any bid is opened.
#
# Tender values are evidence too, but only when they carry a page and the line they came from. This
# node reads the labelled fields with extract_tender_pdf and carries the tool's own record through
# untouched: the field, its value, and where on the page it sits. Missing fields are listed rather
# than filled in, and a tender that cannot be read is one error, not a stopped run.
#
# When no tender is supplied, this node returns empty fields. Web uploads are bids only, and a run
# without a tender is normal rather than a failure.

from typing import Any, Dict

from agent.state import AgentState
from agent.tools import extract_tender_pdf


def tender_intake_node(state: AgentState) -> dict:
    """Read the tender's labelled fields, or return empty fields when none was supplied."""
    path = state.get("tender_path")
    if not path:
        return {"tender": {}, "tender_fields": {}, "tender_missing": [], "tender_rejected": []}

    try:
        result: Dict[str, Any] = extract_tender_pdf(state["run_id"], path)
    except ValueError as exc:
        return {"tender": {}, "tender_fields": {}, "tender_missing": [],
                "tender_rejected": [], "errors": [f"tender {path}: {exc}"]}

    return {
        "tender": result,
        "tender_fields": result.get("fields", {}),
        "tender_missing": result.get("missing", []),
        "tender_rejected": result.get("rejected", []),
    }
