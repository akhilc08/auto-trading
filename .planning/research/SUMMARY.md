# Project Research Summary

**Project:** auto-trading — MotherDuck Cloud Deployment (v1.0 milestone)
**Researched:** 2026-06-03 (via MotherDuck MCP tools — authoritative)
**Confidence:** HIGH

## Executive Summary

This milestone adds a cloud observability and analytics layer to a working Alpaca-based algo trading system. The architecture uses three MotherDuck products: (1) Python writes trade fills and position snapshots to **MotherDuck** from GitHub Actions, (2) a **MotherDuck Flight** runs post-market on MotherDuck compute to aggregate daily P&L (no extra infra needed), and (3) **MotherDuck Dives** provide interactive visualizations querying live data.

**Flights IS a real, shipping product** — a Python program that runs on MotherDuck compute (2 CPU, 16GB RAM) with pip packages and a cron schedule. This makes the aggregation pipeline cleaner: the Flight runs directly on MotherDuck, no GitHub Actions cron needed for it. Strategy execution stays in GitHub Actions because Alpaca API keys require encrypted secrets (Flight `config` is not encrypted).

The integration is entirely additive. New file: `core/motherduck_logger.py`. Minimal edits: `core/order_manager.py` (optional `md_logger=None` param) and `runner.py` (construct logger, pass to OrderManager, call snapshots after run). Zero strategy files change.

---

## Key Findings

### Stack
- Only new dependency: `duckdb==1.5.2` (pin exactly for Flight reproducibility)
- MotherDuck extension bundled in standard `duckdb` pip package
- Flights: Python on MotherDuck compute, `duckdb.connect("md:")` auto-picks up `MOTHERDUCK_TOKEN`
- Dives: React components with `useSQLQuery` (rows are `data` directly — no `.data.rows`)
- GitHub Actions: `timezone: "America/New_York"` now supported on crons (March 2026)

### Features
- **Flights** handle daily P&L aggregation (runs at 6 PM ET; filters `WHERE status = 'filled'`)
- **4 Dives**: trade log (LOW), live positions (LOW), equity curve (LOW-MEDIUM), strategy comparison (MEDIUM-HIGH)
- Schema must include `strategy_name`, `account_name`, `TIMESTAMPTZ` from row 1 — cannot be retrofitted
- Win rate requires `pnl` column computed in Python at fill time (not SQL-derived)

### Architecture
- **Injection point**: `OrderManager` (not `BaseStrategy`) — all orders from all 13 strategies flow through 5 methods
- **Snapshot timing**: after `run_cron()` exits, pull positions from Alpaca and write snapshot
- **3 GitHub Actions workflow files** (not 13): one per account (`stat_arb.yml`, `macro_vol.yml`, `trend_following.yml`) with matrix jobs
- **1 Flight**: `daily-pnl-aggregation`, `schedule_cron: "0 23 * * 1-5"` (6 PM ET summer)
- MotherDuck database name: `trading`; all tables in `main` schema

### Critical Pitfalls
1. **Flight `config` is not encrypted** — Alpaca keys must stay in GitHub Actions secrets only
2. **Service account token** (not personal) for both GitHub secret and Flight `access_token_name`
3. **Schema columns from day one** — `strategy_name`, `account_name`, `TIMESTAMPTZ`; retrofitting leaves NULLs
4. **Idempotent inserts** — `ON CONFLICT (order_id) DO NOTHING`; do NOT use `DO UPDATE` on conflict column (DuckDB bug #16698)
5. **Pin duckdb** in Flight `requirements_txt` — unpinned grabs incompatible PyPI version
6. **Flight cron at 6 PM ET** — not 4:30 PM; fills are async, need lag before aggregating
7. **GitHub Actions 60-day auto-disable** — monitor `portfolio_snapshots` for missing days
8. **Dive table names**: always `"trading"."main"."trades"` (fully qualified, double-quoted)
9. **No arbitrary Tailwind** in Dives — `style={{}}` for custom colors, not `bg-[#hex]`

---

## Implications for Roadmap

5-phase structure:

| Phase | Deliverable | Key files |
|-------|-------------|-----------|
| 1 | Schema + Logger | `core/motherduck_logger.py`, `requirements.txt` |
| 2 | Integration | `core/order_manager.py`, `runner.py` |
| 3 | GitHub Actions | `.github/workflows/stat_arb.yml`, `macro_vol.yml`, `trend_following.yml` |
| 4 | Flight | `daily-pnl-aggregation` Flight (created via MCP) |
| 5 | Dives | 4 Dives created via MCP after real data exists |

Build order is strict: each phase depends on the previous. Schema must exist before logger; logger before GitHub Actions; real trade data before Flight makes sense; all upstream data before Dives.

---

## Confidence Assessment

| Area | Confidence | Source |
|------|------------|--------|
| Flights (real product) | HIGH | MotherDuck MCP `get_flight_guide` — authoritative |
| Dives (real product) | HIGH | MotherDuck MCP `get_dive_guide` — authoritative |
| Flight config unencrypted | HIGH | Explicitly stated in flight guide |
| duckdb version pin | HIGH | Flight guide explicitly warns about unpinned versions |
| GitHub Actions structure | HIGH | Code inspection of existing repo |
| Integration points | HIGH | Code inspection — OrderManager confirmed as single injection point |
| Schema design | MEDIUM | Standard trading conventions; no official MotherDuck trading schema reference |

---

*Research completed: 2026-06-03 via MotherDuck MCP tools*
*Ready for roadmap: yes*
