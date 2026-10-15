# Talk to a community MCP server: Postgres MCP Pro, read-only, used only as the research fallback.
#
# Our own search tool takes fixed parameters. When it has been tried twice and the pool is still
# thin, this asks a server we did not write for the schema it actually has, and lets the model write
# one read-only query against that schema. The point is not to replace our search: it is to recover
# from the case our fixed tool cannot express.
#
# The model writes the SQL, so it is guarded three times over:
#   1. the server runs in restricted mode: read-only transactions, SQL parsed and checked, 30s cap
#   2. our own check: one statement, must start with SELECT or WITH, no write word anywhere in it
#   3. our own check: only tenders, awards and award_labels may be named, so the model cannot read
#      audit_log or reports, which are this project's own records
# And the connection is a Postgres role that holds SELECT on those three tables and nothing else,
# so even a bypass of all three checks would find nothing to read and no way to write.
#
# Every call is audited under the run's run_id, exactly like our own tools, so the audit trail shows
# a community call as plainly as a first-hand one. Every failure is quiet: this is a fallback, and a
# fallback that raises would take the run down with it.

import ast
import asyncio
import json
import os
import re
import threading
from typing import Any, Dict, List

from config import settings
from mcp_server.audit import audited
from agent.tracing import traced

FORBIDDEN = ("insert", "update", "delete", "drop", "truncate", "alter", "create", "grant", "revoke",
              "copy", "comment", "vacuum", "analyze", "refresh", "commit", "rollback", "set",
              "reset", "listen", "notify", "call", "do", "execute")

READABLE_TABLES = ("tenders", "awards", "award_labels")

_session: Dict[str, Any] = {}
_loop: Any = None
_thread: Any = None


class CommunityQueryRefused(ValueError):
    """Raised when a query is not a plain read of the evidence tables. Nothing is sent."""


class CommunityServerError(RuntimeError):
    """Raised when the community server itself refuses or fails a call. Nothing is written."""


def _sql(sql: str) -> str:
    """Strip SQL comments, so a write cannot hide behind one."""
    return re.sub(r"--[^\n]*", " ", re.sub(r"/\*.*?\*/", " ", sql, flags=re.S))


def validate_sql(sql: str) -> str:
    """Refuse anything that is not one plain read of the evidence tables, and return it cleaned."""
    cleaned = _sql(sql or "").strip()
    if not cleaned:
        raise CommunityQueryRefused("the query is empty")
    if not re.match(r"^\(?\s*(select|with)\b", cleaned, flags=re.I):
        raise CommunityQueryRefused(f"only a SELECT or WITH query is allowed, got: {cleaned[:60]!r}")
    lowered = cleaned.lower()
    for word in FORBIDDEN:
        if re.search(rf"\b{word}\b", lowered):
            raise CommunityQueryRefused(f"the query contains the refused word '{word}'")
    for table in ("reports", "audit_log", "checkpoint", "load_log"):
        if re.search(rf"\b{table}", lowered):
            raise CommunityQueryRefused(f"only {', '.join(READABLE_TABLES)} may be read, not {table}")
    if cleaned.count(";"):
        raise CommunityQueryRefused("only one statement is allowed, and none may be chained")
    return cleaned

def normalize_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Turn the server's rows into the candidate shape our own search returns."""
    candidates = []
    for row in rows:
        if not row.get("award_id"):
            continue
        row = dict(row)
        if row.get("value_kes") is not None:
            row["value_kes"] = float(row["value_kes"])
        candidates.append(row)
    return candidates


def _content(result: Any) -> List[Dict[str, Any]]:
    """Read the content blocks from an MCP result, whether it arrives as a model or a dict."""
    blocks = getattr(result, "content", None)
    if blocks is None and isinstance(result, dict):
        blocks = result.get("content")
    return blocks or []


def _text(result: Any) -> str:
    """Read the JSON payload out of an MCP tool result, from a model block or a plain dict."""
    parts = []
    for part in _content(result):
        value = getattr(part, "text", None)
        if value is None and isinstance(part, dict):
            value = part.get("text")
        if isinstance(value, str):
            parts.append(value)
    return "".join(parts)


def _rows(result: Any) -> List[Dict[str, Any]]:
    """Parse a tool result into rows, tolerating a bare array or a wrapped one."""
    if getattr(result, "isError", False) or (isinstance(result, dict) and result.get("isError")):
        raise CommunityServerError(f"the community server refused the call: {_text(result)[:200]}")

    text = _text(result)
    if not text:
        structured = getattr(result, "structuredContent", None) or (
            result.get("structuredContent") if isinstance(result, dict) else None)
        if isinstance(structured, dict):
            for key in ("rows", "data", "results"):
                if isinstance(structured.get(key), list):
                    return structured[key]
            return [structured]
        return []
    # The server returns a Python literal, single quotes and all, and it prints Postgres NUMERIC as
    # Decimal('...'), which is a call and not a literal. Both are rewritten before parsing, so the
    # only thing being evaluated here is data: literal_eval never executes anything.
    text = re.sub(r"Decimal\((['\"])([^'\"]*)\1\)", r"\2", text)
    for parse in (json.loads, ast.literal_eval):
        try:
            parsed = parse(text)
            break
        except (json.JSONDecodeError, ValueError, SyntaxError):
            parsed = None
    if parsed is None:
        return []
    if isinstance(parsed, dict):
        for key in ("rows", "data", "results"):
            if isinstance(parsed.get(key), list):
                return parsed[key]
        return [parsed]
    return parsed if isinstance(parsed, list) else []


def enabled() -> bool:
    """Whether the community server can be used at all."""
    return bool(settings.community_mcp_enabled and settings.community_mcp_database_url)


def _ensure_loop() -> asyncio.AbstractEventLoop:
    """One background event loop for the whole run, because an MCP session lives inside a loop.

    Opening a loop per call would be simpler and would also break: a session started in one loop
    cannot be used from another, and the server subprocess dies with the loop that spawned it.
    """
    global _loop, _thread
    if _loop is None:
        _loop = asyncio.new_event_loop()
        _thread = threading.Thread(target=_loop.run_forever, daemon=True, name="community-mcp")
        _thread.start()
    return _loop


async def _open() -> Any:
    """Start the community server once and return its session."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=settings.community_mcp_command,
        # Postgres MCP Pro has not moved to MCP 2 yet, where FastMCP became MCPServer, so its
        # subprocess is pinned to the 1.x line while the rest of this project stays on 2.x.
        args=settings.community_mcp_args.split() + [f"--access-mode={settings.community_mcp_access_mode}"],
        env={**os.environ, "DATABASE_URI": settings.community_mcp_database_url},
    )
    stdio = stdio_client(params)
    read, write = await stdio.__aenter__()
    client = ClientSession(read, write)
    await client.__aenter__()
    await client.initialize()
    _session.update({"stdio": stdio, "client": client})
    return client


async def _call(tool: str, arguments: Dict[str, Any]) -> Any:
    """Call one tool on the community server, opening the session if this is the first call."""
    client = _session.get("client") or await _open()
    return await client.call_tool(tool, arguments)


def _call_sync(tool: str, arguments: Dict[str, Any]) -> Any:
    """Call the server from our synchronous nodes. The one seam a test replaces."""
    loop = _ensure_loop()
    return asyncio.run_coroutine_threadsafe(_call(tool, arguments), loop).result()


async def _aclose() -> None:
    """Close the session inside the loop that opened it."""
    client = _session.pop("client", None)
    stdio = _session.pop("stdio", None)
    if client is not None:
        await client.__aexit__(None, None, None)
    if stdio is not None:
        await stdio.__aexit__(None, None, None)


def close() -> None:
    """Shut the community server and its loop down when the run ends."""
    global _loop, _thread
    if _loop is None:
        return
    if _session:
        try:
            asyncio.run_coroutine_threadsafe(_aclose(), _loop).result(timeout=10)
        except Exception:
            pass
    _loop.call_soon_threadsafe(_loop.stop)
    if _thread is not None:
        _thread.join(timeout=10)
    _loop, _thread = None, None


@traced("tool")
@audited("community_schema")
def describe_schema(run_id: str) -> List[Dict[str, Any]]:
    """Ask the community server what tables and columns exist, so the model writes real SQL."""
    if not enabled():
        return []
    try:
        result = _call_sync("list_objects", {"schema_name": "public"})
        return _rows(result)
    except Exception as exc:
        return _record_failure(run_id, f"community schema lookup failed: {exc}")


@traced("tool")
@audited("community_query")
def run_query(run_id: str, sql: str) -> List[Dict[str, Any]]:
    """Run one guarded read-only query on the community server and return candidate rows."""
    if not enabled():
        return []
    try:
        cleaned = validate_sql(sql)
    except CommunityQueryRefused as exc:
        return _record_failure(run_id, f"community query refused: {exc}")

    try:
        result = _call_sync("execute_sql", {"sql": cleaned})
        return normalize_rows(_rows(result))[:settings.community_mcp_max_rows]
    except Exception as exc:
        return _record_failure(run_id, f"community query failed: {exc}")


def fallback_candidates(run_id: str, sql: str) -> List[Dict[str, Any]]:
    """The rows one fallback query found, already trimmed and normalised."""
    return run_query(run_id, sql)


def _record_failure(run_id: str, message: str) -> List[Dict[str, Any]]:
    """Note a failure in audit_log and carry on with nothing. A fallback never stops a run."""
    from mcp_server import audit

    audit.log_call(run_id=run_id, tool="community_error", inputs={}, output={"error": message})
    return []
