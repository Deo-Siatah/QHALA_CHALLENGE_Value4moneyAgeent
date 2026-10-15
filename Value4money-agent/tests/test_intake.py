import pytest

from agent.nodes import intake
from agent.nodes.intake import intake_node
from agent.state import initial_state
from conftest import make_pdf

APEX_LINES = [
    "Bidder: Apex Supplies Ltd",
    "Tender reference: KPLC/POLES/2026/001",
    "Currency: KES",
    "1 | 11m treated wooden pole | each | 10000 | 15500 | 155,000,000",
    "Stated total: 155,000,000",
]

BORA_LINES = [
    "Bidder: Bora Contractors",
    "Tender reference: KPLC/POLES/2026/001",
    "Currency: KES",
    "1 | 11m treated wooden pole | each | 10000 | 16000 | 160,000,000",
    "Stated total: 160,000,000",
]

OTHER_TENDER_LINES = [
    "Bidder: Zed Works",
    "Tender reference: KPLC/OTHER/2026/002",
    "Currency: KES",
    "1 | Office chairs | each | 40 | 15000 | 600,000",
    "Stated total: 600,000",
]

BROKEN_LINES = ["This file is not a bid at all", "Nothing here will parse"]


@pytest.fixture
def bids_dir(tmp_path, monkeypatch):
    """A tmp_path holding every PDF under test, and bids_dir pointed at it."""
    monkeypatch.setattr(intake.settings, "bids_dir", tmp_path)
    return tmp_path


@pytest.fixture(autouse=True)
def logged(audit_conn, monkeypatch):
    """Point the audit wrapper at the temporary audit_log table for every test in this module."""
    from mcp_server import audit
    from conftest import SharedConnection

    monkeypatch.setattr(audit, "get_conn", lambda: SharedConnection(audit_conn))

    def read():
        return audit_conn.execute(
            "SELECT * FROM audit_log WHERE run_id = %s ORDER BY id", ("run-1",)).fetchall()

    return read


@pytest.fixture
def asked(monkeypatch):
    """Capture the intake_tender_profile payload and reply with a canned profile."""
    calls = []

    def install(answer=None):
        def fake_ask(prompt_name, payload):
            calls.append((prompt_name, payload))
            return answer if answer is not None else {"category": "goods",
                                                     "description": "supply of treated wooden poles"}

        monkeypatch.setattr(intake, "ask_json", fake_ask)
        return calls

    return install


def run(pdf_paths, **overrides):
    state = initial_state("run-1", [str(p) for p in pdf_paths], "2026-03-01T09:00:00Z")
    state.update(overrides)
    return intake_node(state)


def test_two_bids_are_parsed_and_named(bids_dir, asked):
    apex = make_pdf(bids_dir, "apex.pdf", APEX_LINES)
    bora = make_pdf(bids_dir, "bora.pdf", BORA_LINES)
    calls = asked()

    result = run([apex, bora])

    assert [b["bidder"] for b in result["bids"]] == ["Apex Supplies Ltd", "Bora Contractors"]
    assert result["tender_ref"] == "KPLC/POLES/2026/001"
    assert result["category"] == "goods"
    assert result["description"] == "supply of treated wooden poles"
    assert result["parse_issues"] == []

    name, payload = calls[0]
    assert name == "intake_tender_profile"
    assert payload["tender_ref"] == "KPLC/POLES/2026/001"
    assert payload["items"][0]["description"] == "11m treated wooden pole"
    assert payload["items"][0]["quantity"] == 10000


def test_one_unreadable_pdf_does_not_stop_the_others(bids_dir, asked):
    apex = make_pdf(bids_dir, "apex.pdf", APEX_LINES)
    broken = make_pdf(bids_dir, "broken.pdf", BROKEN_LINES)
    asked()

    result = run([apex, broken])

    assert [b["bidder"] for b in result["bids"]] == ["Apex Supplies Ltd"]
    assert len(result["parse_issues"]) == 1
    assert "broken.pdf" in result["parse_issues"][0]
    assert "errors" not in result


def test_a_missing_file_is_recorded_and_named(bids_dir, asked):
    apex = make_pdf(bids_dir, "apex.pdf", APEX_LINES)
    asked()

    result = run([apex, bids_dir / "not-there.pdf"])

    assert len(result["bids"]) == 1
    assert "not-there.pdf" in result["parse_issues"][0]


def test_no_parsable_bid_ends_the_run_without_asking_the_model(bids_dir, asked):
    broken = make_pdf(bids_dir, "broken.pdf", BROKEN_LINES)
    calls = asked()

    result = run([broken])

    assert result["bids"] == []
    assert result["parse_issues"]
    assert "errors" in result
    assert "no bid could be parsed" in result["errors"][0]
    assert calls == []


def test_bids_from_two_different_tenders_are_an_error(bids_dir, asked):
    apex = make_pdf(bids_dir, "apex.pdf", APEX_LINES)
    other = make_pdf(bids_dir, "other.pdf", OTHER_TENDER_LINES)
    asked()

    result = run([apex, other])

    assert "errors" in result
    assert "KPLC/POLES/2026/001" in result["errors"][0]
    assert "KPLC/OTHER/2026/002" in result["errors"][0]


def test_arithmetic_issues_come_from_the_tool_untouched(bids_dir, asked):
    wrong = [
        "Bidder: Apex Supplies Ltd",
        "Tender reference: KPLC/POLES/2026/001",
        "Currency: KES",
        "1 | 11m treated wooden pole | each | 10000 | 15500 | 155,000,000",
        "Stated total: 160,000,000",
    ]
    apex = make_pdf(bids_dir, "apex.pdf", wrong)
    asked()

    result = run([apex])

    assert result["bids"][0]["arithmetic_ok"] is False
    assert result["bids"][0]["issues"]


@pytest.mark.parametrize("answer, expected", [
    ({"category": "construction", "description": "poles"}, "category"),
    ({"category": "goods", "description": "   "}, "description"),
])
def test_a_bad_profile_from_the_model_is_refused(bids_dir, asked, answer, expected):
    apex = make_pdf(bids_dir, "apex.pdf", APEX_LINES)
    asked(answer)

    with pytest.raises(ValueError) as err:
        run([apex])

    assert expected in str(err.value)
    assert "intake_tender_profile" in str(err.value)


def test_the_paths_come_from_state_not_from_a_directory_scan(bids_dir, asked):
    apex = make_pdf(bids_dir, "apex.pdf", APEX_LINES)
    make_pdf(bids_dir, "unlisted.pdf", BORA_LINES)
    asked()

    result = run([apex])

    assert [b["bidder"] for b in result["bids"]] == ["Apex Supplies Ltd"]


def test_every_pdf_read_is_logged_under_the_run(bids_dir, asked, logged):
    apex = make_pdf(bids_dir, "apex.pdf", APEX_LINES)
    bora = make_pdf(bids_dir, "bora.pdf", BORA_LINES)
    asked()

    run([apex, bora])

    rows = logged()
    assert len(rows) == 2
    assert [r["tool"] for r in rows] == ["parse_bid_pdf", "parse_bid_pdf"]
    assert [r["input"]["path"] for r in rows] == [str(apex), str(bora)]
    assert all(r["run_id"] == "run-1" for r in rows)
    assert [r["output"]["bidder"] for r in rows] == ["Apex Supplies Ltd", "Bora Contractors"]


def test_an_unreadable_pdf_is_logged_as_an_error(bids_dir, asked, logged):
    broken = make_pdf(bids_dir, "broken.pdf", BROKEN_LINES)
    asked()

    run([broken])

    rows = logged()
    assert len(rows) == 1
    assert "error" in rows[0]["output"]


def test_initial_state_takes_the_list_of_paths():
    state = initial_state("run-1", ["a.pdf", "b.pdf"], "2026-03-01T09:00:00Z")

    assert state["pdf_paths"] == ["a.pdf", "b.pdf"]
    assert "pdf_path" not in state
    assert "exclude_ocid" not in state
