#!/usr/bin/env python
"""
Grid search for the trend following strategy.
Goal: beat 8% annual return with Sharpe > 1.0 and max DD < 30%.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from strategies.trend_following.backtest import BacktestParams, run_backtest

SEEDS = [42, 123, 777, 999, 1337]
TARGET_ROI = 0.08
TARGET_SHARPE = 1.0
TARGET_MAX_DD = 0.30
TARGET_TRADES = 5

# Grid: (fast_window, slow_window, entry_threshold, vol_target, num_instruments)
PARAM_GRID = [
    (10,  30,  0.005, 0.10,  5),
    (10,  30,  0.005, 0.15,  5),
    (10,  30,  0.005, 0.20,  5),
    (10,  30,  0.010, 0.10,  5),
    (10,  30,  0.010, 0.15,  5),
    (10,  30,  0.010, 0.20,  5),
    (20,  60,  0.005, 0.10,  5),
    (20,  60,  0.005, 0.15,  5),
    (20,  60,  0.005, 0.20,  5),
    (20,  60,  0.010, 0.10,  5),
    (20,  60,  0.010, 0.15,  5),
    (20,  60,  0.010, 0.20,  5),
    (5,   20,  0.005, 0.15,  5),
    (5,   20,  0.010, 0.15,  5),
    (5,   20,  0.005, 0.20,  5),
    (10,  30,  0.005, 0.15, 10),
    (10,  30,  0.010, 0.15, 10),
    (20,  60,  0.005, 0.15, 10),
    (20,  60,  0.010, 0.15, 10),
    (5,   20,  0.005, 0.15, 10),
    (5,   20,  0.010, 0.20, 10),
    (10,  30,  0.005, 0.20, 15),
    (10,  30,  0.010, 0.20, 15),
    (20,  60,  0.005, 0.20, 15),
    (20,  60,  0.010, 0.20, 15),
]


def meets_target(avg_roi, avg_sharpe, avg_maxdd, avg_trades):
    return (
        avg_roi >= TARGET_ROI
        and avg_sharpe >= TARGET_SHARPE
        and avg_maxdd <= TARGET_MAX_DD
        and avg_trades >= TARGET_TRADES
    )


print("=" * 95)
print("Trend Following Optimization — Target: ROI > 8%, Sharpe > 1.0, MaxDD < 30%")
print("=" * 95)
hdr = f"{'Fast':>4} {'Slow':>4} {'EThr':>5} {'VTgt':>5} {'Inst':>4}  "
hdr += f"{'ROI':>7}  {'Shrp':>5}  {'DD':>6}  {'Win%':>5}  {'Trd':>5}  {'Status'}"
print(hdr)
print("-" * 95)

good_configs = []
best_roi = -999.0
best_row = None

for fast_w, slow_w, ethr, vtgt, ninst in PARAM_GRID:
    params = BacktestParams(
        fast_window=fast_w,
        slow_window=slow_w,
        entry_threshold=ethr,
        vol_target=vtgt,
        num_instruments=ninst,
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

    ok = meets_target(avg_roi, avg_sharpe, avg_maxdd, avg_trades)
    status = "GOOD" if ok else ("--" if avg_roi > TARGET_ROI else "  ")

    row = f"{fast_w:4d} {slow_w:4d} {ethr:5.3f} {vtgt:5.2f} {ninst:4d}  "
    row += f"{avg_roi*100:6.1f}%  {avg_sharpe:5.2f}  {avg_maxdd*100:5.1f}%  {avg_winrate*100:4.0f}%  {avg_trades:5.0f}  {status}"
    print(row)

    if ok:
        good_configs.append((avg_roi, avg_sharpe, avg_maxdd, avg_winrate, avg_trades, params))
    if avg_roi > best_roi:
        best_roi = avg_roi
        best_row = (avg_roi, avg_sharpe, avg_maxdd, avg_winrate, avg_trades, params)

print("=" * 95)

if good_configs:
    best = max(good_configs, key=lambda x: x[1])
    roi, sharpe, dd, wr, trades, p = best
    print(f"\nSUCCESS — Best config beating 8% target:")
    print(f"  fast_window={p.fast_window}  slow_window={p.slow_window}  entry_threshold={p.entry_threshold}")
    print(f"  vol_target={p.vol_target}  num_instruments={p.num_instruments}")
    print(f"  ROI={roi*100:.1f}%  Sharpe={sharpe:.2f}  MaxDD={dd*100:.1f}%  WinRate={wr*100:.0f}%  Trades/yr={trades:.0f}")
    sys.exit(0)
else:
    if best_row:
        roi, sharpe, dd, wr, trades, p = best_row
        print(f"\nBest so far (ROI={roi*100:.1f}%) — fast={p.fast_window}  slow={p.slow_window}  vol_target={p.vol_target}  inst={p.num_instruments}")
    sys.exit(1)
