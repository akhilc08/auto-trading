# Domain Pitfalls

**Domain:** MotherDuck cloud integration + GitHub Actions deployment for Python trading framework
**Researched:** 2026-06-02

---

## Critical Pitfalls

Mistakes that cause rewrites, data loss, or silent trading errors.

---

### Pitfall 1: Writing to MotherDuck with a Personal Token Instead of a Service Account Token

**What goes wrong:** Developer creates a personal access token, stores it in GitHub Actions secrets, and uses it for CI writes. When the developer rotates their password, changes their account settings, or the token expires (if TTL was set), all GitHub Actions writes to MotherDuck silently fail — often without surfacing a clear error in CI logs until you notice the Dives are empty.

**Why it happens:** The MotherDuck auth docs present personal tokens first (for interactive use) and service accounts are buried in a separate guide. CI users naturally grab the first token they can create.

**Consequences:** Write failures go undetected; trades are executed by Alpaca but no records land in MotherDuck. The Dives show no data rather than an error. Harder to detect than a crashed workflow.

**Prevention:** Create a dedicated MotherDuck service account (Settings → Service Accounts) for the GitHub Actions integration. Store the service account token — not your personal token — in GitHub Secrets. Service accounts survive personal account changes. Set the token to non-expiring (omit TTL) since there is no rotation mechanism built into this project yet.

**Phase:** Address in GitHub Actions setup phase, before any MotherDuck writes are wired in.

---

### Pitfall 2: GitHub Actions Cron Timing Is Not Reliable for Market-Hours Strategies

**What goes wrong:** You schedule a strategy at `cron: "5 16 * * 1-5"` (UTC, which is 4:05 PM UTC = 12:05 PM ET in summer — WRONG) or at the right UTC time but GitHub fires the job 15–30+ minutes late. The strategy either runs at the wrong time of day or misses the post-close window entirely.

**Why it happens:** Two independent bugs compound:
1. GitHub Actions cron uses UTC. Eastern Time is UTC-5 (EST) or UTC-4 (EDT). The correct UTC expression for 4:05 PM ET is `5 21 * * 1-5` (winter/EST) and `5 20 * * 1-5` (summer/EDT). Developers often confuse ET with UTC.
2. GitHub's scheduled workflows share a job queue with all other Actions triggers globally. During peak load (top of the hour, Monday mornings), delays of 15–30+ minutes are routine with no SLA guarantee.

**Consequences:** Daily strategies (`INTERVAL = "1d"`) use a scheduler that triggers at 4:05 PM ET. If the GitHub Actions cron fires 20 minutes late, the strategy fires at 4:25 PM ET, after the post-close consolidation window.

**Prevention:**
- Express all cron times in UTC with a comment showing the ET equivalent. Use `20 21 * * 1-5` (EST/winter) but be explicit about DST.
- Avoid scheduling at exactly `:00` past the hour (highest contention). Use `:07` or `:13` offsets.
- Do NOT rely on cron timing alone for execution accuracy. The existing `_is_market_hours()` check in `scheduler.py` is a guard but it only prevents out-of-hours execution — it cannot compensate for a 30-minute delay that pushes past a deadline.
- For production use, consider triggering via `workflow_dispatch` from an external cron service (cron-job.org, AWS EventBridge) that POSTs to the GitHub API, which decouples scheduling clock from Actions queue.

**Phase:** Timezone/cron correctness must be locked in during GitHub Actions workflow authoring. Add a UTC comment next to every cron expression at authoring time.

---

### Pitfall 3: GitHub Actions Auto-Disables Scheduled Workflows After 60 Days of Repository Inactivity

**What goes wrong:** The strategies stop trading without any visible error. GitHub silently disables scheduled workflows when no repository commits, PRs, or issues have occurred in 60 days. An email notification is sent but is easy to miss.

**Why it happens:** This is a GitHub policy for inactive repositories — documented but counterintuitive for "set-and-forget" trading bots that run daily but rarely receive code changes.

**Consequences:** All scheduled strategy workflows stop. Alpaca positions that should be managed (e.g., stops, rebalancing) are not. You may not notice until you check the Dives and see stale data.

**Prevention:** The simplest mitigation is to add a dummy commit schedule or ensure at least one non-automated commit per 60 days. A more robust mitigation is to monitor for missing MotherDuck writes — if `portfolio_snapshots` has no rows for the last trading day, alert via email or Slack. Do not rely on GitHub notifications alone.

**Phase:** Document and set a reminder during GitHub Actions setup. Add a data-freshness check to the Flights pipeline so missing days surface as a visible anomaly in Dives.

---

### Pitfall 4: Multiple Concurrent GitHub Actions Jobs Writing to the Same MotherDuck Database

**What goes wrong:** With 13 strategies across 3 accounts, if strategies are triggered by separate workflow runs or a matrix job fires them in parallel, multiple Python processes may attempt simultaneous writes to MotherDuck. Unlike local DuckDB, MotherDuck handles concurrent writes from the cloud layer, but the `duckdb` Python package's within-process concurrency rules still apply: two threads in the same process writing to the same table can conflict.

**Why it happens:** Matrix-based GitHub Actions workflows (one job per strategy) are the natural implementation choice. They appear to be independent, but all write to the same MotherDuck database.

**Consequences:** With MotherDuck's cloud layer, multi-process writes from separate GitHub Actions jobs are handled correctly (MotherDuck serializes them server-side). However, if you use `duckdb.connect()` in multiple threads within one Python process, you risk write conflicts and data corruption.

**Prevention:** Keep MotherDuck writes single-threaded within each strategy runner process. Each GitHub Actions job (one per strategy) connects independently — this is fine. Never share a `duckdb.connect()` connection object across threads within one process. Use `INSERT ... ON CONFLICT DO NOTHING` for idempotent writes so retried jobs do not create duplicates.

**Phase:** Address during `core/motherduck_logger.py` implementation. Document the threading rule as a comment in the logger.

---

### Pitfall 5: Storing Secrets in Workflow Files or Logs

**What goes wrong:** During debugging, a developer adds `run: env` or `run: printenv` to a workflow step to diagnose a failing connection. This prints all environment variables — including `MOTHERDUCK_TOKEN`, `ALPACA_API_KEY`, and `ALPACA_SECRET_KEY` — to the public (or team-visible) GitHub Actions log. GitHub only masks the exact stored secret string; URL-encoded, base64-encoded, or truncated variants are printed in cleartext.

**Why it happens:** Debug-and-forget: the `printenv` step is added during a failing deployment and never removed. On private repos it is less obviously dangerous, so cleanup is deprioritized.

**Consequences:** MotherDuck token and Alpaca keys are visible in workflow logs. With Alpaca live-mode keys, this is a direct financial exposure risk.

**Prevention:** Never add `env`, `printenv`, or any env-dumping step to a workflow. Pass secrets only to the specific step that needs them using `env:` at the step level, not at the job level. After any debugging session, review the full workflow file before committing. Treat Alpaca live-mode keys as bank credentials.

**Phase:** Security review checklist item for GitHub Actions workflow authoring. Enforce via code review, not tooling.

---

## Moderate Pitfalls

---

### Pitfall 6: Storing Timestamps Without UTC Normalization in the Trade Log

**What goes wrong:** `motherduck_logger.py` stores `datetime.now()` (local machine time) instead of `datetime.now(timezone.utc)`. In GitHub Actions, the runner timezone is UTC by default, so this often works — until a developer runs the logger locally (in ET or PT), producing timestamps that are 4-5 hours off. The `trades` table ends up with mixed-timezone timestamps that break JOIN conditions, daily aggregation in Flights, and equity curve ordering in Dives.

**Why it happens:** Python's `datetime.now()` returns naive local time. The existing `AlpacaClient.get_latest_bars()` already uses `datetime.now(datetime.timezone.utc)` — that same pattern must be applied to every timestamp written to MotherDuck.

**Consequences:** P&L aggregations in Flights bucket trades into the wrong trading day. DST transitions create ambiguous timestamps (two different fills appear to have the same timestamp). Dives equity curve shows jumps/gaps.

**Prevention:** All timestamps stored to MotherDuck must be `TIMESTAMPTZ` columns initialized with `datetime.now(timezone.utc)` or `datetime.utcnow()` (Python). Never call `datetime.now()` without a timezone. Display ET in Dives via `AT TIME ZONE 'America/New_York'` in the query, not at storage time.

**Phase:** Address during schema design and `motherduck_logger.py` implementation. Enforce in code review.

---

### Pitfall 7: Schema Design — Missing `strategy_name` and `account_name` Columns Break All Cross-Strategy Queries

**What goes wrong:** The `trades` table is created without `strategy_name` and `account_name` columns, or these are added later via `ALTER TABLE`. Any Flights query or Dive that tries to compare strategies or per-account P&L must either recompute strategy from order metadata or fail. The 13+ strategy + 3-account matrix is the entire point of the analytics layer.

**Why it happens:** Initial schema is modeled on a single-strategy trade log, then requirements expand. Adding columns after the fact with `ALTER TABLE ADD COLUMN` works in DuckDB, but existing rows get `NULL` for the new column, corrupting historical comparisons until a backfill is run.

**Prevention:** Include `strategy_name VARCHAR NOT NULL` and `account_name VARCHAR NOT NULL` in the initial schema DDL. These come directly from `accounts.py` at logging time. Do not design the schema without first enumerating all dimensions needed for cross-strategy Dives.

**Phase:** Schema DDL design phase, before any data is written.

---

### Pitfall 8: No Idempotency Guard — GitHub Actions Retry Creates Duplicate Trade Records

**What goes wrong:** A GitHub Actions job fails mid-run (network error, Alpaca timeout) and is manually re-run. The strategy re-executes `on_bar`, submits orders again (Alpaca rejects them as duplicates or fills a second order), and if order submission was partially completed before the logger write, the MotherDuck `trades` table gets either duplicate rows or orphaned order IDs.

**Why it happens:** The strategy runner has no "already ran today" guard. `run_cron` in `scheduler.py` runs a blocking scheduler inside the Actions job — if the job is re-run from scratch, the strategy fires again from the beginning.

**Consequences:** Double-counted fills in Flights P&L aggregations. Possible double-orders on Alpaca in paper mode (each would be a separate fill if the first order closed between runs).

**Prevention:**
- Use `INSERT INTO trades ... ON CONFLICT (order_id) DO NOTHING` to make the MotherDuck write idempotent on Alpaca order ID.
- For the strategy runner in GitHub Actions mode (not APScheduler mode), add a lightweight "already-ran-today" check against MotherDuck's `portfolio_snapshots` table at startup before executing.

**Phase:** Address during `motherduck_logger.py` implementation and GitHub Actions workflow design.

---

### Pitfall 9: Flights Pipeline — Aggregating Before All Fills Are Confirmed

**What goes wrong:** The Flights pipeline runs at 4:30 PM ET to aggregate the day's P&L. Strategies submit `TimeInForce.DAY` market orders around 4:05 PM ET (after close). Fills may not appear in Alpaca's API for several minutes after order submission. If the Flights aggregation runs before all fills are confirmed and written to MotherDuck, the day's P&L is incomplete.

**Why it happens:** Post-close order fills are async. Alpaca may return `status: "pending_new"` for several minutes before confirming the fill price. The `motherduck_logger.py` writes the order submission event, not the confirmed fill.

**Consequences:** Flights aggregation shows partial daily P&L. The next run will have no "catch-up" mechanism and the missing fills may never be aggregated into that day's record.

**Prevention:** Log two events: order submission (with `status=submitted`) and fill confirmation (with `status=filled`, `filled_at`, `filled_avg_price`). The fill confirmation requires a follow-up Alpaca API call. Schedule the Flights aggregation at 6:00 PM ET (not 4:30 PM ET) to give fills time to settle. Alternatively, the Flights query should only aggregate `WHERE status = 'filled'`.

**Phase:** This crosses both `motherduck_logger.py` implementation and Flights pipeline design. Must be addressed before Flights are authored.

---

### Pitfall 10: Dives Querying Full Trade History Without a Date Filter

**What goes wrong:** The "Trade Log" Dive runs a `SELECT * FROM trades` query with no date range filter. After 3-6 months of daily strategy execution across 13 strategies, this table may have tens of thousands of rows. The Dive is slow to render because it scans the full table.

**Why it happens:** Dives are generated from natural language prompts. If you ask for "show me all trades," the AI generates an unfiltered query. This is fine at launch, but becomes a UX problem at scale.

**Prevention:** Every Dive query should include a default date filter (e.g., `WHERE traded_at >= CURRENT_DATE - INTERVAL '90 days'`). The MotherDuck docs note that slow Dives are caused by queries scanning too much data, and the fix is to add filters or sort the underlying table on the timestamp column. Sort the `trades` table by `traded_at` at insert time to optimize row-group pruning.

**Phase:** Address when authoring Dives. Add explicit date bounds to every Dive query.

---

## Minor Pitfalls

---

### Pitfall 11: Forgetting DST When Hardcoding the 4:05 PM ET Cron

**What goes wrong:** A single UTC cron expression cannot represent "4:05 PM ET" year-round, because Eastern Time shifts between UTC-5 (EST, November–March) and UTC-4 (EDT, March–November). A cron that is correct in winter fires at 5:05 PM ET in summer (missing post-close by an hour).

**Prevention:** Use two cron lines in the workflow: one for EST (`5 21 * * 1-5`, Nov–Mar) and one for EDT (`5 20 * * 1-5`, Mar–Nov). GitHub now supports a `timezone:` field on cron schedules (added March 2026) — use `timezone: "America/New_York"` to eliminate this entirely.

**Phase:** GitHub Actions workflow authoring.

---

### Pitfall 12: The `_load_env()` in `runner.py` Silently Falls Back to `.env` if `.env.<account>` Is Missing

**What goes wrong:** In GitHub Actions, if a strategy's account env file is not represented by properly named secrets (e.g., `STAT_ARB_ALPACA_API_KEY`), `_load_env()` silently falls back to a `.env` file that does not exist in CI, leaving `ALPACA_API_KEY` unset. `AlpacaClient.__init__` will then throw a `KeyError` on the first run, but the error message looks like an Alpaca bug rather than a missing secret.

**Prevention:** In the GitHub Actions workflow, set environment variables directly from secrets (e.g., `ALPACA_API_KEY: ${{ secrets.STAT_ARB_ALPACA_API_KEY }}`). The `_load_env()` path is designed for local development. Do not rely on it in CI — set env vars explicitly in the workflow step.

**Phase:** GitHub Actions workflow authoring.

---

### Pitfall 13: DuckDB `ON CONFLICT` Bug With Updating the Conflict Column

**What goes wrong:** If you write an upsert like `INSERT INTO trades ... ON CONFLICT (order_id) DO UPDATE SET order_id = excluded.order_id`, DuckDB has a known bug (issue #16698) where updating the conflict column sets other row values to NULL. This silently corrupts the row.

**Prevention:** Never update the conflict column in a `DO UPDATE` clause. Use `DO NOTHING` for trade log inserts (an order ID is immutable — if it already exists, skip). Reserve `DO UPDATE` only for mutable fields like `status` or `filled_avg_price`.

**Phase:** `motherduck_logger.py` implementation.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|----------------|------------|
| Schema DDL (trades, positions, portfolio_snapshots) | Missing `strategy_name`/`account_name` causes NULL backfill pain | Include all dimension columns in initial DDL |
| Schema DDL | Naive `TIMESTAMP` instead of `TIMESTAMPTZ` | Use `TIMESTAMPTZ`, always write UTC |
| `motherduck_logger.py` | Personal token instead of service account token | Service account token from the start |
| `motherduck_logger.py` | Non-idempotent inserts cause duplicates on retry | `ON CONFLICT (order_id) DO NOTHING` |
| `motherduck_logger.py` | Write confirmed-fill, not just order submission | Log `filled_avg_price` + `filled_at` via follow-up API call |
| GitHub Actions workflows | UTC cron offset wrong for ET | Use `timezone: "America/New_York"` in cron definition |
| GitHub Actions workflows | Cron fires 15-30 min late during peak load | Avoid `:00` offsets; accept the latency risk or use external trigger |
| GitHub Actions workflows | 60-day inactivity auto-disable | Monitor for missing daily MotherDuck rows |
| GitHub Actions workflows | Secrets leaked via `printenv` debug steps | Never add env-dump steps to workflow files |
| GitHub Actions workflows | `.env.<account>` fallback silently misses secrets | Set env vars explicitly in workflow step |
| Flights pipeline | Aggregating before fills are confirmed | Schedule Flights at 6 PM ET; only aggregate `status = 'filled'` |
| Dives authoring | Unfiltered `SELECT *` becomes slow at scale | Always add `WHERE traded_at >= CURRENT_DATE - INTERVAL '90 days'` |
| Dives authoring | Dive not saved — just shown | Explicitly say "create a Dive" in the prompt, not just "show me a chart" |

---

## Sources

- MotherDuck Connecting: https://motherduck.com/docs/key-tasks/authenticating-and-connecting-to-motherduck/connecting-to-motherduck/
- MotherDuck Auth: https://motherduck.com/docs/key-tasks/authenticating-and-connecting-to-motherduck/authenticating-to-motherduck/
- MotherDuck Service Accounts: https://motherduck.com/docs/key-tasks/service-accounts-guide/
- MotherDuck Data Warehousing: https://motherduck.com/docs/key-tasks/data-warehousing/
- MotherDuck Dives: https://motherduck.com/docs/key-tasks/ai-and-motherduck/dives/
- DuckDB Concurrency: https://duckdb.org/docs/current/connect/concurrency
- DuckDB ALTER TABLE: https://duckdb.org/docs/current/sql/statements/alter_table
- DuckDB ON CONFLICT bug #16698: https://github.com/duckdb/duckdb/issues/16698
- GitHub Actions cron drift: https://crontap.com/blog/github-actions-cron-drift-problem
- GitHub Actions scheduling discussion: https://github.com/orgs/community/discussions/156282
- GitHub Actions 60-day inactivity: https://github.com/fischerscode/DockerFlutter/issues/50
- GitHub Actions limits: https://docs.github.com/en/actions/reference/limits
- GitHub Actions secrets leaking: https://www.karimrahal.com/2023/01/05/github-actions-leaking-secrets/
- UTC in finance infrastructure: https://www.timestored.com/data/utc-finance-infra
