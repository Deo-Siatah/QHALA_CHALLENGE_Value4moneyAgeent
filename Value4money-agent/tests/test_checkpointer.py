import uuid
from urllib.parse import quote

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command

from agent import checkpointer, graph
from agent.checkpointer import checkpointer as open_checkpointer
from agent.graph import build_graph
from config import settings

CHECKPOINT_TABLES = ["checkpoint_migrations", "checkpoints", "checkpoint_blobs", "checkpoint_writes"]


@pytest.fixture
def schema():
    """A temporary schema name, dropped when the test ends. Nothing here ever touches public."""
    if not settings.database_url:
        pytest.skip("DATABASE_URL not set")

    import psycopg

    name = f"test_{uuid.uuid4().hex[:12]}"
    conn = psycopg.connect(settings.database_url, autocommit=True)
    try:
        conn.execute(f'CREATE SCHEMA "{name}"')
        yield name
    finally:
        conn.execute(f'DROP SCHEMA "{name}" CASCADE')
        conn.close()


def connect_to(name, autocommit=False):
    """A connection whose search_path is the temporary schema, with no transaction left open."""
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(url_for(name), row_factory=dict_row, autocommit=autocommit)


def pool_for(name):
    """A small committed pool on the temporary schema, the shape the saver needs."""
    from psycopg_pool import ConnectionPool

    return ConnectionPool(url_for(name), min_size=1, max_size=2, open=True)


def url_for(name):
    """The same connection string, pointed at the temporary schema."""
    return f"{settings.database_url}&options={quote(f'-c search_path={name}')}"


def _faked(monkeypatch):
    """Fake every node except approval, so the run stops at the human decision."""
    monkeypatch.setattr(graph, "intake_node", lambda s: {"bids": [{"bidder": "Apex"}]})
    monkeypatch.setattr(graph, "research_node",
                        lambda s: {"search_attempts": 1, "search": {"match": "strict"}})
    monkeypatch.setattr(graph, "quality_check_node", lambda s: {"pool_size": 12})
    monkeypatch.setattr(graph, "score_node",
                        lambda s: {"benchmark": {"n": 12, "confidence": "medium", "bids": []}})
    monkeypatch.setattr(graph, "draft_node",
                        lambda s: {"review_markdown": "# report\n\nbody\n",
                                   "verify_rounds": s.get("verify_rounds", 0) + 1,
                                   "summary": "Twelve awards were compared."})
    monkeypatch.setattr(graph, "verify_sources_node", lambda s: {"verify_ok": True})
    monkeypatch.setattr(graph, "file_node", lambda s: {"submission": {"report_id": 7}})


def test_setting_the_tables_up_twice_is_harmless(schema):
    conn = connect_to(schema, autocommit=True)
    try:
        PostgresSaver(conn).setup()
        PostgresSaver(conn).setup()

        names = {row["tablename"] for row in conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = current_schema()").fetchall()}
    finally:
        conn.close()

    for table in CHECKPOINT_TABLES:
        assert table in names


def test_a_paused_run_resumes_from_postgres_in_a_new_connection(schema, monkeypatch):
    _faked(monkeypatch)
    config = {"configurable": {"thread_id": "run-persist"}}
    checkpointer.init_checkpoints(url_for(schema))

    first_pool = pool_for(schema)
    try:
        paused = build_graph(PostgresSaver(first_pool)).invoke(
            {"run_id": "run-persist", "review_markdown": "# report\n"}, config)
    finally:
        first_pool.close()

    assert "__interrupt__" in paused
    assert "submission" not in paused

    second_pool = pool_for(schema)
    try:
        result = build_graph(PostgresSaver(second_pool)).invoke(
            Command(resume={"decision": "approved", "approved_by": "Grace Wanjiku", "note": "seen"}),
            config)
    finally:
        second_pool.close()

    assert result["approval_status"] == "approved"
    assert result["approved_by"] == "Grace Wanjiku"
    assert result["approval_note"] == "seen"
    assert result["submission"] == {"report_id": 7}


def test_the_context_manager_sets_up_and_closes_its_pool(schema):
    with open_checkpointer(url_for(schema)) as saver:
        pool = saver.conn
        assert pool.closed is False

    assert pool.closed is True

    conn = connect_to(schema)
    try:
        tables = {row["tablename"] for row in conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = current_schema()").fetchall()}
    finally:
        conn.close()

    for table in CHECKPOINT_TABLES:
        assert table in tables


def test_a_test_run_never_creates_tables_in_public(schema, monkeypatch):
    import psycopg
    from psycopg.rows import dict_row

    def public_tables():
        conn = psycopg.connect(settings.database_url, row_factory=dict_row)
        try:
            return {row["tablename"] for row in conn.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
                "AND tablename LIKE 'checkpoint%'").fetchall()}
        finally:
            conn.close()

    _faked(monkeypatch)
    before = public_tables()

    with open_checkpointer(url_for(schema)) as saver:
        build_graph(saver).invoke({"run_id": "run-schema", "review_markdown": "# report\n"},
                                  {"configurable": {"thread_id": "run-schema"}})

    # A real run creates these in public on purpose. A test must leave them exactly as it found them.
    assert public_tables() == before


def test_one_thread_can_be_deleted_without_touching_another(schema, monkeypatch):
    _faked(monkeypatch)
    checkpointer.init_checkpoints(url_for(schema))

    pool = pool_for(schema)
    try:
        saver = PostgresSaver(pool)
        run = build_graph(saver)
        run.invoke({"run_id": "a", "review_markdown": "# a\n"}, {"configurable": {"thread_id": "a"}})
        run.invoke({"run_id": "b", "review_markdown": "# b\n"}, {"configurable": {"thread_id": "b"}})

        saver.delete_thread("a")

        assert saver.get_tuple({"configurable": {"thread_id": "a"}}) is None
        assert saver.get_tuple({"configurable": {"thread_id": "b"}}) is not None
    finally:
        pool.close()


def test_a_missing_database_url_is_refused_clearly(monkeypatch):
    monkeypatch.setattr(checkpointer.settings, "database_url", "")

    with pytest.raises(ValueError) as err:
        with open_checkpointer():
            pass

    assert "DATABASE_URL" in str(err.value)


def test_the_in_memory_saver_still_pauses_without_a_database(monkeypatch):
    _faked(monkeypatch)
    config = {"configurable": {"thread_id": "run-memory"}}

    paused = build_graph(InMemorySaver()).invoke(
        {"run_id": "run-memory", "review_markdown": "# report\n"}, config)

    assert "__interrupt__" in paused