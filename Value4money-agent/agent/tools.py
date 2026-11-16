from typing import Any, Dict, List, Optional

from config import settings
from mcp_server.audit import audited
from mcp_server.tools.parse_bid_pdf import parse_bid as _parse_bid
from mcp_server.tools.extract_bid import extract_bid as _extract_bid
from mcp_server.tools.extract_tender import extract_tender_pdf as _extract_tender_pdf
from mcp_server.tools.record_intake_correction import record_intake_correction as _record_intake_correction
from mcp_server.tools.find_comparable_awards import find_comparable_awards as _find_comparable_awards
from mcp_server.tools.flag_data_quality import flag_data_quality as _flag_data_quality
from mcp_server.tools.benchmark_price import benchmark_price as _benchmark_price
from mcp_server.tools.draft_review_file import draft_review_file as _draft_review_file
from mcp_server.tools.submit_for_committee import submit_for_committee as _submit_for_committee
from agent.tracing import traced


@audited("parse_bid_pdf")
@traced("tool")
def parse_bid_pdf(run_id: str, path: str) -> Dict[str, Any]:
    """Read one bid PDF with the tolerant extractor, logged under run_id."""
    return _extract_bid(path, settings.bids_dir)


@audited("parse_bid_pdf")
@traced("tool")
def parse_bid_pdf_strict(run_id: str, path: str) -> Dict[str, Any]:
    """Read one bid PDF with the strict parser, logged under run_id."""
    return _parse_bid(path, settings.bids_dir)


@audited("extract_tender_pdf")
@traced("tool")
def extract_tender_pdf(run_id: str, path: str) -> Dict[str, Any]:
    """Extract tender fields with page and line sources, logged under run_id."""
    return _extract_tender_pdf(path, settings.tender_dir)


@audited("record_intake_correction")
@traced("tool")
def record_intake_correction(run_id: str, field: str, value: Any, approved_by: str,
                             reason: str) -> Dict[str, Any]:
    """Record a named human's correction, logged under run_id."""
    return _record_intake_correction(field, value, approved_by, reason)


@audited("find_comparable_awards")
@traced("tool")
def find_comparable_awards(run_id: str, query: str, category: Optional[str] = None,
                           buyer_id: Optional[str] = None, match: str = "strict",
                           min_year: Optional[int] = None,
                           exclude_ocid: Optional[str] = None,
                           required_terms: Optional[List[str]] = None) -> Dict[str, Any]:
    """Search public past awards, logged under run_id."""
    return _find_comparable_awards(query, category, buyer_id, match, min_year, exclude_ocid,
                                   required_terms)


@audited("flag_data_quality")
@traced("tool")
def flag_data_quality(run_id: str, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Rule-check candidate awards, logged under run_id."""
    return _flag_data_quality(candidates)


@audited("benchmark_price")
@traced("tool")
def benchmark_price(run_id: str, bids: List[Dict[str, Any]],
                    pool: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Place each bid total against the pool, logged under run_id."""
    return _benchmark_price(bids, pool)


@audited("draft_review_file")
@traced("tool")
def draft_review_file(run_id: str, review: Dict[str, Any]) -> Dict[str, str]:
    """Render the committee evidence file, logged under run_id."""
    return _draft_review_file(review)


@audited("submit_for_committee")
@traced("tool")
def submit_for_committee(run_id: str, report_md: str, approved_by: str,
                         review_json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """File the approved report, logged under run_id."""
    return _submit_for_committee(run_id, report_md, approved_by, review_json=review_json)
