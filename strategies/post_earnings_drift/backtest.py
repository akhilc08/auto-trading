import math
from dataclasses import dataclass, field

import numpy as np


@dataclass
class BacktestParams:
    n_stocks: int = 40
    surprise_threshold_pct: float = 5.0
    holding_days: int = 25
    stop_loss_pct: float = 0.08
    position_size_usd: float = 10_000
    max_positions: int = 8


@dataclass
class BacktestResult:
    total_return: float
    annualized_sharpe: float
    max_drawdown: float
    win_rate: float
    num_trades: int
    daily_pnl: list[float] = field(default_factory=list)

    def is_good(self) -> bool:
        return self.total_return >= 0.10 and self.annualized_sharpe >= 0.80

    def summary(self) -> str:
        return (
            f"Sharpe={self.annualized_sharpe:.2f}  "
            f"TotalRet={self.total_return * 100:.1f}%  "
            f"MaxDD={self.max_drawdown * 100:.1f}%  "
            f"WinRate={self.win_rate * 100:.0f}%  "
            f"Trades={self.num_trades}"
        )


def _sharpe(daily_returns: list[float]) -> float:
    arr = np.array(daily_returns)
    if arr.std() < 1e-10:
        return 0.0
    return float(arr.mean() / arr.std() * math.sqrt(252))


def _max_drawdown(daily_returns: list[float]) -> float:
    cumulative = np.cumprod(1 + np.array(daily_returns))
    running_max = np.maximum.accumulate(cumulative)
    drawdowns = (running_max - cumulative) / running_max
    return float(drawdowns.max()) if len(drawdowns) > 0 else 0.0


def run_backtest(params: BacktestParams, seed: int = 42) -> BacktestResult:
    n_days = 1260  # 5 years of trading days
    rng = np.random.default_rng(seed)

    # --- Generate stock prices: random walk per stock ---
    drift = 0.0003
    vol = 0.015
    log_returns = rng.normal(drift, vol, size=(params.n_stocks, n_days))
    prices = np.ones((params.n_stocks, n_days + 1)) * 100.0
    for d in range(n_days):
        prices[:, d + 1] = prices[:, d] * np.exp(log_returns[:, d])

    # --- Generate earnings events: each stock reports every ~63 days ---
    earnings_events: list[tuple[int, int, float]] = []  # (day, stock_idx, surprise)
    report_interval = 63
    for s in range(params.n_stocks):
        offset = rng.integers(0, report_interval)
        d = int(offset)
        while d < n_days:
            surprise = float(rng.normal(3.0, 12.0))
            earnings_events.append((d, s, surprise))
            d += report_interval

    # Sort by day for chronological processing
    earnings_events.sort(key=lambda x: x[0])

    # --- Inject PEAD drift into prices after qualifying earnings ---
    for day, stock_idx, surprise in earnings_events:
        if abs(surprise) < params.surprise_threshold_pct:
            continue
        drift_per_day = 0.002 * (surprise / 10.0)
        for offset in range(params.holding_days):
            future_day = day + offset + 1
            if future_day > n_days:
                break
            multiplier = 1.0 + drift_per_day * (0.85 ** offset)
            prices[stock_idx, future_day:] *= multiplier

    # --- Simulate strategy day by day ---
    # Active positions: {stock_idx: {entry_price, direction, entry_day, days_held}}
    active_positions: dict[int, dict] = {}
    completed_trades: list[float] = []  # pnl per trade

    # Track daily pnl at portfolio level
    capital = params.position_size_usd * max(params.max_positions, 1)
    daily_pnl: list[float] = [0.0] * n_days

    # Build per-day earnings lookup
    events_by_day: dict[int, list[tuple[int, float]]] = {}
    for day, stock_idx, surprise in earnings_events:
        events_by_day.setdefault(day, []).append((stock_idx, surprise))

    for day in range(n_days):
        # --- Mark-to-market existing positions ---
        for s_idx, pos in list(active_positions.items()):
            current_price = prices[s_idx, day + 1]
            prev_price = prices[s_idx, day]
            direction_sign = 1 if pos["direction"] == "long" else -1
            qty = pos["qty"]
            day_pnl = direction_sign * qty * (current_price - prev_price)
            daily_pnl[day] += day_pnl / capital

        # --- Age and check exits ---
        to_remove = []
        for s_idx, pos in list(active_positions.items()):
            pos["days_held"] += 1
            current_price = prices[s_idx, day + 1]
            entry_price = pos["entry_price"]
            direction_sign = 1 if pos["direction"] == "long" else -1
            pnl_pct = (current_price - entry_price) / entry_price * direction_sign

            exit_trade = False
            if pnl_pct < -params.stop_loss_pct:
                exit_trade = True
            elif pos["days_held"] >= params.holding_days:
                exit_trade = True

            if exit_trade:
                trade_pnl = direction_sign * pos["qty"] * (current_price - entry_price)
                completed_trades.append(trade_pnl)
                to_remove.append(s_idx)

        for s_idx in to_remove:
            del active_positions[s_idx]

        # --- Enter new positions from today's earnings ---
        if day not in events_by_day:
            continue

        day_events = events_by_day[day]
        # Sort by abs surprise descending
        day_events.sort(key=lambda x: abs(x[1]), reverse=True)

        new_entries = 0
        for s_idx, surprise in day_events:
            if new_entries >= 3:  # MAX_NEW_POSITIONS_PER_DAY
                break
            if s_idx in active_positions:
                continue
            if len(active_positions) >= params.max_positions:
                break
            if abs(surprise) < params.surprise_threshold_pct:
                continue

            entry_price = prices[s_idx, day + 1]
            size_usd = params.position_size_usd * min(1.0, abs(surprise) / 20.0 + 0.5)
            qty = size_usd / entry_price if entry_price > 0 else 0.0
            if qty <= 0:
                continue

            direction = "long" if surprise > 0 else "short"
            active_positions[s_idx] = {
                "entry_price": entry_price,
                "direction": direction,
                "days_held": 0,
                "qty": qty,
            }
            new_entries += 1

    # Close any remaining open positions at end
    for s_idx, pos in active_positions.items():
        current_price = prices[s_idx, n_days]
        direction_sign = 1 if pos["direction"] == "long" else -1
        trade_pnl = direction_sign * pos["qty"] * (current_price - pos["entry_price"])
        completed_trades.append(trade_pnl)

    # --- Compute metrics ---
    total_return = sum(daily_pnl)
    sharpe = _sharpe(daily_pnl)
    max_dd = _max_drawdown(daily_pnl)
    num_trades = len(completed_trades)
    wins = sum(1 for p in completed_trades if p > 0)
    win_rate = wins / num_trades if num_trades > 0 else 0.0

    return BacktestResult(
        total_return=total_return,
        annualized_sharpe=sharpe,
        max_drawdown=max_dd,
        win_rate=win_rate,
        num_trades=num_trades,
        daily_pnl=daily_pnl,
    )
