# Turn structured results into the committee evidence file in Markdown. Pure, writes nothing.
# The model supplies only short notes; code supplies every figure and every finding sentence.
# The tool renders the structure itself and enforces the house rules:
# no source means no finding, no award language, no statistics when evidence is thin.

from typing import Any, Dict, List, Literal, Optional, Union
import re
from pydantic import BaseModel, Field, field_validator

from .report_format import amount, exclusion_label, kes, pct_phrase, position_label, source_label


class ReviewError(ValueError):
    """Raised when a review breaks a house rule."""


class BidNote(BaseModel):
    bidder: str
    arithmetic_issues: List[str] = Field(default_factory=list)
    comment: Optional[str] = None


class PoolSource(BaseModel):
    kind: Literal["pool"] = "pool"
    award_id: str


class BidSource(BaseModel):
    kind: Literal["bid"] = "bid"
    bidder: str
    file: Optional[str] = None
    page: Optional[int] = None


FindingSource = Union[PoolSource, BidSource]


class Finding(BaseModel):
    text: str
    sources: List[FindingSource] = Field(default_factory=list)
    kind: str = ""
    key: str = ""
    note: Optional[str] = None

    @field_validator("sources", mode="before")
    @classmethod
    def _legacy_ids(cls, value: Any) -> Any:
        """Accept an old string source as a pool award citation."""
        if not isinstance(value, list):
            return value
        return [{"kind": "pool", "award_id": item} if isinstance(item, str) else item
                for item in value]


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
    summary_note: Optional[str] = None
    benchmark: Dict[str, Any]
    search: Dict[str, Any] = Field(default_factory=dict)
    excluded: Dict[str, int] = Field(default_factory=dict)
    bids: List[BidNote] = Field(default_factory=list)
    findings: List[Finding] = Field(default_factory=list)
    sources: List[SourceRecord] = Field(default_factory=list)
    report_degraded: bool = False


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
    """Format an amount without the currency, for a table column that names KES."""
    return amount(value)


def _pool_lines(benchmark: Dict[str, Any], search: Dict[str, Any],
                excluded: Dict[str, int]) -> List[str]:
    """Build the comparison pool section: count, statistics, the search used and exclusions."""
    lines = [f"- Comparable awards (n): {benchmark.get('n')}",
             f"- Confidence: {benchmark.get('confidence')}"]
    if benchmark.get("confidence") == "insufficient":
        lines.insert(1, f"- {NOT_ENOUGH}")
    else:
        lines[1:1] = [
            f"- Median award value: {kes(benchmark['median_kes'])}",
            f"- Normal range (Q1-Q3): {kes(benchmark['q1_kes'])} to {kes(benchmark['q3_kes'])}",
        ]
    used = ", ".join(f"{key}={value}" for key, value in search.items()) or "none recorded"
    lines.append(f"- Search: {used}")
    dropped = ", ".join(f"{exclusion_label(code)} ({count})"
                        for code, count in excluded.items()) or "none"
    lines.append(f"- Excluded candidates: {dropped}")
    return lines


def _bids_table(review: Review) -> List[str]:
    """Build the bids table from the benchmark rows, with arithmetic issues and a note."""
    benchmark_rows = {row["bidder"]: row for row in review.benchmark.get("bids", [])}
    lines = ["| Bidder | Total (KES) | % vs median | Position | Comment |",
             "| --- | ---: | ---: | --- | --- |"]
    for note in review.bids:
        row = benchmark_rows.get(note.bidder)
        if row is None:
            raise ReviewError(f"bids[{note.bidder}] has no matching row in benchmark.bids")
        if row["position"] is None:
            total, pct, position = amount(row["total"]), "n/a", "n/a"
        else:
            total, pct = amount(row["total"]), pct_phrase(row.get("pct_vs_median"))
            position = position_label(row["position"])
        parts = list(note.arithmetic_issues)
        if note.comment:
            parts.append(note.comment)
        comment = "; ".join(parts) or "-"
        lines.append(f"| {note.bidder} | {total} | {pct} | {position} | {comment} |")
    return lines


def _sources_table(sources: List[SourceRecord]) -> List[str]:
    """Build the sources table for every pooled award, plus the data-year range."""
    lines = ["| Award ID | OCID | Data year | Buyer | Title | Value (KES) |",
             "| --- | --- | ---: | --- | --- | ---: |"]
    years = []
    for source in sources:
        if source.data_year is not None:
            years.append(source.data_year)
        value = _kes(source.value_kes) if source.value_kes is not None else "-"
        year = source.data_year if source.data_year is not None else "-"
        lines.append(f"| {source.award_id} | {source.ocid or '-'} | {year} | "
                     f"{source.buyer_name or '-'} | {source.title or '-'} | {value} |")
    if years:
        lines += ["", f"Dataset: Kenya OCDS award records, data years {min(years)}-{max(years)}."]
    return lines


def _source_ok(source: FindingSource, known: set) -> bool:
    """Whether a source names a pooled award or a readable bid document."""
    if source.kind == "pool":
        return source.award_id in known
    return bool(source.bidder)


def render_review(review: Dict[str, Any]) -> Dict[str, str]:
    """Render and validate the committee evidence file, returning its Markdown."""
    parsed = Review(**review)
    _scan(parsed.summary, "summary")
    if parsed.summary_note:
        _scan(parsed.summary_note, "summary note")
    for note in parsed.bids:
        if note.comment:
            _scan(note.comment, f"comment for bid '{note.bidder}'")

    known = {source.award_id for source in parsed.sources}
    for index, finding in enumerate(parsed.findings, start=1):
        if not finding.sources:
            raise ReviewError(f"finding {index} has no sources: no source, no finding")
        unknown = [source.award_id for source in finding.sources
                   if source.kind == "pool" and source.award_id not in known]
        if unknown:
            raise ReviewError(f"finding {index} cites unknown award_id(s): {', '.join(unknown)}")
        missing_bid = [source.bidder for source in finding.sources
                       if source.kind == "bid" and not source.bidder]
        if missing_bid:
            raise ReviewError(f"finding {index} cites a bid source without a bidder")
        _scan(finding.text, f"finding {index} text")
        if finding.note:
            _scan(finding.note, f"finding {index} note")

    md = [f"# Price review evidence: {parsed.tender_ref}", "",
          f"- Run ID: {parsed.run_id}", "", f"> {NOTICE}", "",
          "## Summary", "", parsed.summary, "",
          "## Comparison pool", ""]
    md += _pool_lines(parsed.benchmark, parsed.search, parsed.excluded)
    md += ["", "## Bids", ""] + _bids_table(parsed) + ["", "## Findings", ""]
    for index, finding in enumerate(parsed.findings, start=1):
        labels = ", ".join(source_label(source) for source in finding.sources)
        md += [f"{index}. {finding.text}", f"   Sources: {labels}", ""]
    md += ["## Limitations", ""] + [f"- {line}" for line in LIMITATIONS] + ["", "## Sources", ""]
    return {"markdown": "\n".join(md + _sources_table(parsed.sources)).rstrip() + "\n"}


def draft_review_file(review: Dict[str, Any]) -> Dict[str, str]:
    """Draft the committee evidence file in Markdown.

    The Phase 3 model travels with the review so the filed Markdown and the print HTML
    are the same structured record. A review without it still renders the legacy file.
    """
    model_data = review.get("report_model")
    if isinstance(model_data, dict):
        from .report_markdown import render_markdown
        from .report_model import ReportModel

        model = ReportModel(**model_data)
        if model.assistant_note:
            _scan(model.assistant_note, "assistant note")
        return {"markdown": render_markdown(model)}
    return render_review(review)

