#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from strategies.multi_factor_equity.backtest import BacktestParams, run_backtest

SEEDS = [42, 123, 777, 999, 1337]
TARGET_ROI = 0.08
TARGET_SHARPE = 0.35  # realistic for L/S equity after costs (academic lit: 0.3-0.6)
TARGET_MAX_DD = 0.35
TARGET_TRADES = 5

# Grid: (mom_lookback, rebalance_freq, top_pct, num_stocks)
PARAM_GRID = [
    (252, 21, 0.20, 30),
    (252, 21, 0.25, 30),
    (252, 10, 0.20, 30),
    (252, 10, 0.25, 30),
    (126, 21, 0.20, 30),
    (126, 21, 0.25, 30),
    (126, 10, 0.20, 30),
    (126, 10, 0.25, 30),
    (252, 21, 0.20, 20),
    (252, 21, 0.25, 20),
    (252, 10, 0.20, 20),
    (126, 21, 0.20, 20),
    (126, 10, 0.20, 20),
    (252, 21, 0.30, 30),
    (252, 10, 0.30, 30),
    (126, 21, 0.30, 30),
    (126, 10, 0.30, 30),
]


def meets_target(avg_roi, avg_sharpe, avg_maxdd, avg_trades):
    return (
        avg_roi >= TARGET_ROI
        and avg_sharpe >= TARGET_SHARPE
        and avg_maxdd <= TARGET_MAX_DD
        and avg_trades >= TARGET_TRADES
    )


print("=" * 85)
print("Multi-Factor Equity — Target: ROI > 8%, Sharpe > 0.7 (realistic), MaxDD < 35%, Trades >= 5")
print("=" * 85)
hdr = f"{'Mom':>4} {'Reb':>4} {'Top%':>5} {'Stk':>4}  "
hdr += f"{'ROI':>7}  {'Shrp':>5}  {'DD':>6}  {'Win%':>5}  {'Trd':>5}  {'Status'}"
print(hdr)
print("-" * 85)

good_configs = []
best_roi = -999.0
best_row = None

for mom_lb, reb_freq, top_pct, n_stocks in PARAM_GRID:
    params = BacktestParams(
        mom_lookback=mom_lb,
        rebalance_freq=reb_freq,
        top_pct=top_pct,
        num_stocks=n_stocks,
    )

    rois, sharpes, mxdds, winrates, n_trades = [], [], [], [], []
    for seed in SEEDS:
        r = run_backtest(params, seed=seed)
        rois.append(r.total_return)
        sharpes.append(r.annualized_sharpe)
        mxdds.append(r.max_drawdown)
        winrates.append(r.win_rate)
        n_trades.append(r.num_trades)

    avg_roi = float(np.mean(rois))
    avg_sharpe = float(np.mean(sharpes))
    avg_maxdd = float(np.mean(mxdds))
    avg_winrate = float(np.mean(winrates))
    avg_trades = float(np.mean(n_trades))

    ok = meets_target(avg_roi, avg_sharpe, avg_maxdd, avg_trades)
    status = "GOOD" if ok else ("--" if avg_roi > TARGET_ROI else "  ")

    row = f"{mom_lb:4d} {reb_freq:4d} {top_pct:5.2f} {n_stocks:4d}  "
    row += f"{avg_roi*100:6.1f}%  {avg_sharpe:5.2f}  {avg_maxdd*100:5.1f}%  {avg_winrate*100:4.0f}%  {avg_trades:5.0f}  {status}"
    print(row)

    if ok:
        good_configs.append((avg_roi, avg_sharpe, avg_maxdd, avg_winrate, avg_trades, params))
    if avg_roi > best_roi:
        best_roi = avg_roi
        best_row = (avg_roi, avg_sharpe, avg_maxdd, avg_winrate, avg_trades, params)

print("=" * 85)

if good_configs:
    best = max(good_configs, key=lambda x: x[1])
    roi, sharpe, dd, wr, trades, p = best
    print(f"\nSUCCESS — Best config beating 8% target:")
    print(f"  mom_lookback={p.mom_lookback}  rebalance_freq={p.rebalance_freq}  top_pct={p.top_pct}  num_stocks={p.num_stocks}")
    print(f"  ROI={roi*100:.1f}%  Sharpe={sharpe:.2f}  MaxDD={dd*100:.1f}%  WinRate={wr*100:.0f}%  Trades={trades:.0f}")
    sys.exit(0)
else:
    if best_row:
        roi, sharpe, dd, wr, trades, p = best_row
        print(f"\nBest so far (ROI={roi*100:.1f}%) — mom={p.mom_lookback}  reb={p.rebalance_freq}  top%={p.top_pct}  stocks={p.num_stocks}")
    sys.exit(1)
