---
phase: 02-flights
plan: 02
type: execute
wave: 2
depends_on: ["02-01"]
files_modified:
  - flights/exec/_runner.py
  - flights/exec/_logger.py
  - flights/exec/requirements.txt
  - flights/exec/exec_stat_arb.py
autonomous: false
requirements: [EXEC-01, EXEC-04, EXEC-05, EXEC-06, EXEC-07, EXEC-08, SECRETS-02, SECRETS-03]
user_setup:
  - service: alpaca
    why: "Per-account Alpaca paper API credentials, stored as MotherDuck secrets in plan 02-01"
    env_vars:
      - name: MOTHERDUCK_TOKEN
        source: "MotherDuck Settings -> Service Accounts (service account token, not personal)"
must_haves:
  truths:
    - "A MotherDuck Flight named exec-stat-arb exists with the stat_arb account's five strategies bundled in its source"
    - "exec-stat-arb reads Alpaca credentials from the alpaca_stat_arb MotherDuck secret and connects to Alpaca"
    - "Triggering exec-stat-arb during market hours writes trades, positions, and portfolio_snapshots rows"
    - "Triggering exec-stat-arb when the market is closed exits cleanly with no orders"
  artifacts:
    - path: "flights/exec/_runner.py"
      provides: "Reusable execution-Flight scaffold: market-hours guard, strategy loop, snapshot/fill handling"
      min_lines: 40
    - path: "flights/exec/_logger.py"
      provides: "Inline MotherDuckLogger logic bundled for Flight runtime (mirrors Phase 1 core/motherduck_logger.py)"
      min_lines: 40
    - path: "flights/exec/exec_stat_arb.py"
      provides: "exec-stat-arb Flight entrypoint: def main() running the five stat_arb strategies"
      contains: "def main"
    - path: "flights/exec/requirements.txt"
      provides: "Pinned Flight deps"
      contains: "duckdb==1.5.2"
  key_links:
    - from: "flights/exec/exec_stat_arb.py"
      to: "alpaca_stat_arb secret"
      via: "duckdb secret read-back -> Alpaca TradingClient"
      pattern: "alpaca_stat_arb"
    - from: "flights/exec/_runner.py"
      to: "get_clock().is_open"
      via: "market-hours guard"
      pattern: "is_open"
    - from: "flights/exec/_logger.py"
      to: "trading.main.trades"
      via: "duckdb.connect('md:') INSERT ON CONFLICT"
      pattern: "ON CONFLICT"
---

<objective>
Build the reusable execution-Flight scaffold and the first execution Flight, `exec-stat-arb`,
which runs the five stat_arb-account strategies (stat_arb, stat_arb_v2, stat_arb_v3,
market_neutral, market_neutral_v2) entirely on MotherDuck compute. The Flight reads Alpaca
credentials from the `alpaca_stat_arb` secret (plan 02-01), connects to Alpaca, runs each
strategy's logic, and writes trades/positions/portfolio_snapshots to MotherDuck via inline
logger logic. A market-hours guard makes the Flight a no-op when the market is closed.

This plan establishes the shared scaffold (`_runner.py`, `_logger.py`, `requirements.txt`)
that plan 02-03 reuses for the other two execution Flights, so it is sequenced first.

Purpose: Move the most complex account's execution off any local runner / GitHub Actions and
onto a scheduled Flight — proving the full path (secret -> Alpaca -> strategy -> MotherDuck
writes) end to end.
Output: Reusable execution scaffold + bundled logger + the live `exec-stat-arb` Flight.
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
@.planning/research/ARCHITECTURE.md
@.planning/research/STACK.md
@.planning/research/PITFALLS.md
@.planning/research/FEATURES.md
@.planning/phases/02-flights/02-01-secrets-PLAN.md
@core/alpaca_client.py
@core/order_manager.py
@core/scheduler.py
@core/base_strategy.py
@strategies/stat_arb/strategy.py
@strategies/stat_arb/config.py
</context>

<design_notes>
Honor these phase-wide decisions (no CONTEXT.md/RESEARCH.md for the phase):

- **Flight source lives in the repo** under `flights/exec/` so it is reviewable and versioned;
  the live Flight is created/deployed by uploading this source via the MotherDuck Flight
  mechanism. The bundled `_runner.py` / `_logger.py` are imported by each Flight entrypoint.
- **Bundled, not imported from core/:** Flights run on MotherDuck compute and cannot import the
  repo's `core/` package unless it is bundled into the Flight source. EXEC-05 says the logger
  logic is "bundled inline." `flights/exec/_logger.py` re-implements the Phase 1
  `MotherDuckLogger` write logic (CREATE TABLE IF NOT EXISTS guard, log_order with
  `INSERT ... ON CONFLICT (order_id) DO NOTHING`, snapshot_positions, snapshot_portfolio) so
  the Flight is self-contained. It targets the SAME tables Phase 1 defines
  (`trading.main.trades/positions/portfolio_snapshots`). It does NOT redefine the Phase 1
  schema differently — it uses CREATE TABLE IF NOT EXISTS matching Phase 1's DDL.
- **Strategy code IS imported** from the repo's `strategies/` package when bundled into the
  Flight source. The Flight bundle includes `strategies/` + `core/base_strategy.py` so each
  strategy class instantiates and `on_bar()` runs. Do NOT modify any strategy file.
- **Account/strategy grouping** follows EXEC-01 exactly: account `stat_arb` =
  [stat_arb, stat_arb_v2, stat_arb_v3, market_neutral, market_neutral_v2]. Secret name
  `alpaca_stat_arb` (from plan 02-01).
- **Scheduling (EXEC-06):** every strategy here is daily (`INTERVAL = "1d"`, fires 16:05 ET
  after close). Set the Flight `schedule_cron` to run once on Mon-Fri shortly after the close:
  `"5 20 * * 1-5"` UTC summer (16:05 ET / UTC-4) — note winter is `"5 21 * * 1-5"` (UTC-5).
  Record the chosen cron + DST note in the SUMMARY. The Flight calls each strategy's `on_bar()`
  once per run (not via APScheduler — the Flight schedule replaces the local scheduler).
- **Market guard (EXEC-07):** call `alpaca.get_clock().is_open` once at the top of `main()`;
  if False, log "market closed — exiting, no orders" and return before instantiating strategies.
- **Alpaca connection (EXEC-04):** read `api_key`/`secret_key` from the `alpaca_stat_arb` secret
  using the read-back call confirmed in plan 02-01 SUMMARY, then build a paper TradingClient +
  data client (mirror `core/alpaca_client.AlpacaClient`, but source keys from the secret, not
  os.environ). Use paper mode.
- **Fill handling:** after running all strategies, poll Alpaca for fills and update trade rows
  (mirror the Phase 1 update_fill contract: filled_at, filled_avg_price, computed pnl), then
  write position + portfolio snapshots. This satisfies success criterion 2 (trades, positions,
  portfolio_snapshots rows).
</design_notes>

<artifacts_this_phase_produces>
This plan creates:
- **Flight (live, in MotherDuck):** `exec-stat-arb`
- **Files:** `flights/exec/_runner.py`, `flights/exec/_logger.py`, `flights/exec/exec_stat_arb.py`, `flights/exec/requirements.txt`
- **Functions:** `flights/exec/_runner.run_account_flight(account_name, strategy_names, secret_name)`, `flights/exec/exec_stat_arb.main()`
- **Class:** `flights/exec/_logger.FlightLogger` (bundled MotherDuck write logic)
- **Convention:** account secret read via `alpaca_<account>`; Flight cron `"5 20 * * 1-5"` (summer) / `"5 21 * * 1-5"` (winter)
</artifacts_this_phase_produces>

<phase1_dependency_note>
This plan assumes Phase 1 (Schema, Logger & Integration) has defined the tables
`trading.main.trades`, `trading.main.positions`, `trading.main.portfolio_snapshots` and the
`MotherDuckLogger` write contracts (log_order ON CONFLICT DO NOTHING, update_fill,
snapshot_positions, snapshot_portfolio). Phase 1 is NOT yet built. `flights/exec/_logger.py`
must MATCH the Phase 1 schema (SCHEMA-01/02/03 column lists in REQUIREMENTS.md) and Phase 1
write semantics. If Phase 1 ships a `core/motherduck_logger.py` whose column names or conflict
clause differ from REQUIREMENTS.md, reconcile `_logger.py` to the shipped Phase 1 version
before deploying the Flight. Acceptance criteria below assert the column lists from
REQUIREMENTS.md as the source of truth.
</phase1_dependency_note>

<tasks>

<task type="auto">
  <name>Task 1: Build bundled logger + Flight requirements (the write layer)</name>
  <files>flights/exec/_logger.py, flights/exec/requirements.txt</files>
  <read_first>
    - .planning/REQUIREMENTS.md (SCHEMA-01/02/03 column lists; EXEC-05; EXEC-08; AGG/INSERT semantics)
    - .planning/research/PITFALLS.md (#3 schema columns day one, #4 ON CONFLICT DO NOTHING not DO UPDATE, #9 UTC timestamps)
    - .planning/research/STACK.md (duckdb==1.5.2 pin, duckdb.connect("md:"))
    - core/alpaca_client.py (the AlpacaClient interface the logger snapshots from)
  </read_first>
  <action>
    Create `flights/exec/requirements.txt` pinning `duckdb==1.5.2` and `alpaca-py>=0.8.0`
    (matches repo requirements.txt; alpaca-trade-api per EXEC-08 — use the SDK the strategies
    already import, which is alpaca-py). Create `flights/exec/_logger.py` with a `FlightLogger`
    class taking a live `duckdb.connect("md:")` connection. It runs `CREATE TABLE IF NOT EXISTS`
    for `trading.main.trades`, `positions`, `portfolio_snapshots` using the exact SCHEMA-01/02/03
    columns and types (order_id VARCHAR PK; strategy_name, account_name, symbol, side, qty,
    submitted_at TIMESTAMPTZ, filled_at TIMESTAMPTZ, filled_avg_price, pnl, status). Methods:
    `log_order(order, strategy_name, account_name)` -> `INSERT INTO trading.main.trades ...
    ON CONFLICT (order_id) DO NOTHING` (DO NOTHING only — DuckDB bug #16698, never DO UPDATE on
    the conflict column); `update_fill(order_id, filled_at, filled_avg_price, pnl)`;
    `snapshot_positions(positions, strategy_name, account_name)`;
    `snapshot_portfolio(account, strategy_name, account_name)`. All timestamps use
    `datetime.now(timezone.utc)`.
  </action>
  <verify>
    <automated>test -f flights/exec/requirements.txt && grep -q 'duckdb==1.5.2' flights/exec/requirements.txt && python -c "import ast; t=ast.parse(open('flights/exec/_logger.py').read()); cls=[n for n in ast.walk(t) if isinstance(n,ast.ClassDef) and n.name=='FlightLogger']; assert cls, 'no FlightLogger'; m=[f.name for f in ast.walk(cls[0]) if isinstance(f,ast.FunctionDef)]; assert {'log_order','update_fill','snapshot_positions','snapshot_portfolio'} <= set(m), m; src=open('flights/exec/_logger.py').read(); assert 'ON CONFLICT' in src and 'DO NOTHING' in src and 'DO UPDATE' not in src; print('PASS')"</automated>
  </verify>
  <acceptance_criteria>
    - `requirements.txt` pins `duckdb==1.5.2` (EXEC-08).
    - `FlightLogger` defines `log_order`, `update_fill`, `snapshot_positions`, `snapshot_portfolio`.
    - `log_order` uses `ON CONFLICT (order_id) DO NOTHING`; the file contains NO `DO UPDATE`.
    - `CREATE TABLE IF NOT EXISTS` statements use the SCHEMA-01/02/03 column lists and `TIMESTAMPTZ` for `submitted_at`/`filled_at`/`snapshot_at`.
  </acceptance_criteria>
  <done>FlightLogger writes to the Phase 1 tables with idempotent inserts; deps pinned.</done>
</task>

<task type="auto">
  <name>Task 2: Build the reusable execution scaffold (_runner.py) and the exec-stat-arb entrypoint</name>
  <files>flights/exec/_runner.py, flights/exec/exec_stat_arb.py</files>
  <read_first>
    - flights/exec/_logger.py (FlightLogger from Task 1)
    - flights/secrets/create_secrets.sql + .planning/phases/02-flights/02-01-SUMMARY.md (secret read-back call)
    - core/scheduler.py (run_cron job structure — on_bar(bars) call pattern to mirror once)
    - core/alpaca_client.py (TradingClient/data client construction to mirror, keys from secret)
    - strategies/stat_arb/strategy.py + config.py (how a strategy is instantiated and on_bar called)
    - .planning/REQUIREMENTS.md (EXEC-01, EXEC-04, EXEC-05, EXEC-06, EXEC-07)
  </read_first>
  <action>
    Create `flights/exec/_runner.py` with
    `run_account_flight(account_name, strategy_names, secret_name)`. It: (1) connects
    `duckdb.connect("md:")`; (2) reads `api_key`/`secret_key` from `secret_name` via the
    plan-02-01 read-back call; (3) builds a paper Alpaca TradingClient + StockHistoricalDataClient
    from those keys (mirror core/alpaca_client.AlpacaClient but keys from secret); (4) calls
    `trading.get_clock().is_open` — if closed, log "market closed — exiting, no orders" and
    return immediately (EXEC-07); (5) constructs a `FlightLogger(con)`; (6) for each strategy
    name: import `strategies.<name>.strategy` + `config`, find the BaseStrategy subclass
    (mirror runner.py discovery), instantiate with an OrderManager whose order methods call
    `FlightLogger.log_order(...)`, fetch latest bars, call `on_bar(bars)` once; (7) after all
    strategies, poll Alpaca for fills and `update_fill(...)`, then `snapshot_positions(...)` and
    `snapshot_portfolio(...)` for the account. Then create `flights/exec/exec_stat_arb.py` with
    `def main():` that calls
    `run_account_flight("stat_arb", ["stat_arb","stat_arb_v2","stat_arb_v3","market_neutral","market_neutral_v2"], "alpaca_stat_arb")`.
    Do NOT modify any file under strategies/ or core/.
  </action>
  <verify>
    <automated>python -c "import ast; r=ast.parse(open('flights/exec/_runner.py').read()); fns=[n.name for n in ast.walk(r) if isinstance(n,ast.FunctionDef)]; assert 'run_account_flight' in fns; rsrc=open('flights/exec/_runner.py').read(); assert 'is_open' in rsrc and ('duckdb.connect(\"md:\")' in rsrc or \"duckdb.connect('md:')\" in rsrc); e=ast.parse(open('flights/exec/exec_stat_arb.py').read()); efns=[n.name for n in ast.walk(e) if isinstance(n,ast.FunctionDef)]; assert 'main' in efns; esrc=open('flights/exec/exec_stat_arb.py').read(); assert 'alpaca_stat_arb' in esrc; [s in esrc or print('warn',s) for s in ['stat_arb_v2','stat_arb_v3','market_neutral']]; print('PASS')"</automated>
  </verify>
  <acceptance_criteria>
    - `_runner.run_account_flight` connects via `duckdb.connect("md:")`, reads the named secret, and calls `get_clock().is_open` as an early guard that returns with no orders when closed (EXEC-07).
    - `exec_stat_arb.main()` invokes `run_account_flight` with account `stat_arb`, all five EXEC-01 strategy names, and secret `alpaca_stat_arb` (EXEC-01, SECRETS-03).
    - No file under `strategies/` or `core/` is modified (git diff shows only files under `flights/`).
  </acceptance_criteria>
  <done>exec_stat_arb.main() runs the five strategies through the scaffold, guarded by market hours, writing via FlightLogger.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking-human">
  <name>Task 3: Deploy exec-stat-arb Flight and verify end-to-end against MotherDuck</name>
  <read_first>
    - flights/exec/exec_stat_arb.py, flights/exec/_runner.py, flights/exec/_logger.py, flights/exec/requirements.txt
    - .planning/phases/02-flights/02-01-SUMMARY.md (secrets must exist first)
    - .planning/REQUIREMENTS.md (Phase 2 success criteria 2 and 3)
  </read_first>
  <what-built>
    A Flight named `exec-stat-arb` whose source is `flights/exec/exec_stat_arb.py` (with
    `_runner.py`, `_logger.py`, the `strategies/` package, and `core/base_strategy.py` bundled),
    `requirements_txt` = `flights/exec/requirements.txt`, `access_token_name` = the service
    account token, and `schedule_cron` = `"5 20 * * 1-5"` (summer; winter `"5 21 * * 1-5"`).
    Deploy it via the MotherDuck Flight mechanism (MCP create_flight / SQL MD_CREATE_FLIGHT).
  </what-built>
  <how-to-verify>
    1. Confirm the three secrets from plan 02-01 exist (run verify_secrets.py).
    2. Manually trigger `exec-stat-arb` during market hours (or with a temporary forced run).
       Confirm it completes without error and that `trading.main.trades`,
       `trading.main.positions`, and `trading.main.portfolio_snapshots` gain rows with
       `strategy_name` in the five stat_arb strategies and `account_name = 'stat_arb'`
       (Phase 2 success criterion 2).
    3. Manually trigger `exec-stat-arb` when the market is CLOSED. Confirm the Flight log shows
       "market closed — exiting, no orders" and NO new trades rows appear
       (Phase 2 success criterion 3).
    4. Confirm no Alpaca key/secret value appears in the Flight source, config, or logs.
  </how-to-verify>
  <acceptance_criteria>
    - The `exec-stat-arb` Flight exists in MotherDuck with the cron above and access_token_name set.
    - A market-hours run produces trades/positions/portfolio_snapshots rows tagged with account_name='stat_arb'.
    - A market-closed run logs the closed message and produces zero new trades rows.
    - No plaintext Alpaca credential appears in Flight source/config/logs.
  </acceptance_criteria>
  <resume-signal>Type "approved" once the market-hours run wrote rows and the market-closed run exited cleanly, or describe failures.</resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| MotherDuck secret store → exec-stat-arb Flight | Alpaca credentials read at runtime |
| exec-stat-arb Flight → Alpaca API | order submission with account credentials |
| Flight → MotherDuck tables | trade/position writes |
| repo (git) → public | Flight source must contain no plaintext credentials |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-02-01 | Information Disclosure | Alpaca keys leak into Flight source/config | mitigate | Keys read only from `alpaca_stat_arb` secret at runtime; Task 3 verifies no key appears in source/config/logs (SECRETS-02) |
| T-02-02-02 | Information Disclosure | Flight logs print credentials | mitigate | `_runner.py` logs only strategy/account names; never logs the key/secret values |
| T-02-02-03 | Elevation of Privilege | Flight reads another account's credentials | mitigate | Flight passes only `alpaca_stat_arb`; per-account scoping from plan 02-01 (SECRETS-03) |
| T-02-02-04 | Tampering | Duplicate trade rows on Flight re-run | mitigate | `log_order` uses `ON CONFLICT (order_id) DO NOTHING`; re-trigger does not duplicate |
| T-02-02-05 | Denial of Service | Flight runs and trades when market closed | mitigate | `get_clock().is_open` early-return guard (EXEC-07); Task 3 verifies zero orders when closed |
| T-02-02-SC | Tampering | duckdb / alpaca-py pip install in Flight | mitigate | duckdb pinned `==1.5.2`, alpaca-py is the package already in repo requirements.txt; both first-party/well-known, no [ASSUMED]/[SUS] packages introduced |
</threat_model>

<verification>
- exec_stat_arb.main() exists and wires the five EXEC-01 strategies with secret alpaca_stat_arb.
- _runner.py has the is_open market guard and duckdb.connect("md:") write path.
- _logger.py uses ON CONFLICT DO NOTHING and the SCHEMA-01/02/03 columns.
- Live: market-hours run writes rows; market-closed run writes nothing (Task 3 checkpoint).
- No file under strategies/ or core/ modified.
</verification>

<success_criteria>
- exec-stat-arb Flight runs the five stat_arb strategies on MotherDuck compute (EXEC-01).
- Reads Alpaca creds from alpaca_stat_arb secret and connects to Alpaca (EXEC-04, SECRETS-02/03).
- Writes trades, positions, portfolio_snapshots via bundled logger (EXEC-05).
- Scheduled at the post-close market cron (EXEC-06); exits cleanly when market closed (EXEC-07).
- duckdb==1.5.2 pinned in requirements (EXEC-08).
</success_criteria>

<output>
Create `.planning/phases/02-flights/02-02-SUMMARY.md` when done. Record the deployed Flight
name, chosen cron (+ DST note), and that the scaffold (_runner.py/_logger.py) is reusable by
plan 02-03.
</output>
