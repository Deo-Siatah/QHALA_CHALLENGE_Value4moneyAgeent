# ARCHITECTURE.md

Why the agent is shaped this way. The README covers what it does and how to run it; this covers the
decisions behind it.

## 1. Agent shape

One workflow, not a swarm. A single LangGraph `StateGraph` with eight node-level agents:

```
intake → research → quality_check → score → draft → verify_sources → approval → file
```

An explicit workflow over agents that message each other, because every step here carries an audit
obligation: a committee can ask which tool produced a number, and the only reliable answer is a path
through the graph.

**Autonomy lives in three places, and nowhere else.**

- **Self-directed search.** `research` asks the model for its next search move;
  `route_after_quality_check` loops back while the pool is thin, capped at 3 attempts. Each attempt
  changes strategy — broader matching, a later year, a rephrased query.
- **Self-correction.** `verify_sources` checks every finding cites a record that exists; if a citation
  fails, the run returns to `draft`, capped at 2 rounds.
- **A human gate.** `approval` interrupts. A Postgres checkpoint means a person can answer an hour
  later, or a week later from another process, on the same `thread_id`.

**Code does the arithmetic, the model does the language, a named human decides.** Four model call
sites: profile the tender, choose the next search, judge same-work, write the wording. Median,
quartiles and percentages come from `benchmark_price` in Python, so the numbers do not depend on a
model having a good day.

**Abstention is a feature.** Too few comparables and `benchmark` returns `confidence: insufficient`
rather than a number to fill the gap.

## 2. MCP: built versus borrowed

|              | Own (`mcp_server/`)               | Borrowed (Postgres MCP Pro)                 |
| ------------ | --------------------------------- | ------------------------------------------- |
| Transport    | stdio, `FastMCP("value4money")`   | stdio, via `uvx`                           |
| Tools        | 6, purpose-built                  | whatever the model asks of it               |
| Role         | the whole workflow                | research fallback only, after 2 thin searches |
| DB access    | primary Postgres URL              | separate SELECT-only role                   |

**Why we built our own six.** Domain operations, not generic queries: check a bid's arithmetic, find
comparables, flag unusable records, place bids against a pool, draft the file, submit with a named
approver. Each is a fixed contract the workflow depends on, and each takes a `run_id` so the audit
wrapper can log it.

**Why we borrowed one.** Our search takes fixed parameters and cannot express a question the schema
did not anticipate. The borrowed server reports what tables actually exist and lets the model write one
read-only query against them. It recovers what our tool cannot express; it does not replace it.

**The honest caveat.** Our six tools are called **in-process** via `agent/tools.py`, not over MCP. The
surface in `server.py` carries identical names and arguments, so a node could switch to stdio without
changing a line. The reason is the audit guarantee: one audited entry point per tool means no node can
bypass `audit_log`. We would rather state this than let a reviewer find it.

**Guard rails, four deep.** Restricted mode (read-only, parsed SQL, 30s cap) → our check that it is one
`SELECT`/`WITH` with no write keyword → our allowlist (`tenders`, `awards`, `award_labels`, so it
cannot read `audit_log` or `reports`) → a role holding `SELECT` on nothing else. A bypass of all three
still finds nothing to read and no way to write.

## 3. Cross-cutting decisions

- **Audit before execution.** One `audit_log` row per tool call, written *before* the tool runs. A
  failed audit write blocks the tool. First-hand and borrowed calls look identical in the trail.
- **`audit_log` is not the trace.** Opik shows what the agent did and how slowly; Postgres records what
  happened. A run that traces nothing has still filed its evidence.
- **State lives in Postgres.** The checkpointer is what makes an interrupted run survivable, which is
  what the human gate requires.
- **No vector database, no embeddings.** Retrieval is Postgres full-text and trigram search, so every
  citation resolves to a real `award_id` rather than a similarity guess.
- **A scale guard.** A candidate more than 10x above or below the median bid total is dropped before the
  model sees it. It began as a bug: an early roads run benchmarked billion-kes bids against a
  million-kes median and called all six "far above" by up to 87,000%. Now it drops them and reports
  insufficient evidence instead.

## Roadmap

The search cannot yet be told to find comparables **of a size**: the bid median and scale ratio do not
reach the search payload, so a road tender returns million-kes awards that the guard then drops, while
the database holds road awards of 3.39bn and 1.31bn KES that would serve. The fix is to carry the
value band into `research_next_move` and the fallback SQL prompt, keeping the guard as the check.