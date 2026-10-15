# Write one row per tool call to audit_log: the inputs before, the output after.
# It never imports mcp, so agent/mcp_client.py can wrap direct tool calls the same way.
# The row is inserted before the tool runs, so a crash mid-call still leaves a trace.
# A failed audit write raises AuditError and blocks the tool: nothing runs unlogged.

import functools
import inspect
from contextlib import contextmanager
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import PurePath
from typing import Any, Callable, Dict, Optional
from psycopg.types.json import Jsonb
from .db import get_conn


class AuditError(RuntimeError):
    """Raised when a call could not be logged; the tool must not run."""


def _jsonable(value: Any) -> Any:
    """Turn a tool's value into something psycopg can store as JSONB."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, PurePath):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(v) for v in value]
    return str(value)


def _check_run_id(run_id: Any) -> str:
    """Refuse a missing run_id: audit_log.run_id is NOT NULL and is the trace key."""
    if not isinstance(run_id, str) or not run_id.strip():
        raise AuditError(f"run_id must be a non-empty string, got {run_id!r}")
    return run_id


@contextmanager
def _audit_conn():
    """Give one short-lived connection for one audit statement, wrapped as AuditError."""
    try:
        conn = get_conn()
    except Exception as exc:
        raise AuditError(f"audit_log write failed: {exc}") from exc
    try:
        yield conn
        conn.commit()
    except Exception as exc:
        conn.rollback()
        raise AuditError(f"audit_log write failed: {exc}") from exc
    finally:
        conn.close()


def log_call(run_id: str, tool: str, inputs: Dict[str, Any], output: Optional[Any] = None,
             actor: str = "agent", approved_by: Optional[str] = None) -> int:
    """Insert one audit_log row and return its id."""
    _check_run_id(run_id)
    with _audit_conn() as conn:
        row = conn.execute(
            "INSERT INTO audit_log (run_id, actor, tool, input, output, approved_by) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (run_id, actor, tool, Jsonb(_jsonable(inputs)),
             None if output is None else Jsonb(_jsonable(output)), approved_by),
        ).fetchone()
    return row["id"]


def finish_call(row_id: int, output: Any) -> None:
    """Store the result of a call in the row inserted before it ran."""
    with _audit_conn() as conn:
        conn.execute("UPDATE audit_log SET output = %s WHERE id = %s", (Jsonb(_jsonable(output)), row_id))


def audited(tool: str, actor: str = "agent") -> Callable:
    """Wrap a tool function so every call is written to audit_log under its run_id."""
    def decorate(fn: Callable) -> Callable:
        signature = inspect.signature(fn)

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            bound = signature.bind(*args, **kwargs)
            run_id = _check_run_id(bound.arguments.pop("run_id", None))
            approved_by = bound.arguments.get("approved_by")
            row_id = log_call(run_id, tool, bound.arguments, None, actor, approved_by)
            try:
                output = fn(*args, **kwargs)
            except Exception as exc:
                finish_call(row_id, {"error": f"{type(exc).__name__}: {exc}"})
                raise
            finish_call(row_id, output)
            return output

        wrapper.__signature__ = signature
        return wrapper

    return decorate
