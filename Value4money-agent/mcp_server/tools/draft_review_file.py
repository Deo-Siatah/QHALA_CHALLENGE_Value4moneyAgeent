# Turn structured results into the committee evidence file in Markdown. Pure, writes nothing.
# The model supplies only short wording: a summary, per-bid comments, finding texts.
# The tool renders the structure itself and enforces the house rules:
# no source means no finding, no award language, no statistics when evidence is thin.

from typing import Any, Dict, List, Optional
import re
from pydantic import BaseModel, Field


class ReviewError(ValueError):
    """Raised when a review breaks a house rule."""


class BidNote(BaseModel):
    bidder: str
    arithmetic_issues: List[str] = Field(default_factory=list)
    comment: Optional[str] = None


class Finding(BaseModel):
    text: str
    sources: List[str] = Field(default_factory=list)


class SourceRecord(BaseModel):
    award_id: str
    ocid: Optional[str] = None
    data_year: Optional[int] = None
    buyer_name: Optional[str] = None
    title: Optional[str] = None
    value_kes: Optional[float] = None


class Review(BaseModel):
    run_id: str
    tender_ref: str
    summary: str
    benchmark: Dict[str, Any]
    search: Dict[str, Any] = Field(default_factory=dict)
    excluded: Dict[str, int] = Field(default_factory=dict)
    bids: List[BidNote] = Field(default_factory=list)
    findings: List[Finding] = Field(default_factory=list)
    sources: List[SourceRecord] = Field(default_factory=list)


NOTICE = ("Evidence for committee review. This file does not recommend an award. "
          "Bids are synthetic demonstration data. Past awards are public Kenya OCDS records.")

NOT_ENOUGH = "Not enough comparable awards to benchmark these bids."

LIMITATIONS = [
    "Award values are contract-level totals. The data carries no scope, quality or location, "
    "so a total on its own cannot show whether the work is comparable.",
    "A total far from the middle of the pool is a reason to ask the buyer a question, "
    "not proof of anything.",
    "The 50% and quartile cut-offs are adjustable settings in config.py, not rules of evidence.",
]

FORBIDDEN_WORDS = ["recommend", "winner", "should win", "overpriced", "gouging", "rigging",
                   "rigged", "fraud", "corrupt"]


def _scan(text: str, where: str) -> None:
    """Refuse model-written text that uses award or accusation language."""
    lowered = text.lower()
    for word in FORBIDDEN_WORDS:
        if re.search(rf"\b{re.escape(word)}\b", lowered):
            raise ReviewError(f"{where} contains the forbidden word '{word}'")


def _kes(value: float) -> str:
    """Format an amount with thousands separators and two decimals."""
    return f"{value:,.2f}"


def _pool_lines(benchmark: Dict[str, Any], search: Dict[str, Any], excluded: Dict[str, int]) -> List[str]:
    """Build the comparison pool section: count, statistics, the search used and exclusions."""
    lines = [f"- Comparable awards (n): {benchmark.get('n')}",
             f"- Confidence: {benchmark.get('confidence')}"]
    if benchmark.get("confidence") == "insufficient":
        lines.insert(1, f"- {NOT_ENOUGH}")
    else:
        lines[1:1] = [
            f"- Median award value: KES {_kes(benchmark['median_kes'])}",
            f"- Normal range (Q1-Q3): KES {_kes(benchmark['q1_kes'])} to KES {_kes(benchmark['q3_kes'])}",
        ]
    used = ", ".join(f"{key}={value}" for key, value in search.items()) or "none recorded"
    lines.append(f"- Search: {used}")
    dropped = ", ".join(f"{code} ({count})" for code, count in excluded.items()) or "none"
    lines.append(f"- Excluded candidates: {dropped}")
    return lines


def _bids_table(review: Review) -> List[str]:
    """Build the bids table from the benchmark rows, with the model's comment or issues."""
    benchmark_rows = {row["bidder"]: row for row in review.benchmark.get("bids", [])}
    lines = ["| Bidder | Total (KES) | % vs median | Position | Comment |",
             "| --- | ---: | ---: | --- | --- |"]
    for note in review.bids:
        row = benchmark_rows.get(note.bidder)
        if row is None:
            raise ReviewError(f"bids[{note.bidder}] has no matching row in benchmark.bids")
        if row["position"] is None:
            total, pct, position = _kes(row["total"]), "n/a", "n/a"
        else:
            total, pct, position = _kes(row["total"]), f"{row['pct_vs_median']}%", row["position"]
        comment = "; ".join(note.arithmetic_issues + ([note.comment] if note.comment else [])) or "-"
        lines.append(f"| {note.bidder} | {total} | {pct} | {position} | {comment} |")
    return lines


def _sources_table(sources: List[SourceRecord]) -> List[str]:
    """Build the sources table for every cited award, plus the data-year range."""
    lines = ["| Award ID | OCID | Data year | Buyer | Title | Value (KES) |",
             "| --- | --- | ---: | --- | --- | ---: |"]
    years = []
    for s in sources:
        if s.data_year is not None:
            years.append(s.data_year)
        value = _kes(s.value_kes) if s.value_kes is not None else "-"
        year = s.data_year if s.data_year is not None else "-"
        lines.append(f"| {s.award_id} | {s.ocid or '-'} | {year} | {s.buyer_name or '-'} | {s.title or '-'} | {value} |")
    if years:
        lines += ["", f"Dataset: Kenya OCDS award records, data years {min(years)}-{max(years)}."]
    return lines


def render_review(review: Dict[str, Any]) -> Dict[str, str]:
    """Render and validate the committee evidence file, returning its Markdown."""
    parsed = Review(**review)
    _scan(parsed.summary, "summary")
    for note in parsed.bids:
        if note.comment:
            _scan(note.comment, f"comment for bid '{note.bidder}'")

    known = {source.award_id for source in parsed.sources}
    for i, finding in enumerate(parsed.findings, start=1):
        if not finding.sources:
            raise ReviewError(f"finding {i} has no sources: no source, no finding")
        unknown = [award_id for award_id in finding.sources if award_id not in known]
        if unknown:
            raise ReviewError(f"finding {i} cites unknown award_id(s): {', '.join(unknown)}")
        _scan(finding.text, f"finding {i} text")

    md = [f"# Price review evidence: {parsed.tender_ref}", "",
          f"- Run ID: {parsed.run_id}", "", f"> {NOTICE}", "",
          "## Summary", "", parsed.summary, "",
          "## Comparison pool", ""]
    md += _pool_lines(parsed.benchmark, parsed.search, parsed.excluded)
    md += ["", "## Bids", ""] + _bids_table(parsed) + ["", "## Findings", ""]
    for i, finding in enumerate(parsed.findings, start=1):
        md += [f"{i}. {finding.text}", f"   Sources: {', '.join(finding.sources)}", ""]
    md += ["## Limitations", ""] + [f"- {line}" for line in LIMITATIONS] + ["", "## Sources", ""]
    return {"markdown": "\n".join(md + _sources_table(parsed.sources)).rstrip() + "\n"}


def draft_review_file(review: Dict[str, Any]) -> Dict[str, str]:
    """Draft the committee evidence file in Markdown."""
    return render_review(review)
