# Auto-Trading Infrastructure Design

**Date:** 2026-05-11  
**Status:** Approved  

---

## Overview

A Python monorepo for running multiple independent algorithmic trading strategies via Alpaca. Each strategy lives in its own folder under `strategies/`. Shared infrastructure (Alpaca client, order management, scheduling, logging) lives in `core/`. A single `runner.py` CLI launches any strategy in any mode.

---

## Repository Structure

```
auto-trading/
├── .env                       # secrets — gitignored
├── .env.example               # committed template
├── .gitignore
├── requirements.txt           # shared deps (alpaca-py, python-dotenv, APScheduler, etc.)
├── runner.py                  # CLI entry point
├── core/
│   ├── __init__.py
│   ├── alpaca_client.py       # thin Alpaca API wrapper (reads from .env)
│   ├── base_strategy.py       # abstract BaseStrategy class
│   ├── order_manager.py       # place/cancel/track orders
│   ├── logger.py              # structured per-strategy logging
│   └── scheduler.py           # cron + streaming orchestration
├── strategies/
│   └── <strategy-name>/
│       ├── __init__.py
│       ├── strategy.py        # implements BaseStrategy
│       └── config.py          # symbols, interval, per-strategy params
└── logs/                      # gitignored — written at runtime
    └── <strategy-name>/
        └── YYYY-MM-DD.log
```

---

## Core Components

### `BaseStrategy` (abstract)

Every strategy inherits this class. Defines the interface:

- `on_bar(bar)` — called on each OHLCV bar (cron/scheduled strategies)
- `on_quote(quote)` — called on each real-time quote tick (streaming strategies)
- `run()` — entry point wired by `runner.py`; strategies do not call this themselves

### `AlpacaClient`

Thin wrapper around `alpaca-py`. Reads `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` from `.env`. The paper vs live environment is controlled by the `--mode` flag on `runner.py`, which sets the appropriate Alpaca base URL. Strategies never import the SDK directly.

### `OrderManager`

Helpers for placing market and limit orders, querying current positions, and canceling open orders. Strategies call `order_manager.buy(symbol, qty)` — no raw SDK calls in strategy logic. Checks current position before placing to prevent accidental doubling. All orders are logged before and after submission; failed orders log and skip without retrying.

### `scheduler.py`

Supports two execution modes, selected at launch:

- **Cron mode**: APScheduler fires `on_bar()` on the interval defined in the strategy's `config.py`. Market hours guard is on by default — no firing outside 9:30am–4:00pm ET. Strategies can opt out with `TRADE_OUTSIDE_HOURS = True` in their config.
- **Stream mode**: Opens Alpaca's WebSocket for the symbols defined in `config.py` and routes quote/trade events to `on_quote()`.

### `runner.py` (CLI)

```bash
python runner.py --strategy momentum --mode paper --trigger cron
python runner.py --strategy pairs_trade --mode live --trigger stream
```

Discovers the strategy by folder name, imports its `config.py`, wires it to the correct scheduler mode, and starts it. Rejects any strategy class that does not implement `BaseStrategy`.

---

## Per-Strategy Config

Each strategy's `config.py` controls all tunable parameters:

```python
# strategies/momentum/config.py
SYMBOLS = ["AAPL", "TSLA"]
INTERVAL = "1m"               # cron interval: 1m, 5m, 1h, etc.
TRADE_OUTSIDE_HOURS = False   # respect market hours guard
# ...strategy-specific params below
```

The interval is fully per-strategy — a momentum strategy might run every minute, an EOD mean-reversion strategy might trigger once at 3:55pm.

---

## Paper vs Live

Controlled entirely by the `--mode paper|live` flag on `runner.py`. This sets the Alpaca base URL:

- `paper`: `https://paper-api.alpaca.markets`
- `live`: `https://api.alpaca.markets`

No strategy code changes between environments. Both use the same credentials from `.env`. Which mode a strategy runs in is decided per-strategy at launch time.

---

## Secrets & Configuration

`.env` (gitignored):
```
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
```

`.env.example` (committed):
```
ALPACA_API_KEY=
ALPACA_SECRET_KEY=
```

No secrets in `config.py`. No secrets committed to git.

---

## Error Handling

- All exceptions inside `on_bar()` and `on_quote()` are caught by the scheduler, logged with full traceback, and the strategy continues on the next tick
- Only fatal errors (bad credentials, cannot connect to Alpaca) halt the process
- `OrderManager` checks current position before placing — no accidental doubling
- Failed orders log the error and skip — no retry loops that could cause runaway trades
- Market hours guard prevents firing outside trading hours by default

---

## Logging

Each strategy writes to `logs/<strategy-name>/YYYY-MM-DD.log`. Structured format: timestamp, action, symbol, qty, price. `logs/` is gitignored.

---

## Backtesting

Out of scope for this framework. Strategies will be backtested using an external tool (vectorbt or backtrader) separately. The `BaseStrategy` interface is designed to be compatible with wrapping in a backtest harness later if needed.

---

## Conventions

- One strategy per folder, named in `snake_case`
- `strategy.py` must subclass `BaseStrategy` — `runner.py` enforces this at startup
- No Alpaca SDK imports inside strategy files — all Alpaca access goes through `core/`
- `config.py` is committed; `.env` is not
- `logs/` is gitignored

---

## `.gitignore` covers

```
.env
logs/
__pycache__/
*.pyc
.venv/
*.egg-info/
dist/
```
