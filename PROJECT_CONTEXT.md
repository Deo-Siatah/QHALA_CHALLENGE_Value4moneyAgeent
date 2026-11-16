# Hasibu / Value4money Agent - Transferable Project Context

This document is the compact orientation and operating truth for the repository. Read it before
making changes, together with `Value4money-agent/agents.md`, which remains the binding coding and
testing instruction file.

## 1. Identity And Purpose

Hasibu is a LangGraph evidence-preparation agent for the Agentic AI for Africa Innovation Challenge,
Governance track, Value for Money theme.

Given a Kenyan public tender and synthetic bid PDFs, it:

1. Reads tender fields and bid documents.
2. Checks bid arithmetic.
3. Searches public historical awards.
4. Removes unusable or mismatched records.
5. Benchmarks bid totals against comparable awards.
6. Writes a sourced evidence file for a human committee.
7. Pauses for named human approval before filing.

Hasibu prepares evidence. The committee decides.

It must never select a winner, recommend an award, or describe a bidder as overpriced, gouging,
rigging, fraudulent, corrupt, or equivalent. Findings must be factual, sourced, and cautious.

## 2. Binding Rules

The authoritative rules are in `Value4money-agent/agents.md`.

- Every finding needs source records, normally `award_id`/`ocid` and `data_year`.
- Every tool call is audited with inputs, outputs, timestamp, and `run_id`.
- Irreversible filing requires a named human approver.
- Real procurement data is public closed-tender data only.
- Bid PDFs are synthetic and must remain labelled as synthetic.
- No personal data about individuals.
- Thin evidence must be reported as insufficient; never guessed around.
- Never commit `.env`, secrets, or `data/raw/`.
- Money is KES; calculations are performed in code, not by the model.
- Tests are the specification. Do not delete, skip, xfail, loosen, or rewrite tests merely to pass.
- Windows/PowerShell commands are required; use `uv run` for Python commands.

## 3. Repository Shape

The project root is `Value4money-agent/`.

| Area | Responsibility |
|---|---|
| `config.py` | One Pydantic settings object; environment-backed configuration |
| `main.py` | Interactive CLI entry point |
| `agent/` | LangGraph workflow, state, model wrapper, audit wrappers, CLI and checkpointing |
| `agent/nodes/` | One node per workflow stage |
| `agent/prompts/` | Model prompts and persona |
| `api/` | FastAPI server, runner, SSE events, snapshots, report downloads |
| `web/` | React/Vite frontend with Tailwind v4, Radix, CVA, Lucide and React Query |
| `mcp_server/` | Own tools, database access, audit wrapper and report renderers |
| `loader/` | Schema setup, OCDS loading, demo data and synthetic PDFs |
| `sql/` | Schema, indexes, report migration and demo data |
| `tests/` | Python specification tests |
| `web/src/test/` | Frontend tests |
| `sample_bids/` | Synthetic chainlink fence bid PDFs |
| `pdfs/` | Synthetic road bid PDFs |
| `outputs/` | Drafts and filed report files; do not treat as source code |

Important documents:

- `Value4money-agent/agents.md`: binding agent instructions.
- `Value4money-agent/README.md`: user-facing setup and workflow documentation.
- `Value4money-agent/ARCHITECTURE.md`: design decisions and caveats.
- `Value4money-agent/EVALS.md`: recorded evaluation results and known failures.

## 4. Actual Graph Workflow

The current graph has ten nodes:

```text
tender_intake
  -> bid_intake
  -> confirm_intake
  -> research
  -> quality_check
  -> score
  -> draft
  -> verify_sources
  -> approval
  -> file
```

Loops:

- `quality_check -> research` while the judged pool is too thin, capped by
  `settings.max_research_attempts`.
- `verify_sources -> draft` while report checks fail, capped by
  `settings.max_draft_attempts`.

Approval is a LangGraph interrupt. The Postgres checkpointer lets the run pause and resume later
using the same `thread_id`/`run_id`.

### Node responsibilities

- `tender_intake`: extracts labelled tender fields with page/text sources; missing fields remain
  missing.
- `bid_intake`: reads every bid, tracks status/confidence, and carries arithmetic issues.
- `confirm_intake`: CLI may pause for a named confirmation; web mode disables the gate and records
  issues instead because the browser has no separate intake confirmation screen.
- `research`: performs deterministic first search, then asks the model only how to widen later
  searches; candidates accumulate by `award_id`.
- `quality_check`: fixed rules remove bad values, wrong currencies, duplicates, missing ids and
  scale mismatches; model judgements decide same-work/suspect cases.
- `score`: calls deterministic `benchmark_price`; median, quartiles and percentages are code-owned.
- `draft`: code builds findings and sources; the model supplies bounded notes; report is rendered.
- `verify_sources`: checks citations, source coverage, required findings, positions, and note rules.
- `approval`: validates a named person and decision; thin evidence requires explicit
  `publish_anyway` to file.
- `file`: validates approval and calls the audited submission tool.

## 5. State And Report Data

`agent/state.py` defines `AgentState` and reducers. The important report fields are:

- `bids`, `candidates`, `pool`, `pool_size`, `excluded`, `excluded_awards`.
- `benchmark`, `findings`, `sources`, `summary_note`, `finding_notes`.
- `review_markdown`: the Markdown report body.
- `report_model`: JSON form of the structured `ReportModel` used by the modern renderers.
- `verify_ok`, `verify_failures`, `approval_status`, `approved_by`, `submission`.

The structured report model was added to fix a data split where Markdown was populated but print/PDF
renderers reconstructed incomplete data. New drafts carry `report_model`; filing reuses it and falls
back to rebuilding for older checkpoints.

## 6. Data And Database

Postgres is required. `DATABASE_URL` is loaded through `config.py`.

Main tables:

- `tenders`: public tender metadata.
- `awards`: contract-level award totals and public record fields.
- `award_labels`: optional work labels.
- `audit_log`: pre-execution tool audit records.
- `reports`: filed Markdown, approver, fingerprint and structured `review_json`.
- LangGraph checkpoint tables: created by `PostgresSaver.setup()`.

Schema files:

- `sql/01_schema.sql`: base schema.
- `sql/02_indexes.sql`: indexes and analysis.
- `sql/03_report_columns.sql`: additive migration for `reports.fingerprint` and
  `reports.review_json`.
- `sql/demo_data.sql`: generated demo slice.

Setup/migration command:

```powershell
cd Value4money-agent
uv run python -m loader.setup
```

This is idempotent and applies the report-column migration. It does not reload demo awards when the
database already contains awards.

The scale guard drops awards more than `MAX_SCALE_RATIO` (default 10x) above or below the median
stated bid total. This prevents a road-scale bid from being compared with fence-scale awards.

## 7. Auditing And MCP

`agent/tools.py` wraps own tool calls with `mcp_server.audit.audited`. An audit row is created before
the underlying function runs; output or an error is written afterward. If the audit write fails, the
tool is blocked.

Own tools are called in-process for the audit guarantee, although `mcp_server/server.py` exposes an
equivalent stdio MCP surface.

The borrowed Postgres MCP server is a research fallback only. It is restricted to read-only
`SELECT`/`WITH` queries over `tenders`, `awards`, and `award_labels`. It cannot access `reports` or
`audit_log`. SQL is guarded locally and row output is capped.

## 8. Checkpointing And Database Resilience

`agent/checkpointer.py` uses a process-wide `PostgresSaver` and `ConnectionPool` for the web API, and
a short-lived pool for scripted runs. The pool now uses `ConnectionPool.check_connection` so a
connection terminated by a PostgreSQL administrator action is detected before reuse.

An observed production failure was:

```text
AdminShutdown: terminating connection due to administrator command
```

It occurred before `tender_intake`, leaving every step pending. The database was reachable again and
the fix was to health-check pooled connections. If it recurs, inspect the database provider logs and
restart the API process so a fresh pool is created.

## 9. Filing And Report Formats

The filing tool `mcp_server/tools/submit_for_committee.py`:

1. Validates run id, report body and named approver.
2. Computes a Markdown fingerprint.
3. Inserts `reports` data transactionally.
4. Writes `outputs/reports/<run_id>.md` and HTML when structured data is available.
5. Rolls back if file writing or HTML rendering fails.

The web report endpoints are:

- `/api/runs/{run_id}/report`: exact Markdown body.
- `/api/runs/{run_id}/report.html`: self-contained modern HTML report.
- `/api/runs/{run_id}/report.pdf`: structured modern PDF report.
- `/api/runs/{run_id}/report.tex`: LaTeX source.

Print and PDF options:

- `orientation=portrait|landscape`.
- `paper_size=A4|Letter`.
- The frontend defaults to landscape/A4 and sends the selected values to both Print report and
  Download PDF.
- The Print report action opens the generated PDF endpoint in a new tab; it does not open HTML.
- The browser report card is marked `.print-only`; the print stylesheet hides the rest of the run
  page while retaining the report.

## 10. Web UI Current Truth

The web app is under `Value4money-agent/web/`.

### Landing page

`web/src/pages/StartPage.tsx` now explains:

1. Read the documents.
2. Compare public awards.
3. Prepare the file.

It clearly states that Hasibu prepares evidence and the committee decides. Tender and bid PDFs are
staged before **Start Analysis**; selecting files alone never starts a run.

### Live run page

`RunPage.tsx` shows a premium evidence-review header, status, run id, elapsed time, alerts and the
step workflow.

`StepStream.tsx` behavior is intentional:

- During processing, one focal step is shown.
- A numbered badge identifies the current step.
- Model tokens and step details appear in that slot.
- Completed steps use a tick and summary.
- After approval/finish, all steps become a vertical expandable overview.

The UI uses Tailwind v4 CSS-first tokens, Radix where applicable, CVA variants, React Query and
Lucide icons. The visual direction is white paper, navy text, pale blue surfaces and cobalt actions.

## 11. Commands

From `Value4money-agent/`:

```powershell
uv sync
uv run python -m loader.setup
uv run python main.py
uv run pytest tests/test_quality_check.py -q
uv run python -m compileall -q agent api loader mcp_server
```

Web commands from `Value4money-agent/web/`:

```powershell
npm install
npm run dev
npm test
npm run typecheck
npm run build
```

Recommended focused validation:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
uv run pytest tests/test_api_server.py tests/test_api_runner.py tests/test_checkpointer.py -q -p no:warnings
```

Disabling pytest plugin autoload avoids an unrelated installed `langsmith` pytest plugin startup
problem observed in this environment.

## 12. Test Status And Known Caveats

Recent verified results:

- Frontend full suite: 62 tests passed.
- Frontend production build: passed; Vite reports only a chunk-size warning.
- API server lifecycle/report tests: passed in focused runs.
- Checkpointer and runner tests: 34 passed after connection health-check changes.
- Python diagnostics on touched modules: clean in recent checks.

Recorded caveat in `EVALS.md`:

- One verification fixture expects 12 pooled awards while the symmetric scale guard correctly drops
  an out-of-band award. The fixture and guard are inconsistent; do not weaken the guard without an
  explicit decision.

Architecture roadmap caveat:

- Research does not yet pass the bid value band into the search query. Scale filtering catches the
  mismatch afterward, but a future improvement could search by size earlier.

## 13. Git And Remote State

Current branch is `main`. At the time this file was created:

- `HEAD`: `d6055f7` - `modified chnages for phase 3 Hasibu, ui& ux + functionality improvemnt`.
- `origin` fetch: `https://github.com/Deo-Siatah/QHALA_Value4money-agent-V2`.
- `mirror` fetch/push: `https://github.com/Deo-Siatah/QHALA_CHALLENGE_Value4moneyAgeent`.
- The second repository was successfully pushed from `d00812d` to `d6055f7`.

Important caution: the current Git configuration output showed `origin` fetch pointing to V2 but
`origin` push pointing to the second repository. The intended dual-push setup was not fully verified
because one configuration command was skipped. Before relying on `git push origin main` to update
both repositories, inspect:

```powershell
git config --get-all remote.origin.url
git config --get-all remote.origin.pushurl
git remote -v
```

To configure both push destinations explicitly:

```powershell
git remote set-url --add --push origin https://github.com/Deo-Siatah/QHALA_Value4money-agent-V2
git remote set-url --add --push origin https://github.com/Deo-Siatah/QHALA_CHALLENGE_Value4moneyAgeent
git remote -v
```

Do not force-push or overwrite a divergent target without inspecting its history first.

## 14. How A New Agent Should Work

1. Read this file and `Value4money-agent/agents.md`.
2. Inspect `git status --short --branch`; preserve unrelated user changes.
3. Identify the smallest owning file/symbol and one falsifiable local hypothesis.
4. Follow repository plan-first behavior for new tasks.
5. After approval, add a focused failing test, run it red, then make the smallest implementation fix.
6. Run focused executable validation before broad searches or unrelated edits.
7. Keep evidence wording and safety constraints intact.
8. Use the replay route for deterministic frontend behavior checks.
9. Run relevant backend/frontend checks before finishing.
10. Report residual risks, unavailable services, and unrelated existing failures explicitly.

## 15. Current Working Assumptions

- Windows PowerShell is the execution environment.
- PostgreSQL is the source of truth for public procurement data, audits, reports and checkpoints.
- The API process must remain alive during browser runs; it is not serverless.
- The browser uses a Vite/Vercel proxy for the API token; the token must not reach client code.
- UI changes must preserve the evidence-only language and greyscale-readable status semantics.
- Generated documentation should remain free of Lovable references unless explicitly requested.
