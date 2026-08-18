# Phase 1: Schema, Logger & Integration - Pattern Map

**Mapped:** 2026-06-03
**Files analyzed:** 5 (1 new, 2 edits, 1 new test, 1 new test)
**Analogs found:** 4 / 5

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `core/motherduck_logger.py` | service | CRUD + batch | `core/logger.py` | role-match (both are logger services; data flow differs) |
| `core/order_manager.py` | service | request-response | self (existing file) | exact (edit only) |
| `runner.py` | config/entrypoint | request-response | self (existing file) | exact (edit only) |
| `tests/test_motherduck_logger.py` | test | — | `tests/test_live_execution.py` | role-match |
| `tests/test_order_manager_logging.py` | test | — | `tests/test_live_execution.py` | exact |

## Pattern Assignments

### `core/motherduck_logger.py` (service, CRUD)

**Analog:** `core/logger.py`

**Imports pattern** (`core/logger.py` lines 1-4):
```python
import logging
import os
from logging.handlers import TimedRotatingFileHandler
```
New file replaces stdlib logging with duckdb; structure (module-level imports, single class, one public factory or `__init__`) matches.

**Class init + side-effect-on-construction pattern** (`core/logger.py` lines 6-35):
```python
def get_logger(strategy_name: str) -> logging.Logger:
    log_dir = os.path.join("logs", strategy_name)
    os.makedirs(log_dir, exist_ok=True)
    ...
    return logger
```
`MotherDuckLogger.__init__` follows the same "accept a config value, open a resource, run idempotent setup" structure. Replace `os.makedirs` with `duckdb.connect` + `_ensure_schema()`.

**Core pattern for `core/motherduck_logger.py`** (from RESEARCH.md architecture patterns):
```python
import os
from datetime import datetime, timezone
import duckdb

class MotherDuckLogger:
    def __init__(self, token: str):
        self.con = duckdb.connect("md:", config={"motherduck_token": token})
        self._ensure_schema()

    def _ensure_schema(self):
        self.con.execute("CREATE DATABASE IF NOT EXISTS trading")
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS trading.main.trades (
                order_id         VARCHAR PRIMARY KEY,
                strategy_name    VARCHAR NOT NULL,
                account_name     VARCHAR NOT NULL,
                symbol           VARCHAR NOT NULL,
                side             VARCHAR NOT NULL,
                qty              DECIMAL(18,4) NOT NULL,
                submitted_at     TIMESTAMPTZ NOT NULL,
                filled_at        TIMESTAMPTZ,
                filled_avg_price DECIMAL(18,4),
                pnl              DECIMAL(18,4),
                status           VARCHAR NOT NULL DEFAULT 'submitted'
            )
        """)
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS trading.main.positions (
                snapshot_at     TIMESTAMPTZ NOT NULL,
                strategy_name   VARCHAR NOT NULL,
                account_name    VARCHAR NOT NULL,
                symbol          VARCHAR NOT NULL,
                qty             DECIMAL(18,4) NOT NULL,
                avg_entry_price DECIMAL(18,4) NOT NULL,
                current_price   DECIMAL(18,4),
                unrealized_pl   DECIMAL(18,4)
            )
        """)
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS trading.main.portfolio_snapshots (
                snapshot_at   TIMESTAMPTZ NOT NULL,
                strategy_name VARCHAR NOT NULL,
                account_name  VARCHAR NOT NULL,
                equity        DECIMAL(18,4),
                cash          DECIMAL(18,4),
                buying_power  DECIMAL(18,4)
            )
        """)
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS trading.main.daily_pnl (
                date          DATE NOT NULL,
                strategy_name VARCHAR NOT NULL,
                account_name  VARCHAR NOT NULL,
                realized_pnl  DECIMAL(18,4),
                unrealized_pnl DECIMAL(18,4),
                PRIMARY KEY (date, strategy_name, account_name)
            )
        """)

    def log_order(self, order, strategy_name: str, account_name: str):
        if order is None:
            return
        self.con.execute("""
            INSERT INTO trading.main.trades
                (order_id, strategy_name, account_name, symbol, side, qty, submitted_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'submitted')
            ON CONFLICT (order_id) DO NOTHING
        """, [
            str(order.id), strategy_name, account_name,
            order.symbol, str(order.side.value),
            float(order.qty), order.submitted_at,
        ])

    def update_fill(self, order_id: str, filled_at, filled_avg_price, pnl):
        self.con.execute("""
            UPDATE trading.main.trades
            SET filled_at = ?, filled_avg_price = ?, pnl = ?, status = 'filled'
            WHERE order_id = ?
        """, [filled_at, filled_avg_price, pnl, order_id])

    def snapshot_positions(self, positions, strategy_name: str, account_name: str):
        now = datetime.now(timezone.utc)
        for p in positions:
            self.con.execute("""
                INSERT INTO trading.main.positions
                    (snapshot_at, strategy_name, account_name, symbol, qty,
                     avg_entry_price, current_price, unrealized_pl)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                now, strategy_name, account_name,
                p.symbol,
                float(p.qty),
                float(p.avg_entry_price),
                float(p.current_price) if p.current_price else None,
                float(p.unrealized_pl) if p.unrealized_pl else None,
            ])

    def snapshot_portfolio(self, account, strategy_name: str, account_name: str):
        now = datetime.now(timezone.utc)
        self.con.execute("""
            INSERT INTO trading.main.portfolio_snapshots
                (snapshot_at, strategy_name, account_name, equity, cash, buying_power)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [
            now, strategy_name, account_name,
            float(account.equity) if account.equity else None,
            float(account.cash) if account.cash else None,
            float(account.buying_power) if account.buying_power else None,
        ])
```

---

### `core/order_manager.py` (edit — add md_logger param + log_order calls)

**Analog:** self (`core/order_manager.py` lines 1-98 — the existing file is the pattern)

**Existing `__init__` pattern** (lines 6-8):
```python
class OrderManager:
    def __init__(self, client, logger):
        self.client = client
        self.logger = logger
```
Add `md_logger=None`, `strategy_name=""`, `account_name=""` with defaults so existing callers (`OrderManager(client=client, logger=_NullLogger())` in tests) need no changes.

**Existing order method pattern** (lines 16-31, representative of all 5):
```python
def buy(self, symbol: str, qty: float):
    try:
        self.logger.info(f"BUY {qty} {symbol}")
        order = self.client.trading.submit_order(
            MarketOrderRequest(symbol=symbol, qty=qty,
                               side=OrderSide.BUY, time_in_force=TimeInForce.DAY)
        )
        self.logger.info(f"BUY submitted order_id={order.id}")
        return order
    except Exception as e:
        self.logger.error(f"BUY failed {symbol}: {e}")
        return None
```
Insert `if self.md_logger: self.md_logger.log_order(order, self.strategy_name, self.account_name)` immediately after `self.logger.info(f"BUY submitted ...")` and before `return order`. Same pattern applies to `sell`, `short_sell`, `buy_to_cover`.

**`close_position` exception** (lines 84-91):
```python
def close_position(self, symbol: str):
    try:
        self.logger.info(f"Closing position {symbol}")
        self.client.trading.close_position(symbol)
        self.logger.info(f"Position closed {symbol}")
    except Exception as e:
        self.logger.error(f"Close position failed {symbol}: {e}")
```
`close_position` returns nothing. Do NOT call `log_order` here — no Order object is returned. Document with a comment.

---

### `runner.py` (edit — construct logger, pass to OrderManager, wrap run_cron)

**Analog:** self (`runner.py` lines 1-73 — edit only)

**Existing imports block** (lines 1-13):
```python
import argparse
import importlib
import sys
from pathlib import Path

from dotenv import load_dotenv

from core.accounts import account_for
from core.alpaca_client import AlpacaClient
from core.base_strategy import BaseStrategy
from core.logger import get_logger
from core.order_manager import OrderManager
from core.scheduler import run_cron, run_stream
```
Add `import os` at the top (stdlib). Add conditional import of `MotherDuckLogger` inside `main()` after token check (avoids import-time side effects when token is absent).

**Existing OrderManager construction** (lines 54-56):
```python
logger = get_logger(args.strategy)
client = AlpacaClient(mode=args.mode)
order_manager = OrderManager(client=client, logger=logger)
```
Replace with:
```python
logger = get_logger(args.strategy)
client = AlpacaClient(mode=args.mode)
account_name = account_for(args.strategy)
token = os.environ.get("MOTHERDUCK_TOKEN")
md_logger = None
if token:
    from core.motherduck_logger import MotherDuckLogger
    md_logger = MotherDuckLogger(token)
order_manager = OrderManager(
    client=client, logger=logger, md_logger=md_logger,
    strategy_name=args.strategy, account_name=account_name,
)
```

**Existing cron/stream dispatch** (lines 66-69):
```python
if args.trigger == "cron":
    run_cron(strategy, client, config_module)
else:
    run_stream(strategy, client, config_module)
```
Wrap with `try/finally` for snapshot + fill poll:
```python
try:
    if args.trigger == "cron":
        run_cron(strategy, client, config_module)
    else:
        run_stream(strategy, client, config_module)
finally:
    if md_logger:
        positions = client.trading.get_all_positions()
        md_logger.snapshot_positions(positions, args.strategy, account_name)
        account = client.trading.get_account()
        md_logger.snapshot_portfolio(account, args.strategy, account_name)
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus
        import datetime as dt
        today = dt.date.today()
        orders = client.trading.get_orders(GetOrdersRequest(
            status=QueryOrderStatus.CLOSED,
            after=dt.datetime.combine(today, dt.time.min, tzinfo=dt.timezone.utc),
        ))
        for o in orders:
            if o.filled_at and o.filled_avg_price:
                md_logger.update_fill(str(o.id), o.filled_at, float(o.filled_avg_price), None)
```

---

### `tests/test_motherduck_logger.py` (test, new)

**Analog:** `tests/test_live_execution.py`

**Test file structure** (lines 1-18):
```python
"""..docstring.."""
import datetime
import importlib

import numpy as np
import pytest

from core.base_strategy import BaseStrategy
from core.order_manager import OrderManager
```
Copy file-level docstring + import block style. Use `pytest` with no config file (auto-discovery). No class wrappers around tests — top-level functions prefixed `test_`.

**Mock object pattern** (lines 44-63 — `_MockTrading`):
```python
class _MockTrading:
    def __init__(self, orders):
        self.orders = orders

    def submit_order(self, req):
        self.orders.append(req)
        return type("O", (), {"id": "mock-order"})()
```
For MotherDuckLogger tests: use `duckdb.connect()` (in-memory, no `"md:"`) to exercise schema creation and SQL methods without a live token. Pattern: accept a pre-built connection in `__init__` for test injection, or monkey-patch.

**Null/stub helper pattern** (lines 81-85):
```python
class _NullLogger:
    def info(self, *a, **k):
        pass
    warning = error = debug = info
```
Use the same pattern for a stub `MotherDuckLogger` in `test_order_manager_logging.py`.

**Key tests to implement:**
- `test_no_token_no_exception` — construct nothing when `MOTHERDUCK_TOKEN` absent
- `test_idempotent_insert` — call `log_order` twice with same order_id; assert 1 row in `trades`
- `test_update_fill` — log an order then update_fill; assert `status='filled'`
- `test_snapshot_positions` — snapshot_positions inserts correct row count
- `test_snapshot_portfolio` — snapshot_portfolio inserts one row with correct values

---

### `tests/test_order_manager_logging.py` (test, new)

**Analog:** `tests/test_live_execution.py`

**`_build` helper pattern** (lines 88-100):
```python
def _build(strategy_pkg, client=None):
    client = client or MockClient()
    ...
    om = OrderManager(client=client, logger=_NullLogger())
    strat = cls(client=client, order_manager=om, logger=_NullLogger(), config=cm)
    return strat, cm, client
```
Copy this pattern. Build `OrderManager` with a mock `md_logger` that records calls, assert `md_logger.log_order` was called with correct args for each of the 4 order methods (buy, sell, short_sell, buy_to_cover). Assert `close_position` does NOT call `log_order`.

**Assert pattern** (lines 108-113):
```python
assert any(cm.MARKET_PROXY in req for req in client.latest_requests), (
    "market_neutral did not fetch MARKET_PROXY live -> ..."
)
```
Follow same assert-with-message style.

---

## Shared Patterns

### Graceful degradation (token check)
**Source:** RESEARCH.md Pattern 3 + `runner.py` lines 36-38 (env loading pattern)
**Apply to:** `runner.py` (construction guard) and `MotherDuckLogger.__init__` (never called without token)
```python
token = os.environ.get("MOTHERDUCK_TOKEN")
md_logger = None
if token:
    from core.motherduck_logger import MotherDuckLogger
    md_logger = MotherDuckLogger(token)
```

### Parameterized DuckDB queries (SQL injection prevention)
**Source:** RESEARCH.md Pattern 1
**Apply to:** All `con.execute()` calls in `core/motherduck_logger.py`
```python
# Always use ? placeholders, never f-strings for user/SDK data
self.con.execute("INSERT INTO ... VALUES (?, ?, ?)", [val1, val2, val3])
```

### Optional float cast for Alpaca string fields
**Source:** RESEARCH.md Pattern 4
**Apply to:** All Alpaca model fields inserted into DuckDB in `motherduck_logger.py`
```python
float(x) if x is not None else None
# e.g.:
float(order.qty)
float(position.avg_entry_price)
float(account.equity) if account.equity else None
str(order.side.value)   # enum → string
```

### Try/except with return None (order method error handling)
**Source:** `core/order_manager.py` lines 29-31
**Apply to:** All new code inside existing `OrderManager` methods
```python
    except Exception as e:
        self.logger.error(f"BUY failed {symbol}: {e}")
        return None
```
The `md_logger.log_order()` call must be inside the `try` block, after the `submit_order` call succeeds, so a logger failure doesn't suppress the order result. If `log_order` itself raises, let it propagate (fail loud on logging errors during development).

### Backward-compatible `__init__` extension
**Source:** `core/order_manager.py` line 6, `tests/test_live_execution.py` line 98
**Apply to:** `core/order_manager.py` `__init__` signature change
```python
# Before (existing call sites use this — must remain valid):
OrderManager(client=client, logger=_NullLogger())

# After (new signature with defaults):
def __init__(self, client, logger, md_logger=None, strategy_name="", account_name=""):
```

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `requirements.txt` (edit) | config | — | Not a code file; single line addition `duckdb==1.5.2` |

## Metadata

**Analog search scope:** `core/`, `runner.py`, `tests/`
**Files scanned:** 6 (`core/logger.py`, `core/order_manager.py`, `core/accounts.py`, `runner.py`, `tests/test_live_execution.py`, `core/base_strategy.py` implied)
**Pattern extraction date:** 2026-06-03
