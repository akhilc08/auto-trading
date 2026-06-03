---
phase: 02-flights
plan: 04
type: execute
wave: 1
depends_on: []
files_modified:
  - flights/aggregation/daily_pnl.py
  - flights/aggregation/requirements.txt
autonomous: false
requirements: [AGG-01, AGG-02, AGG-03, AGG-04, AGG-05, AGG-06]
must_haves:
  truths:
    - "A MotherDuck Flight named daily-pnl-aggregation reads trades and writes aggregated rows to daily_pnl"
    - "Aggregation includes only WHERE status = 'filled' trades for the prior trading day"
    - "The Flight is scheduled at 6 PM ET Mon-Fri"
    - "Re-running the Flight on the same date overwrites rows (idempotent) — re-run produces the same row count, not duplicates"
  artifacts:
    - path: "flights/aggregation/daily_pnl.py"
      provides: "daily-pnl-aggregation Flight entrypoint: def main() reading trades, writing daily_pnl"
      contains: "def main"
    - path: "flights/aggregation/requirements.txt"
      provides: "Pinned Flight deps"
      contains: "duckdb==1.5.2"
  key_links:
    - from: "flights/aggregation/daily_pnl.py"
      to: "trading.main.daily_pnl"
      via: "ON CONFLICT (date, strategy_name, account_name) DO UPDATE"
      pattern: "ON CONFLICT"
    - from: "flights/aggregation/daily_pnl.py"
      to: "trading.main.trades"
      via: "SELECT WHERE status = 'filled'"
      pattern: "status = 'filled'"
---

<objective>
Build the daily aggregation Flight `daily-pnl-aggregation`: a Python program on MotherDuck
compute that reads the `trades` table, aggregates the prior trading day's filled trades into
per-strategy / per-account daily metrics (realized_pnl, trade_count, win_count, and the
schema's sharpe_7d / max_drawdown columns), and writes them to `daily_pnl` idempotently so a
re-run on the same date overwrites rather than duplicates.

This Flight is independent of the secrets and execution Flights — it touches no Alpaca
credentials, only MotherDuck data — so it can be built and verified in parallel (Wave 1).

Purpose: Produce the aggregated `daily_pnl` rows that Phase 3's equity-curve and
strategy-comparison Dives depend on, on an automatic post-market schedule.
Output: A pinned-dependency aggregation Flight, deployed and verified idempotent.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/REQUIREMENTS.md
@.planning/research/FEATURES.md
@.planning/research/PITFALLS.md
@.planning/research/STACK.md
</context>

<design_notes>
- **Flight source** lives at `flights/aggregation/daily_pnl.py` (versioned, reviewable);
  deployed via the MotherDuck Flight mechanism.
- **Schema target (SCHEMA-04):** `trading.main.daily_pnl` with composite PK
  (date, strategy_name, account_name) and columns realized_pnl, trade_count, win_count,
  sharpe_7d, max_drawdown. The Flight runs `CREATE TABLE IF NOT EXISTS` matching this DDL
  before inserting (Phase 1 may already create it; the IF NOT EXISTS guard makes the Flight
  self-sufficient and matches Phase 1, not redefines it differently).
- **Prior trading day (AGG-02):** aggregate trades whose `filled_at::DATE` equals the prior
  trading day and `status = 'filled'`. Use `CURRENT_DATE - INTERVAL 1 DAY` for the date stamp;
  because the Flight runs Mon-Fri at 6 PM ET, "prior trading day" for a Monday run is the
  preceding Friday — note this in the SUMMARY but a simple `- 1 DAY` is acceptable for v1.0
  (weekend runs are not scheduled, so Monday aggregates Friday only if a Friday run is
  separately scheduled; document the chosen interpretation and keep it consistent).
- **Idempotency (AGG-05):** use
  `INSERT INTO trading.main.daily_pnl (...) SELECT ... ON CONFLICT (date, strategy_name,
  account_name) DO UPDATE SET realized_pnl = EXCLUDED.realized_pnl, trade_count =
  EXCLUDED.trade_count, win_count = EXCLUDED.win_count, sharpe_7d = EXCLUDED.sharpe_7d,
  max_drawdown = EXCLUDED.max_drawdown`. NOTE: PITFALLS #4 / DuckDB bug #16698 forbids
  `DO UPDATE SET <conflict_col> = ...` ON THE CONFLICT-KEY columns (date/strategy_name/
  account_name). Here we DO UPDATE only NON-key metric columns, which is safe and is exactly
  what AGG-05 requires. Do NOT update any of the three PK columns in the SET clause.
- **sharpe_7d / max_drawdown:** SCHEMA-04 includes these columns. The FEATURES.md example
  computes only realized_pnl/trade_count/win_count. Compute sharpe_7d (7-day rolling Sharpe of
  daily realized_pnl per strategy/account) and max_drawdown (max peak-to-trough of cumulative
  daily realized_pnl) in SQL from `daily_pnl`'s own history for the trailing window; if
  insufficient history exists, write NULL for those two columns rather than a wrong value. Do
  NOT drop these columns or stub them with a hardcoded constant.
- **Auth (AGG-06):** Flight uses `access_token_name` = service account token (PITFALLS #1);
  connects via `duckdb.connect("md:")` (token auto-injected). No Alpaca creds involved.
- **Schedule (AGG-03):** `schedule_cron` = `"0 23 * * 1-5"` (6 PM ET summer / UTC-4); winter is
  `"0 22 * * 1-5"` (UTC-5). Record the active value + DST note in the SUMMARY.
- **Deps (AGG-04):** `requirements_txt` pins `duckdb==1.5.2` only (no Alpaca SDK needed).
</design_notes>

<artifacts_this_phase_produces>
This plan creates:
- **Flight (live, in MotherDuck):** `daily-pnl-aggregation`
- **Files:** `flights/aggregation/daily_pnl.py`, `flights/aggregation/requirements.txt`
- **Function:** `flights/aggregation/daily_pnl.main()`
- **SQL object written:** rows in `trading.main.daily_pnl`
- **Convention:** Flight cron `"0 23 * * 1-5"` (summer) / `"0 22 * * 1-5"` (winter)
</artifacts_this_phase_produces>

<phase1_dependency_note>
Assumes Phase 1 created `trading.main.trades` (SCHEMA-01: status, pnl, filled_at, strategy_name,
account_name) and `trading.main.daily_pnl` (SCHEMA-04). Phase 1 is NOT yet built. The Flight's
`CREATE TABLE IF NOT EXISTS daily_pnl` guard uses the SCHEMA-04 DDL so the Flight works even if
run before/after the Phase 1 logger first writes. If Phase 1 ships different daily_pnl column
names, reconcile the aggregation SQL to the shipped schema. Until Phase 1 produces filled
trades, a live run will write zero rows — that is correct, not a failure.
</phase1_dependency_note>

<tasks>

<task type="auto">
  <name>Task 1: Write the daily_pnl aggregation Flight entrypoint and requirements</name>
  <files>flights/aggregation/daily_pnl.py, flights/aggregation/requirements.txt</files>
  <read_first>
    - .planning/REQUIREMENTS.md (SCHEMA-04 daily_pnl columns; AGG-01..06)
    - .planning/research/FEATURES.md (the build pattern example + daily_pnl DDL)
    - .planning/research/PITFALLS.md (#4 ON CONFLICT — DO UPDATE only on non-key cols; #7 6PM ET, filter status='filled')
    - .planning/research/STACK.md (duckdb==1.5.2 pin, duckdb.connect("md:"))
  </read_first>
  <action>
    Create `flights/aggregation/requirements.txt` pinning exactly `duckdb==1.5.2`. Create
    `flights/aggregation/daily_pnl.py` with `def main():` that connects via
    `duckdb.connect("md:")`, runs `CREATE TABLE IF NOT EXISTS trading.main.daily_pnl` with the
    SCHEMA-04 columns and composite PK (date, strategy_name, account_name), then runs an
    `INSERT INTO trading.main.daily_pnl (date, strategy_name, account_name, realized_pnl,
    trade_count, win_count, sharpe_7d, max_drawdown) SELECT ... FROM trading.main.trades WHERE
    status = 'filled' AND filled_at::DATE = CURRENT_DATE - INTERVAL 1 DAY GROUP BY
    strategy_name, account_name` with `date = CURRENT_DATE - INTERVAL 1 DAY`. Compute
    realized_pnl = SUM(pnl), trade_count = COUNT(*), win_count = SUM(CASE WHEN pnl > 0 THEN 1
    ELSE 0 END); compute sharpe_7d and max_drawdown from the trailing daily_pnl history per
    strategy/account (NULL when insufficient history). End the statement with
    `ON CONFLICT (date, strategy_name, account_name) DO UPDATE SET realized_pnl =
    EXCLUDED.realized_pnl, trade_count = EXCLUDED.trade_count, win_count = EXCLUDED.win_count,
    sharpe_7d = EXCLUDED.sharpe_7d, max_drawdown = EXCLUDED.max_drawdown` — never updating any
    PK column. Print the number of rows affected.
  </action>
  <verify>
    <automated>test -f flights/aggregation/requirements.txt && grep -q 'duckdb==1.5.2' flights/aggregation/requirements.txt && python -c "import ast; t=ast.parse(open('flights/aggregation/daily_pnl.py').read()); fns=[n.name for n in ast.walk(t) if isinstance(n,ast.FunctionDef)]; assert 'main' in fns; s=open('flights/aggregation/daily_pnl.py').read(); assert ('duckdb.connect(\"md:\")' in s or \"duckdb.connect('md:')\" in s); assert \"status = 'filled'\" in s; assert 'ON CONFLICT (date, strategy_name, account_name)' in s; assert 'DO UPDATE' in s; print('PASS')"</automated>
  </verify>
  <acceptance_criteria>
    - `requirements.txt` pins exactly `duckdb==1.5.2` (AGG-04).
    - `main()` connects via `duckdb.connect("md:")` and reads `trading.main.trades`, writes `trading.main.daily_pnl` (AGG-01).
    - The SELECT filters `WHERE status = 'filled'` and the prior trading day via `filled_at::DATE = CURRENT_DATE - INTERVAL 1 DAY` (AGG-02).
    - The INSERT ends with `ON CONFLICT (date, strategy_name, account_name) DO UPDATE SET ...` updating only the five non-key metric columns (AGG-05); no PK column appears in the SET clause.
    - sharpe_7d and max_drawdown are computed (or NULL on insufficient history), never a hardcoded constant.
  </acceptance_criteria>
  <done>daily_pnl.main() aggregates filled prior-day trades into daily_pnl idempotently; deps pinned.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking-human">
  <name>Task 2: Deploy daily-pnl-aggregation Flight and verify idempotency</name>
  <read_first>
    - flights/aggregation/daily_pnl.py, flights/aggregation/requirements.txt
    - .planning/REQUIREMENTS.md (AGG-03 cron, AGG-06 access_token_name; Phase 2 success criterion 4)
    - .planning/research/PITFALLS.md (#1 service account token, #5 pin duckdb, #7 6PM ET schedule)
  </read_first>
  <what-built>
    A Flight named `daily-pnl-aggregation` whose source is `flights/aggregation/daily_pnl.py`,
    `requirements_txt` = `flights/aggregation/requirements.txt`, `access_token_name` = the
    service account token (NOT a personal token — PITFALLS #1), and `schedule_cron` =
    `"0 23 * * 1-5"` (6 PM ET summer; winter `"0 22 * * 1-5"`). Deploy via the MotherDuck
    Flight mechanism (MCP create_flight / SQL MD_CREATE_FLIGHT).
  </what-built>
  <how-to-verify>
    1. Confirm the Flight exists with the 6 PM ET cron and a SERVICE-ACCOUNT access_token_name.
    2. Manually trigger `daily-pnl-aggregation`. If `trades` already has filled rows for the
       prior day, confirm `trading.main.daily_pnl` gains rows (one per strategy/account with
       filled trades). If `trades` has no prior-day filled rows yet (Phase 1 not yet producing
       data), confirm the Flight completes with zero rows and no error — that is correct.
    3. Record the daily_pnl row count, then trigger the Flight a SECOND time for the same date.
       Confirm the row count is unchanged (idempotent overwrite, not duplicate) — Phase 2
       success criterion 4.
    4. Spot-check one row: realized_pnl = sum of that strategy's filled pnl for the day,
       win_count = count of pnl > 0; sharpe_7d / max_drawdown populated or NULL (not a constant).
  </how-to-verify>
  <acceptance_criteria>
    - The `daily-pnl-aggregation` Flight exists with cron `"0 23 * * 1-5"` (or winter equivalent) and a service-account access_token_name (AGG-03, AGG-06).
    - First run writes daily_pnl rows for prior-day filled trades (or zero rows cleanly if none exist).
    - A second run on the same date leaves the row count unchanged (idempotent — AGG-05, success criterion 4).
    - A spot-checked row's realized_pnl/win_count match the underlying filled trades.
  </acceptance_criteria>
  <resume-signal>Type "approved" once the Flight ran, wrote correct daily_pnl rows (or zero cleanly), and a re-run left the count unchanged, or describe failures.</resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| MotherDuck access token → daily-pnl-aggregation Flight | service-account token injected at runtime |
| Flight → MotherDuck tables | reads trades, writes daily_pnl |

This Flight handles NO Alpaca credentials — the credential-exposure threat surface is limited
to the MotherDuck access token.

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-04-01 | Spoofing | Personal MotherDuck token used instead of service account | mitigate | access_token_name set to a service-account token (PITFALLS #1); Task 2 verifies token type |
| T-02-04-02 | Tampering | Re-run duplicates daily_pnl rows | mitigate | `ON CONFLICT (date, strategy_name, account_name) DO UPDATE` on non-key columns only (AGG-05); Task 2 verifies row count stable on re-run |
| T-02-04-03 | Tampering | DuckDB bug #16698 corrupts rows via DO UPDATE on conflict column | mitigate | SET clause updates only the five non-key metric columns; never the PK columns (PITFALLS #4) |
| T-02-04-04 | Information Disclosure | Unfilled/pending trades pollute P&L | mitigate | `WHERE status = 'filled'` filter (AGG-02) |
| T-02-04-05 | Tampering | Unpinned duckdb grabs incompatible PyPI version, Flight fails | mitigate | `duckdb==1.5.2` pinned in requirements.txt (AGG-04, PITFALLS #5) |
| T-02-04-SC | Tampering | duckdb pip install in Flight | mitigate | duckdb is first-party/well-known, pinned to 1.5.2; no [ASSUMED]/[SUS] packages introduced |
</threat_model>

<verification>
- daily_pnl.main() reads trades (status='filled', prior day) and writes daily_pnl with ON CONFLICT DO UPDATE on non-key columns (AGG-01/02/05).
- requirements.txt pins duckdb==1.5.2 (AGG-04).
- Live: Flight deployed with 6 PM ET cron + service-account token (AGG-03/06); re-run is idempotent (Task 2 checkpoint).
</verification>

<success_criteria>
- daily-pnl-aggregation Flight reads trades and writes daily_pnl (AGG-01).
- Aggregates only filled trades for the prior trading day (AGG-02).
- Scheduled 6 PM ET Mon-Fri (AGG-03); duckdb==1.5.2 pinned (AGG-04).
- Idempotent re-run via ON CONFLICT DO UPDATE (AGG-05); service-account access_token_name (AGG-06).
</success_criteria>

<output>
Create `.planning/phases/02-flights/02-04-SUMMARY.md` when done. Record the deployed Flight name,
active cron (+ DST note), and the idempotency verification result.
</output>
