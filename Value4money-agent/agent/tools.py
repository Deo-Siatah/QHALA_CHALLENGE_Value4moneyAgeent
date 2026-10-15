# One audited entry point per tool, as plain Python functions. Nodes import from here and never from
# mcp_server.tools, so every call a node makes in process is written to audit_log under its run_id.
# Despite the name this file used to carry, this is not an MCP client: nothing here speaks MCP.
# The names and arguments match the MCP tool surface in server.py exactly, so a node
# could talk to the server over stdio later without changing a line.
# Each call is also an Opik span, placed inside the audit wrapper so the span measures the
# tool call itself and not the audit write around it.

from typing import Any, Dict, List, Optional

from config import settings
from mcp_server.audit import audited
from agent.tracing import traced
from mcp_server.tools.parse_bid_pdf import parse_bid_pdf as _parse_bid_pdf
from mcp_server.tools.find_comparable_awards import find_comparable_awards as _find_comparable_awards
from mcp_server.tools.flag_data_quality import flag_data_quality as _flag_data_quality
from mcp_server.tools.benchmark_price import benchmark_price as _benchmark_price
from mcp_server.tools.draft_review_file import draft_review_file as _draft_review_file
from mcp_server.tools.submit_for_committee import submit_for_committee as _submit_for_committee


@audited("parse_bid_pdf")
@traced("tool")
def parse_bid_pdf(run_id: str, path: str) -> Dict[str, Any]:
    """Parse one bid PDF, logged under run_id."""
    return _parse_bid_pdf(path)


@audited("find_comparable_awards")
@traced("tool")
def find_comparable_awards(run_id: str, query: str, category: Optional[str] = None,
                           buyer_id: Optional[str] = None, match: str = "strict",
                           min_year: Optional[int] = None,
                           exclude_ocid: Optional[str] = None) -> Dict[str, Any]:
    """Search public past awards, logged under run_id."""
    return _find_comparable_awards(query, category, buyer_id, match, min_year, exclude_ocid)


@audited("flag_data_quality")
@traced("tool")
def flag_data_quality(run_id: str, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Rule-check candidate awards, logged under run_id."""
    return _flag_data_quality(candidates)


@audited("benchmark_price")
@traced("tool")
def benchmark_price(run_id: str, bids: List[Dict[str, Any]],
                    pool: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Benchmark the bid totals, logged under run_id."""
    return _benchmark_price(bids, pool)


@audited("draft_review_file")
@traced("tool")
def draft_review_file(run_id: str, review: Dict[str, Any]) -> Dict[str, str]:
    """Render the committee evidence file, logged under run_id."""
    return _draft_review_file(review)


@audited("submit_for_committee")
@traced("tool")
def submit_for_committee(run_id: str, report_md: str, approved_by: str) -> Dict[str, Any]:
    """File the approved report, logged under run_id."""
    return _submit_for_committee(run_id, report_md, approved_by)
