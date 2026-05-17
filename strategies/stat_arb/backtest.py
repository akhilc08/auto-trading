"""
Vectorized backtester for the stat arb strategy.
Uses synthetic cointegrated pairs — no API credentials needed.
"""
import math
from dataclasses import dataclass, field
from typing import NamedTuple

import numpy as np

from strategies.stat_arb.pair_selector import cointegration_test, is_valid_pair
from strategies.stat_arb.signals import PairPosition, SignalResult, compute_signal
from strategies.stat_arb.spread import KalmanSpread


@dataclass
class BacktestParams:
    entry_zscore: float = 2.0
    exit_zscore: float = 0.5
    stoploss_zscore: float = 3.5
    max_holding_days: int = 90
    reentry_cooldown_days: int = 10
    position_size_usd: float = 10_000
    formation_days: int = 252
    kalman_delta: float = 1e-4
    kalman_obs_noise: float = 1e-3
    coint_pvalue_threshold: float = 0.05
    hlife_min: float = 2.0
    hlife_max: float = 30.0
    leverage: float = 1.0
    rolling_window: int = 60
    num_pairs: int = 5


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
    trades: list[TradeRecord] = field(default_factory=list)

    def is_good(self) -> bool:
        return (
            self.annualized_sharpe >= 1.0
            and self.max_drawdown <= 0.20
            and self.win_rate >= 0.50
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


def _generate_pair(n: int, phi: float, noise_std: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    log_b = np.cumsum(rng.normal(0, 0.01, n)) + 4.6
    spread = np.zeros(n)
    for i in range(1, n):
        spread[i] = phi * spread[i - 1] + rng.normal(0, noise_std)
    log_a = log_b + spread
    return np.exp(log_a), np.exp(log_b)


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


_PHI_POOL = [0.85, 0.88, 0.82, 0.90, 0.87, 0.83, 0.86, 0.89, 0.84, 0.91,
             0.80, 0.92, 0.81, 0.93, 0.79]
_NOISE_POOL = [0.005, 0.006, 0.004, 0.007, 0.005, 0.006, 0.004, 0.005, 0.006, 0.007,
               0.004, 0.005, 0.006, 0.004, 0.005]


def run_backtest(params: BacktestParams, seed: int = 42) -> BacktestResult:
    """
    Simulates the stat arb strategy on synthetic cointegrated pairs.
    Splits data into formation + trading periods.
    Supports leverage, configurable rolling window, and variable pair count.
    """
    total_days = params.formation_days + 252
    n = min(params.num_pairs, len(_PHI_POOL))
    phi_values = _PHI_POOL[:n]
    noise_values = _NOISE_POOL[:n]
    pair_seeds = [seed + i for i in range(n)]

    all_daily_returns: list[float] = [0.0] * 252
    all_trades: list[TradeRecord] = []
    pairs_included = 0

    for phi, noise_std, pseed in zip(phi_values, noise_values, pair_seeds):
        prices_a, prices_b = _generate_pair(total_days, phi=phi, noise_std=noise_std, seed=pseed)

        form_a = np.log(prices_a[:params.formation_days])
        form_b = np.log(prices_b[:params.formation_days])

        if not is_valid_pair(
            form_a, form_b,
            pvalue_threshold=params.coint_pvalue_threshold,
            hlife_min=params.hlife_min,
            hlife_max=params.hlife_max,
        ):
            continue

        pairs_included += 1
        kalman = KalmanSpread(delta=params.kalman_delta, obs_noise=params.kalman_obs_noise)
        innov_buf: list[float] = []
        for a, b in zip(form_a, form_b):
            e, _ = kalman.update(a, b)
            innov_buf.append(e)
        innov_buf = innov_buf[-params.rolling_window:]

        trade_a = prices_a[params.formation_days:]
        trade_b = prices_b[params.formation_days:]

        position = PairPosition.NONE
        bars_held = 0
        cooldown = 0
        qty_a = qty_b = 0.0
        entry_price_a = entry_price_b = 0.0
        entry_day = 0
        entry_position: PairPosition = PairPosition.NONE

        for day in range(len(trade_a)):
            if cooldown > 0:
                cooldown -= 1

            log_pa = math.log(trade_a[day])
            log_pb = math.log(trade_b[day])
            e, _ = kalman.update(log_pa, log_pb)

            innov_buf.append(e)
            if len(innov_buf) > params.rolling_window:
                innov_buf.pop(0)
            ibuf = np.array(innov_buf)
            ibuf_std = float(ibuf.std())
            zscore = (e - float(ibuf.mean())) / ibuf_std if ibuf_std > 1e-10 else 0.0

            signal = compute_signal(
                zscore=zscore,
                position=position,
                bars_held=bars_held,
                entry_zscore=params.entry_zscore,
                exit_zscore=params.exit_zscore,
                stoploss_zscore=params.stoploss_zscore,
                max_holding_days=params.max_holding_days,
            )

            if position is PairPosition.NONE and cooldown == 0:
                if signal is SignalResult.ENTER_LONG:
                    qty_a = params.position_size_usd * params.leverage / trade_a[day]
                    qty_b = params.position_size_usd * params.leverage / trade_b[day]
                    entry_price_a = trade_a[day]
                    entry_price_b = trade_b[day]
                    position = PairPosition.LONG
                    entry_position = PairPosition.LONG
                    bars_held = 0
                    entry_day = day
                elif signal is SignalResult.ENTER_SHORT:
                    qty_a = params.position_size_usd * params.leverage / trade_a[day]
                    qty_b = params.position_size_usd * params.leverage / trade_b[day]
                    entry_price_a = trade_a[day]
                    entry_price_b = trade_b[day]
                    position = PairPosition.SHORT
                    entry_position = PairPosition.SHORT
                    bars_held = 0
                    entry_day = day

            elif position is not PairPosition.NONE:
                if signal in (SignalResult.EXIT, SignalResult.STOP, SignalResult.TIME_STOP):
                    if entry_position is PairPosition.LONG:
                        pnl = qty_a * (trade_a[day] - entry_price_a) - qty_b * (trade_b[day] - entry_price_b)
                    else:
                        pnl = -qty_a * (trade_a[day] - entry_price_a) + qty_b * (trade_b[day] - entry_price_b)

                    capital = params.position_size_usd * 2
                    ret = pnl / capital
                    all_daily_returns[day] += ret
                    all_trades.append(TradeRecord(entry_day, day, pnl, signal.value))

                    if signal is SignalResult.STOP:
                        cooldown = params.reentry_cooldown_days
                    position = PairPosition.NONE
                    bars_held = 0
                else:
                    bars_held += 1

    if pairs_included == 0:
        return BacktestResult(0.0, 0.0, 0.0, 0.0, 0)

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
