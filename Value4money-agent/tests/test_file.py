import pytest

from agent.nodes import file as file_node_module
from agent.nodes.file import file_node

REPORT = "# Price review evidence: TENDER/NC/2026/014\n\n## Summary\n\nEighteen awards.\n"


@pytest.fixture
def filed(audit_conn, reports_conn, tmp_path, monkeypatch):
    """Point the filing tool at the temporary tables and tmp_path, and record what it received."""
    from mcp_server import audit
    from mcp_server.tools import submit_for_committee as tool
    from conftest import SharedConnection

    monkeypatch.setattr(audit, "get_conn", lambda: SharedConnection(audit_conn))
    monkeypatch.setattr(tool, "get_conn", lambda: SharedConnection(reports_conn))
    monkeypatch.setattr(file_node_module.settings, "outputs_dir", tmp_path)

    calls = []
    real = file_node_module.submit_for_committee

    def spy(run_id, report_md, approved_by):
        calls.append((run_id, report_md, approved_by))
        return real(run_id, report_md, approved_by)

    monkeypatch.setattr(file_node_module, "submit_for_committee", spy)
    return calls, tmp_path


def approved(**overrides):
    state = {"run_id": "run-1", "approval_status": "approved", "approved_by": "Grace Wanjiku",
             "approval_note": "checked", "review_markdown": REPORT}
    state.update(overrides)
    return state


def test_an_approved_report_is_filed_and_the_file_written(filed):
    calls, tmp_path = filed

    result = file_node(approved())

    assert calls == [("run-1", REPORT, "Grace Wanjiku")]
    assert result["submission"]["run_id"] == "run-1"
    assert result["submission"]["approved_by"] == "Grace Wanjiku"
    assert (tmp_path / "reports" / "run-1.md").read_text(encoding="utf-8") == REPORT
    assert "errors" not in result


def test_the_filing_is_logged_with_the_approver(filed, audit_conn):
    filed[0]

    file_node(approved())

    rows = audit_conn.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
    assert [r["tool"] for r in rows] == ["submit_for_committee"]
    assert rows[0]["approved_by"] == "Grace Wanjiku"
    assert rows[0]["run_id"] == "run-1"


@pytest.mark.parametrize("status", ["pending", "rejected", "no_report"])
def test_a_report_is_not_filed_without_an_approval(filed, status):
    calls, tmp_path = filed

    with pytest.raises(ValueError) as err:
        file_node(approved(approval_status=status))

    assert "approval_status" in str(err.value)
    assert calls == []
    assert not (tmp_path / "reports").exists()


def test_a_placeholder_approver_is_refused(filed):
    calls, tmp_path = filed

    with pytest.raises(ValueError) as err:
        file_node(approved(approved_by="agent"))

    assert "approved_by" in str(err.value)
    assert calls == []


def test_an_empty_report_is_refused(filed):
    calls, tmp_path = filed

    with pytest.raises(ValueError) as err:
        file_node(approved(review_markdown="   "))

    assert "review_markdown" in str(err.value)
    assert calls == []


def test_a_refused_filing_is_recorded_and_nothing_is_stored(filed):
    calls, tmp_path = filed
    file_node(approved())

    result = file_node(approved())

    assert "submission" not in result
    assert "already been filed" in result["errors"][0]
    assert len(reports_rows(tmp_path)) == 1


def reports_rows(tmp_path):
    return list((tmp_path / "reports").glob("*.md"))