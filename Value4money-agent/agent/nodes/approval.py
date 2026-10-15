# Stop the run and wait for a named human. Nothing is written and nothing is filed without one.
#
# What this node does, in order:
#  1. It refuses to ask about nothing. If the previous draft left no report, because draft_review_file
#     rejected the wording, there is nothing to put in front of a person. The node says the run has no
#     report and returns without interrupting, and route_after_approval ends the run there because the
#     status is not approved.
#  2. Otherwise it interrupts with what the approver needs in order to decide: the run, the tender
#     reference, the summary, the size and confidence of the pool with its median and range, one line
#     per bid, any failures the automated checks could not clear, and the full report as rendered. If
#     verify_sources did not pass before the redraft cap was spent, those failures are in the payload,
#     so the person sees exactly what is unresolved and decides for themselves. The same payload is
#     the record of what was actually approved.
#  3. It reads the resume value and accepts only a real decision from a real person: decision must be
#     approved or rejected, and approved_by must be a name of at least two characters that is not one
#     of the placeholders the filing tool also refuses. That rule is imported rather than repeated, so
#     approval and filing cannot drift apart. A malformed resume stops the run with an error naming
#     the field, rather than being quietly counted as a rejection.
#
# What it returns: the approval status, the approver's name and their note.

from typing import Any, Dict

from langgraph.types import interrupt

from mcp_server.tools.submit_for_committee import PLACEHOLDERS
from agent.state import AgentState

DECISIONS = ("approved", "rejected")


def _request(state: AgentState) -> Dict[str, Any]:
    """Everything the approver is shown, including the report itself and anything unresolved."""
    benchmark = state.get("benchmark", {})
    return {
        "run_id": state["run_id"],
        "tender_ref": state.get("tender_ref"),
        "summary": state.get("summary", ""),
        "benchmark": {"n": benchmark.get("n"), "confidence": benchmark.get("confidence"),
                      "median_kes": benchmark.get("median_kes"),
                      "q1_kes": benchmark.get("q1_kes"), "q3_kes": benchmark.get("q3_kes")},
        "bids": benchmark.get("bids", []),
        "verify_ok": bool(state.get("verify_ok", False)),
        "verify_failures": state.get("verify_failures", []),
        "review_markdown": state.get("review_markdown", ""),
    }


def _read_decision(payload: Any) -> Dict[str, str]:
    """Read the resume value, refusing anything that is not a decision by a named person."""
    if not isinstance(payload, dict):
        raise ValueError(f"approval must resume with a dict, got {type(payload).__name__}: {payload!r}")
    decision = payload.get("decision")
    if decision not in DECISIONS:
        raise ValueError(f"approval decision must be one of {list(DECISIONS)}, got {decision!r}")
    name = payload.get("approved_by")
    if not isinstance(name, str) or len(name.strip()) < 2:
        raise ValueError(f"approved_by must be a named human, got {name!r}")
    if name.strip().lower() in PLACEHOLDERS:
        raise ValueError(f"approved_by must be a named human, got placeholder {name.strip()!r}")
    note = payload.get("note") or ""
    return {"decision": decision, "approved_by": name.strip(),
            "note": note if isinstance(note, str) else str(note)}


def approval_node(state: AgentState) -> dict:
    """Pause the run and record a named human's decision."""
    if not (state.get("review_markdown") or "").strip():
        return {"approval_status": "no_report", "approved_by": None,
                "approval_note": "no review was produced to approve"}

    decision = _read_decision(interrupt(_request(state)))
    return {"approval_status": decision["decision"], "approved_by": decision["approved_by"],
            "approval_note": decision["note"]}