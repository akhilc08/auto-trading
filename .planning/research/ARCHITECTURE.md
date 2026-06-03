# Architecture Patterns

**Project:** auto-trading MotherDuck cloud layer
**Researched:** 2026-06-03 (rewritten via MotherDuck MCP tools — authoritative)
**Confidence:** HIGH

## System Overview

```
Alpaca API ──► GitHub Actions (strategy execution)
                  │
                  ├─► core/motherduck_logger.py ──► MotherDuck `trading` DB
                  │         (writes trades, positions, snapshots)
                  │
                  └─► MotherDuck Flight (daily-pnl-aggregation)
                            │ (runs at 6 PM ET on MotherDuck compute)
                            ▼
                       daily_pnl table ──► Dives (equity curve, strategy comparison)
                       
MotherDuck tables (trades, positions) ──► Dives (trade log, live positions)
```

## Integration Points in Existing Code

### `core/motherduck_logger.py` (NEW)
Single new file. Holds the DuckDB connection for one `runner.py` execution lifetime.

```python
class MotherDuckLogger:
    def __init__(self, token: str):
        self.con = duckdb.connect("md:", config={"motherduck_token": token})
        self._ensure_schema()
    
    def _ensure_schema(self): ...   # CREATE TABLE IF NOT EXISTS for all 4 tables
    def log_order(self, order, strategy_name, account_name): ...
    def update_fill(self, order_id, filled_at, filled_avg_price, pnl): ...
    def snapshot_positions(self, positions, strategy_name, account_name): ...
    def snapshot_portfolio(self, account, strategy_name, account_name): ...
```

### `core/order_manager.py` (MODIFIED — minimal)
Add optional `md_logger=None` to `__init__`. Call `md_logger.log_order()` in all 5 order methods after submission. Backward-compatible — all existing callers (tests, local runs) continue working without changes.

```python
class OrderManager:
    def __init__(self, client, logger, md_logger=None):
        self.md_logger = md_logger
        ...
    
    def buy(self, symbol, qty, ...):
        order = self.client.submit_order(...)
        if self.md_logger:
            self.md_logger.log_order(order, self.strategy_name, self.account_name)
        return order
```

**Injection point:** `OrderManager`, not `BaseStrategy`. Every order from all 13 strategies flows through the 5 order methods — single injection point covers everything.

### `runner.py` (MODIFIED — minimal)
Construct logger when `MOTHERDUCK_TOKEN` present, pass to `OrderManager`, call snapshots after `run_cron()` returns, poll fills.

```python
md_logger = None
if os.environ.get("MOTHERDUCK_TOKEN"):
    md_logger = MotherDuckLogger(os.environ["MOTHERDUCK_TOKEN"])

order_manager = OrderManager(client=client, logger=logger, md_logger=md_logger)
strategy = strategy_class(client=client, order_manager=order_manager, ...)

run_cron(strategy, client, config_module)

if md_logger:
    # Snapshot positions and portfolio after run
    positions = client.get_all_positions()
    account = client.get_account()
    md_logger.snapshot_positions(positions, args.strategy, account_name)
    md_logger.snapshot_portfolio(account, args.strategy, account_name)
    # Poll fills for submitted orders
    md_logger.poll_and_update_fills(client)
```

**Zero strategy files change.**

## GitHub Actions Structure

3 workflow files (not 13) — one per account, matrix over that account's strategies:

| Workflow | Account | Strategies |
|----------|---------|-----------|
| `stat_arb.yml` | stat_arb | stat_arb, stat_arb_v2, stat_arb_v3, market_neutral, market_neutral_v2 |
| `macro_vol.yml` | macro_vol | vol_risk_premium |
| `trend_following.yml` | trend_following | trend_following, trend_following_v2, multi_factor_equity, multi_factor_equity_v2, regime_switching, post_earnings_drift, rl_alpha, deep_learning, alt_data_fusion |

Each workflow:
- Matrix job per strategy in that account
- `fail-fast: false` (one strategy failing doesn't cancel siblings)
- `timezone: "America/New_York"` on cron
- `workflow_dispatch` for manual testing
- Secrets: `MOTHERDUCK_TOKEN` (shared), per-account `ALPACA_API_KEY` + `ALPACA_SECRET_KEY`
- Explicit env var mapping — no `.env` file fallback

## MotherDuck Flight Structure

**One Flight: `daily-pnl-aggregation`**
- `source_code`: Python with `def main():` that reads `trades`, writes `daily_pnl`
- `requirements_txt`: `duckdb==1.5.2`
- `access_token_name`: service account token label
- `schedule_cron`: `"0 23 * * 1-5"` (6 PM ET Mon–Fri in summer / UTC-4; adjust for winter UTC-5 → `"0 22 * * 1-5"`)
- No `config` needed — only MotherDuck token required, provided via `access_token_name`

Created via `mcp__claude_ai_MotherDuck__create_flight` during the Flights phase.

## MotherDuck Database

Single database: `trading`
- All strategies separated by `strategy_name` and `account_name` columns
- Schema: `main` (default)
- Full table references for Dives: `"trading"."main"."trades"` etc.

## Build Order

1. **Schema + Logger** — `core/motherduck_logger.py` with `_ensure_schema()`, add `duckdb` to requirements.txt
2. **Integration** — modify `core/order_manager.py` and `runner.py`; test locally without token (graceful degradation)
3. **GitHub Actions** — 3 workflow files, secrets configured, `workflow_dispatch` test
4. **Flight** — create `daily-pnl-aggregation` Flight via MCP, test with manual `run_flight`
5. **Dives** — create 4 Dives via MCP after real data exists in tables
