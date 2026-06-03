"""Live-execution regression tests.

The signals/* unit tests cover the math; these cover the live on_bar path that
the scheduler actually drives, using a mock Alpaca client. They guard the bugs
that made several strategies silently never trade:
  - market_neutral never received the SPY proxy bar
  - multi_factor / trend_following never preloaded rolling history
  - PEAD recorded positions even when the order was rejected
"""
import datetime
import importlib

import numpy as np
import pytest

from core.base_strategy import BaseStrategy
from core.order_manager import OrderManager


class _Bar:
    def __init__(self, close, ts):
        self.close = close
        self.open = close
        self.high = close * 1.01
        self.low = close * 0.99
        self.volume = 1_000_000
        self.vwap = close
        self.timestamp = ts
        self.trade_count = 100


def make_barset(symbols, n):
    """Dict-of-lists shaped like AlpacaClient.get_*_bars (post .data normalization)."""
    out = {}
    t0 = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    for s in symbols:
        rng = np.random.default_rng(abs(hash(s)) % (2**32))
        steps = rng.normal(0.0004, 0.012, n)
        px = 100 * np.exp(np.cumsum(steps))
        out[s] = [_Bar(float(p), t0 + datetime.timedelta(days=i)) for i, p in enumerate(px)]
    return out


class _MockTrading:
    def __init__(self, orders):
        self.orders = orders

    def submit_order(self, req):
        self.orders.append(req)
        return type("O", (), {"id": "mock-order"})()

    def get_open_position(self, symbol):
        return None

    def get_all_positions(self):
        return []

    def close_position(self, symbol):
        self.orders.append(("close", symbol))

    def cancel_orders(self):
        pass


class MockClient:
    def __init__(self):
        self.orders = []
        self.trading = _MockTrading(self.orders)
        self.latest_requests = []   # symbol lists passed to get_latest_bars
        self.hist_calls = 0

    def get_latest_bars(self, symbols, timeframe=None):
        self.latest_requests.append(list(symbols))
        return make_barset(list(symbols), 5)

    def get_historical_bars(self, symbols, n_days, timeframe=None):
        self.hist_calls += 1
        return make_barset(list(symbols), max(int(n_days), 5))


class _NullLogger:
    def info(self, *a, **k):
        pass

    warning = error = debug = info


def _build(strategy_pkg, client=None):
    client = client or MockClient()
    sm = importlib.import_module(f"strategies.{strategy_pkg}.strategy")
    cm = importlib.import_module(f"strategies.{strategy_pkg}.config")
    cls = next(
        getattr(sm, n) for n in dir(sm)
        if isinstance(getattr(sm, n), type)
        and issubclass(getattr(sm, n), BaseStrategy)
        and getattr(sm, n) is not BaseStrategy
    )
    om = OrderManager(client=client, logger=_NullLogger())
    strat = cls(client=client, order_manager=om, logger=_NullLogger(), config=cm)
    return strat, cm, client


# ── market_neutral: must obtain the SPY proxy price during the live update ──
def test_market_neutral_fetches_proxy_during_update():
    strat, cm, client = _build("market_neutral")
    # Scheduler hands only config.SYMBOLS (no MARKET_PROXY) to on_bar.
    bars = make_barset(cm.SYMBOLS, 5)
    strat.on_bar(bars)
    # The strategy must have fetched the proxy itself (the bug: it never did).
    assert any(cm.MARKET_PROXY in req for req in client.latest_requests), (
        "market_neutral did not fetch MARKET_PROXY live -> residual never computed, never trades"
    )


# ── multi_factor: rolling return history must be preloaded so it can rebalance ──
def test_multi_factor_preloads_history():
    strat, cm, client = _build("multi_factor_equity")
    strat.on_bar(make_barset(cm.SYMBOLS, 5))
    min_history = max(cm.MOM_LOOKBACK, cm.VOL_LOOKBACK)
    seeded = min(len(strat._return_history[s]) for s in cm.SYMBOLS)
    assert client.hist_calls >= 1, "multi_factor never called get_historical_bars"
    assert seeded >= min_history, (
        f"return history not seeded (have {seeded}, need {min_history}) -> never becomes ready"
    )


# ── trend_following: EMAs/buffers must be warmed from history, not a single seed ──
def test_trend_following_warms_from_history():
    strat, cm, client = _build("trend_following")
    strat.on_bar(make_barset(cm.SYMBOLS, 5))
    assert client.hist_calls >= 1, "trend_following never called get_historical_bars"
    states = list(strat._states.values())
    assert all(s.initialized for s in states)
    # warmed: ATR buffer populated and fast EMA diverged from slow EMA
    assert any(len(s.atr_buf) > 5 for s in states), "ATR buffer not warmed from history"
    assert any(abs(s.fast_ema - s.slow_ema) > 1e-9 for s in states), "EMAs still cold (fast==slow)"


# ── PEAD: a rejected entry order must NOT create a phantom position ──
def _patch_surprise(monkeypatch, value, only_symbol=None):
    import strategies.post_earnings_drift.strategy as ped

    def fake(sym, lookback):
        if only_symbol is None or sym == only_symbol:
            return value
        return None

    monkeypatch.setattr(ped, "get_earnings_surprise", fake)


def test_pead_no_phantom_position_on_rejected_order(monkeypatch):
    strat, cm, client = _build("post_earnings_drift")
    target = cm.SYMBOLS[0]
    _patch_surprise(monkeypatch, 10.0, only_symbol=target)
    # Simulate Alpaca rejecting the order (order_manager returns None).
    monkeypatch.setattr(strat.order_manager, "buy", lambda *a, **k: None)
    strat.on_bar(make_barset(cm.SYMBOLS, 5))
    assert target not in strat._positions, "phantom position recorded after rejected order"


def test_pead_records_position_on_successful_order(monkeypatch):
    strat, cm, client = _build("post_earnings_drift")
    target = cm.SYMBOLS[0]
    _patch_surprise(monkeypatch, 10.0, only_symbol=target)
    strat.on_bar(make_barset(cm.SYMBOLS, 5))
    assert target in strat._positions, "position not recorded after successful order"


def test_stat_arb_crisis_blackout_suppresses_entries(monkeypatch):
    import math as _math
    import strategies.stat_arb.strategy as sa
    from strategies.stat_arb.spread import KalmanSpread
    from strategies.stat_arb.signals import PairPosition, SignalResult

    strat, cm, client = _build("stat_arb")
    # Skip real formation; inject a ready, flat pair on the SPY/IVV proxy pair.
    strat._initialized = True
    kal = KalmanSpread(delta=cm.KALMAN_DELTA, obs_noise=cm.KALMAN_OBS_NOISE)
    pair = sa._PairState("SPY", "IVV", kal, innov_buf=[0.0] * 60, position=PairPosition.NONE)
    strat._pairs = [pair]

    # Force an entry signal regardless of z-score so we isolate the blackout gate.
    monkeypatch.setattr(sa, "compute_signal", lambda **kw: SignalResult.ENTER_LONG)

    def _bars(spy, ivv):
        return {"SPY": [_Bar(spy, None)], "IVV": [_Bar(ivv, None)]}

    # Crisis: market proxy moves +20% in a day -> blackout, no entry placed.
    strat._prev_proxy_close = 100.0
    strat._update(_bars(120.0, 100.0))
    assert len(client.orders) == 0, "entry must be suppressed during crisis blackout"

    # Calm: proxy moves +0.5% -> entry proceeds.
    pair.position = PairPosition.NONE
    strat._prev_proxy_close = 100.0
    strat._update(_bars(100.5, 100.0))
    assert len(client.orders) > 0, "entry must proceed when there is no crisis blackout"


def test_stat_arb_trades_on_single_on_bar(monkeypatch):
    # Regression: on_bar must NOT early-return after formation. The one-shot Flight calls on_bar
    # exactly once, so _update (the only path to an order) has to run on that same call.
    import strategies.stat_arb.strategy as sa
    from strategies.stat_arb.spread import KalmanSpread
    from strategies.stat_arb.signals import PairPosition, SignalResult

    strat, cm, client = _build("stat_arb")
    kal = KalmanSpread(delta=cm.KALMAN_DELTA, obs_noise=cm.KALMAN_OBS_NOISE)
    pair = sa._PairState("AAA", "BBB", kal, innov_buf=[0.0] * 60, position=PairPosition.NONE)

    def fake_formation():
        strat._pairs = [pair]
        strat._initialized = True

    monkeypatch.setattr(strat, "_run_formation", fake_formation)
    monkeypatch.setattr(sa, "compute_signal", lambda **kw: SignalResult.ENTER_LONG)

    strat.on_bar({"AAA": [_Bar(100.0, None)], "BBB": [_Bar(50.0, None)]})
    assert len(client.orders) > 0, "stat_arb must place an order on its single one-shot on_bar call"


def test_multi_factor_rebalances_on_first_trading_day_of_month():
    strat, cm, client = _build("multi_factor_equity")
    # Mock history spans 2024-01-01..~2024-10; a live bar dated in a later month is that month's
    # first trading day, so the calendar gate opens and the strategy rebalances.
    d = datetime.datetime(2024, 12, 2, tzinfo=datetime.timezone.utc)
    strat.on_bar({s: [_Bar(100.0, d)] for s in cm.SYMBOLS})
    assert len(client.orders) > 0, "multi_factor must rebalance on the first trading day of the month"


def test_multi_factor_skips_mid_month():
    strat, cm, client = _build("multi_factor_equity")
    # 2024-01-15 has earlier January trading days in the mock history -> not a rebalance day.
    d = datetime.datetime(2024, 1, 15, tzinfo=datetime.timezone.utc)
    strat.on_bar({s: [_Bar(100.0, d)] for s in cm.SYMBOLS})
    assert len(client.orders) == 0, "multi_factor must not rebalance mid-month"


def _trending_spy():
    return [100.0 * (1.001 ** i) for i in range(252)]


def test_regime_switching_trades_when_confirmed(monkeypatch):
    import strategies.regime_switching.strategy as rs

    strat, cm, client = _build("regime_switching")
    monkeypatch.setattr(rs, "fetch_vix", lambda: (15.0, 16.0))
    monkeypatch.setattr(strat, "_spy_history", _trending_spy)
    monkeypatch.setattr(rs, "fetch_vix_series", lambda n: ([15.0] * n, [16.0] * n))

    strat.on_bar({s: [_Bar(100.0, None)] for s in cm.SYMBOLS})
    assert len(client.orders) > 0, "regime_switching must place orders once the regime is confirmed"


def test_regime_switching_idempotent_when_already_positioned(monkeypatch):
    import strategies.regime_switching.strategy as rs

    strat, cm, client = _build("regime_switching")
    monkeypatch.setattr(rs, "fetch_vix", lambda: (15.0, 16.0))
    monkeypatch.setattr(strat, "_spy_history", _trending_spy)
    monkeypatch.setattr(rs, "fetch_vix_series", lambda n: ([15.0] * n, [16.0] * n))
    # Already holding QQQ (the TRENDING target) -> no churn.
    held = type("P", (), {"symbol": "QQQ"})()
    monkeypatch.setattr(client.trading, "get_all_positions", lambda: [held])

    strat.on_bar({s: [_Bar(100.0, None)] for s in cm.SYMBOLS})
    assert len(client.orders) == 0, "must not re-trade when already in the target regime allocation"


def test_regime_switching_holds_when_unconfirmed(monkeypatch):
    import strategies.regime_switching.strategy as rs

    strat, cm, client = _build("regime_switching")
    monkeypatch.setattr(rs, "fetch_vix", lambda: (15.0, 16.0))
    monkeypatch.setattr(strat, "_spy_history", _trending_spy)
    # VIX history unavailable -> regime cannot be confirmed -> hold, no orders.
    monkeypatch.setattr(rs, "fetch_vix_series", lambda n: (None, None))

    strat.on_bar({s: [_Bar(100.0, None)] for s in cm.SYMBOLS})
    assert len(client.orders) == 0, "unconfirmed regime must not trade"


def test_order_manager_rejects_invalid_qty():
    client = MockClient()
    om = OrderManager(client=client, logger=_NullLogger())
    assert om.buy("AAPL", 0) is None
    assert om.sell("AAPL", -5) is None
    assert om.short_sell("AAPL", float("nan")) is None
    assert client.orders == [], "no order may be submitted for non-positive/non-finite qty"
    assert om.buy("AAPL", 3) is not None, "a valid qty must still submit"


def test_daily_pnl_realized_from_fills():
    from flights.aggregation.daily_pnl import _realized_metrics

    d1, d2 = datetime.date(2024, 1, 2), datetime.date(2024, 1, 3)
    long_round_trip = [
        ("s", "a", "AAPL", "buy", 10, 100.0, d1),
        ("s", "a", "AAPL", "sell", 10, 110.0, d2),
    ]
    m = _realized_metrics(long_round_trip)
    assert m[("s", "a", d2)]["realized"] == 100.0   # (110-100)*10
    assert m[("s", "a", d2)]["wins"] == 1
    assert m[("s", "a", d1)]["realized"] == 0.0      # opening leg realizes nothing

    short_round_trip = [
        ("s", "a", "TSLA", "sell", 5, 200.0, d1),    # open short
        ("s", "a", "TSLA", "buy", 5, 180.0, d2),     # cover
    ]
    m2 = _realized_metrics(short_round_trip)
    assert m2[("s", "a", d2)]["realized"] == 100.0   # (200-180)*5 cover profit


def test_pead_short_qty_is_whole_shares(monkeypatch):
    strat, cm, client = _build("post_earnings_drift")
    target = cm.SYMBOLS[0]
    _patch_surprise(monkeypatch, -10.0, only_symbol=target)
    captured = {}
    real_short = strat.order_manager.short_sell

    def spy_short(symbol, qty):
        captured["qty"] = qty
        return real_short(symbol, qty)

    monkeypatch.setattr(strat.order_manager, "short_sell", spy_short)
    strat.on_bar(make_barset(cm.SYMBOLS, 5))
    assert "qty" in captured, "no short order submitted on negative surprise"
    assert captured["qty"] == int(captured["qty"]) and captured["qty"] >= 1, (
        f"short qty {captured['qty']} must be whole shares (Alpaca rejects fractional shorts)"
    )
