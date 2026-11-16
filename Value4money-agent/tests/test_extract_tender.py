import pytest

from conftest import make_pdf
from mcp_server.paths import PathOutsideError
from mcp_server.tools.extract_tender import extract_tender_pdf

TENDER_LINES = [
    "Tender No.: KURA/ENG/2026/001",
    "Title: Construction of classroom blocks",
    "Procuring entity: Ministry of Education",
    "County: Nairobi",
    "Procurement method: Open tender",
    "Closing date: 2026-12-01",
    "Budget: KES 5,000,000",
]


def test_labelled_fields_are_extracted_with_their_source(tmp_path):
    path = make_pdf(tmp_path, "tender.pdf", TENDER_LINES)

    result = extract_tender_pdf(path, tmp_path)

    fields = result["fields"]
    assert fields["reference"]["value"] == "KURA/ENG/2026/001"
    assert fields["reference"]["source"]["page"] == 1
    assert "KURA/ENG/2026/001" in fields["reference"]["source"]["text"]
    assert fields["title"]["value"] == "Construction of classroom blocks"
    assert fields["buyer"]["value"] == "Ministry of Education"
    assert fields["county"]["value"] == "Nairobi"
    assert fields["method"]["value"] == "Open tender"
    assert fields["closing_date"]["value"] == "2026-12-01"
    assert fields["budget_kes"]["value"] == 5_000_000
    assert result["missing"] == []


def test_a_filled_value_that_is_not_on_the_page_is_rejected(tmp_path):
    path = make_pdf(tmp_path, "tender.pdf", TENDER_LINES)

    result = extract_tender_pdf(path, tmp_path, filled={"county": "Mombasa"})

    assert "county" not in result["fields"] or result["fields"]["county"]["value"] != "Mombasa"
    assert any(item["field"] == "county" and item["value"] == "Mombasa"
               for item in result["rejected"])


def test_a_filled_value_that_is_on_the_page_is_accepted(tmp_path):
    path = make_pdf(tmp_path, "tender.pdf", TENDER_LINES)

    result = extract_tender_pdf(path, tmp_path, filled={"title": "Construction of classroom blocks"})

    assert result["fields"]["title"]["value"] == "Construction of classroom blocks"


def test_a_tender_outside_its_folder_is_refused(tmp_path):
    tenders = tmp_path / "tenders"
    evil = tmp_path / "tenders_evil"
    tenders.mkdir()
    evil.mkdir()
    path = make_pdf(evil, "tender.pdf", TENDER_LINES)

    with pytest.raises(PathOutsideError):
        extract_tender_pdf(path, tenders)
