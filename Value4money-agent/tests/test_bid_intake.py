from agent.nodes import bid_intake
from agent.nodes.bid_intake import bid_intake_node


def _bid(bidder, **overrides):
    base = {"bidder": bidder, "tender_ref": "T/1", "currency": "KES", "items": [],
            "stated_total": 1000.0, "computed_total": 1000.0, "arithmetic_ok": True,
            "issues": [], "confidence": "high", "status": "ok", "method": "strict",
            "flagged_pages": [], "unresolved_pages": []}
    base.update(overrides)
    return base


def test_every_bid_is_read_through_the_audited_extractor(monkeypatch):
    calls = []

    def fake_extract(run_id, path):
        calls.append((run_id, path))
        return _bid(f"bidder-{path}")

    monkeypatch.setattr(bid_intake, "parse_bid_pdf", fake_extract)
    monkeypatch.setattr(bid_intake, "ask_json", lambda name, payload: {"category": "works",
                                                                      "description": "fencing"})

    result = bid_intake_node({"run_id": "run-1", "pdf_paths": ["a.pdf", "b.pdf"]})

    assert sorted(calls) == [("run-1", "a.pdf"), ("run-1", "b.pdf")]
    assert len(result["bids"]) == 2
    assert result["bid_status"]["a.pdf"] == "ok"
    assert result["tender_ref"] == "T/1"
    assert result["category"] == "works"
    assert result["core_terms"] == ["fencing"]


def test_an_unreadable_bid_is_named_and_kept_out_of_the_status_table(monkeypatch):
    def fake_extract(run_id, path):
        if path == "bad.pdf":
            raise ValueError("File not found")
        return _bid("Apex")

    monkeypatch.setattr(bid_intake, "parse_bid_pdf", fake_extract)
    monkeypatch.setattr(bid_intake, "ask_json", lambda name, payload: {"category": "works",
                                                                      "description": "fencing"})

    result = bid_intake_node({"run_id": "run-1", "pdf_paths": ["bad.pdf", "good.pdf"]})

    assert len(result["bids"]) == 1
    assert "bad.pdf" in result["parse_issues"][0]
    assert "bad.pdf" not in result["bid_status"]


def test_the_tender_reference_must_agree_across_bids_and_the_tender(monkeypatch):
    monkeypatch.setattr(bid_intake, "parse_bid_pdf",
                        lambda run_id, path: _bid("Apex", tender_ref="T/2"))
    monkeypatch.setattr(bid_intake, "ask_json", lambda name, payload: {"category": "works",
                                                                      "description": "fencing"})

    result = bid_intake_node({"run_id": "run-1", "pdf_paths": ["a.pdf"],
                              "tender_fields": {"reference": {"value": "T/1"}}})

    assert result["tender_ref_conflict"] is True
    assert any("does not match the tender T/1" in error for error in result["errors"])


def test_the_tender_reference_is_used_when_the_bid_has_none(monkeypatch):
    monkeypatch.setattr(bid_intake, "parse_bid_pdf",
                        lambda run_id, path: _bid("Apex", tender_ref=""))
    monkeypatch.setattr(bid_intake, "ask_json", lambda name, payload: {"category": "works",
                                                                      "description": "fencing"})

    result = bid_intake_node({"run_id": "run-1", "pdf_paths": ["a.pdf"],
                              "tender_fields": {"reference": {"value": "T/1"}}})

    assert result["tender_ref"] == "T/1"
    assert result["tender_ref_conflict"] is False
    assert "errors" not in result


def test_the_tender_title_is_the_description_and_the_model_only_classifies(monkeypatch):
    calls = []

    def fake_ask(name, payload):
        calls.append((name, payload))
        return {"category": "works"}

    monkeypatch.setattr(bid_intake, "parse_bid_pdf", lambda run_id, path: _bid("Apex"))
    monkeypatch.setattr(bid_intake, "ask_json", fake_ask)

    result = bid_intake_node({
        "run_id": "run-1", "pdf_paths": ["a.pdf"],
        "tender_fields": {"reference": {"value": "T/1"},
                          "title": {"value": "Construction of classroom blocks"}},
    })

    assert result["description"] == "Construction of classroom blocks"
    assert result["category"] == "works"
    assert result["core_terms"] == ["construction", "classroom"]
    assert calls[0][0] == "intake_tender_category"
    assert calls[0][1]["title"] == "Construction of classroom blocks"
