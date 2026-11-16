from mcp_server.tools.report_chart import render_chart_svg


def test_the_chart_numbers_every_bid_marker(report_model):
    svg = render_chart_svg(report_model)

    assert svg.count('class="bid-marker"') == 3
    assert ">1<" in svg and ">2<" in svg and ">3<" in svg


def test_a_bid_above_the_clamp_is_drawn_at_the_edge_and_marked_off_chart(report_model):
    svg = render_chart_svg(report_model)

    assert 'class="bid-marker off-chart"' in svg
    bora = next(point for point in report_model.chart.bid_points if point.bidder == "Bora")
    assert bora.off_chart is True


def test_the_chart_marks_the_normal_range_and_the_usual_price(report_model):
    svg = render_chart_svg(report_model)

    assert 'class="normal-range"' in svg
    assert 'class="usual-price"' in svg
    assert "Normal range" in svg
    assert "Usual price" in svg


def test_the_chart_has_an_accessible_title_and_description(report_model):
    svg = render_chart_svg(report_model)

    assert "<title>Usual price chart</title>" in svg
    assert "comparable awards and bid totals" in svg


def test_the_chart_is_deterministic_so_the_same_run_prints_the_same_file(report_model):
    assert render_chart_svg(report_model) == render_chart_svg(report_model)


def test_a_thin_pool_has_no_chart(report_state, report_review):
    from mcp_server.tools.report_model import build_report_model

    report_state["benchmark"] = {
        "n": 2, "confidence": "insufficient", "median_kes": None, "q1_kes": None,
        "q3_kes": None, "bids": []}
    report_review["benchmark"] = report_state["benchmark"]
    model = build_report_model(report_review, report_state)

    assert render_chart_svg(model) == ""
