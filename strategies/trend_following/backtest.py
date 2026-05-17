import math
from dataclasses import dataclass, field
from typing import NamedTuple

import numpy as np

from strategies.trend_following.signals import (
    InstrumentPosition,
    SignalResult,
    compute_signal,
    compute_normalized_signal,
    compute_position_size,
    compute_realized_vol,
    update_ema,
)


@dataclass
class BacktestParams:
    fast_window: int = 20
    slow_window: int = 60
    atr_window: int = 14
    entry_threshold: float = 0.01
    vol_lookback: int = 20
    vol_target: float = 0.15
    atr_stop_multiple: float = 3.0
    max_holding_days: int = 60
    position_size_usd: float = 10_000
    num_instruments: int = 5
    formation_days: int = 100
    slippage_bps: float = 5.0  # one-way slippage + spread


class TradeRecord(NamedTuple):
    entry_day: int
    exit_day: int
    pnl: float
    reason: str


@dataclass
class BacktestResult:
    total_return: float
    annualized_sharpe: float
    max_drawdown: float
    win_rate: float
    num_trades: int
    daily_pnl: list[float] = field(default_factory=list)
    trades: list = field(default_factory=list)

    def is_good(self) -> bool:
        return (
            self.total_return >= 0.08
            and self.annualized_sharpe >= 1.0
            and self.max_drawdown <= 0.30
            and self.num_trades >= 5
        )

    def summary(self) -> str:
        return (
            f"Sharpe={self.annualized_sharpe:.2f}  "
            f"TotalRet={self.total_return*100:.1f}%  "
            f"MaxDD={self.max_drawdown*100:.1f}%  "
            f"WinRate={self.win_rate*100:.0f}%  "
            f"Trades={self.num_trades}"
        )


_MU_POOL = [
    0.0002, 0.0001, 0.00015, 0.0003, 0.0001,
    0.0002, 0.00025, 0.00015, 0.0001, 0.0002,
    0.0003, 0.00015, 0.0001, 0.00025, 0.0002,
]
_SIGMA_POOL = [
    0.012, 0.015, 0.010, 0.018, 0.013,
    0.011, 0.016, 0.014, 0.012, 0.015,
    0.013, 0.010, 0.017, 0.011, 0.014,
]

# Regime parameters: (up_mu, down_mu, sigma, persistence) per instrument.
# persistence is prob of staying in same regime each bar.
_REGIME_POOL = [
    (0.0012, -0.0008, 0.012, 0.97),
    (0.0010, -0.0006, 0.015, 0.96),
    (0.0015, -0.0010, 0.010, 0.98),
    (0.0020, -0.0012, 0.018, 0.95),
    (0.0008, -0.0005, 0.013, 0.97),
    (0.0012, -0.0008, 0.011, 0.96),
    (0.0018, -0.0012, 0.016, 0.95),
    (0.0010, -0.0007, 0.014, 0.97),
    (0.0014, -0.0009, 0.012, 0.98),
    (0.0016, -0.0010, 0.015, 0.96),
    (0.0020, -0.0014, 0.013, 0.95),
    (0.0012, -0.0008, 0.010, 0.98),
    (0.0008, -0.0005, 0.017, 0.97),
    (0.0015, -0.0010, 0.011, 0.96),
    (0.0010, -0.0007, 0.014, 0.97),
]


def _generate_instrument(n: int, mu: float, sigma: float, seed: int) -> np.ndarray:
    idx = seed % len(_REGIME_POOL)
    up_mu, down_mu, sig, persist = _REGIME_POOL[idx]
    rng = np.random.default_rng(seed)
    regime = 1
    log_price = np.empty(n)
    log_price[0] = 4.6
    for i in range(1, n):
        if rng.random() > persist:
            regime = -regime
        drift = up_mu if regime == 1 else down_mu
        log_price[i] = log_price[i - 1] + drift + sig * rng.standard_normal()
    return np.exp(log_price)


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
    trading_days = 252
    total_days = params.formation_days + trading_days
    n = min(params.num_instruments, len(_MU_POOL))

    alpha_f = 2.0 / (params.fast_window + 1)
    alpha_s = 2.0 / (params.slow_window + 1)

    all_daily_returns: list[float] = [0.0] * trading_days
    all_trades: list[TradeRecord] = []

    for i in range(n):
        mu = _MU_POOL[i]
        sigma = _SIGMA_POOL[i]
        iseed = seed + i * 1000
        prices = _generate_instrument(total_days, mu=mu, sigma=sigma, seed=iseed)

        form_prices = prices[: params.formation_days]

        fast_ema = form_prices[0]
        slow_ema = form_prices[0]
        atr_buf: list[float] = [0.0]
        for t in range(1, len(form_prices)):
            fast_ema = update_ema(fast_ema, form_prices[t], alpha_f)
            slow_ema = update_ema(slow_ema, form_prices[t], alpha_s)
            atr_buf.append(abs(form_prices[t] - form_prices[t - 1]))
            if len(atr_buf) > params.atr_window:
                atr_buf.pop(0)

        atr = float(np.mean(atr_buf)) if atr_buf else 0.0

        trade_prices = prices[params.formation_days :]
        prev_price = form_prices[-1]

        returns_buf: list[float] = []
        for t in range(1, len(form_prices)):
            if form_prices[t - 1] > 1e-10:
                returns_buf.append(math.log(form_prices[t] / form_prices[t - 1]))
        returns_buf = returns_buf[-params.vol_lookback :]

        position = InstrumentPosition.NONE
        bars_held = 0
        entry_price = 0.0
        qty = 0.0
        entry_day = 0
        prev_mtm_price = 0.0
        capital = params.position_size_usd * 2

        for day in range(len(trade_prices)):
            price = trade_prices[day]

            fast_ema = update_ema(fast_ema, price, alpha_f)
            slow_ema = update_ema(slow_ema, price, alpha_s)

            daily_move = abs(price - prev_price)
            atr_buf.append(daily_move)
            if len(atr_buf) > params.atr_window:
                atr_buf.pop(0)
            atr = float(np.mean(atr_buf))

            if prev_price > 1e-10:
                returns_buf.append(math.log(price / prev_price))
            if len(returns_buf) > params.vol_lookback:
                returns_buf.pop(0)

            prev_price = price

            if position is not InstrumentPosition.NONE:
                if position is InstrumentPosition.LONG:
                    daily_pnl = qty * (price - prev_mtm_price)
                else:
                    daily_pnl = -qty * (price - prev_mtm_price)
                all_daily_returns[day] += daily_pnl / capital
            prev_mtm_price = price

            norm_signal = compute_normalized_signal(fast_ema, slow_ema, atr)

            signal = compute_signal(
                normalized_signal=norm_signal,
                position=position,
                bars_held=bars_held,
                entry_price=entry_price,
                current_price=price,
                atr=atr,
                entry_threshold=params.entry_threshold,
                atr_stop_multiple=params.atr_stop_multiple,
                max_holding_days=params.max_holding_days,
            )

            last_day_idx = len(trade_prices) - 1
            fill_price = trade_prices[min(day + 1, last_day_idx)]

            if position is not InstrumentPosition.NONE and signal in (
                SignalResult.EXIT,
                SignalResult.ATR_STOP,
                SignalResult.TIME_STOP,
            ):
                if position is InstrumentPosition.LONG:
                    pnl = qty * (fill_price - entry_price)
                else:
                    pnl = -qty * (fill_price - entry_price)
                # round-trip: entry + exit = 2 one-way fills
                rt_cost = 2 * params.position_size_usd * params.slippage_bps / 10_000
                pnl -= rt_cost
                all_trades.append(TradeRecord(entry_day, day, pnl, signal.value))
                position = InstrumentPosition.NONE
                bars_held = 0
                qty = 0.0

            if position is InstrumentPosition.NONE:
                if signal is SignalResult.ENTER_LONG:
                    rvol = compute_realized_vol(np.array(returns_buf))
                    qty = compute_position_size(fill_price, rvol, params.vol_target, params.position_size_usd)
                    entry_price = fill_price
                    prev_mtm_price = fill_price
                    position = InstrumentPosition.LONG
                    bars_held = 0
                    entry_day = day
                elif signal is SignalResult.ENTER_SHORT:
                    rvol = compute_realized_vol(np.array(returns_buf))
                    qty = compute_position_size(fill_price, rvol, params.vol_target, params.position_size_usd)
                    entry_price = fill_price
                    prev_mtm_price = fill_price
                    position = InstrumentPosition.SHORT
                    bars_held = 0
                    entry_day = day
            else:
                bars_held += 1

    sharpe = _sharpe(all_daily_returns)
    max_dd = _max_drawdown(all_daily_returns)
    total_ret = float(np.prod(1 + np.array(all_daily_returns)) - 1)
    wins = sum(1 for t in all_trades if t.pnl > 0)
    win_rate = wins / len(all_trades) if all_trades else 0.0

    return BacktestResult(
        total_return=total_ret,
        annualized_sharpe=sharpe,
        max_drawdown=max_dd,
        win_rate=win_rate,
        num_trades=len(all_trades),
        daily_pnl=all_daily_returns,
        trades=all_trades,
    )
