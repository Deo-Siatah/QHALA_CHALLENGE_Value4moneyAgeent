import pytest

from agent import community_mcp
from agent.community_mcp import (CommunityQueryRefused, describe_schema, fallback_candidates,
                                 normalize_rows, run_query, validate_sql)

SELECT = ("SELECT a.award_id, a.value_kes FROM awards a JOIN tenders t ON a.ocid = t.ocid "
          "WHERE a.value_kes > 0 ORDER BY a.value_kes LIMIT 30")


@pytest.fixture(autouse=True)
def audit_goes_to_a_temporary_table(audit_conn, monkeypatch):
    """Every test in this module writes to the temporary audit_log, never the real one.

    Two of these tests exercise the failure path, which records to audit_log itself, so the guard
    has to be module-wide rather than per test.
    """
    from mcp_server import audit
    from conftest import SharedConnection

    monkeypatch.setattr(audit, "get_conn", lambda: SharedConnection(audit_conn))


@pytest.fixture
def off(monkeypatch):
    """The community server switched off, as it is when disabled or has no URL."""
    monkeypatch.setattr(community_mcp, "_session", None)
    monkeypatch.setattr(community_mcp.settings, "community_mcp_enabled", False)
    return monkeypatch


@pytest.mark.parametrize("sql", [
    "SELECT 1",
    "WITH x AS (SELECT 1) SELECT * FROM x",
    "  select award_id from awards",
])
def test_a_plain_read_is_allowed(sql):
    validate_sql(sql)


@pytest.mark.parametrize("sql", [
    "DELETE FROM awards",
    "UPDATE awards SET value_kes = 0",
    "DROP TABLE awards",
    "TRUNCATE awards",
    "CREATE TABLE x (a int)",
    "ALTER TABLE awards ADD COLUMN x int",
    "GRANT ALL ON awards TO public",
    "COMMIT",
    "ROLLBACK",
    "SET default_transaction_read_only = off",
    "COPY awards TO '/tmp/out.csv'",
    "SELECT 1; DELETE FROM awards",
    "EXPLAIN DELETE FROM awards",
    "INSERT INTO awards (award_id) VALUES ('x')",
])
def test_anything_that_is_not_a_plain_read_is_refused(sql):
    with pytest.raises(CommunityQueryRefused) as err:
        validate_sql(sql)

    assert "SELECT" in str(err.value) or "refused" in str(err.value)


@pytest.mark.parametrize("sql", [
    "SELECT * FROM reports",
    "SELECT * FROM audit_log",
    "SELECT * FROM checkpoints",
    "SELECT * FROM tenders JOIN reports ON true",
])
def test_only_the_evidence_tables_may_be_read(sql):
    with pytest.raises(CommunityQueryRefused) as err:
        validate_sql(sql)

    assert "tenders" in str(err.value)


def test_an_empty_query_is_refused():
    with pytest.raises(CommunityQueryRefused):
        validate_sql("   ")


def test_rows_are_normalised_into_candidate_shape():
    from decimal import Decimal

    rows = [{"award_id": "a01", "value_kes": Decimal("2069300.00"), "title": "Classroom works",
             "supplier_norm": None, "quality_flags": []}]

    candidates = normalize_rows(rows)

    assert isinstance(candidates[0]["value_kes"], float)
    assert candidates[0]["award_id"] == "a01"
    assert candidates[0]["title"] == "Classroom works"


def test_rows_without_an_award_id_are_dropped():
    assert normalize_rows([{"value_kes": 1.0}, {"award_id": "a01", "value_kes": 1.0}]) == [
        {"award_id": "a01", "value_kes": 1.0}]


def test_disabled_is_a_clean_no_op(off):
    assert describe_schema("run-1") == []
    assert run_query("run-1", SELECT) == []
    assert fallback_candidates("run-1", SELECT) == []


def test_a_guarded_call_writes_one_audit_row(off, audit_conn, monkeypatch):
    from mcp_server import audit
    from conftest import SharedConnection

    monkeypatch.setattr(audit, "get_conn", lambda: SharedConnection(audit_conn))
    monkeypatch.setattr(community_mcp.settings, "community_mcp_enabled", True)
    monkeypatch.setattr(community_mcp, "_call_sync", lambda tool, arguments: {
        "content": [{"type": "text", "text": '[{"award_id": "a01", "value_kes": 1000.0}]'}]})

    found = run_query("run-audit", SELECT)

    assert [row["award_id"] for row in found] == ["a01"]
    rows = audit_conn.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
    assert [r["tool"] for r in rows] == ["community_query"]
    assert rows[0]["run_id"] == "run-audit"


def test_a_server_failure_is_recorded_and_returns_nothing(off, monkeypatch):
    monkeypatch.setattr(community_mcp.settings, "community_mcp_enabled", True)

    def broken(tool, arguments):
        raise RuntimeError("uvx could not fetch postgres-mcp")

    monkeypatch.setattr(community_mcp, "_call_sync", broken)

    assert run_query("run-1", SELECT) == []


def test_a_refused_query_is_audited_before_anything_is_sent(off, audit_conn, monkeypatch):
    from mcp_server import audit
    from conftest import SharedConnection

    monkeypatch.setattr(audit, "get_conn", lambda: SharedConnection(audit_conn))
    monkeypatch.setattr(community_mcp.settings, "community_mcp_enabled", True)
    monkeypatch.setattr(community_mcp, "_call_sync", lambda tool, arguments: {"content": []})

    assert run_query("run-guard", "DELETE FROM awards") == []

    rows = audit_conn.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
    # One row says the community query returned nothing, the next says why it was never sent.
    assert [r["tool"] for r in rows] == ["community_query", "community_error"]
    assert "refused" in rows[1]["output"]["error"]


def test_the_schema_call_is_audited(off, audit_conn, monkeypatch):
    from mcp_server import audit
    from conftest import SharedConnection

    monkeypatch.setattr(audit, "get_conn", lambda: SharedConnection(audit_conn))
    monkeypatch.setattr(community_mcp.settings, "community_mcp_enabled", True)
    monkeypatch.setattr(community_mcp, "_call_sync", lambda tool, arguments: {"content": []})

    describe_schema("run-schema")

    rows = audit_conn.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
    assert [r["tool"] for r in rows] == ["community_schema"]
