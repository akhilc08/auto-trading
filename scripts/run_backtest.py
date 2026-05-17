#!/usr/bin/env python
"""
Parameter search loop for the stat arb strategy.
Iterates over parameter grids, reports results, exits when good params found.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.stat_arb.backtest import BacktestParams, run_backtest

PARAM_GRID = [
    # (entry_z, exit_z, stoploss_z, max_hold)
    (2.0, 0.5, 3.5, 90),
    (1.75, 0.5, 3.5, 90),
    (1.5, 0.5, 3.0, 60),
    (2.0, 0.75, 3.5, 90),
    (2.0, 0.5, 3.0, 60),
    (1.75, 0.75, 3.5, 90),
    (1.5, 0.25, 3.0, 90),
    (2.0, 0.5, 4.0, 120),
    (1.75, 0.5, 3.0, 90),
    (1.5, 0.75, 3.5, 60),
]

SEEDS = [42, 123, 777]

print("=" * 65)
print("Stat Arb Backtesting Loop")
print("=" * 65)
print(f"{'Entry':>6} {'Exit':>5} {'Stop':>5} {'Hold':>5}  Result")
print("-" * 65)

best_sharpe = -999.0
best_params = None
best_result = None
good_configs: list[tuple] = []

for entry_z, exit_z, stop_z, max_hold in PARAM_GRID:
    params = BacktestParams(
        entry_zscore=entry_z,
        exit_zscore=exit_z,
        stoploss_zscore=stop_z,
        max_holding_days=max_hold,
    )

    # Average across seeds for robustness
    sharpes, mxdds, winrates, n_trades = [], [], [], []
    for seed in SEEDS:
        r = run_backtest(params, seed=seed)
        sharpes.append(r.annualized_sharpe)
        mxdds.append(r.max_drawdown)
        winrates.append(r.win_rate)
        n_trades.append(r.num_trades)

    avg_sharpe = sum(sharpes) / len(sharpes)
    avg_maxdd = sum(mxdds) / len(mxdds)
    avg_winrate = sum(winrates) / len(winrates)
    avg_trades = sum(n_trades) / len(n_trades)

    status = "GOOD" if (avg_sharpe >= 1.0 and avg_maxdd <= 0.20 and avg_winrate >= 0.50 and avg_trades >= 5) else "    "

    print(
        f"{entry_z:6.2f} {exit_z:5.2f} {stop_z:5.2f} {max_hold:5d}  "
        f"Sharpe={avg_sharpe:5.2f}  DD={avg_maxdd*100:5.1f}%  "
        f"Win={avg_winrate*100:4.0f}%  Trades={avg_trades:5.1f}  {status}"
    )

    if avg_sharpe > best_sharpe:
        best_sharpe = avg_sharpe
        best_params = params
        best_result = (avg_sharpe, avg_maxdd, avg_winrate, avg_trades)

    if status == "GOOD":
        good_configs.append((entry_z, exit_z, stop_z, max_hold, avg_sharpe))

print("=" * 65)

if good_configs:
    best_good = max(good_configs, key=lambda x: x[4])
    print(f"\nSUCCESS — Best good config:")
    print(f"  entry_zscore={best_good[0]}  exit_zscore={best_good[1]}  "
          f"stoploss_zscore={best_good[2]}  max_holding_days={best_good[3]}")
    print(f"  Avg Sharpe={best_good[4]:.2f}")
    sys.exit(0)
else:
    print(f"\nNo config met all thresholds yet.")
    if best_result:
        print(f"Best so far: entry_z={best_params.entry_zscore}  "
              f"Sharpe={best_result[0]:.2f}  DD={best_result[1]*100:.1f}%  "
              f"Win={best_result[2]*100:.0f}%")
    sys.exit(1)
