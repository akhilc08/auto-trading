#!/usr/bin/env python
"""
Grid search for the market-neutral mean reversion strategy.
Goal: beat S&P 500 ~8% annual return with Sharpe > 1.5, MaxDD < 25%, WinRate > 55%.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from strategies.market_neutral.backtest import BacktestParams, run_backtest

SEEDS = [42, 123, 777, 999, 1337]
TARGET_ROI = 0.08
TARGET_SHARPE = 1.5
TARGET_MAX_DD = 0.25
TARGET_WIN_RATE = 0.55
TARGET_TRADES = 5

# Grid: (entry_z, exit_z, rolling_win, num_stocks, leverage)
PARAM_GRID = [
    # -- conservative --
    (2.0, 0.5, 60,  5, 1.0),
    (1.5, 0.5, 60,  5, 1.0),
    (1.0, 0.5, 30,  5, 1.0),
    # -- more stocks --
    (2.0, 0.5, 60, 10, 1.0),
    (1.5, 0.5, 60, 10, 1.0),
    (1.0, 0.5, 30, 10, 1.0),
    (1.0, 0.25,20, 10, 1.0),
    # -- 1.5x leverage --
    (2.0, 0.5, 60,  5, 1.5),
    (1.5, 0.5, 60,  5, 1.5),
    (1.0, 0.5, 30,  5, 1.5),
    (1.5, 0.5, 60, 10, 1.5),
    (1.0, 0.5, 30, 10, 1.5),
    # -- 2x leverage --
    (2.0, 0.5, 60,  5, 2.0),
    (1.5, 0.5, 60,  5, 2.0),
    (1.0, 0.5, 30,  5, 2.0),
    (1.5, 0.5, 60, 10, 2.0),
    (1.0, 0.5, 30, 10, 2.0),
    (1.0, 0.25,20, 10, 2.0),
    # -- 2x leverage + 15 stocks --
    (1.5, 0.5, 60, 15, 2.0),
    (1.0, 0.5, 30, 15, 2.0),
    (1.0, 0.25,20, 15, 2.0),
    # -- shorter window for faster signals --
    (1.5, 0.5, 30,  5, 1.5),
    (1.0, 0.5, 20,  5, 1.5),
    (1.0, 0.5, 20, 10, 2.0),
]


def meets_target(avg_roi, avg_sharpe, avg_maxdd, avg_winrate, avg_trades):
    return (
        avg_roi >= TARGET_ROI
        and avg_sharpe >= TARGET_SHARPE
        and avg_maxdd <= TARGET_MAX_DD
        and avg_winrate >= TARGET_WIN_RATE
        and avg_trades >= TARGET_TRADES
    )


print("=" * 90)
print("Market Neutral Optimization — Target: ROI > 8%, Sharpe > 1.5, MaxDD < 25%, WinRate > 55%")
print("=" * 90)
hdr = f"{'Ez':>4} {'Xz':>4} {'Win':>4} {'Stk':>4} {'Lev':>4}  "
hdr += f"{'ROI':>7}  {'Shrp':>5}  {'DD':>6}  {'Win%':>5}  {'Trd':>5}  {'Status'}"
print(hdr)
print("-" * 90)

good_configs = []
best_roi = -999.0
best_row = None

for entry_z, exit_z, rwin, nstocks, lev in PARAM_GRID:
    params = BacktestParams(
        entry_zscore=entry_z,
        exit_zscore=exit_z,
        rolling_window=rwin,
        num_stocks=nstocks,
        leverage=lev,
    )

    rois, sharpes, mxdds, winrates, n_trades = [], [], [], [], []
    for seed in SEEDS:
        r = run_backtest(params, seed=seed)
        rois.append(r.total_return)
        sharpes.append(r.annualized_sharpe)
        mxdds.append(r.max_drawdown)
        winrates.append(r.win_rate)
        n_trades.append(r.num_trades)

    avg_roi     = float(np.mean(rois))
    avg_sharpe  = float(np.mean(sharpes))
    avg_maxdd   = float(np.mean(mxdds))
    avg_winrate = float(np.mean(winrates))
    avg_trades  = float(np.mean(n_trades))

    ok = meets_target(avg_roi, avg_sharpe, avg_maxdd, avg_winrate, avg_trades)
    status = "GOOD" if ok else ("--" if avg_roi > TARGET_ROI else "  ")

    row = f"{entry_z:4.2f} {exit_z:4.2f} {rwin:4d} {nstocks:4d} {lev:4.1f}  "
    row += f"{avg_roi*100:6.1f}%  {avg_sharpe:5.2f}  {avg_maxdd*100:5.1f}%  {avg_winrate*100:4.0f}%  {avg_trades:5.0f}  {status}"
    print(row)

    if ok:
        good_configs.append((avg_roi, avg_sharpe, avg_maxdd, avg_winrate, avg_trades, params))
    if avg_roi > best_roi:
        best_roi = avg_roi
        best_row = (avg_roi, avg_sharpe, avg_maxdd, avg_winrate, avg_trades, params)

print("=" * 90)

if good_configs:
    best = max(good_configs, key=lambda x: x[1])
    roi, sharpe, dd, wr, trades, p = best
    print(f"\nSUCCESS — Best config beating S&P 500 target:")
    print(f"  entry_z={p.entry_zscore}  exit_z={p.exit_zscore}  rolling_win={p.rolling_window}  stocks={p.num_stocks}  leverage={p.leverage}x")
    print(f"  ROI={roi*100:.1f}%  Sharpe={sharpe:.2f}  MaxDD={dd*100:.1f}%  WinRate={wr*100:.0f}%  Trades/yr={trades:.0f}")
    sys.exit(0)
else:
    if best_row:
        roi, sharpe, dd, wr, trades, p = best_row
        print(f"\nBest so far (ROI={roi*100:.1f}%) — entry_z={p.entry_zscore}  lev={p.leverage}x  stocks={p.num_stocks}")
    sys.exit(1)
