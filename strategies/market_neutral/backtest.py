import math
from dataclasses import dataclass, field
from typing import NamedTuple

import numpy as np
import statsmodels.api as sm

from strategies.market_neutral.signals import Position, Signal, compute_signal


_PHI_POOL = [0.85, 0.88, 0.82, 0.90, 0.87, 0.83, 0.86, 0.89, 0.84, 0.91,
             0.80, 0.92, 0.81, 0.93, 0.79]
_NOISE_POOL = [0.005, 0.006, 0.004, 0.007, 0.005, 0.006, 0.004, 0.005, 0.006, 0.007,
               0.004, 0.005, 0.006, 0.004, 0.005]
_BETA_POOL = [1.0, 0.8, 1.2, 0.7, 1.3, 0.9, 1.1, 0.6, 1.4, 0.85,
              1.05, 1.15, 0.75, 1.25, 0.95]


@dataclass
class BacktestParams:
    entry_zscore: float = 2.0
    exit_zscore: float = 0.5
    stoploss_zscore: float = 3.5
    max_holding_days: int = 60
    reentry_cooldown_days: int = 10
    position_size_usd: float = 10_000
    formation_days: int = 252
    rolling_window: int = 60
    num_stocks: int = 5
    leverage: float = 1.0
    slippage_bps: float = 3.0  # one-way slippage + spread per leg (stock + index hedge)


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
            self.annualized_sharpe >= 1.5
            and self.max_drawdown <= 0.25
            and self.win_rate >= 0.55
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
    total_days = params.formation_days + 252
    n = min(params.num_stocks, len(_PHI_POOL))

    rng = np.random.default_rng(seed)
    market_returns = rng.normal(0.0003, 0.012, total_days)
    log_market = np.cumsum(market_returns) + np.log(100.0)
    market_prices = np.exp(log_market)

    all_daily_returns: list[float] = [0.0] * 252
    all_trades: list[TradeRecord] = []
    stocks_included = 0

    for i in range(n):
        phi = _PHI_POOL[i]
        noise_std = _NOISE_POOL[i]
        beta_true = _BETA_POOL[i]
        stock_rng = np.random.default_rng(seed + i + 1)

        alpha_series = np.zeros(total_days)
        for t in range(1, total_days):
            alpha_series[t] = phi * alpha_series[t - 1] + stock_rng.normal(0, noise_std)
        log_stock = beta_true * log_market + alpha_series
        stock_prices = np.exp(log_stock)

        form_log_stock = log_stock[:params.formation_days]
        form_log_market = log_market[:params.formation_days]
        X = sm.add_constant(form_log_market)
        ols_result = sm.OLS(form_log_stock, X).fit()
        beta_hat = ols_result.params[1]
        alpha_hat = ols_result.params[0]

        resid_formation = form_log_stock - beta_hat * form_log_market - alpha_hat
        resid_buf: list[float] = list(resid_formation[-params.rolling_window:])

        stocks_included += 1

        trade_stock = stock_prices[params.formation_days:]
        trade_market = market_prices[params.formation_days:]
        trade_log_stock = log_stock[params.formation_days:]
        trade_log_market = log_market[params.formation_days:]

        position = Position.NONE
        bars_held = 0
        cooldown = 0
        qty_stock = 0.0
        qty_market_pos = 0.0
        entry_price_stock = 0.0
        entry_price_market = 0.0
        entry_position = Position.NONE
        entry_day = 0

        for day in range(len(trade_stock)):
            if cooldown > 0:
                cooldown -= 1

            residual = trade_log_stock[day] - beta_hat * trade_log_market[day] - alpha_hat
            resid_buf.append(residual)
            if len(resid_buf) > params.rolling_window:
                resid_buf.pop(0)

            rbuf = np.array(resid_buf)
            rbuf_std = float(rbuf.std())
            zscore = (residual - float(rbuf.mean())) / rbuf_std if rbuf_std > 1e-10 else 0.0

            signal = compute_signal(
                zscore=zscore,
                position=position,
                bars_held=bars_held,
                entry_zscore=params.entry_zscore,
                exit_zscore=params.exit_zscore,
                stoploss_zscore=params.stoploss_zscore,
                max_holding_days=params.max_holding_days,
            )

            last_idx = len(trade_stock) - 1
            fill_idx = min(day + 1, last_idx)

            if position is Position.NONE and cooldown == 0:
                if signal is Signal.ENTER_LONG:
                    entry_price_stock = trade_stock[fill_idx]
                    entry_price_market = trade_market[fill_idx]
                    qty_stock = params.position_size_usd * params.leverage / entry_price_stock
                    qty_market_pos = params.position_size_usd * params.leverage * beta_hat / entry_price_market
                    position = Position.LONG
                    entry_position = Position.LONG
                    bars_held = 0
                    entry_day = fill_idx
                elif signal is Signal.ENTER_SHORT:
                    entry_price_stock = trade_stock[fill_idx]
                    entry_price_market = trade_market[fill_idx]
                    qty_stock = params.position_size_usd * params.leverage / entry_price_stock
                    qty_market_pos = params.position_size_usd * params.leverage * beta_hat / entry_price_market
                    position = Position.SHORT
                    entry_position = Position.SHORT
                    bars_held = 0
                    entry_day = fill_idx

            elif position is not Position.NONE:
                if signal in (Signal.EXIT, Signal.STOP, Signal.TIME_STOP):
                    if entry_position is Position.LONG:
                        pnl = (
                            qty_stock * (trade_stock[fill_idx] - entry_price_stock)
                            - qty_market_pos * (trade_market[fill_idx] - entry_price_market)
                        )
                    else:
                        pnl = (
                            -qty_stock * (trade_stock[fill_idx] - entry_price_stock)
                            + qty_market_pos * (trade_market[fill_idx] - entry_price_market)
                        )
                    # 4 one-way fills: stock entry/exit + hedge entry/exit
                    rt_cost = 4 * params.position_size_usd * params.leverage * params.slippage_bps / 10_000
                    pnl -= rt_cost

                    capital = params.position_size_usd * 2
                    ret = pnl / capital
                    all_daily_returns[fill_idx] += ret
                    all_trades.append(TradeRecord(entry_day, fill_idx, pnl, signal.value))

                    if signal is Signal.STOP:
                        cooldown = params.reentry_cooldown_days
                    position = Position.NONE
                    bars_held = 0
                    qty_stock = 0.0
                    qty_market_pos = 0.0
                else:
                    bars_held += 1

    if stocks_included == 0:
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
