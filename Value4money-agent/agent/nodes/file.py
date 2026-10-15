# File the approved report. The last node, and the only one that changes anything outside this run.
#
# What this node does, in order:
#  1. It checks that a named human actually approved. approval_status must be approved, and the
#     approver's name is checked again here with the same rule approval used, so a report cannot be
#     filed under a name that the approval node would have refused. A missing approval, a placeholder
#     name or an empty report raises an error naming what is wrong, because there is no next node to
#     route to and nothing may be written on a doubtful authority.
#  2. It calls submit_for_committee under the run's own run_id, which inserts the report row and writes
#     outputs/reports/<run_id>.md in one transaction and logs the approver in audit_log. The tool
#     refuses a duplicate run_id, a blank body and an unwritable file, and rolls its row back if the
#     write fails.
#  3. If the tool refuses, the reason is recorded and no submission is stored, so the run ends with a
#     stated cause rather than a traceback. Nothing was written in that case, and a run without a
#     submission is a run that filed nothing.
#
# What it returns: the tool's record of the filing, or the reason it did not happen.

from mcp_server.tools.submit_for_committee import PLACEHOLDERS, SubmitError
from agent.state import AgentState
from agent.tools import submit_for_committee
from config import settings


def _approver(state: AgentState) -> str:
    """Return the name of the human who approved, refusing anything that is not one."""
    if state.get("approval_status") != "approved":
        raise ValueError(f"approval_status is {state.get('approval_status')!r}: the report may only be "
                         "filed after a named human approved it")
    name = state.get("approved_by")
    if not isinstance(name, str) or len(name.strip()) < 2:
        raise ValueError(f"approved_by must be a named human, got {name!r}")
    if name.strip().lower() in PLACEHOLDERS:
        raise ValueError(f"approved_by must be a named human, got placeholder {name.strip()!r}")
    markdown = state.get("review_markdown")
    if not isinstance(markdown, str) or not markdown.strip():
        raise ValueError("review_markdown is empty: there is nothing to file")
    return name.strip()


def file_node(state: AgentState) -> dict:
    """Submit the approved report, or record why it could not be submitted."""
    approved_by = _approver(state)
    try:
        submission = submit_for_committee(state["run_id"], state["review_markdown"], approved_by)
    except SubmitError as exc:
        return {"errors": [f"submit_for_committee refused the report: {exc}"]}
    return {"submission": submission}