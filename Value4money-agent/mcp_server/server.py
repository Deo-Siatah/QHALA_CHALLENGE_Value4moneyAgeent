# Register the eight own tools on a stdio MCP server.
# Each tool takes a run_id, which the audit wrapper strips and writes to audit_log.
# The tool functions themselves are untouched: this file is only the MCP surface.

from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from config import settings
from .audit import audited
from .tools.extract_bid import extract_bid_pdf
from .tools.extract_tender import extract_tender_pdf
from .tools.record_intake_correction import record_intake_correction
from .tools.find_comparable_awards import find_comparable_awards
from .tools.flag_data_quality import flag_data_quality
from .tools.benchmark_price import benchmark_price
from .tools.draft_review_file import draft_review_file
from .tools.submit_for_committee import submit_for_committee

mcp = FastMCP("value4money",
              instructions="Price evidence for a human tender committee. Every call needs a run_id.")


@audited("parse_bid_pdf")
def parse_bid_pdf_tool(run_id: str, path: str) -> Dict[str, Any]:
    """Read one bid PDF with the strict path, then layout tables when needed."""
    return extract_bid_pdf(path)


@audited("extract_tender_pdf")
def extract_tender_pdf_tool(run_id: str, path: str,
                            filled: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Read the tender's labelled fields and verify any supplied values."""
    return extract_tender_pdf(path, settings.tender_dir, filled)


@audited("record_intake_correction")
def record_intake_correction_tool(run_id: str, field: str, value: Any, approved_by: str,
                                  reason: str = "") -> Dict[str, Any]:
    """Record a named person's correction to the intake."""
    return record_intake_correction(field, value, approved_by, reason)


@audited("find_comparable_awards")
def find_comparable_awards_tool(run_id: str, query: str, category: Optional[str] = None,
                                buyer_id: Optional[str] = None, match: str = "strict",
                                min_year: Optional[int] = None,
                                exclude_ocid: Optional[str] = None,
                                required_terms: Optional[List[str]] = None) -> Dict[str, Any]:
    """Search public past awards that look like the described job."""
    return find_comparable_awards(query, category, buyer_id, match, min_year, exclude_ocid,
                                  required_terms)


@audited("flag_data_quality")
def flag_data_quality_tool(run_id: str, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Decide which candidate awards are unusable, suspect or usable."""
    return flag_data_quality(candidates)


@audited("benchmark_price")
def benchmark_price_tool(run_id: str, bids: List[Dict[str, Any]],
                         pool: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Place each bid total against the comparable pool with plain statistics."""
    return benchmark_price(bids, pool)


@audited("draft_review_file")
def draft_review_file_tool(run_id: str, review: Dict[str, Any]) -> Dict[str, str]:
    """Render and validate the committee evidence file as Markdown."""
    return draft_review_file(review)


@audited("submit_for_committee")
def submit_for_committee_tool(run_id: str, report_md: str, approved_by: str,
                              review_json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """File the approved report. Needs a named human approver."""
    return submit_for_committee(run_id, report_md, approved_by, review_json=review_json)


for _fn in [parse_bid_pdf_tool, extract_tender_pdf_tool, record_intake_correction_tool,
            find_comparable_awards_tool, flag_data_quality_tool,
            benchmark_price_tool, draft_review_file_tool, submit_for_committee_tool]:
    mcp.add_tool(_fn, name=_fn.__name__[:-5])


def main() -> None:
    """Start the server on stdio, the transport the agent launches it with."""
    mcp.run("stdio")


if __name__ == "__main__":
    main()
