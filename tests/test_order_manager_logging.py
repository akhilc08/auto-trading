"""Tests that OrderManager calls md_logger.log_order after each order submission.

Covers all 5 order methods: buy, sell, short_sell, buy_to_cover, close_position.
Also verifies backward compatibility when md_logger is not provided (INTEG-01).
"""
import datetime
import uuid

from core.order_manager import OrderManager


class _FakeOrder:
    """Minimal Order stub matching the Alpaca SDK fields log_order reads."""

    def __init__(self, symbol="AAPL"):
        self.id = str(uuid.uuid4())
        self.symbol = symbol
        self.side = type("Side", (), {"value": "buy"})()
        self.qty = "1"
        self.submitted_at = datetime.datetime.now(datetime.timezone.utc)


class _MockTrading:
    """Mock Alpaca trading client that returns a fake Order for every operation."""

    def submit_order(self, req):
        return _FakeOrder(symbol=req.symbol if hasattr(req, "symbol") else "AAPL")

    def get_open_position(self, symbol):
        return None

    def close_position(self, symbol):
        return _FakeOrder(symbol=symbol)

    def cancel_orders(self):
        pass


class MockClient:
    def __init__(self):
        self.trading = _MockTrading()


class _NullLogger:
    def info(self, *a, **k):
        pass

    warning = error = debug = info


class _RecordingLogger:
    """Stub md_logger that records every log_order call."""

    def __init__(self):
        self.calls = []

    def log_order(self, order, strategy_name, account_name):
        self.calls.append((order, strategy_name, account_name))


def _build_om(rec=None):
    """Construct an OrderManager with a recording md_logger."""
    return OrderManager(
        client=MockClient(),
        logger=_NullLogger(),
        md_logger=rec,
        strategy_name="stat_arb",
        account_name="stat_arb",
    )


# ── backward compat ──────────────────────────────────────────────────────────

def test_backward_compat_no_md_logger():
    """OrderManager(client=..., logger=...) with no md_logger still works (INTEG-01)."""
    om = OrderManager(client=MockClient(), logger=_NullLogger())
    order = om.buy("AAPL", 1)
    assert order is not None


# ── per-method logging ────────────────────────────────────────────────────────

def test_buy_logs_order():
    rec = _RecordingLogger()
    om = _build_om(rec)
    order = om.buy("AAPL", 1)
    assert len(rec.calls) == 1
    assert rec.calls[0][0] is order


def test_sell_logs_order():
    rec = _RecordingLogger()
    om = _build_om(rec)
    order = om.sell("AAPL", 1)
    assert len(rec.calls) == 1
    assert rec.calls[0][0] is order


def test_short_sell_logs_order():
    rec = _RecordingLogger()
    om = _build_om(rec)
    order = om.short_sell("AAPL", 1)
    assert len(rec.calls) == 1
    assert rec.calls[0][0] is order


def test_buy_to_cover_logs_order():
    rec = _RecordingLogger()
    om = _build_om(rec)
    order = om.buy_to_cover("AAPL", 1)
    assert len(rec.calls) == 1
    assert rec.calls[0][0] is order


def test_close_position_logs_order():
    """close_position must capture the Order the SDK returns and pass it to log_order."""
    rec = _RecordingLogger()
    om = _build_om(rec)
    order = om.close_position("AAPL")
    assert len(rec.calls) == 1
    assert rec.calls[0][0] is order


# ── strategy/account names injected via __init__ ─────────────────────────────

def test_log_order_receives_strategy_and_account():
    """log_order must receive the strategy_name and account_name set on __init__ (Pitfall 4)."""
    rec = _RecordingLogger()
    om = _build_om(rec)
    om.buy("AAPL", 1)
    assert rec.calls[0][1] == "stat_arb"
    assert rec.calls[0][2] == "stat_arb"
