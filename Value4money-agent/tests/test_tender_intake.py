from agent.nodes.tender_intake import tender_intake_node


def test_no_tender_means_nothing_to_read():
    result = tender_intake_node({"run_id": "run-1", "tender_path": None})

    assert result["tender"] == {}
    assert result["tender_fields"] == {}
    assert result["tender_missing"] == []


def test_a_supplied_tender_is_read_with_its_sources(tmp_path, monkeypatch):
    from agent.nodes import tender_intake

    def fake_extract(run_id, path):
        return {"fields": {"reference": {"value": "T/1",
                                        "source": {"page": 1, "text": "Tender No.: T/1"}}},
                "missing": ["title"], "rejected": [], "pages": []}

    monkeypatch.setattr(tender_intake, "extract_tender_pdf", fake_extract)

    result = tender_intake_node({"run_id": "run-1", "tender_path": str(tmp_path / "t.pdf")})

    assert result["tender_fields"]["reference"]["value"] == "T/1"
    assert result["tender_missing"] == ["title"]
    assert result["tender"]["fields"]["reference"]["value"] == "T/1"


def test_an_unreadable_tender_is_an_error_not_a_crash(tmp_path, monkeypatch):
    from agent.nodes import tender_intake

    def refuse(run_id, path):
        raise ValueError("Unable to extract text from PDF: broken")

    monkeypatch.setattr(tender_intake, "extract_tender_pdf", refuse)

    result = tender_intake_node({"run_id": "run-1", "tender_path": str(tmp_path / "t.pdf")})

    assert result["tender_fields"] == {}
    assert "broken" in result["errors"][0]
