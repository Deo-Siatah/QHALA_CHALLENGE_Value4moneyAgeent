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
            "approved_by TEXT)"
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