"""Build the one structured model both report renderers use."""

from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from . import report_labels as labels
from .report_format import kes, pct_phrase

NOT_STATED = "Not stated in the documents"
NOT_COMPARED = "Not compared"


class BenchmarkView(BaseModel):
    n: Optional[int] = None
    confidence: str = "insufficient"
    median: Optional[float] = None
    q1: Optional[float] = None
    q3: Optional[float] = None


class BidRow(BaseModel):
    number: int
    bidder: str
    file: Optional[str] = None
    total_page: Optional[int] = None
    readable: bool
    total: Optional[float] = None
    total_text: str
    comparison: str
    state: str
    state_label: str
    shape: str
    check_texts: List[str] = Field(default_factory=list)


class PoolRow(BaseModel):
    award_id: str
    title: Optional[str] = None
    buyer_name: Optional[str] = None
    data_year: Optional[int] = None
    value_kes: Optional[float] = None
    value_text: str


class SetAsideRow(BaseModel):
    award_id: str
    title: Optional[str] = None
    value_kes: Optional[float] = None
    value_text: str
    reason_code: str
    reason_label: str


class BidPoint(BaseModel):
    number: int
    bidder: str
    total: float
    state: str
    off_chart: bool = False


class PoolPoint(BaseModel):
    award_id: str
    total: float


class ChartData(BaseModel):
    clamp_max: float
    usual_price: float
    q1: float
    q3: float
    bid_points: List[BidPoint] = Field(default_factory=list)
    pool_points: List[PoolPoint] = Field(default_factory=list)


class ReportModel(BaseModel):
    run_id: str
    tender_ref: str
    notice: str
    prepared_date: str
    tender_title: str
    title_inferred: bool
    buyer: str
    county: str
    bottom_line: str
    usual_price: str
    normal_range: str
    evidence_strength: str
    benchmark: BenchmarkView
    bids: List[BidRow] = Field(default_factory=list)
    annex_pool: List[PoolRow] = Field(default_factory=list)
    set_asides: List[SetAsideRow] = Field(default_factory=list)
    excluded: Dict[str, int] = Field(default_factory=dict)
    assistant_note: Optional[str] = None
    caution_lines: List[str] = Field(default_factory=list)
    method_points: List[str] = Field(default_factory=list)
    glossary: List[Tuple[str, str]] = Field(default_factory=list)
    chart: Optional[ChartData] = None
    page_1_text: str = ""
    report_degraded: bool = False


def _field(tender_fields: Dict[str, Any], name: str) -> Optional[str]:
    """The value of one tender field, whether it arrived bare or with a source wrapper."""
    value = (tender_fields or {}).get(name)
    if isinstance(value, dict):
        value = value.get("value")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _float(value: Any) -> Optional[float]:
    """A money value as a float, or None when there is no usable figure."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _check_texts(parsed: Dict[str, Any], readable: bool) -> List[str]:
    """The page-one check column: what a person should look at in this bid."""
    if not readable:
        name = parsed.get("file") or parsed.get("bidder") or "the bid file"
        pages = []
        for entry in (parsed.get("flagged_pages") or []) + (parsed.get("unresolved_pages") or []):
            page = entry.get("page") if isinstance(entry, dict) else entry
            if page is not None and page not in pages:
                pages.append(page)
        text = f"The bid file {name} could not be read."
        if pages:
            text += " Page " + ", ".join(str(page) for page in pages) + " could not be read."
        return [text]

    stated = _float(parsed.get("stated_total"))
    computed = _float(parsed.get("computed_total"))
    if parsed.get("arithmetic_ok") is False and stated is not None and computed is not None:
        difference = abs(stated - computed)
        return [("The stated total " + kes(stated) + " does not match the line items, which add up to "
                 + kes(computed) + ", a difference of " + kes(difference) + ".")]
    if parsed.get("arithmetic_ok") is False:
        issues = [str(issue) for issue in parsed.get("issues") or []]
        if issues:
            return issues
    return ["Nothing flagged for this bid."]


def _bid_rows(state: Dict[str, Any], scored: Dict[str, Dict[str, Any]],
              insufficient: bool) -> List[BidRow]:
    """Every bid, sorted by total, with the unreadable ones last."""
    rows: List[BidRow] = []
    for parsed in state.get("bids") or []:
        total = _float(parsed.get("stated_total"))
        readable = parsed.get("status") == "ok" and total is not None
        scored_row = scored.get(parsed.get("bidder")) or {}
        raw_position = scored_row.get("position") if readable and not insufficient else None
        position = raw_position if raw_position else None
        state_word = position or "not_compared"
        comparison = pct_phrase(scored_row.get("pct_vs_median")) if position else "not compared"
        rows.append(BidRow(
            number=0,
            bidder=str(parsed.get("bidder") or "Unnamed bidder"),
            file=parsed.get("file"),
            total_page=parsed.get("total_page"),
            readable=readable,
            total=total if readable else None,
            total_text=kes(total) if readable and total is not None else NOT_COMPARED,
            comparison=comparison,
            state=state_word,
            state_label=labels.state_label(position),
            shape=labels.state_shape(position),
            check_texts=_check_texts(parsed, readable),
        ))
    rows.sort(key=lambda row: (not row.readable, row.total if row.total is not None else float("inf"),
                               row.bidder))
    for index, row in enumerate(rows, start=1):
        row.number = index
    return rows


def _pool_rows(state: Dict[str, Any]) -> List[PoolRow]:
    """The comparable awards, in value order, with the figures the annex prints."""
    rows = []
    for award in state.get("pool") or []:
        value = _float(award.get("value_kes"))
        rows.append(PoolRow(
            award_id=str(award.get("award_id") or "unknown"),
            title=award.get("title"),
            buyer_name=award.get("buyer_name"),
            data_year=award.get("data_year"),
            value_kes=value,
            value_text=kes(value) if value is not None else NOT_STATED,
        ))
    rows.sort(key=lambda row: (row.value_kes is None,
                               row.value_kes if row.value_kes is not None else float("inf"),
                               row.award_id))
    return rows


def _set_asides(state: Dict[str, Any]) -> List[SetAsideRow]:
    """Every candidate the run set aside, with a reason a committee can read."""
    rows = []
    for award in state.get("excluded_awards") or []:
        value = _float(award.get("value_kes"))
        code = str(award.get("reason_code") or "excluded")
        rows.append(SetAsideRow(
            award_id=str(award.get("award_id") or "unknown"),
            title=award.get("title"),
            value_kes=value,
            value_text=kes(value) if value is not None else NOT_STATED,
            reason_code=code,
            reason_label=labels.reason_label(code),
        ))
    return rows


def _chart(benchmark: BenchmarkView, bids: List[BidRow],
           pool: List[PoolRow]) -> Optional[ChartData]:
    """The page-one chart, or nothing when the evidence is too thin to draw one."""
    if benchmark.confidence == "insufficient" or not benchmark.q3 or benchmark.q3 <= 0:
        return None
    clamp = benchmark.q3 * 2
    points = [BidPoint(number=bid.number, bidder=bid.bidder, total=bid.total,
                       state=bid.state, off_chart=bid.total > clamp)
              for bid in bids if bid.readable and bid.total is not None]
    pool_points = [PoolPoint(award_id=row.award_id, total=row.value_kes)
                   for row in pool if row.value_kes is not None]
    return ChartData(clamp_max=clamp, usual_price=benchmark.median or 0.0,
                     q1=benchmark.q1 or 0.0, q3=benchmark.q3,
                     bid_points=points, pool_points=pool_points)


def _page_one_text(model: "ReportModel") -> str:
    """The page-one words, kept apart from the assistant note on page two."""
    lines = [model.bottom_line, "", "| # | Bidder | Total | Usual price comparison | What to check |"]
    for bid in model.bids:
        lines.append(f"| {bid.number} | {bid.bidder} | {bid.total_text} | {bid.comparison} | "
                     f"{bid.state_label}; {' '.join(bid.check_texts)} |")
    lines += ["", "Usual price: " + model.usual_price,
              "Normal range: " + model.normal_range]
    return "\n".join(lines)


def build_report_model(review: Dict[str, Any], state: Dict[str, Any]) -> ReportModel:
    """Turn the run's review and state into the one model both renderers read."""
    benchmark_raw = review.get("benchmark") or state.get("benchmark") or {}
    median = _float(benchmark_raw.get("median_kes"))
    q1 = _float(benchmark_raw.get("q1_kes"))
    q3 = _float(benchmark_raw.get("q3_kes"))
    confidence = str(benchmark_raw.get("confidence") or "insufficient")
    insufficient = confidence == "insufficient" or median is None or q1 is None or q3 is None
    benchmark = BenchmarkView(n=benchmark_raw.get("n"), confidence=confidence,
                              median=median, q1=q1, q3=q3)

    scored = {str(row.get("bidder")): row for row in benchmark_raw.get("bids") or []}
    bids = _bid_rows(state, scored, insufficient)
    pool = _pool_rows(state)
    set_asides = _set_asides(state)

    if insufficient:
        usual_price = "Not enough evidence"
        normal_range = "Not enough evidence"
    else:
        usual_price = kes(median)
        normal_range = f"{kes(q1)} to {kes(q3)}"

    within = sum(1 for bid in bids if bid.state == "within_range")
    questions = sum(1 for bid in bids if bid.state in labels.QUESTION_STATES)
    unreadable = sum(1 for bid in bids if not bid.readable)
    line = labels.bottom_line(within=within, questions=questions, n=len(bids),
                              unreadable=unreadable, insufficient=insufficient)

    fields = state.get("tender_fields") or {}
    title_field = _field(fields, "title")
    description = state.get("description")
    title_inferred = title_field is None
    tender_title = title_field or (str(description).strip() if description else NOT_STATED)
    buyer = _field(fields, "buyer") or NOT_STATED
    county = _field(fields, "county") or NOT_STATED
    note = review.get("summary_note")
    if note is None:
        note = state.get("summary_note")
    if isinstance(note, str) and not note.strip():
        note = None

    model = ReportModel(
        run_id=str(review.get("run_id") or state.get("run_id") or ""),
        tender_ref=str(review.get("tender_ref") or state.get("tender_ref") or ""),
        notice=labels.NOTICE,
        prepared_date=labels.prepared_date(state.get("started_at") or ""),
        tender_title=tender_title,
        title_inferred=title_inferred,
        buyer=buyer,
        county=county,
        bottom_line=line,
        usual_price=usual_price,
        normal_range=normal_range,
        evidence_strength=labels.evidence_label("insufficient" if insufficient else confidence),
        benchmark=benchmark,
        bids=bids,
        annex_pool=pool,
        set_asides=set_asides,
        excluded=dict(state.get("excluded") or review.get("excluded") or {}),
        assistant_note=note,
        caution_lines=list(labels.CAUTION_LINES),
        method_points=list(labels.METHOD_POINTS),
        glossary=list(labels.GLOSSARY),
        chart=_chart(benchmark, bids, pool),
        report_degraded=bool(review.get("report_degraded") or state.get("report_degraded")),
    )
    model.page_1_text = _page_one_text(model)
    return model

