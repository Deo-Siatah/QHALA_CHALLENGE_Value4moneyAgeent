# The SQL files are part of the product: a stranger applies them to an empty database. These tests
# read them as text and assert the things that would otherwise only fail on someone else's machine.

from pathlib import Path

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"

SCHEMA = SQL_DIR / "01_schema.sql"
INDEXES = SQL_DIR / "02_indexes.sql"


def read(path: Path) -> str:
    """The SQL file as text."""
    return path.read_text(encoding="utf-8")


def test_the_schema_creates_the_extension_the_indexes_need():
    """gin_trgm_ops does not exist until pg_trgm is on, and a fresh database has neither."""
    assert "CREATE EXTENSION IF NOT EXISTS pg_trgm" in read(SCHEMA)


def test_the_extension_is_created_before_the_indexes_that_use_it():
    schema = read(SCHEMA)
    indexes = read(INDEXES)

    assert "gin_trgm_ops" in indexes
    assert schema.index("pg_trgm") < schema.index("CREATE TABLE")


def test_every_table_the_agent_reads_is_created():
    schema = read(SCHEMA)

    for table in ["tenders", "awards", "award_labels", "audit_log", "reports"]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in schema


def test_every_index_is_created_only_if_absent():
    """Setup runs on a database that may already have them."""
    for line in read(INDEXES).splitlines():
        if line.strip().startswith("CREATE INDEX"):
            assert "IF NOT EXISTS" in line


def test_the_awards_table_keeps_the_foreign_key_to_its_tender():
    """The demo slice loads tenders before awards, and the database still enforces it."""
    assert "REFERENCES tenders(ocid)" in read(SCHEMA)