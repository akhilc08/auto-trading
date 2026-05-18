import math
from dataclasses import dataclass, field

import numpy as np

from strategies.vol_risk_premium.signals import Signal, compute_signal, realized_vol


@dataclass
class BacktestParams:
    vix_mean: float = 18.0
    vix_reversion: float = 0.10
    spike_prob: float = 0.015
    spike_size: float = 10.0
    ts_ratio_mean: float = 1.08
    vix_crisis: float = 35.0
    vix_caution: float = 25.0
    composite_entry: float = 0.40
    composite_full: float = 0.70
    position_size_usd: float = 10_000
    slippage_bps: float = 3.0  # ETF, tighter spread
    stop_loss_pct: float = 0.18  # exit if SVXY drops 18% from entry


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


def _sharpe(daily_pnl: list[float]) -> float:
    arr = np.array(daily_pnl)
    if arr.std() < 1e-10:
        return 0.0
    return float(arr.mean() / arr.std() * math.sqrt(252))


def _max_drawdown(daily_pnl: list[float]) -> float:
    cumulative = np.cumprod(1 + np.array(daily_pnl))
    running_max = np.maximum.accumulate(cumulative)
    drawdowns = (running_max - cumulative) / running_max
    return float(drawdowns.max()) if len(drawdowns) > 0 else 0.0


def run_backtest(params: BacktestParams, seed: int = 42) -> BacktestResult:
    trading_days = 1260
    rng = np.random.default_rng(seed)

    annual_carry = 0.15

    vix_series = np.empty(trading_days)
    vix_series[0] = params.vix_mean

    for t in range(1, trading_days):
        reversion = params.vix_reversion * (params.vix_mean - vix_series[t - 1])
        noise = 1.5 * rng.standard_normal()
        spike = 0.0
        if rng.random() < params.spike_prob:
            spike = rng.exponential(params.spike_size)
        vix_series[t] = max(5.0, vix_series[t - 1] + reversion + noise + spike)

    ts_ratio_series = np.empty(trading_days)
    for t in range(trading_days):
        ratio = params.ts_ratio_mean + 0.03 * rng.standard_normal()
        if vix_series[t] > 35.0:
            ratio -= 0.15
        elif vix_series[t] > 25.0:
            ratio -= 0.10
        ts_ratio_series[t] = ratio

    spy_log_returns = np.empty(trading_days)
    spy_log_returns[0] = 0.0
    for t in range(1, trading_days):
        delta_vix = vix_series[t] - vix_series[t - 1]
        spy_log_returns[t] = 0.00035 - 0.008 * delta_vix + 0.01 * rng.standard_normal()

    svxy_returns = np.empty(trading_days)
    svxy_returns[0] = 0.0
    for t in range(1, trading_days):
        delta_vix = vix_series[t] - vix_series[t - 1]
        # Major vol spike: delta_vix > 15 → severe loss for short-vol products
        if delta_vix > 15.0:
            svxy_returns[t] = -0.35
        elif delta_vix > 8.0:
            svxy_returns[t] = -0.15
        else:
            svxy_returns[t] = annual_carry / 252 - 0.45 * (delta_vix / vix_series[t - 1])

    daily_pnl: list[float] = [0.0] * trading_days
    position_shares: float = 0.0
    svxy_price: float = 15.0
    entry_price: float = 0.0
    entry_day: int = 0
    portfolio_value: float = params.position_size_usd  # track capital to prevent ruin

    spy_returns_buf: list[float] = []
    completed_trades: list[float] = []

    for t in range(trading_days):
        svxy_price_prev = svxy_price
        svxy_price = svxy_price * math.exp(svxy_returns[t])
        svxy_price = max(0.01, svxy_price)

        spy_returns_buf.append(spy_log_returns[t])
        if len(spy_returns_buf) > 22:
            spy_returns_buf = spy_returns_buf[-22:]

        if position_shares > 0 and portfolio_value > 0:
            dollar_pnl = position_shares * (svxy_price - svxy_price_prev)
            day_ret = dollar_pnl / portfolio_value
            daily_pnl[t] = max(-0.999, day_ret)
            portfolio_value = max(0.0, portfolio_value + dollar_pnl)

            # stop-loss: exit if SVXY fell more than stop_loss_pct from entry
            if entry_price > 0 and svxy_price < entry_price * (1 - params.stop_loss_pct):
                trade_pnl = position_shares * (svxy_price - entry_price)
                trade_pnl -= position_shares * svxy_price * params.slippage_bps / 10_000
                completed_trades.append(trade_pnl)
                portfolio_value = max(0.0, portfolio_value - position_shares * svxy_price * params.slippage_bps / 10_000)
                position_shares = 0.0

        if len(spy_returns_buf) < 22:
            continue

        rv = realized_vol(spy_returns_buf[-22:])
        vix3m = vix_series[t] * ts_ratio_series[t]

        signal, _ = compute_signal(
            vix=vix_series[t],
            vix3m=vix3m,
            rv=rv,
            vix_crisis=params.vix_crisis,
            vix_caution=params.vix_caution,
            composite_entry=params.composite_entry,
            composite_full=params.composite_full,
        )

        available = min(params.position_size_usd, portfolio_value)
        if available <= 0:
            continue

        if signal == Signal.STRONG and position_shares == 0:
            fill_price = svxy_price
            position_shares = max(1.0, math.floor(available / fill_price))
            entry_price = fill_price
            entry_day = t
            slip = position_shares * fill_price * params.slippage_bps / 10_000
            daily_pnl[t] -= slip / max(portfolio_value, 1.0)
        elif signal == Signal.MODERATE and position_shares == 0:
            fill_price = svxy_price
            position_shares = max(1.0, math.floor((available * 0.5) / fill_price))
            entry_price = fill_price
            entry_day = t
            slip = position_shares * fill_price * params.slippage_bps / 10_000
            daily_pnl[t] -= slip / max(portfolio_value, 1.0)
        elif signal == Signal.NONE and position_shares > 0:
            trade_pnl = position_shares * (svxy_price - entry_price)
            trade_pnl -= position_shares * svxy_price * params.slippage_bps / 10_000
            completed_trades.append(trade_pnl)
            position_shares = 0.0

    if position_shares > 0:
        trade_pnl = position_shares * (svxy_price - entry_price)
        completed_trades.append(trade_pnl)

    total_return = float(np.prod(1 + np.array(daily_pnl)) - 1)
    sharpe = _sharpe(daily_pnl)
    max_dd = _max_drawdown(daily_pnl)
    wins = sum(1 for p in completed_trades if p > 0)
    win_rate = wins / len(completed_trades) if completed_trades else 0.0
    num_trades = len(completed_trades)

    return BacktestResult(
        total_return=total_return,
        annualized_sharpe=sharpe,
        max_drawdown=max_dd,
        win_rate=win_rate,
        num_trades=num_trades,
        daily_pnl=daily_pnl,
    )
