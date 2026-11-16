"""Render the self-contained print HTML from the report model."""

from html import escape

from . import report_labels as labels
from .report_chart import render_chart_svg
from .report_format import source_label

STYLE = """
@page { size: A4; margin: 18mm 16mm 24mm; }
* { box-sizing: border-box; }
body { font-family: Georgia, 'Times New Roman', serif; color: #1d1d1d; margin: 0;
       font-size: 11pt; line-height: 1.45; }
h1 { font-size: 20pt; margin: 0 0 4mm; }
h2 { font-size: 14pt; margin: 7mm 0 2mm; border-bottom: 1px solid #8aa6bf; padding-bottom: 1mm; }
h3 { font-size: 11.5pt; margin: 5mm 0 1.5mm; }
p { margin: 2mm 0; }
.meta { color: #555; margin: 1mm 0; }
.notice { border-left: 3px solid #1f4e79; padding: 2mm 3mm; background: #f3f7fb; }
.bottom-line { font-size: 13pt; font-weight: bold; margin: 4mm 0; }
.figures { display: flex; gap: 6mm; flex-wrap: wrap; }
.figures div { border: 1px solid #c8d6e3; padding: 2mm 3mm; }
table { width: 100%; border-collapse: collapse; margin: 2mm 0; font-size: 9.5pt; }
thead { display: table-header-group; }
tr { page-break-inside: avoid; }
th, td { border: 1px solid #b8c7d6; padding: 1.5mm; text-align: left; vertical-align: top; }
th { background: #e8eff5; }
td.num, th.num { text-align: right; }
.state-cell { white-space: nowrap; }
.state-icon { width: 14px; height: 14px; vertical-align: -2px; margin-right: 1.5mm; }
.page-one { page-break-after: always; }
.footer { position: fixed; bottom: 0; left: 0; right: 0; border-top: 1px solid #8aa6bf;
          padding-top: 1mm; font-size: 8.5pt; color: #555; }
.approval { margin-top: 8mm; border: 1px solid #1f4e79; padding: 3mm; font-size: 10pt; }
.fingerprint { font-family: Consolas, monospace; font-size: 8.5pt; word-break: break-all; }
.chart { width: 100%; height: auto; border: 1px solid #c8d6e3; margin: 3mm 0; }
"""


def _e(value) -> str:
    """Every run string passes through here before it reaches the page."""
    return escape("" if value is None else str(value), quote=True)


def _state_icon(shape: str, label: str) -> str:
    """The silhouette and the word say the same thing, so neither depends on colour."""
    drawn = {
        "hollow-circle": '<circle cx="8" cy="8" r="6" fill="none" stroke="#1f4e79" stroke-width="2"/>',
        "triangle-up": '<polygon points="8,1 15,14 1,14" fill="#1f4e79"/>',
        "triangle-down": '<polygon points="8,15 15,2 1,2" fill="#1f4e79"/>',
        "filled-circle": '<circle cx="8" cy="8" r="6" fill="#1f4e79"/>',
        "diamond": '<polygon points="8,1 15,8 8,15 1,8" fill="#1f4e79"/>',
        "square": '<rect x="2" y="2" width="12" height="12" fill="#1f4e79"/>',
    }.get(shape, '<rect x="2" y="2" width="12" height="12" fill="#1f4e79"/>')
    return (f'<svg class="state-icon" viewBox="0 0 16 16" role="img" aria-label="{_e(label)}">'
            f"<title>{_e(label)}</title>{drawn}</svg>")


def _bid_rows(model) -> str:
    rows = []
    for bid in model.bids:
        checks = " ".join(bid.check_texts)
        rows.append(
            "<tr>"
            f'<td class="num">{bid.number}</td>'
            f"<td>{_e(bid.bidder)}</td>"
            f'<td class="num">{_e(bid.total_text)}</td>'
            f"<td>{_e(bid.comparison)}</td>"
            f'<td class="state-cell">{_state_icon(bid.shape, bid.state_label)}'
            f"{_e(bid.state_label)}</td>"
            f"<td>{_e(checks)}</td>"
            "</tr>"
        )
    return "".join(rows)


def _arithmetic(model) -> str:
    items = []
    for bid in model.bids:
        if not bid.readable:
            continue
        if any("stated total" in check.lower() for check in bid.check_texts):
            source = source_label({"kind": "bid", "bidder": bid.bidder, "file": bid.file,
                                   "page": bid.total_page})
            items.append(f"<li>{_e(source)}: {_e(' '.join(bid.check_texts))}</li>")
    return "".join(items) or "<li>No stated total disagreed with its line items.</li>"


def _unreadable(model) -> str:
    items = []
    for bid in model.bids:
        if bid.readable:
            continue
        source = source_label({"kind": "bid", "bidder": bid.bidder, "file": bid.file,
                               "page": bid.total_page})
        items.append(f"<li>{_e(source)}: {_e(' '.join(bid.check_texts))}</li>")
    return "".join(items) or "<li>Every bid document could be read.</li>"


def _set_aside_rows(model) -> str:
    rows = []
    for row in model.set_asides:
        rows.append("<tr>"
                    f"<td>{_e(row.award_id)}</td>"
                    f"<td>{_e(row.title or labels.NOT_STATED)}</td>"
                    f'<td class="num">{_e(row.value_text)}</td>'
                    f"<td>{_e(row.reason_label)}</td>"
                    "</tr>")
    return "".join(rows) or "<tr><td colspan='4'>No award was set aside.</td></tr>"


def _pool_rows(model) -> str:
    rows = []
    for row in model.annex_pool:
        year = row.data_year if row.data_year is not None else "-"
        rows.append("<tr>"
                    f"<td>{_e(row.award_id)}</td>"
                    f"<td>{_e(row.title or labels.NOT_STATED)}</td>"
                    f"<td>{_e(row.buyer_name or labels.NOT_STATED)}</td>"
                    f'<td class="num">{_e(year)}</td>'
                    f'<td class="num">{_e(row.value_text)}</td>'
                    "</tr>")
    return "".join(rows) or "<tr><td colspan='5'>No comparable award was found.</td></tr>"


def _questions(model) -> str:
    items = []
    for bid in model.bids:
        if bid.readable and bid.state in labels.QUESTION_STATES:
            items.append(f"<li>{_e(bid.bidder)}: {_e(bid.state_label)}. What to check: "
                         f"{_e(' '.join(bid.check_texts))}</li>")
    for row in model.set_asides:
        items.append(f"<li>Was {_e(row.award_id)} rightly set aside as "
                     f"{_e(row.reason_label)}?</li>")
    return "".join(items) or "<li>No question is raised for the committee by these figures.</li>"


def _excluded_summary(model) -> str:
    if not model.excluded:
        return "No candidate award was excluded."
    parts = [f"{labels.reason_label(code)} ({count})"
             for code, count in sorted(model.excluded.items())]
    return "Candidates excluded in this run: " + ", ".join(parts) + "."


def render_html(model, fingerprint, approved_by=None, created_at=None,
                orientation="portrait", paper_size="A4"):
    """The print-ready file with the requested paper settings."""
    if orientation not in {"portrait", "landscape"}:
        raise ValueError("orientation must be 'portrait' or 'landscape'")
    if paper_size not in {"A4", "Letter"}:
        raise ValueError("paper_size must be 'A4' or 'Letter'")
    page_style = STYLE.replace("@page { size: A4;",
                               f"@page {{ size: {paper_size} {orientation};")
    short = (fingerprint or "")[:12]
    chart = render_chart_svg(model)
    chart_block = chart if chart else ""
    note = model.assistant_note or labels.ASSISTANT_MISSING
    approval = ""
    if approved_by:
        approval = (
            '<section class="approval">'
            f"<p>Approved by: {_e(approved_by)}</p>"
            f"<p>Filed at: {_e(created_at or 'Not recorded')}</p>"
            f'<p class="fingerprint">fingerprint {_e(fingerprint)}</p>'
            "</section>"
        )
    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Price review evidence: {_e(model.tender_ref)}</title>"
        f"<style>{page_style}</style></head><body>"
        '<main class="page-one">'
        f"<h1>Price review evidence: {_e(model.tender_ref)}</h1>"
        f'<p class="meta">Prepared: {_e(model.prepared_date)}</p>'
        f'<p class="meta">Run ID: {_e(model.run_id)}</p>'
        f'<p class="notice">{_e(model.notice)}</p>'
        f'<p class="bottom-line">{_e(model.bottom_line)}</p>'
        '<div class="figures">'
        f"<div><strong>Usual price</strong><br>{_e(model.usual_price)}</div>"
        f"<div><strong>Normal range</strong><br>{_e(model.normal_range)}</div>"
        f"<div><strong>Evidence</strong><br>{_e(model.evidence_strength)}</div>"
        "</div>"
        f"{chart_block}"
        "<h2>Bids</h2>"
        "<table><thead><tr><th class=\"num\">#</th><th>Bidder</th><th class=\"num\">Total</th>"
        "<th>Usual price comparison</th><th>State</th><th>What to check</th></tr></thead>"
        f"<tbody>{_bid_rows(model)}</tbody></table>"
        "<h2>What this table does not show</h2><ul>"
        + "".join(f"<li>{_e(line)}</li>" for line in model.caution_lines)
        + "</ul></main>"
        '<section class="page-two">'
        "<h2>Method</h2><ul>"
        + "".join(f"<li>{_e(point)}</li>" for point in model.method_points)
        + "</ul>"
        "<h3>Assistant note</h3>"
        f"<p><em>{_e(labels.ASSISTANT_LABEL)}</em></p><p>{_e(note)}</p>"
        "<h2>Arithmetic and set-asides</h2>"
        "<h3>Totals that do not match their line items</h3>"
        f"<ul>{_arithmetic(model)}</ul>"
        "<h3>Bids that could not be read</h3>"
        f"<ul>{_unreadable(model)}</ul>"
        "<h3>Set-aside awards</h3>"
        "<table><thead><tr><th>Award</th><th>Title</th><th class=\"num\">Value</th>"
        f"<th>Reason</th></tr></thead><tbody>{_set_aside_rows(model)}</tbody></table>"
        f"<p>{_e(_excluded_summary(model))}</p>"
        "<h2>Questions for the committee</h2>"
        f"<ul>{_questions(model)}</ul>"
        "<h2>Annex: comparable awards</h2>"
        "<table><thead><tr><th>Award</th><th>Title</th><th>Buyer</th><th class=\"num\">Year</th>"
        f"<th class=\"num\">Value</th></tr></thead><tbody>{_pool_rows(model)}</tbody></table>"
        "<h2>Annex: set-aside awards</h2>"
        "<table><thead><tr><th>Award</th><th>Title</th><th class=\"num\">Value</th>"
        f"<th>Reason</th></tr></thead><tbody>{_set_aside_rows(model)}</tbody></table>"
        "<h2>Glossary</h2><dl>"
        + "".join(f"<dt>{_e(term)}</dt><dd>{_e(meaning)}</dd>"
                  for term, meaning in model.glossary)
        + "</dl></section>"
        f'<footer class="footer">Run {_e(model.run_id)} &middot; evidence fingerprint {_e(short)}</footer>'
        f"{approval}"
        "</body></html>"
    )
