from mcp_server.tools.verify_rows import verify_extracted_rows

PAGE = "1 | Chainlink fabric | roll | 10 | 1,200 | 12,000"


def row(**overrides):
    base = {"item_label": "1", "description": "Chainlink fabric", "unit": "roll",
            "quantity": 10, "unit_price": 1200, "line_total": 12000,
            "source_text": "1 | Chainlink fabric | roll | 10 | 1,200 | 12,000"}
    base.update(overrides)
    return base


def test_a_row_whose_numbers_are_on_the_page_and_add_up_is_accepted():
    result = verify_extracted_rows(PAGE, [row()])

    assert len(result["accepted"]) == 1
    assert result["rejected"] == []
    assert result["accepted"][0]["line_total"] == 12000


def test_a_number_that_is_not_on_the_page_is_rejected():
    result = verify_extracted_rows(PAGE, [row(quantity=999)])

    assert result["accepted"] == []
    assert "999" in result["rejected"][0]["reason"]


def test_a_row_that_does_not_reconcile_is_rejected():
    result = verify_extracted_rows(PAGE, [row(line_total=10)])

    assert result["accepted"] == []
    assert "reconcile" in result["rejected"][0]["reason"]


def test_a_reply_that_is_not_the_schema_is_rejected():
    result = verify_extracted_rows(PAGE, [{"foo": "bar"}, "not a row"])

    assert result["accepted"] == []
    assert len(result["rejected"]) == 2
