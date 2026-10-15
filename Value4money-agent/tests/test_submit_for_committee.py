import pytest
from pathlib import Path

from mcp_server.tools.submit_for_committee import submit_report, submit_for_committee, SubmitError

REPORT = "# Price review evidence: TENDER/NC/2026/014\n\nEvidence for committee review.\n"


def rows(conn, run_id):
    return conn.execute("SELECT * FROM reports WHERE run_id = %s", (run_id,)).fetchall()


def test_valid_submit_inserts_row_writes_file_and_returns_fields(reports_conn, tmp_path):
    result = submit_report(reports_conn, tmp_path, "run-1", REPORT, "Grace Wanjiku")
    reports_conn.commit()

    saved = rows(reports_conn, "run-1")
    assert len(saved) == 1
    assert saved[0]["body_md"] == REPORT
    assert saved[0]["approved_by"] == "Grace Wanjiku"

    file_path = tmp_path / "reports" / "run-1.md"
    assert file_path.exists()
    assert file_path.read_text(encoding="utf-8") == REPORT

    assert result["run_id"] == "run-1"
    assert result["approved_by"] == "Grace Wanjiku"
    assert Path(result["file_path"]) == file_path
    assert result["report_id"] == saved[0]["id"]
    assert result["submitted_at"] is not None


@pytest.mark.parametrize(
    "approved_by",
    ["", "   ", "  a  ", None, "agent", "AI", "System", "bot", "auto", "none", "N/A", "unknown"],
)
def test_blank_and_placeholder_approvers_rejected(reports_conn, tmp_path, approved_by):
    with pytest.raises(SubmitError):
        submit_report(reports_conn, tmp_path, "run-1", REPORT, approved_by)

    assert rows(reports_conn, "run-1") == []
    assert not (tmp_path / "reports" / "run-1.md").exists()


@pytest.mark.parametrize("report_md", ["", "   \n\t ", None])
def test_blank_report_rejected(reports_conn, tmp_path, report_md):
    with pytest.raises(SubmitError):
        submit_report(reports_conn, tmp_path, "run-1", report_md, "Grace Wanjiku")

    assert rows(reports_conn, "run-1") == []
    assert not (tmp_path / "reports" / "run-1.md").exists()


@pytest.mark.parametrize("run_id", ["../x", "a/b", "", "x" * 65, "run 1", "run.1"])
def test_unsafe_run_id_rejected(reports_conn, tmp_path, run_id):
    with pytest.raises(SubmitError):
        submit_report(reports_conn, tmp_path, run_id, REPORT, "Grace Wanjiku")

    assert reports_conn.execute("SELECT count(*) AS n FROM reports").fetchone()["n"] == 0
    assert not (tmp_path / "reports").exists()


def test_duplicate_run_id_rejected(reports_conn, tmp_path):
    submit_report(reports_conn, tmp_path, "run-1", REPORT, "Grace Wanjiku")
    reports_conn.commit()

    with pytest.raises(SubmitError):
        submit_report(reports_conn, tmp_path, "run-1", REPORT + "again\n", "Another Person")

    assert len(rows(reports_conn, "run-1")) == 1


def test_failed_file_write_rolls_back_the_row(reports_conn, tmp_path, monkeypatch):
    def boom(self, *args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", boom)

    with pytest.raises(SubmitError):
        submit_report(reports_conn, tmp_path, "run-1", REPORT, "Grace Wanjiku")

    assert rows(reports_conn, "run-1") == []


def test_wrapper_uses_settings_outputs_dir(monkeypatch, tmp_path, reports_conn):
    import mcp_server.tools.submit_for_committee as module

    monkeypatch.setattr(module, "get_conn", lambda: reports_conn)
    monkeypatch.setattr(module.settings, "outputs_dir", tmp_path)

    result = submit_for_committee("run-9", REPORT, "Grace Wanjiku")

    assert (tmp_path / "reports" / "run-9.md").read_text(encoding="utf-8") == REPORT
    assert result["run_id"] == "run-9"
    assert result["approved_by"] == "Grace Wanjiku"
    assert result["file_path"] == str(tmp_path / "reports" / "run-9.md")
