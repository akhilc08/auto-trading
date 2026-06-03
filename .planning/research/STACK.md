# Technology Stack

**Project:** auto-trading — MotherDuck Cloud Deployment milestone
**Researched:** 2026-06-02
**Scope:** NEW capabilities only — MotherDuck integration, GitHub Actions execution, Dives visualization

---

## New Dependencies Required

### MotherDuck / DuckDB

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `duckdb` | `>=1.1.0,<1.6` | Python-to-MotherDuck writes | The `duckdb` package bundles the MotherDuck extension; no separate install needed. Use `~=1.5.3` to pin to the current MotherDuck-supported max. |

**Rationale:** MotherDuck supports DuckDB client versions 1.4.0–1.5.3 (all regions as of June 2026). The latest stable PyPI release is 1.5.3 (released May 20, 2026). Pinning to `~=1.5.3` keeps you on the supported ceiling without risking breakage from a future 1.6 bump before MotherDuck catches up.

**Do NOT add:** `duckdb-extension-motherduck` — it is a separate extension package that is only needed if you are building a custom DuckDB distribution. The standard `duckdb` pip package includes the MotherDuck extension bundled and auto-loaded on first `ATTACH 'md:'` call.

**Do NOT add:** SQLAlchemy, an ORM, or any other abstraction layer. Direct `duckdb.connect()` is the right approach for simple append-only logging.

---

## Connection and Authentication

### How Python Connects to MotherDuck

```python
import os
import duckdb

conn = duckdb.connect("md:trading", config={"motherduck_token": os.environ["MOTHERDUCK_TOKEN"]})
```

- `md:trading` — connects to the MotherDuck cloud database named `trading`. The database is created on first connect if it does not exist.
- `config={"motherduck_token": ...}` — preferred injection pattern; keeps the token out of the connection string URL (avoids accidental logging).
- Alternative: `duckdb.connect("md:trading?motherduck_token=TOKEN")` — works but leaks token in logs/traces if you print the connection string.
- Alternative: set `motherduck_token` as an environment variable; DuckDB reads it automatically. This means `duckdb.connect("md:trading")` alone works if `motherduck_token` is exported in the shell environment.

**Confidence:** HIGH — verified against MotherDuck official docs.

### Token Generation

Tokens are created in the MotherDuck UI under Settings > Create Token. Read/Write tokens are the default; set no expiry for a long-lived GitHub Actions secret.

---

## Python Write Patterns

### Recommended: `executemany` for small trade records

For this use case (logging individual fills and position snapshots), `executemany` with parameterized queries is the correct choice. Each strategy produces at most tens of rows per execution — not thousands — so the executemany performance caveat (avoid for >500 rows) does not apply.

```python
conn.executemany(
    "INSERT INTO trades VALUES (?, ?, ?, ?, ?, ?, ?)",
    [(row1_values,), (row2_values,)]
)
```

### When bulk loading is needed (backtests): DataFrame insert

If a future phase loads historical data in bulk:

```python
import pandas as pd
conn.execute("INSERT INTO trades SELECT * FROM df_trades")  # df_trades is in local scope
```

DuckDB scans the local Pandas DataFrame directly via Arrow zero-copy. No `.to_sql()`, no SQLAlchemy needed.

**Do NOT use:** `df.to_sql()` with a DuckDB SQLAlchemy engine for bulk loads — it's slower and adds an unnecessary dependency.

### Concurrency note

Each GitHub Actions job is a separate process with its own connection. MotherDuck handles concurrent appends from multiple jobs to the same cloud database — appends never conflict. No connection pooling, locking, or coordination needed across jobs.

---

## GitHub Actions

### Action versions (current as of June 2026)

| Action | Version | Purpose |
|--------|---------|---------|
| `actions/checkout` | `v4` | Checkout repo |
| `actions/setup-python` | `v5` | Set up Python runtime |

**Note:** v6 of setup-python was observed in documentation snippets but v5 is stable and widely deployed. Use `actions/setup-python@v5` unless a specific v6 feature is needed.

### Cron scheduling for NYSE market hours

GitHub Actions cron runs in UTC with no timezone support. Manual DST conversion required twice per year.

| Market event | EDT (Mar–Nov) UTC | EST (Nov–Mar) UTC | Cron (EDT) | Cron (EST) |
|---|---|---|---|---|
| Market open (9:30 AM ET) | 13:30 UTC | 14:30 UTC | `30 13 * * 1-5` | `30 14 * * 1-5` |
| Market close (4:00 PM ET) | 20:00 UTC | 21:00 UTC | `0 20 * * 1-5` | `0 21 * * 1-5` |
| Pre-market (8:00 AM ET) | 12:00 UTC | 13:00 UTC | `0 12 * * 1-5` | `0 13 * * 1-5` |

**Important caveat:** GitHub schedules drift 5–30 minutes at peak times (top of hour). For strategies that care about exact open-bell timing, build a Python guard that checks whether the market is actually open using Alpaca's `get_clock()` before placing orders. This is already the standard pattern in Alpaca-based bots.

**Always include `workflow_dispatch`** alongside `schedule` to allow manual test runs without waiting for the cron window.

### Secrets injection pattern

Define secrets in GitHub repo Settings > Secrets and variables > Actions. Reference them in workflow YAML as environment variables:

```yaml
env:
  APCA_API_KEY_ID: ${{ secrets.APCA_API_KEY_ID }}
  APCA_API_SECRET_KEY: ${{ secrets.APCA_API_SECRET_KEY }}
  APCA_API_BASE_URL: ${{ secrets.APCA_API_BASE_URL }}
  MOTHERDUCK_TOKEN: ${{ secrets.MOTHERDUCK_TOKEN }}
```

Python reads these with `os.environ["KEY"]` — same as when loaded from `.env` via `python-dotenv` locally. No code changes needed between local and CI execution because the existing `runner.py` already uses `load_dotenv` which falls through to the environment when no `.env.<account>` file exists.

**Per-account secrets:** The project has 3 accounts (`.env.trend`, `.env.stat_arb`, `.env.vol_risk_premium` or similar). Each account's Alpaca keys must be separate secrets in GitHub Actions. Pattern: `TREND_APCA_API_KEY_ID`, `STAT_ARB_APCA_API_KEY_ID`, etc., then the workflow sets the right ones depending on which strategy job runs.

---

## MotherDuck Flights — Status: NOT YET AVAILABLE

**Finding:** "Flights" is not a shipping MotherDuck feature. The term appears in the project doc's aspirational goal list but the actual MotherDuck product has no native scheduled SQL pipeline feature called "Flights." As of June 2026, scheduled queries are marked "in progress" on MotherDuck's public feature request board.

**What exists instead:**
- MotherDuck supports integration with Airflow, Dagster, Prefect, Kestra, and other external orchestrators for scheduled SQL
- For this project's daily aggregation need (P&L rollups, drawdown), the simplest path is a separate GitHub Actions job that runs `python scripts/daily_aggregation.py` which executes the aggregation SQL via `duckdb.connect("md:trading")`. No additional tool needed.

**Confidence:** HIGH — verified against MotherDuck release notes, orchestration docs, and feature request board.

---

## MotherDuck Dives

**What it is:** An AI-generated, persistent, interactive visualization layer in the MotherDuck UI. Dives run live SQL against your MotherDuck databases and are shareable/embeddable.

**How to create them:** Via natural language through an MCP-connected AI agent (Claude, ChatGPT, Cursor). The agent writes the SQL, configures the chart, and saves the Dive into the MotherDuck workspace. You can also manage Dives from SQL using `list_dives` and `read_dive`.

**What this means for the milestone:** Dives are created interactively, not by code in this repo. The milestone deliverable is to have the right data in MotherDuck (correct schema, populated tables) so that Dives can query it. The Dive creation step is a manual/AI-assisted task done in the MotherDuck UI after data is flowing.

**No new Python dependencies required for Dives.**

**Confidence:** HIGH — verified against MotherDuck Dives documentation and release notes.

---

## Updated requirements.txt additions

```
duckdb~=1.1.0
```

Wait — pin to the MotherDuck-supported version ceiling:

```
duckdb>=1.1.0,<1.6.0
```

This allows any 1.x.y in the supported range without jumping to a potentially unsupported 1.6 before MotherDuck confirms compatibility.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Python→MotherDuck write | `duckdb` direct | SQLAlchemy + duckdb dialect | Adds ~500 lines of ORM overhead for what is a simple append operation |
| Python→MotherDuck write | `executemany` (small batches) | Pandas `.to_sql()` | Requires SQLAlchemy; slower for small row counts |
| Scheduling | GitHub Actions cron | Airflow / Prefect | No server to run an orchestrator on; Actions is already the execution env |
| Secrets | GitHub Actions Secrets | HashiCorp Vault | Vault requires infrastructure; Actions Secrets is native and free |
| Scheduled SQL (aggregations) | GitHub Actions job running Python+DuckDB | MotherDuck native Flights | Flights is not yet available; GA Actions job is equivalent and already in use |

---

## Sources

- MotherDuck Python installation + authentication: https://motherduck.com/docs/getting-started/interfaces/client-apis/connect-query-from-python/installation-authentication/
- MotherDuck connecting: https://motherduck.com/docs/key-tasks/authenticating-and-connecting-to-motherduck/connecting-to-motherduck/
- MotherDuck version lifecycle: https://motherduck.com/docs/troubleshooting/version-lifecycle-schedules/
- MotherDuck Python data loading: https://motherduck.com/docs/key-tasks/loading-data-into-motherduck/loading-data-md-python/
- MotherDuck Dives docs: https://motherduck.com/docs/key-tasks/ai-and-motherduck/dives/
- MotherDuck scheduled queries feature request (in progress): https://motherduck.canny.io/feature-requests/p/scheduled-queries-notebooks
- MotherDuck orchestration integrations: https://motherduck.com/docs/integrations/orchestration/
- DuckDB PyPI (1.5.3): https://pypi.org/project/duckdb/
- DuckDB Python DB API docs (Context7 / duckdb-web): executemany, concurrency patterns
- GitHub Actions cron syntax: https://cronbuilder.dev/blog/github-actions-cron-schedule.html
- GitHub Actions secrets docs: https://docs.github.com/en/actions/security-guides/encrypted-secrets
- NYSE market hours UTC conversion: https://www.tradinghours.com/markets/nyse
