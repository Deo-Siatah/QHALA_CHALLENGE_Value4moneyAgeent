from agent.nodes import confirm_intake
from agent.nodes.confirm_intake import confirm_intake_node, intake_needs_review


def _bid(**overrides):
    base = {"bidder": "Apex", "status": "ok", "confidence": "high", "tender_ref": "T/1",
            "stated_total": 1000.0}
    base.update(overrides)
    return base


def test_a_clean_intake_needs_no_person():
    needed, issues = intake_needs_review({"bids": [_bid()]})

    assert needed is False
    assert issues == []


def test_a_low_confidence_bid_needs_a_person():
    needed, issues = intake_needs_review({"bids": [_bid(), _bid(bidder="Scan", confidence="low", status="needs_review", stated_total=None)]})

    assert needed is True
    assert issues


def test_a_tender_with_missing_fields_needs_a_person():
    needed, issues = intake_needs_review({
        "bids": [_bid()],
        "tender": {"fields": {}, "missing": ["reference", "title"]},
    })

    assert needed is True
    assert any("missing" in issue for issue in issues)


def test_a_tender_reference_conflict_stops_the_run(monkeypatch):
    def boom(payload):
        raise AssertionError("a conflicting tender reference must not interrupt")

    monkeypatch.setattr(confirm_intake, "interrupt", boom)

    result = confirm_intake_node({"run_id": "run-1", "bids": [_bid()],
                                  "tender_ref_conflict": True})

    assert result["intake_confirmed"] is False
    assert any("tender" in error for error in result["errors"])


def test_a_clean_intake_is_confirmed_without_an_interrupt():
    result = confirm_intake_node({"run_id": "run-1", "bids": [_bid()]})

    assert result["intake_confirmed"] is True
    assert result["intake_issues"] == []


def test_no_readable_bid_stops_the_run_without_asking_anyone(monkeypatch):
    def boom(payload):
        raise AssertionError("a run with no readable bid must not interrupt")

    monkeypatch.setattr(confirm_intake, "interrupt", boom)

    result = confirm_intake_node({"run_id": "run-1", "bids": []})

    assert result["intake_confirmed"] is False
    assert result["errors"]


def test_a_gate_is_skipped_when_the_web_upload_cannot_answer_it(monkeypatch):
    monkeypatch.setattr(confirm_intake.settings, "intake_gate", False)

    result = confirm_intake_node({"run_id": "run-1",
                                  "bids": [_bid(), _bid(bidder="Scan", confidence="low", status="needs_review", stated_total=None)]})

    assert result["intake_confirmed"] is True
    assert result["intake_issues"]


def test_a_person_who_confirms_records_the_decision(monkeypatch):
    recorded = []
    monkeypatch.setattr(confirm_intake.settings, "intake_gate", True)
    monkeypatch.setattr(confirm_intake, "interrupt",
                        lambda payload: {"confirmed": True, "approved_by": "Grace Wanjiku"})
    monkeypatch.setattr(confirm_intake, "record_intake_correction",
                        lambda *args, **kwargs: recorded.append(args) or {"field": args[1]})

    result = confirm_intake_node({"run_id": "run-1",
                                  "bids": [_bid(), _bid(bidder="Scan", confidence="low", status="needs_review", stated_total=None)]})

    assert result["intake_confirmed"] is True
    assert recorded and recorded[0][1] == "intake"


def test_a_person_who_declines_stops_the_run(monkeypatch):
    monkeypatch.setattr(confirm_intake.settings, "intake_gate", True)
    monkeypatch.setattr(confirm_intake, "interrupt", lambda payload: {"confirmed": False})

    result = confirm_intake_node({"run_id": "run-1",
                                  "bids": [_bid(), _bid(bidder="Scan", confidence="low", status="needs_review", stated_total=None)]})

    assert result["intake_confirmed"] is False
    assert result["errors"]


def test_a_correction_is_recorded_through_the_audited_tool(monkeypatch):
    recorded = []
    monkeypatch.setattr(confirm_intake.settings, "intake_gate", True)
    monkeypatch.setattr(confirm_intake, "interrupt",
                        lambda payload: {"confirmed": True, "approved_by": "Grace Wanjiku",
                                         "corrections": {"county": "Nairobi"}})
    monkeypatch.setattr(confirm_intake, "record_intake_correction",
                        lambda *args, **kwargs: recorded.append(args) or {"field": args[1]})

    result = confirm_intake_node({"run_id": "run-1",
                                  "bids": [_bid(), _bid(bidder="Scan", confidence="low", status="needs_review", stated_total=None)],
                                  "tender_fields": {"county": {"value": "Nairobi"}}})

    assert result["intake_confirmed"] is True
    assert any(call[1:3] == ("county", "Nairobi") for call in recorded)
