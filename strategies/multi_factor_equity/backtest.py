import math
from dataclasses import dataclass, field
from typing import NamedTuple

import numpy as np

from strategies.multi_factor_equity.signals import composite_score, select_legs


_MU_POOL = [
    0.0002, 0.0001, 0.00015, 0.0003, 0.0001, 0.0002, 0.00025, 0.00015, 0.0001, 0.0002,
    0.0003, 0.00015, 0.0001, 0.00025, 0.0002, 0.0001, 0.0003, 0.0002, 0.00015, 0.0001,
    0.0002, 0.00025, 0.0001, 0.0003, 0.00015, 0.0002, 0.0001, 0.00025, 0.0003, 0.0002,
]
_BETA_POOL = [
    1.0, 0.8, 1.2, 0.7, 1.3, 0.9, 1.1, 0.6, 1.4, 0.85,
    1.0, 1.15, 0.75, 1.25, 0.95, 1.05, 0.65, 1.35, 0.80, 1.10,
    1.0, 0.90, 1.20, 0.70, 1.30, 0.85, 1.05, 0.75, 1.15, 0.95,
]
_SIGMA_POOL = [
    0.012, 0.015, 0.010, 0.018, 0.013, 0.011, 0.016, 0.014, 0.012, 0.015,
    0.013, 0.010, 0.017, 0.011, 0.014, 0.012, 0.016, 0.013, 0.015, 0.010,
    0.014, 0.012, 0.011, 0.018, 0.013, 0.015, 0.010, 0.016, 0.012, 0.014,
]

_TRADING_YEARS = 5
# Alpha scale: raw pool values are 1e-4 to 3e-4. Multiply by _ALPHA_SCALE so that
# cross-sectional mu spread is wide enough for momentum signals to be detectable
# above idiosyncratic noise over a 252-day lookback window.
_ALPHA_SCALE = 10.0


@dataclass
class BacktestParams:
    mom_lookback: int = 252
    rev_lookback: int = 21
    vol_lookback: int = 63
    rebalance_freq: int = 21
    top_pct: float = 0.20
    position_size_usd: float = 10_000
    num_stocks: int = 30
    formation_days: int = 252


class TradeRecord(NamedTuple):
    entry_day: int
    exit_day: int
    symbol_idx: int
    direction: int
    pnl: float


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


def _generate_universe(n: int, total_days: int, rng: np.random.Generator) -> np.ndarray:
    market_returns = rng.normal(0.0003, 0.012, total_days)
    log_returns = np.zeros((n, total_days))
    for i in range(n):
        mu = _MU_POOL[i % len(_MU_POOL)] * _ALPHA_SCALE
        beta = _BETA_POOL[i % len(_BETA_POOL)]
        sigma = _SIGMA_POOL[i % len(_SIGMA_POOL)]
        idio = rng.normal(0, sigma, total_days)
        log_returns[i] = mu + beta * market_returns + idio
    return log_returns


def _sharpe(daily_returns: np.ndarray) -> float:
    if daily_returns.std() < 1e-10:
        return 0.0
    return float(daily_returns.mean() / daily_returns.std() * math.sqrt(252))


def _max_drawdown(daily_returns: np.ndarray) -> float:
    cumulative = np.cumprod(1 + daily_returns)
    running_max = np.maximum.accumulate(cumulative)
    drawdowns = (running_max - cumulative) / running_max
    return float(drawdowns.max()) if len(drawdowns) > 0 else 0.0


def run_backtest(params: BacktestParams, seed: int = 42) -> BacktestResult:
    rng = np.random.default_rng(seed)
    n = min(params.num_stocks, len(_MU_POOL))
    trading_days = 252 * _TRADING_YEARS
    total_days = params.formation_days + trading_days

    log_returns = _generate_universe(n, total_days, rng)

    log_prices = np.zeros((n, total_days + 1))
    for t in range(total_days):
        log_prices[:, t + 1] = log_prices[:, t] + log_returns[:, t]
    prices = np.exp(log_prices)

    min_history = max(params.mom_lookback, params.vol_lookback)

    n_each_leg = max(1, int(round(n * params.top_pct)))
    total_capital = params.position_size_usd * n_each_leg * 2

    daily_portfolio_returns = np.zeros(trading_days)
    all_trades: list[TradeRecord] = []

    positions: dict[int, tuple[float, int, float]] = {}
    last_rebalance_day = -1

    for day_offset in range(trading_days):
        t = params.formation_days + day_offset

        if t < min_history:
            continue

        is_rebalance = (day_offset % params.rebalance_freq == 0)

        if is_rebalance:
            hist_returns = log_returns[:, t - min_history:t]
            scores = composite_score(
                hist_returns,
                mom_lookback=params.mom_lookback,
                rev_lookback=params.rev_lookback,
                vol_lookback=params.vol_lookback,
            )
            long_idx, short_idx = select_legs(scores, params.top_pct)

            # Estimate beta per stock from historical returns for beta-weighting
            mkt_hist = hist_returns.mean(axis=0)
            mkt_var = float(mkt_hist.var())
            betas = np.ones(n)
            if mkt_var > 1e-12:
                for i in range(n):
                    cov = float(np.cov(hist_returns[i], mkt_hist)[0, 1])
                    betas[i] = max(0.3, cov / mkt_var)

            for sym_idx, (qty, direction, entry_price) in list(positions.items()):
                close_price = prices[sym_idx, t]
                pnl = direction * qty * (close_price - entry_price)
                all_trades.append(TradeRecord(
                    entry_day=last_rebalance_day,
                    exit_day=day_offset,
                    symbol_idx=sym_idx,
                    direction=direction,
                    pnl=pnl,
                ))

            positions = {}
            for sym_idx in long_idx:
                entry_price = prices[sym_idx, t]
                # Scale position by 1/beta to neutralize market exposure
                beta_wt = 1.0 / betas[sym_idx]
                qty = params.position_size_usd * beta_wt / entry_price
                positions[int(sym_idx)] = (qty, 1, entry_price)
            for sym_idx in short_idx:
                entry_price = prices[sym_idx, t]
                beta_wt = 1.0 / betas[sym_idx]
                qty = params.position_size_usd * beta_wt / entry_price
                positions[int(sym_idx)] = (qty, -1, entry_price)

            last_rebalance_day = day_offset

        if positions and t + 1 <= total_days:
            day_ret = 0.0
            for sym_idx, (qty, direction, entry_price) in positions.items():
                price_today = prices[sym_idx, t]
                price_next = prices[sym_idx, t + 1]
                day_ret += direction * qty * (price_next - price_today)
            daily_portfolio_returns[day_offset] = day_ret / total_capital

    if not all_trades:
        return BacktestResult(0.0, 0.0, 0.0, 0.0, 0)

    sharpe = _sharpe(daily_portfolio_returns)
    max_dd = _max_drawdown(daily_portfolio_returns)
    total_ret = float(np.prod(1 + daily_portfolio_returns) - 1)
    wins = sum(1 for t in all_trades if t.pnl > 0)
    win_rate = wins / len(all_trades) if all_trades else 0.0

    return BacktestResult(
        total_return=total_ret,
        annualized_sharpe=sharpe,
        max_drawdown=max_dd,
        win_rate=win_rate,
        num_trades=len(all_trades),
        daily_pnl=list(daily_portfolio_returns),
        trades=all_trades,
    )
