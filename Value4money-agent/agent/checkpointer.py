# Give the run a memory that outlives the process, so an approval can pause now and resume later.
#
# . LangGraph writes the whole run state to Postgres
# every time the graph pauses, and reads it back when the run is resumed, so the approval interrupt
# in agent/nodes/approval.py survives the process ending:
#
# The tables are LangGraph's own, created on first use by an idempotent setup, and they never touch
# the tender tables. The sync saver is the right one here because every tool and every node in this
# project is synchronous; the async saver is never imported.
#
# Usage:
#     with checkpointer() as saver:
#         graph = build_graph(saver)
#         graph.invoke(state, {"configurable": {"thread_id": run_id}})
#         ... later, in any process ...
#         graph.invoke(Command(resume=decision), {"configurable": {"thread_id": run_id}})

# The migrations build indexes concurrently, which Postgres will not run inside a transaction, so
# setup gets its own autocommit connection. The saver itself is given a small pool rather than one
# bare connection: handed a single connection, psycopg keeps every checkpoint write in an uncommitted
# pipeline, and closing that connection throws the run's state away. The pool commits each write,
# which is what makes a pause survive the process.

from contextlib import contextmanager
from typing import Iterator, Optional

import psycopg
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver

from config import settings

POOL_SIZE = 2


def init_checkpoints(url: str) -> None:
    """Create LangGraph's checkpoint tables if they are missing. Safe to run every time."""
    conn = psycopg.connect(url, autocommit=True)
    try:
        PostgresSaver(conn).setup()
    finally:
        conn.close()


@contextmanager
def checkpointer(conn_string: Optional[str] = None) -> Iterator[PostgresSaver]:
    """Yield a PostgresSaver backed by a small pool, setting its tables up and closing it after."""
    url = conn_string if conn_string is not None else settings.database_url
    if not url:
        raise ValueError("DATABASE_URL is not set: a run needs a checkpointer to remember where it paused")

    init_checkpoints(url)
    pool = ConnectionPool(url, min_size=1, max_size=POOL_SIZE, open=True)
    try:
        yield PostgresSaver(pool)
    finally:
        pool.close()