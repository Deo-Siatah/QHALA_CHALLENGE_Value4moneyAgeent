# Decide whether a person must look at the intake before the run searches anything.
#
# Most intakes need nobody. When every bid was read with high confidence and either no tender was
# supplied or every tender field carries a page, the run continues on its own.
#
# When a bid is a scan, a low-confidence read or the tender is missing fields, a named person has to
# confirm what was read. That confirmation is written through record_intake_correction under the
# run's run_id, together with any field corrections they supply. A person who declines stops the run,
# because a benchmark built on a document nobody checked is exactly the kind of evidence this tool
# must not produce.
#
# Web uploads set settings.intake_gate to False: the browser has no screen for this gate, and the
# upload page accepts bids only. The issues are still recorded and still shown in the report.

from langgraph.types import interrupt

from config import settings
from agent.state import AgentState
from agent.tools import record_intake_correction


def intake_needs_review(state: AgentState) -> tuple[bool, list[str]]:
    """Whether a person must confirm the intake, and the plain reasons why."""
    bids = state.get("bids") or []
    issues: list[str] = []
    if not bids:
        return True, ["no bid was produced"]

    usable = False
    for bid in bids:
        if bid.get("status") == "ok" and bid.get("stated_total") is not None:
            usable = True
        if bid.get("status") != "ok" or bid.get("confidence") != "high":
            issues.append(f"{bid.get('bidder') or 'a bid'}: {bid.get('status')} "
                          f"({bid.get('confidence')} confidence)")
    if not usable:
        issues.append("no bid could be read with a stated total")

    tender = state.get("tender") or {}
    if tender:
        missing = tender.get("missing") or []
        if missing:
            issues.append("tender is missing: " + ", ".join(missing))

    return bool(issues), issues


def _payload(state: AgentState, issues: list[str]) -> dict:
    """What the person is shown: the bids read, the tender fields found, and the reasons for the gate."""
    return {
        "gate": "intake",
        "run_id": state.get("run_id"),
        "tender_ref": state.get("tender_ref"),
        "bids": [{"bidder": bid.get("bidder"), "status": bid.get("status"),
                  "confidence": bid.get("confidence"), "total": bid.get("stated_total")}
                 for bid in state.get("bids") or []],
        "tender_fields": state.get("tender_fields") or {},
        "issues": issues,
    }


def confirm_intake_node(state: AgentState) -> dict:
    """Confirm a clean intake, or ask a named person to confirm the rest."""
    needed, issues = intake_needs_review(state)
    usable = any(bid.get("status") == "ok" for bid in state.get("bids") or [])

    if state.get("tender_ref_conflict"):
        return {"intake_confirmed": False, "intake_issues": issues,
                "errors": ["intake: bids do not all belong to the tender that was uploaded"]}

    if not usable:
        return {"intake_confirmed": False, "intake_issues": issues,
                "errors": ["intake: no bid could be read with a stated total"]}
    if not needed:
        return {"intake_confirmed": True, "intake_issues": []}
    if not settings.intake_gate:
        return {"intake_confirmed": True, "intake_issues": issues}

    answer = interrupt(_payload(state, issues))
    confirmed = answer.get("confirmed")
    if confirmed is None:
        confirmed = answer.get("decision") == "approved"
    if not confirmed:
        return {"intake_confirmed": False, "intake_issues": issues,
                "errors": ["intake: a person declined to confirm what was read"]}

    approved_by = answer.get("approved_by") or ""
    recorded = [record_intake_correction(state["run_id"], "intake", "confirmed", approved_by)]
    for field, value in (answer.get("corrections") or {}).items():
        recorded.append(record_intake_correction(state["run_id"], field, value, approved_by,
                                                 answer.get("note") or ""))
    return {"intake_confirmed": True, "intake_issues": issues, "intake_corrections": recorded}
