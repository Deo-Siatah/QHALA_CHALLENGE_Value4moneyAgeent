# The one object that holds everything the run knows, across all ten nodes:
# tender_intake -> bid_intake -> confirm_intake -> research -> quality_check -> score -> draft ->
# verify_sources -> approval -> file.
# Two loops live in it as counters: quality_check back to research (max 3), verify_sources back to draft (max 2).
# total=False because LangGraph nodes return partial dicts, and only the approval interrupt pauses it.
# Tool results are stored exactly as the tool returned them, so the tool stays the source of truth.
# Pool verdicts are the model's call on each suspect award: keep or exclude, with its reason.
# Findings are replaced by each redraft, not appended to, so one finding never appears twice.
# The three lists that carry an add reducer are logs: they only ever grow through the run.

import operator
from typing import Annotated, Any
from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    """Everything one run of the agent knows, from the bid PDF to the filed report."""

    run_id: str
    pdf_paths: list[str]
    tender_path: str | None
    started_at: str

    #intake
    tender: dict[str, Any]
    tender_fields: dict[str, dict[str, Any]]
    tender_missing: list[str]
    tender_rejected: list[dict[str, Any]]
    bid_status: dict[str, str]
    intake_confirmed: bool
    intake_issues: list[str]
    intake_corrections: list[dict[str, Any]]
    tender_ref: str
    tender_ref_conflict: bool
    category: str
    description: str
    core_terms: list[str]
    bids: list[dict[str, Any]]
    parse_issues: Annotated[list[str], operator.add]

    #research
    query: str
    match: str
    min_year: int | None
    search_attempts: int
    search: dict[str, Any]
    last_search: dict[str, Any]
    candidates: list[dict[str, Any]]
    pool_verdicts: dict[str, dict[str, str]]
    #quality
    quality: dict[str, Any]
    quality_attempts: int
    excluded: dict[str, int]
    #scoring
    pool: list[dict[str, Any]]
    pool_size: int
    benchmark: dict[str, Any]
    #draft
    summary: str
    summary_note: str | None
    finding_notes: dict[str, str]
    report_degraded: bool
    bid_comments: dict[str, str]
    findings: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    review_markdown: str
    report_model: dict[str, Any]
    verify_rounds: int
    verify_ok: bool
    verify_failures: Annotated[list[str], operator.add]
    #approval & filing
    approval_status: str
    approved_by: str | None
    approval_note: str | None
    submission: dict[str, Any]
    #errors
    errors: Annotated[list[str], operator.add]


class ApprovalDecision(TypedDict):
    """What a human sends back through the approval interrupt."""

    decision: str
    approved_by: str
    note: str


def initial_state(run_id: str, pdf_paths: list[str], started_at: str,
                  tender_path: str | None = None) -> AgentState:
    """The state a run starts from, with counters at zero and approval still pending."""
    return {
        "run_id": run_id,
        "pdf_paths": pdf_paths,
        "tender_path": tender_path,
        "started_at": started_at,
        "tender": {},
        "tender_fields": {},
        "tender_missing": [],
        "tender_rejected": [],
        "bid_status": {},
        "intake_confirmed": False,
        "intake_issues": [],
        "intake_corrections": [],
        "tender_ref_conflict": False,
        "core_terms": [],
        "parse_issues": [],
        "match": "strict",
        "search_attempts": 0,
        "search": {},
        "quality_attempts": 0,
        "pool_verdicts": {},
        "excluded": {},
        "pool": [],
        "pool_size": 0,
        "summary_note": None,
        "finding_notes": {},
        "report_degraded": False,
        "bid_comments": {},
        "findings": [],
        "sources": [],
        "verify_rounds": 0,
        "verify_failures": [],
        "approval_status": "pending",
        "approved_by": None,
        "approval_note": None,
        "errors": [],
    }
