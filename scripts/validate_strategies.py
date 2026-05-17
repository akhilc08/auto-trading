#!/usr/bin/env python
"""
Validates all strategy variants against the >10% ROI threshold using the existing
backtest infrastructure. Prints a pass/fail table. Strategies that fail are flagged.
Usage: python scripts/validate_strategies.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from strategies.trend_following.backtest import BacktestParams as TFParams, run_backtest as tf_bt
from strategies.multi_factor_equity.backtest import BacktestParams as MFParams, run_backtest as mf_bt
from strategies.market_neutral.backtest import BacktestParams as MNParams, run_backtest as mn_bt
from strategies.stat_arb.backtest import BacktestParams as SAParams, run_backtest as sa_bt

SEEDS = [42, 123, 777, 999, 1337]
MIN_ROI = 0.10
MIN_SHARPE = 0.80


def avg_over_seeds(run_fn, params):
    rois, sharpes, dds = [], [], []
    for seed in SEEDS:
        np.random.seed(seed)
        r = run_fn(params)
        rois.append(r.total_return)
        sharpes.append(r.annualized_sharpe)
        dds.append(r.max_drawdown)
    return (
        sum(rois) / len(rois),
        sum(sharpes) / len(sharpes),
        sum(dds) / len(dds),
    )


CONFIGS = [
    # ── Stat Arb ──────────────────────────────────────────────────
    ("stat_arb",    "balanced",     sa_bt,
     SAParams(entry_zscore=1.5, rolling_window=60,  stoploss_zscore=3.0, max_holding_days=60,  num_pairs=5)),
    ("stat_arb_v2", "aggressive",   sa_bt,
     SAParams(entry_zscore=1.0, rolling_window=30,  stoploss_zscore=3.0, max_holding_days=45,  num_pairs=5)),
    ("stat_arb_v3", "conservative", sa_bt,
     SAParams(entry_zscore=1.6, rolling_window=60,  stoploss_zscore=3.5, max_holding_days=90,  num_pairs=5)),

    # ── Trend Following ───────────────────────────────────────────
    ("trend_following",    "equity/bond",  tf_bt,
     TFParams(fast_window=20, slow_window=60, entry_threshold=0.01, vol_target=0.20, num_instruments=5)),
    ("trend_following_v2", "commodity/fx", tf_bt,
     TFParams(fast_window=10, slow_window=30, entry_threshold=0.01, vol_target=0.20, num_instruments=10)),

    # ── Multi-Factor Equity ───────────────────────────────────────
    ("multi_factor_equity",    "large-cap",  mf_bt,
     MFParams(mom_lookback=252, rebalance_freq=21, top_pct=0.20)),
    ("multi_factor_equity_v2", "sector-ETF", mf_bt,
     MFParams(mom_lookback=126, rev_lookback=5, vol_lookback=21, rebalance_freq=42, top_pct=0.25)),

    # ── Market Neutral ────────────────────────────────────────────
    ("market_neutral",    "tech mega-cap",    mn_bt,
     MNParams(entry_zscore=2.0, exit_zscore=0.5, rolling_window=60, num_stocks=10, leverage=1.0)),
    ("market_neutral_v2", "fin/consumer",     mn_bt,
     MNParams(entry_zscore=1.5, exit_zscore=0.3, rolling_window=30, num_stocks=10, leverage=1.0)),
]

COL = 58
print("=" * COL)
print("  Strategy Validation  (>10% ROI, Sharpe >0.8)")
print("=" * COL)
print(f"  {'Strategy':<26} {'ROI':>7} {'Sharpe':>7} {'MaxDD':>7}  {'Status'}")
print("  " + "-" * (COL - 2))

failed = []
passed = []

for name, variant, fn, params in CONFIGS:
    try:
        roi, sharpe, dd = avg_over_seeds(fn, params)
        ok = roi >= MIN_ROI and sharpe >= MIN_SHARPE
        status = "\033[92mPASS\033[0m" if ok else "\033[91mFAIL\033[0m"
        label = f"{name} ({variant})"
        print(f"  {label:<26} {roi*100:>6.1f}%  {sharpe:>6.2f}  {dd*100:>6.1f}%  {status}")
        if ok:
            passed.append(name)
        else:
            failed.append((name, roi, sharpe))
    except Exception as exc:
        print(f"  {name:<26}  ERROR: {exc}")
        failed.append((name, 0, 0))

print("=" * COL)
print(f"\n  Passed: {len(passed)}/{len(CONFIGS)}")
if failed:
    print(f"  Failed: {', '.join(n for n, *_ in failed)}")
print()
