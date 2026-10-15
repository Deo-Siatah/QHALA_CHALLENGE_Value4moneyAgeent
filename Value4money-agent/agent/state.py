# The one object that holds everything the run knows, across all eight nodes:
# intake -> research -> quality_check -> score -> draft -> verify_sources -> approval -> file.
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
    started_at: str

    tender_ref: str
    category: str
    description: str
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
    bid_comments: dict[str, str]
    findings: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    review_markdown: str
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


def initial_state(run_id: str, pdf_paths: list[str], started_at: str) -> AgentState:
    """The state a run starts from, with counters at zero and approval still pending."""
    return {
        "run_id": run_id,
        "pdf_paths": pdf_paths,
        "started_at": started_at,
        "parse_issues": [],
        "match": "strict",
        "search_attempts": 0,
        "search": {},
        "quality_attempts": 0,
        "pool_verdicts": {},
        "excluded": {},
        "pool": [],
        "pool_size": 0,
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
