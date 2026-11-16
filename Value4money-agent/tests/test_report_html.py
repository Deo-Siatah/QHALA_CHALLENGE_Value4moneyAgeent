from mcp_server.tools.report_html import render_html

FINGERPRINT = "a" * 64


def test_the_html_is_one_self_contained_print_document(report_model):
    html = render_html(report_model, fingerprint=FINGERPRINT)

    assert html.startswith("<!doctype html>")
    assert "<style>" in html
    assert "@page" in html and "A4" in html
    assert "page-break-inside: avoid" in html
    assert "display: table-header-group" in html
    assert "position: fixed" in html
    assert "<script" not in html.lower()
    assert "<link" not in html.lower()
    assert "@import" not in html.lower()
    assert "http://" not in html.lower()
    assert "https://" not in html.lower()


def test_every_string_from_the_run_is_escaped(report_model):
    report_model.bids[0].bidder = "A&B <Ltd>"

    html = render_html(report_model, fingerprint=FINGERPRINT)

    assert "A&amp;B &lt;Ltd&gt;" in html
    assert "A&B <Ltd>" not in html


def test_every_bid_state_has_a_word_and_an_inline_svg_symbol(report_model):
    html = render_html(report_model, fingerprint=FINGERPRINT)

    assert html.count('class="state-icon"') == len(report_model.bids)
    assert html.count("<title") >= len(report_model.bids)
    for word in ("within the usual price", "far above the usual price", "not compared"):
        assert word in html


def test_the_page_one_chart_is_inline_and_has_a_title_and_description(report_model):
    html = render_html(report_model, fingerprint=FINGERPRINT)

    assert 'class="chart"' in html
    assert 'class="bid-marker"' in html
    assert "Usual price chart" in html
    assert "comparable awards and bid totals" in html


def test_the_assistant_note_is_labelled_and_kept_off_page_one(report_model):
    html = render_html(report_model, fingerprint=FINGERPRINT)

    assert "Written by the assistant. Figures in this file are computed by code." in html
    assert "SENTINEL_NOTE" in html
    assert html.index("SENTINEL_NOTE") > html.index('class="page-two"')


def test_the_approval_block_is_rendered_at_view_time_outside_the_hashed_body(report_model):
    html = render_html(report_model, fingerprint=FINGERPRINT,
                       approved_by="Grace Wanjiku", created_at="2026-10-19T12:00:00+00:00")

    assert "Approved by: Grace Wanjiku" in html
    assert FINGERPRINT in html


def test_the_print_footer_carries_the_short_fingerprint_and_run_id(report_model):
    html = render_html(report_model, fingerprint=FINGERPRINT)

    assert "run-1" in html
    assert FINGERPRINT[:12] in html
    assert FINGERPRINT not in html


def test_a_thin_pool_prints_no_chart(report_state, report_review):
    from mcp_server.tools.report_model import build_report_model

    report_state["benchmark"] = {
        "n": 2, "confidence": "insufficient", "median_kes": None, "q1_kes": None,
        "q3_kes": None, "bids": []}
    report_review["benchmark"] = report_state["benchmark"]
    model = build_report_model(report_review, report_state)

    html = render_html(model, fingerprint=FINGERPRINT)

    assert 'class="chart"' not in html
    assert "Not enough evidence" in html
