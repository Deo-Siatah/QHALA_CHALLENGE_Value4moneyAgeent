from pathlib import Path


def _columns(conn):
    rows = conn.execute(
        "SELECT attname FROM pg_attribute "
        "WHERE attrelid = 'reports'::regclass AND attnum > 0 AND NOT attisdropped "
        "ORDER BY attname").fetchall()
    return {row["attname"] for row in rows}


def test_report_columns_migration_is_idempotent(reports_conn):
    sql = Path("sql/03_report_columns.sql").read_text(encoding="utf-8")

    reports_conn.execute(sql)
    reports_conn.commit()
    reports_conn.execute(sql)
    reports_conn.commit()

    assert {"fingerprint", "review_json"} <= _columns(reports_conn)
