from mcp_server.tools.report_model import build_report_model


def test_bids_are_in_total_order_and_the_unreadable_bid_comes_last(report_model):
    assert [bid.bidder for bid in report_model.bids] == ["Zed", "Apex", "Bora", "Broken"]
    assert [bid.number for bid in report_model.bids] == [1, 2, 3, 4]
    assert not hasattr(report_model.bids[0], "rank")


def test_every_bid_is_kept_even_when_it_could_not_be_compared(report_model):
    broken = report_model.bids[-1]

    assert broken.readable is False
    assert broken.total is None
    assert broken.total_text == "Not compared"
    assert broken.state == "not_compared"
    assert broken.state_label == "not compared"
    assert "broken.pdf" in " ".join(broken.check_texts)


def test_each_comparable_bid_carries_a_figure_a_comparison_and_a_state(report_model):
    bora = next(bid for bid in report_model.bids if bid.bidder == "Bora")

    assert bora.total_text == "KES 8,650,000.00"
    assert bora.comparison == "205% above"
    assert bora.state == "far_above"
    assert bora.state_label == "far above the usual price"
    assert bora.shape == "filled-circle"


def test_a_total_that_misses_its_line_items_is_a_question_on_page_one(report_model):
    zed = next(bid for bid in report_model.bids if bid.bidder == "Zed")

    assert any("stated total" in check.lower() for check in zed.check_texts)
    assert any("line items" in check.lower() for check in zed.check_texts)
    assert any("KES 60,000.00" in check for check in zed.check_texts)
    assert zed.state == "within_range"


def test_a_bid_inside_the_range_with_nothing_else_wrong_says_nothing_flagged(report_model):
    apex = next(bid for bid in report_model.bids if bid.bidder == "Apex")

    assert apex.check_texts == ["Nothing flagged for this bid."]


def test_the_bottom_line_counts_within_and_question_bids(report_model):
    assert report_model.bottom_line.startswith("2 of 4 bids are within the usual price")
    assert "1 is worth a question first" in report_model.bottom_line
    assert "1 bid could not be read" in report_model.bottom_line


def test_the_usual_price_and_range_are_written_in_full_kes(report_model):
    assert report_model.usual_price == "KES 2,839,845.72"
    assert report_model.normal_range == (
        "KES 1,956,829.00 to KES 3,494,974.74")
    assert report_model.evidence_strength == "Strong"


def test_the_annex_lists_every_pool_award_in_value_order(report_model):
    assert [row.award_id for row in report_model.annex_pool] == ["a01", "a03", "a02"]
    assert [row.value_text for row in report_model.annex_pool] == [
        "KES 2,501,490.00", "KES 2,839,845.72", "KES 3,289,999.48"]


def test_the_set_aside_award_keeps_its_plain_word_reason(report_model):
    assert len(report_model.set_asides) == 1
    row = report_model.set_asides[0]

    assert row.award_id == "a09"
    assert row.reason_code == "different_work"
    assert row.reason_label == "different work"


def test_the_header_says_when_the_run_started_in_east_africa_time(report_model):
    assert report_model.prepared_date == "19 October 2026, 14:09 EAT"
    assert report_model.tender_title == "Construction of classroom blocks"
    assert report_model.buyer == "Ministry of Education"
    assert report_model.county == "Nairobi"
    assert report_model.title_inferred is False


def test_a_title_taken_from_the_bids_is_marked_as_such(report_state, report_review):
    report_state["tender_fields"] = {}
    report_state["description"] = "construction of classroom blocks"

    model = build_report_model(report_review, report_state)

    assert model.tender_title == "construction of classroom blocks"
    assert model.title_inferred is True
    assert model.buyer == "Not stated in the documents"
    assert model.county == "Not stated in the documents"


def test_a_thin_pool_has_no_chart_and_says_not_enough_evidence(report_state, report_review):
    report_state["benchmark"] = {
        "n": 2, "confidence": "insufficient", "median_kes": None, "q1_kes": None,
        "q3_kes": None, "bids": []}
    report_review["benchmark"] = report_state["benchmark"]

    model = build_report_model(report_review, report_state)

    assert model.chart is None
    assert model.evidence_strength == "Not enough evidence"
    assert model.bottom_line.startswith("Not enough comparable awards")
    assert model.usual_price == "Not enough evidence"
    assert all(bid.comparison == "not compared" for bid in model.bids if bid.readable)


def test_the_chart_clamp_is_twice_the_upper_quartile_by_default(report_model):
    assert report_model.chart is not None
    assert report_model.chart.clamp_max == report_model.benchmark.q3 * 2
    bora = next(point for point in report_model.chart.bid_points if point.bidder == "Bora")
    assert bora.off_chart is True


def test_the_assistant_note_is_kept_for_page_two_but_never_became_page_one_text(report_model):
    assert report_model.assistant_note == "SENTINEL_NOTE"
    assert report_model.page_1_text is not None
    assert "SENTINEL_NOTE" not in report_model.page_1_text
