import pytest
from pathlib import Path
from fpdf import FPDF


def make_pdf(directory: Path, name: str, lines: list[str]) -> Path:
    """Create a PDF with given lines using fpdf2."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    
    for line in lines:
        pdf.cell(0, 10, txt=line, ln=True)
    
    pdf_path = directory / name
    pdf.output(str(pdf_path))
    return pdf_path


@pytest.fixture(scope="session")
def db_conn():
    """Database connection fixture for tests. Skipped if DATABASE_URL is unset."""
    from config import settings
    if not settings.database_url:
        pytest.skip("DATABASE_URL not set")

    from psycopg import connect
    from psycopg.rows import dict_row
    
    # Connect using the direct URL (non-pooled)
    conn = connect(settings.database_url, row_factory=dict_row)
    
    try:
        # Create temp tables that shadow the real ones
        conn.execute("CREATE TEMP TABLE tenders (LIKE public.tenders INCLUDING DEFAULTS)")
        conn.execute("CREATE TEMP TABLE awards (LIKE public.awards INCLUDING DEFAULTS)")
        
        # Insert test data
        test_data = [
            # Valid awards
            ("t1", "award1", "tender1", "Classroom construction", "works", "buyer1", "2024", 1000000, "KES", "Supplier A", None, "lot1", []),
            ("t2", "award2", "tender2", "Road maintenance", "works", "buyer2", "2024", 2000000, "KES", "Supplier B", None, "lot1", []),
            ("t3", "award3", "tender3", "Classroom supplies", "goods", "buyer1", "2023", 500000, "KES", "Supplier C", None, "lot1", []),
            ("t4", "award4", "tender4", "Classroom renovation", "works", "buyer3", "2025", 1500000, "KES", "Supplier D", None, "lot1", []),
            ("t5", "award5", "tender5", "Classroom furniture", "goods", "buyer4", "2024", 750000, "KES", "Supplier E", None, "lot1", []),
            # Edge cases
            ("t6", "award6", "tender6", "Construction project", "works", "buyer5", "2024", 0, "KES", "Supplier F", None, "lot1", []),  # Zero value
            ("t7", "award7", "tender7", "USD project", "works", "buyer6", "2024", 3000000, "USD", "Supplier G", None, "lot1", []),  # Non-KES
            ("t8", "award8", "tender8", "Classroom repair", "works", "buyer1", "2024", 1200000, "KES", "Supplier H", None, "lot1", ["no_supplier"]),
            ("t9", "award9", "tender9", "Clasroom construction", "works", "buyer7", "2024", 1800000, "KES", "Supplier I", None, "lot1", []),  # Misspelled
        ]
        
        for tender_id, award_id, ocid, title, category, buyer_id, year, value, currency, supplier, supplier_norm, lot_group, flags in test_data:
            conn.execute(
                "INSERT INTO tenders (ocid, title, category, buyer_id, data_year) VALUES (%s, %s, %s, %s, %s)",
                (ocid, title, category, buyer_id, int(year))
            )
            conn.execute(
                "INSERT INTO awards (award_id, ocid, data_year, value_kes, currency, supplier_name, supplier_norm, lot_group, quality_flags) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (award_id, ocid, int(year), value, currency, supplier, supplier_norm, lot_group, flags)
            )
        
        conn.commit()
        yield conn
        
    finally:
        conn.close()


@pytest.fixture(scope="module")
def _reports_session():
    """One connection per test module holding a temporary reports table."""
    from config import settings
    if not settings.database_url:
        pytest.skip("DATABASE_URL not set")

    from psycopg import connect
    from psycopg.rows import dict_row

    conn = connect(settings.database_url, row_factory=dict_row)
    try:
        # Created explicitly, not LIKE public.reports, which would reuse the real sequence
        conn.execute(
            "CREATE TEMP TABLE reports ("
            "id BIGSERIAL PRIMARY KEY, "
            "run_id TEXT NOT NULL, "
            "created_at TIMESTAMPTZ NOT NULL DEFAULT now(), "
            "body_md TEXT NOT NULL, "
            "approved_by TEXT, "
            "fingerprint TEXT, "
            "review_json JSONB)"
        )
        conn.commit()
        yield conn
    finally:
        conn.close()


@pytest.fixture
def reports_conn(_reports_session):
    """An empty temporary reports table on the module's connection."""
    _reports_session.execute("TRUNCATE reports RESTART IDENTITY")
    _reports_session.commit()
    return _reports_session


class SharedConnection:
    """Stands in for db.get_conn() in tests: same session, so temp tables stay visible, never closed."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, *args, **kwargs):
        return self._conn.execute(*args, **kwargs)

    def cursor(self, *args, **kwargs):
        return self._conn.cursor(*args, **kwargs)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        pass


@pytest.fixture(scope="module")
def _audit_session():
    """One connection per test module holding a temporary audit_log table."""
    from config import settings
    if not settings.database_url:
        pytest.skip("DATABASE_URL not set")

    from psycopg import connect
    from psycopg.rows import dict_row

    conn = connect(settings.database_url, row_factory=dict_row)
    try:
        # Created explicitly, not LIKE public.audit_log, which would reuse the real sequence
        conn.execute(
            "CREATE TEMP TABLE audit_log ("
            "id BIGSERIAL PRIMARY KEY, "
            "run_id TEXT NOT NULL, "
            "ts TIMESTAMPTZ NOT NULL DEFAULT now(), "
            "actor TEXT NOT NULL, "
            "tool TEXT NOT NULL, "
            "input JSONB, "
            "output JSONB, "
            "approved_by TEXT)"
        )
        conn.commit()
        yield conn
    finally:
        conn.close()


@pytest.fixture
def audit_conn(_audit_session):
    """An empty temporary audit_log table on the module's connection."""
    _audit_session.execute("TRUNCATE audit_log RESTART IDENTITY")
    _audit_session.commit()
    return _audit_session


@pytest.fixture
def report_state():
    """A complete run state with a readable pool, three comparable bids and one unreadable bid."""
    def award(award_id, value):
        return {"award_id": award_id, "ocid": f"ocid-{award_id}", "data_year": 2024,
                "title": "Classroom block construction", "buyer_name": "Ministry of Education",
                "value_kes": value}

    return {
        "run_id": "run-1",
        "tender_ref": "TENDER/NC/2026/014",
        "started_at": "2026-10-19T11:09:22+00:00",
        "description": "construction of classroom blocks",
        "tender_fields": {
            "title": {"value": "Construction of classroom blocks"},
            "buyer": {"value": "Ministry of Education"},
            "county": {"value": "Nairobi"},
        },
        "bids": [
            {"bidder": "Apex", "file": "apex.pdf", "total_page": 2,
             "stated_total": 3_150_000.0, "computed_total": 3_150_000.0,
             "arithmetic_ok": True, "status": "ok", "confidence": "high",
             "issues": [], "flagged_pages": [], "unresolved_pages": []},
            {"bidder": "Zed", "file": "zed.pdf", "total_page": 1,
             "stated_total": 2_750_000.0, "computed_total": 2_690_000.0,
             "arithmetic_ok": False, "status": "ok", "confidence": "high",
             "issues": ["Stated total 2750000.00 does not match computed total 2690000.00"],
             "flagged_pages": [], "unresolved_pages": []},
            {"bidder": "Bora", "file": "bora.pdf", "total_page": 3,
             "stated_total": 8_650_000.0, "computed_total": 8_650_000.0,
             "arithmetic_ok": True, "status": "ok", "confidence": "high",
             "issues": [], "flagged_pages": [], "unresolved_pages": []},
            {"bidder": "Broken", "file": "broken.pdf", "total_page": None,
             "stated_total": None, "computed_total": None,
             "arithmetic_ok": False, "status": "needs_review", "confidence": "low",
             "issues": [], "flagged_pages": [{"page": 2, "kind": "scan"}],
             "unresolved_pages": [{"page": 2, "text": ""}]},
        ],
        "benchmark": {
            "n": 11, "confidence": "high", "median_kes": 2_839_845.72,
            "q1_kes": 1_956_829.0, "q3_kes": 3_494_974.74,
            "bids": [
                {"bidder": "Apex", "total": 3_150_000.0, "pct_vs_median": 10.9,
                 "position": "within_range"},
                {"bidder": "Zed", "total": 2_750_000.0, "pct_vs_median": -3.2,
                 "position": "within_range"},
                {"bidder": "Bora", "total": 8_650_000.0, "pct_vs_median": 204.6,
                 "position": "far_above"},
            ],
        },
        "pool": [award("a01", 2_501_490.0), award("a03", 2_839_845.72),
                 award("a02", 3_289_999.48)],
        "excluded": {"different_work": 4, "scale_mismatch": 1},
        "excluded_awards": [
            {"award_id": "a09", "title": "Pit latrine works",
             "value_kes": 1_000_000.0, "reason_code": "different_work"}],
        "summary_note": "SENTINEL_NOTE",
        "report_degraded": False,
        "findings": [],
        "sources": [],
    }


@pytest.fixture
def report_review(report_state):
    """The Phase 2 review shape the report model is built from."""
    return {
        "run_id": report_state["run_id"],
        "tender_ref": report_state["tender_ref"],
        "summary_note": report_state["summary_note"],
        "benchmark": report_state["benchmark"],
        "findings": report_state["findings"],
        "sources": report_state["sources"],
        "report_degraded": report_state["report_degraded"],
    }


@pytest.fixture
def report_model(report_review, report_state):
    from mcp_server.tools.report_model import build_report_model
    return build_report_model(report_review, report_state)