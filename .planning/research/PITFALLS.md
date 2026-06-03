# Domain Pitfalls

**Domain:** MotherDuck cloud integration + GitHub Actions deployment for Python trading framework
**Researched:** 2026-06-03 (rewritten via MotherDuck MCP tools — authoritative)

## Critical

### 1. Personal MotherDuck token in CI and Flights
Use a **service account token** (MotherDuck Settings → Service Accounts), not a personal token. Personal tokens are tied to your account lifecycle; a service account token survives account changes and supports non-expiring tokens. If your personal token rotates, all MotherDuck writes silently fail while trades continue executing.
- **Prevention:** Create a service account token. Store it as GitHub secret `MOTHERDUCK_TOKEN`. Set as `access_token_name` in the Flight.
- **Phase:** Schema + Logger (Phase 1)

### 2. Flights `config` is not encrypted — never put API keys there
Flights `config` is a `{string: string}` map exposed as env vars. It is NOT encrypted. Alpaca API keys must NOT go in Flight config. This is why strategy execution stays in GitHub Actions (encrypted secrets) and not in Flights.
- **Prevention:** Flight only needs `MOTHERDUCK_TOKEN` (injected via `access_token_name`). All Alpaca keys in GitHub Actions secrets only.
- **Phase:** GitHub Actions (Phase 3), Flight (Phase 4)

### 3. Schema missing `strategy_name`, `account_name`, `TIMESTAMPTZ` from day one
These columns cannot be added cleanly after data exists — rows written before the column existed get NULL, corrupting all cross-strategy queries and historical P&L. Define the full schema in the initial DDL.
- **Prevention:** Write complete DDL in `_ensure_schema()` before any data is written.
- **Phase:** Schema + Logger (Phase 1)

### 4. Non-idempotent inserts cause duplicates on retry
GitHub Actions jobs can be manually re-run. If `log_order()` uses plain `INSERT`, retries create duplicate rows. DuckDB supports `ON CONFLICT (order_id) DO NOTHING`.
- **Note:** DuckDB bug #16698 — do NOT use `DO UPDATE SET conflict_col = ...` (corrupts rows). Use `DO NOTHING` only.
- **Prevention:** All trade inserts use `INSERT INTO trades ... ON CONFLICT (order_id) DO NOTHING`.
- **Phase:** Schema + Logger (Phase 1)

### 5. Flight DuckDB version not pinned
An unpinned `duckdb` in `requirements_txt` grabs the latest PyPI release, which may not be compatible with MotherDuck. The flight fails at `duckdb.connect("md:")` with a version error.
- **Prevention:** Pin exactly: `duckdb==1.5.2` in `requirements_txt`.
- **Phase:** Flight (Phase 4)

## Moderate

### 6. GitHub Actions cron timezone errors
GitHub Actions cron is UTC. ET is UTC-4 (EDT, summer) or UTC-5 (EST, winter). A cron of `"30 16 * * 1-5"` fires at 12:30 PM ET in summer, 11:30 AM ET in winter — silently wrong. As of March 2026, GitHub supports `timezone: "America/New_York"` on cron schedules which handles DST automatically.
- **Prevention:** Always set `timezone: "America/New_York"` on all workflow cron schedules.
- **Phase:** GitHub Actions (Phase 3)

### 7. Aggregating before fills are confirmed
Strategies submit orders around 4:05 PM ET; fills are async and may take minutes. Running the Flight at 4:30 PM produces incomplete daily P&L. The `daily_pnl` Flight should run at 6 PM ET (UTC `"0 22 * * 1-5"` in winter, `"0 23 * * 1-5"` in summer).
- **Prevention:** Schedule Flight cron at 6 PM ET. Filter `WHERE status = 'filled'` in aggregation SQL.
- **Phase:** Flight (Phase 4)

### 8. GitHub Actions 60-day auto-disable
GitHub silently disables scheduled workflows after 60 days without a code commit. A trading bot that runs daily but sees no pushes will stop executing.
- **Prevention:** Monitor `portfolio_snapshots` for missing days — a missing row means the workflow didn't run. Add data freshness check to the Live Positions Dive or a separate alert.
- **Phase:** Dives (Phase 5), or v1.1

### 9. Timestamps not UTC everywhere
Mixed timezones corrupt daily P&L aggregation. The existing `AlpacaClient` already uses `datetime.now(timezone.utc)` — carry this discipline into `motherduck_logger.py`.
- **Prevention:** All timestamps stored as `TIMESTAMPTZ`, all Python writes use `datetime.now(timezone.utc)`.
- **Phase:** Schema + Logger (Phase 1)

### 10. Flight executemany is slow for bulk loads
The Flights guide explicitly warns against `executemany()` against MotherDuck — it runs row-by-row. For the aggregation Flight this doesn't matter (single aggregation INSERT per run). For the logger writing individual trades it's fine (single-digit to tens of rows per run).
- **Prevention:** For bulk historical loads, use file staging (`/tmp/`, `read_json_auto`). Not needed for this milestone's row volumes.

## Minor

### 11. Dive table names not fully qualified
Dives require fully-qualified, double-quoted table names: `"trading"."main"."trades"`. Using bare `trades` or `main.trades` may work during local preview but fail in the saved Dive runtime which may not have the same database context.
- **Prevention:** Always use `"database"."schema"."table"` format in all `useSQLQuery` calls.
- **Phase:** Dives (Phase 5)

### 12. Time series gaps in equity curve Dive
Recharts does NOT interpolate missing time periods — a gap in `daily_pnl` data produces a gap in the line chart. Fill gaps in SQL with `generate_series` LEFT JOIN.
- **Prevention:** Equity curve query uses `generate_series(start, end, INTERVAL 1 DAY) LEFT JOIN daily_pnl`.
- **Phase:** Dives (Phase 5)

### 13. Arbitrary Tailwind bracket syntax in Dives
`bg-[#f8f8f8]`, `text-[#231f20]`, `w-[300px]` do NOT work in Dives — the runtime cannot resolve them. Use `style={{}}` for custom colors and sizes.
- **Prevention:** Use `style={{color: "#231f20", background: "#f8f8f8"}}` instead of bracket classes.
- **Phase:** Dives (Phase 5)
