# AGENTS.md — Value4money-agent

## What this is
A LangGraph agent for the Agentic AI for Africa Innovation Challenge (Governance track, "Value for money" theme). Given a Kenyan public tender and its bids, it compares prices with past awards and writes a sourced evidence file for a human committee. It prepares evidence only.

## Non-negotiable rules
- Never award, recommend a winner, or label anyone "overpriced", "gouging" or "rigging". Findings are evidence, for example: "X% above the middle of N similar awards (records listed)".
- Every finding cites its source records (`ocid` / `award_id` and data year). No source, no finding.
- Every tool call is logged (inputs, outputs, time, `run_id`). Irreversible actions need a named human approver.
- Real data = public, closed tenders only. Bids are synthetic and labelled as such. No personal data about individuals.
- If evidence is thin, say "not enough evidence". Never guess.
- Never commit secrets, `.env`, or raw data (`data/raw/`).

## Stack
Python with `uv`, LangGraph, MCP (our own server in `mcp_server/` plus one borrowed server), PostgreSQL on Neon via `DATABASE_URL`, pytest. Models: open-weights through Ollama for the official run, Groq optional for development.
Windows + PowerShell: no POSIX-only commands. Run everything with `uv run`.

## Layout
```
config.py                 # one settings object for the whole repo
loader/  sql/  data/      # done: loads Kenya OCDS 2024-2026 into Postgres
mcp_server/
  server.py               # registers tools, starts server
  audit.py  db.py
  tools/                  # one file per tool, plain functions
agent/
  state.py  graph.py  llm.py  tools.py  checkpointer.py  tracing.py  run.py  cli.py
  nodes/                  # one file per node
  prompts/                # one .md file per model job
sample_bids/              # synthetic bid PDFs
tests/
```

## Own MCP tools (built one at a time)
`parse_bid_pdf`, `find_comparable_awards`, `flag_data_quality`, `benchmark_price`, `draft_review_file`, `submit_for_committee` (refuses to run without `approved_by`).

## Architecture (decided)
- Nodes: `intake → research
 → quality_check → score → draft → verify_sources → appro
 val → file`.
- Loops: `quality_check → research` (max 3), `verify_sources → draft` (max 2). Approval is a LangGraph `interrupt`.
- Nodes call tools directly in a fixed order. The model only does language jobs (judge similar awards, pick the next search move, typo vs real value, write the draft). **Code does all the maths.**
- Audit logging is one wrapper in `agent/tools.py`, covering every call to every server.
- Borrowed MCP server: Postgres MCP Pro in read-only (restricted) mode, used only as the research fallback.
- Retry caps, thresholds and model settings live in `config.py`.

## Data (Postgres)
Tables: `tenders(ocid, data_year, buyer_id, buyer_name, title, category, method, published_at, quality_flags)`, `awards(award_id, ocid, data_year, award_title, award_description, value_kes, currency, contract_start, contract_end, supplier_name, supplier_norm, lot_group, quality_flags)`, `award_labels`, `audit_log`, `reports`.
- Contract level only: no unit prices, quantities or tender estimates in the real data.
- Tender period dates are unusable. Use `published_at` and contract dates.
- Use `tenders.title` for what was bought. Award titles are often just road names.
- `quality_flags` mark bad rows. Flag, never delete.
- Compare totals only within the same kind of work.

## How to work
1. **Plan mode first:** inspect the repo, give a short plan (files, tests, questions), then stop and wait for approval.
2. After approval: write failing tests and show them red, then the minimum code to turn them green, then stop and report.
3. One task = one tool or module. Do not start the next one.

## Code rules
- One file per tool, plain functions, type hints, one-line docstrings.
- Each tool file starts with short docstrings (max ~10 lines) explaining its method in plain words. No other  comments unless the code is not obvious.
- No unused code, no extra features, no speculative options, no debug prints.
- Do not guess library APIs. Check the installed version's docs.
- Fail with clear errors that name the field or line. Do not swallow exceptions.
- Money is KES. Floats are fine, compared with a 0.01 tolerance.
- Settings come from `config.py`. Add a field only when code needs it. Never hard-code secrets or paths.

## Testing rules
## Tests are the spec
- Once the red run is approved, do not edit tests to make them pass. Fix the code.
- Setup and fixture bugs may be fixed, but report each one.
- If a test seems wrong against the written spec, stop and report: the test name, what it asserts, why it is wrong, and the proposed change. Wait for approval.
- Never delete, skip or xfail a test, and never loosen an assertion.
- Before red: create stubs that raise NotImplementedError, so tests fail on real assertions.
- Tests call the plain functions, not MCP.
- Build test PDFs with `fpdf2` in `tmp_path`. No binary fixtures.
- Never write to the real tables in tests. Database tests are read-only or use a temporary schema, and are skipped when `DATABASE_URL` is unset.