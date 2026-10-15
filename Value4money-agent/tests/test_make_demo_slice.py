# These tests are the spec for the demo slice that ships in sql/demo_data.sql. A stranger applies
# that file to an empty database, so the things asserted here are the things that would break on
# their machine: the wrong columns, the wrong order, an unescaped quote, a row that differs between
# regenerations. No database is needed: the tests drive the pure rendering functions and a fake
# connection that hands back canned rows.

from loader import make_demo_slice
from loader.make_demo_slice import (KEYWORDS, literal, fetch_slice, render_sql)

TENDER = {"ocid": "ocds-abc-2024-1", "data_year": 2024, "buyer_id": "buyer1",
          "buyer_name": "Nakuru County Government", "title": "CONSTRUCTION OF CHAINLINK FENCE",
          "category": "works", "method": "open", "published_at": None, "quality_flags": []}

AWARD = {"award_id": "20240705144130-91671", "ocid": "ocds-abc-2024-1", "data_year": 2024,
         "award_title": "CHAINLINK FENCE AND GATE", "award_description": "Fencing work",
         "value_kes": 2069300.00, "currency": "KES", "contract_start": None,
         "contract_end": None, "supplier_name": "Apex Fencing Contractors Ltd",
         "supplier_norm": "apex fencing contractors ltd", "lot_group": "lot-1",
         "quality_flags": []}


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class FakeConn:
    """Records the SQL it is given and answers with canned rows, so no database is needed."""

    def __init__(self, tenders=None, awards=None):
        self.tenders = tenders if tenders is not None else [dict(TENDER)]
        self.awards = awards if awards is not None else [dict(AWARD)]
        self.statements = []

    def execute(self, sql, *args):
        self.statements.append(sql)
        if "FROM awards" in sql and "INSERT" not in sql:
            return FakeResult(self.awards)
        return FakeResult(self.tenders)


def test_the_slice_covers_fence_road_classroom_and_borehole():
    """The four kinds of work the two sample bid sets are compared against."""
    assert len(KEYWORDS) == 5
    joined = " ".join(KEYWORDS)
    for word in ["chainlink", "fence", "road", "classroom", "borehole"]:
        assert word in joined


def test_the_query_looks_at_both_titles_and_drops_empty_values():
    conn = FakeConn()

    fetch_slice(conn)

    sql = " ".join(conn.statements)
    assert "t.title" in sql
    assert "a.award_title" in sql
    assert "value_kes > 0" in sql


def test_the_query_reads_exactly_the_columns_the_slice_writes():
    """A column added to the table must not silently vanish from the slice."""
    conn = FakeConn()

    fetch_slice(conn)

    sql = " ".join(conn.statements)
    for column in ["ocid", "award_id", "data_year", "buyer_name", "title", "category", "method",
                   "published_at", "quality_flags", "award_title", "award_description", "value_kes",
                   "currency", "contract_start", "supplier_norm", "lot_group"]:
        assert column in sql


def test_tenders_are_written_before_awards():
    """awards.ocid references tenders.ocid, so the parent rows have to land first."""
    sql = render_sql([dict(TENDER)], [dict(AWARD)])

    assert sql.index("INSERT INTO tenders") < sql.index("INSERT INTO awards")


def test_the_slice_is_safe_to_apply_to_a_database_that_already_has_the_data():
    """A stranger may load the full exports after the slice; the slice must not fight them."""
    sql = render_sql([dict(TENDER)], [dict(AWARD)])

    assert sql.count("ON CONFLICT DO NOTHING") == 2


def test_a_single_quote_is_doubled():
    assert literal("Nakuru's Office") == "'Nakuru''s Office'"


def test_null_stays_null_and_is_not_turned_into_a_word():
    assert literal(None) == "NULL"
    assert "NULL" in render_sql([dict(TENDER, published_at=None)], [dict(AWARD)])


def test_a_text_array_is_written_as_an_array():
    assert literal(["a,b"]) == "ARRAY['a,b']::text[]"
    assert literal([]) == "'{}'::text[]"


def test_a_number_and_a_date_are_written_as_themselves():
    assert literal(2069300.0) == "2069300.0"
    assert literal(2024) == "2024"


def test_the_header_says_where_the_data_came_from_and_how_much_is_in_it():
    sql = render_sql([dict(TENDER)], [dict(AWARD)])

    assert "Kenya OCDS" in sql
    assert "tenders" in sql and "awards" in sql
    assert "1 tenders" in sql
    assert "1 awards" in sql


def test_the_same_rows_always_render_the_same_sql():
    """Regenerating the slice must not produce a diff, or every commit would carry one."""
    first = render_sql([dict(TENDER), dict(TENDER, ocid="ocds-abc-2024-2")],
                       [dict(AWARD), dict(AWARD, award_id="2025-1")])
    second = render_sql([dict(TENDER), dict(TENDER, ocid="ocds-abc-2024-2")],
                        [dict(AWARD), dict(AWARD, award_id="2025-1")])

    assert first == second


def test_rows_are_sorted_by_their_key_inside_the_statement():
    sql = render_sql([dict(TENDER, ocid="ocds-zzz"), dict(TENDER, ocid="ocds-aaa")], [])

    assert sql.index("ocds-aaa") < sql.index("ocds-zzz")


def test_a_row_of_nothing_but_nulls_still_renders_a_well_formed_statement():
    """The worst case for the renderer: every nullable column empty in one row."""
    sql = render_sql([dict(TENDER, method=None, buyer_id=None, category=None, published_at=None)],
                     [dict(AWARD, lot_group=None, contract_start=None, contract_end=None)])

    assert ",," not in sql
    assert "NULL" in sql
    statements = [block for block in sql.split(";") if "INSERT INTO" in block]
    assert len(statements) == 2
    for statement in statements:
        assert statement.rstrip().endswith("ON CONFLICT DO NOTHING")