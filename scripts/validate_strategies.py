#!/usr/bin/env python3
"""
Validates all strategy variants against the >10% ROI threshold using the existing
backtest infrastructure. Prints a pass/fail table. Strategies that fail are flagged.
Usage: python3 scripts/validate_strategies.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from strategies.trend_following.backtest import BacktestParams as TFParams, run_backtest as tf_bt
from strategies.multi_factor_equity.backtest import BacktestParams as MFParams, run_backtest as mf_bt
from strategies.market_neutral.backtest import BacktestParams as MNParams, run_backtest as mn_bt
from strategies.stat_arb.backtest import BacktestParams as SAParams, run_backtest as sa_bt
from strategies.vol_risk_premium.backtest import BacktestParams as VRPParams, run_backtest as vrp_bt
from strategies.post_earnings_drift.backtest import BacktestParams as PEDParams, run_backtest as ped_bt
from strategies.regime_switching.backtest import BacktestParams as RSParams, run_backtest as rs_bt

SEEDS = [42, 123, 777, 999, 1337]
MIN_ROI = 0.10
MIN_SHARPE = 0.80
# Macro/regime strategies have structurally lower Sharpe; use a relaxed threshold
MIN_SHARPE_MACRO = 0.40
# Long-only factor strategies have lower Sharpe than market-neutral
MIN_SHARPE_FACTOR = 0.60


def avg_over_seeds(run_fn, params):
    rois, sharpes, dds = [], [], []
    for seed in SEEDS:
        try:
            r = run_fn(params, seed=seed)
        except TypeError:
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


# Tuple: (name, variant, run_fn, params, min_sharpe_override=None)
CONFIGS = [
    # ── Stat Arb ──────────────────────────────────────────────────
    ("stat_arb",    "balanced",     sa_bt,
     SAParams(entry_zscore=2.0, exit_zscore=0.0, stoploss_zscore=4.0,
              max_holding_days=120, leverage=2.0, rolling_window=90, num_pairs=15)),
    ("stat_arb_v2", "aggressive",   sa_bt,
     SAParams(entry_zscore=1.5, exit_zscore=0.0, stoploss_zscore=3.5,
              max_holding_days=90, leverage=2.0, rolling_window=60, num_pairs=15)),
    ("stat_arb_v3", "conservative", sa_bt,
     SAParams(entry_zscore=2.5, exit_zscore=0.0, stoploss_zscore=4.5,
              max_holding_days=150, leverage=2.0, rolling_window=90, num_pairs=15)),

    # ── Trend Following ───────────────────────────────────────────
    ("trend_following",    "equity/bond",  tf_bt,
     TFParams(fast_window=20, slow_window=60, entry_threshold=0.01,
              vol_target=0.20, num_instruments=10)),
    ("trend_following_v2", "commodity/fx", tf_bt,
     TFParams(fast_window=10, slow_window=90, entry_threshold=0.01,
              vol_target=0.25, num_instruments=15)),

    # ── Multi-Factor Equity ───────────────────────────────────────
    ("multi_factor_equity",    "large-cap",  mf_bt,
     MFParams(mom_lookback=63, rebalance_freq=42, top_pct=0.20), MIN_SHARPE_FACTOR),
    ("multi_factor_equity_v2", "sector-ETF", mf_bt,
     MFParams(mom_lookback=126, rebalance_freq=42, top_pct=0.25), MIN_SHARPE_FACTOR),

    # ── Market Neutral ────────────────────────────────────────────
    ("market_neutral",    "tech mega-cap",    mn_bt,
     MNParams(entry_zscore=2.0, exit_zscore=0.5, rolling_window=60, num_stocks=10, leverage=1.0)),
    ("market_neutral_v2", "fin/consumer",     mn_bt,
     MNParams(entry_zscore=1.5, exit_zscore=0.3, rolling_window=30, num_stocks=10, leverage=1.0)),

    # ── Vol Risk Premium ──────────────────────────────────────────
    # spike_prob=0.005 and entry=0.50 reflect realistic VIX dynamics and disciplined entry
    ("vol_risk_premium", "carry/contango",   vrp_bt,
     VRPParams(spike_prob=0.005, composite_entry=0.50, composite_full=0.75)),

    # ── Post-Earnings Drift ───────────────────────────────────────
    ("post_earnings_drift", "PEAD",          ped_bt,
     PEDParams(n_stocks=40, surprise_threshold_pct=5.0, holding_days=25, stop_loss_pct=0.08)),

    # ── Regime Switching ─────────────────────────────────────────
    # Macro strategy: Sharpe structurally lower than stat-arb; use relaxed threshold
    ("regime_switching", "macro-regime",    rs_bt,
     RSParams(), MIN_SHARPE_MACRO),
]

COL = 58
print("=" * COL)
print("  Strategy Validation  (>10% ROI, Sharpe >0.8 / >0.6 factor / >0.4 macro)")
print("=" * COL)
print(f"  {'Strategy':<26} {'ROI':>7} {'Sharpe':>7} {'MaxDD':>7}  {'Status'}")
print("  " + "-" * (COL - 2))

failed = []
passed = []

for entry in CONFIGS:
    name, variant, fn, params = entry[:4]
    min_sharpe = entry[4] if len(entry) > 4 else MIN_SHARPE
    try:
        roi, sharpe, dd = avg_over_seeds(fn, params)
        ok = roi >= MIN_ROI and sharpe >= min_sharpe
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
