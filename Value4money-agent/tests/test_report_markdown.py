from mcp_server.tools.report_markdown import render_markdown


def test_the_body_starts_with_the_one_page_one_title(report_model):
    markdown = render_markdown(report_model)

    assert markdown.startswith("# Price review evidence: TENDER/NC/2026/014")
    assert "Prepared: 19 October 2026, 14:09 EAT" in markdown
    assert "Run ID: run-1" in markdown


def test_page_one_has_the_bottom_line_the_bid_table_and_the_cautions(report_model):
    markdown = render_markdown(report_model)

    assert "## Bottom line" in markdown
    assert "2 of 4 bids are within the usual price" in markdown
    assert "| # | Bidder | Total | Usual price comparison | What to check |" in markdown
    assert "| 3 | Bora | KES 8,650,000.00 | 205% above |" in markdown
    assert "far above the usual price" in markdown
    assert report_model.caution_lines[0] in markdown
    assert report_model.caution_lines[1] in markdown


def test_page_one_uses_no_code_words_and_no_verdict_words(report_model):
    markdown = render_markdown(report_model)
    lower = markdown.lower()

    for code in ("within_range", "above_range", "below_range", "far_above", "far_below",
                 "different_work", "scale_mismatch"):
        assert code not in markdown
    assert "recommended" not in lower
    assert "winner" not in lower
    assert " ok " not in lower


def test_the_assistant_note_appears_only_after_page_two_starts(report_model):
    markdown = render_markdown(report_model)

    assert "## Method" in markdown
    assert "SENTINEL_NOTE" in markdown
    assert markdown.index("SENTINEL_NOTE") > markdown.index("## Method")
    assert "SENTINEL_NOTE" not in markdown[:markdown.index("## Method")]


def test_page_two_names_the_set_asides_arithmetic_and_the_committee_questions(report_model):
    markdown = render_markdown(report_model)

    assert "a09" in markdown
    assert "different work" in markdown
    assert "KES 2,750,000.00" in markdown
    assert "KES 2,690,000.00" in markdown
    assert "KES 60,000.00" in markdown
    assert "broken.pdf" in markdown
    assert "Questions for the committee" in markdown


def test_the_annex_lists_every_award_and_the_glossary(report_model):
    markdown = render_markdown(report_model)

    for award_id in ("a01", "a02", "a03", "a09"):
        assert award_id in markdown
    assert "## Annex: comparable awards" in markdown
    assert "## Annex: set-aside awards" in markdown
    assert "Glossary" in markdown


def test_the_markdown_is_the_filed_record_and_carries_no_approval_block(report_model):
    markdown = render_markdown(report_model)

    assert "Approved by:" not in markdown
    assert "fingerprint" not in markdown.lower()


def test_the_same_model_renders_the_same_body_every_time(report_model):
    assert render_markdown(report_model) == render_markdown(report_model)
