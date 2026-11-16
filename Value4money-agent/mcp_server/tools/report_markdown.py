"""Render the filed Markdown body from the report model."""

from . import report_labels as labels
from .report_format import source_label


def _cell(value) -> str:
    """One table cell with the pipe character kept out of the table's syntax."""
    return str(value).replace("|", "/")


def _bid_table(model) -> list:
    lines = ["| # | Bidder | Total | Usual price comparison | What to check |",
             "| ---: | --- | ---: | --- | --- |"]
    for bid in model.bids:
        checks = " ".join(bid.check_texts)
        lines.append(f"| {bid.number} | {_cell(bid.bidder)} | {bid.total_text} | "
                     f"{bid.comparison} | {bid.state_label}; {_cell(checks)} |")
    return lines


def _arithmetic_lines(model) -> list:
    lines = []
    for bid in model.bids:
        if not bid.readable:
            continue
        if any("stated total" in check.lower() for check in bid.check_texts):
            source = source_label({"kind": "bid", "bidder": bid.bidder, "file": bid.file,
                                   "page": bid.total_page})
            lines.append(f"- {source}: {' '.join(bid.check_texts)}")
    return lines


def _unreadable_lines(model) -> list:
    lines = []
    for bid in model.bids:
        if bid.readable:
            continue
        source = source_label({"kind": "bid", "bidder": bid.bidder, "file": bid.file,
                               "page": bid.total_page})
        lines.append(f"- {source}: {' '.join(bid.check_texts)}")
    return lines


def _set_aside_table(model) -> list:
    lines = ["| Award | Title | Value | Reason |",
             "| --- | --- | ---: | --- |"]
    for row in model.set_asides:
        lines.append(f"| {_cell(row.award_id)} | {_cell(row.title or labels.NOT_STATED)} | "
                     f"{row.value_text} | {row.reason_label} |")
    if not model.set_asides:
        lines.append("| - | No award was set aside | - | - |")
    return lines


def _excluded_summary(model) -> str:
    if not model.excluded:
        return "No candidate award was excluded."
    parts = [f"{labels.reason_label(code)} ({count})"
             for code, count in sorted(model.excluded.items())]
    return "Candidates excluded in this run: " + ", ".join(parts) + "."


def _questions(model) -> list:
    lines = []
    for bid in model.bids:
        if bid.readable and bid.state in labels.QUESTION_STATES:
            lines.append(f"- {bid.bidder}: {bid.state_label}. What to check: "
                         f"{' '.join(bid.check_texts)}")
    for row in model.set_asides:
        lines.append(f"- Was {row.award_id} rightly set aside as {row.reason_label}?")
    if not lines:
        lines.append("- No question is raised for the committee by these figures.")
    return lines


def _pool_table(model) -> list:
    lines = ["| Award | Title | Buyer | Year | Value |",
             "| --- | --- | --- | ---: | ---: |"]
    for row in model.annex_pool:
        lines.append(f"| {_cell(row.award_id)} | {_cell(row.title or labels.NOT_STATED)} | "
                     f"{_cell(row.buyer_name or labels.NOT_STATED)} | "
                     f"{row.data_year if row.data_year is not None else '-'} | {row.value_text} |")
    if not model.annex_pool:
        lines.append("| - | No comparable award was found | - | - | - |")
    return lines


def _set_aside_annex(model) -> list:
    lines = ["| Award | Title | Value | Reason |",
             "| --- | --- | ---: | --- |"]
    for row in model.set_asides:
        lines.append(f"| {_cell(row.award_id)} | {_cell(row.title or labels.NOT_STATED)} | "
                     f"{row.value_text} | {row.reason_label} |")
    if not model.set_asides:
        lines.append("| - | No award was set aside | - | - |")
    return lines


def render_markdown(model) -> str:
    """The filed record: page one, page two and the annex, without approval words."""
    lines = [f"# Price review evidence: {model.tender_ref}", "",
             f"Prepared: {model.prepared_date}", f"Run ID: {model.run_id}", "",
             f"> {model.notice}", "",
             "## Bottom line", "", model.bottom_line, "",
             f"Usual price: {model.usual_price}", f"Normal range: {model.normal_range}",
             f"Evidence: {model.evidence_strength}", "",
             "## Bids", ""]
    lines += _bid_table(model)
    lines += ["", "What this table does not show:"]
    lines += [f"- {line}" for line in model.caution_lines]
    lines += ["", "## Method", ""]
    lines += [f"- {point}" for point in model.method_points]
    lines += ["", "### Assistant note", "", labels.ASSISTANT_LABEL, "",
              model.assistant_note or labels.ASSISTANT_MISSING, "",
              "## Arithmetic and set-asides", "",
              "### Totals that do not match their line items", ""]
    arithmetic = _arithmetic_lines(model)
    lines += arithmetic or ["- No stated total disagreed with its line items."]
    lines += ["", "### Bids that could not be read", ""]
    unreadable = _unreadable_lines(model)
    lines += unreadable or ["- Every bid document could be read."]
    lines += ["", "### Set-aside awards", ""]
    lines += _set_aside_table(model)
    lines += ["", _excluded_summary(model), "",
              "## Questions for the committee", ""]
    lines += _questions(model)
    lines += ["", "## Annex: comparable awards", ""]
    lines += _pool_table(model)
    lines += ["", "## Annex: set-aside awards", ""]
    lines += _set_aside_annex(model)
    lines += ["", "## Glossary", ""]
    lines += [f"- **{term}**: {meaning}" for term, meaning in model.glossary]
    return "\n".join(lines).rstrip() + "\n"
