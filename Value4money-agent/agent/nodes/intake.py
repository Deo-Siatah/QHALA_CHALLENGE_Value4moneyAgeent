# Read the bid PDFs and name the work that was tendered.
#
# What this node does, in order:
#  1. It takes the list of PDF paths from state, one file per bidder, and calls the parse_bid_pdf
#     tool on each one under the run's own run_id, so every read is written to audit_log.
#  2. A PDF that cannot be read becomes one entry in parse_issues naming the file and the reason the
#     tool gave. One unreadable file never stops the run: a tender often arrives with one bad scan.
#  3. If nothing at all could be read, the node records an error and returns with no bids. It does
#     not decide anything there: route_after_intake already sends a run with no bids to the end.
#  4. If the parsed bids disagree about the tender reference, that is recorded as an error, because a
#     report for two tenders is not one tender's evidence.
#  5. Hasibu is then asked, through intake_tender_profile, what kind of work this is and how to
#     describe it in a few words. A category outside works, goods or services, or an empty
#     description, stops the run with a clear error, because a mis-categorised search quietly
#     returns the wrong awards and nobody would notice.
#  6. The node checks no arithmetic and corrects no figures. parse_bid_pdf already compared each
#     line total and the stated total against the sum of its own line items, and the node carries
#     those reported issues through untouched for the draft to state as fact.
#
# What it returns: the parsed bids, the tender reference, the category, the description of the work,
# and any parse issues. Everything else in state is left alone.

from typing import Any, Dict, List

from config import settings
from mcp_server.tools.parse_bid_pdf import BidParseError
from agent.state import AgentState
from agent.llm import ask_json
from agent.tools import parse_bid_pdf

CATEGORIES = ("works", "goods", "services")


def _tender_profile(tender_ref: str, items: List[Dict[str, Any]]) -> Dict[str, str]:
    """Ask the model for the category and a short description, and refuse anything unexpected."""
    answer = ask_json("intake_tender_profile", {"tender_ref": tender_ref, "items": items})
    category, description = answer.get("category"), answer.get("description")
    if category not in CATEGORIES:
        raise ValueError(f"intake_tender_profile gave category {category!r}, "
                         f"expected one of {list(CATEGORIES)}")
    if not isinstance(description, str) or not description.strip():
        raise ValueError(f"intake_tender_profile gave description {description!r}, expected text")
    return {"category": category, "description": description.strip()}


def intake_node(state: AgentState) -> dict:
    """Parse the bid PDFs, then ask the model what kind of work was tendered."""
    run_id = state["run_id"]
    bids: List[Dict[str, Any]] = []
    parse_issues: List[str] = []

    for path in state.get("pdf_paths", []):
        try:
            bids.append(parse_bid_pdf(run_id, path))
        except BidParseError as exc:
            parse_issues.append(f"{path}: {exc}")

    if not bids:
        return {"bids": bids, "parse_issues": parse_issues,
                "errors": [f"no bid could be parsed from {state.get('pdf_paths')}: {parse_issues}"]}

    tender_ref = bids[0]["tender_ref"]
    result: Dict[str, Any] = {
        "bids": bids,
        "parse_issues": parse_issues,
        "tender_ref": tender_ref,
        **_tender_profile(tender_ref, bids[0]["items"]),
    }

    others = sorted({bid["tender_ref"] for bid in bids if bid["tender_ref"] != tender_ref})
    if others:
        result["errors"] = [f"bids disagree on tender reference: {tender_ref} and {', '.join(others)}"]

    return result
