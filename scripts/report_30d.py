#!/usr/bin/env python3
"""
Performance summary report. Reads logs/performance.csv and prints stats + ASCII equity curve.
Usage: python3 scripts/report_30d.py [--days 30]
"""
import argparse
import csv
import datetime
import math
import sys
from pathlib import Path

PERF_CSV = Path(__file__).parent.parent / "logs" / "performance.csv"


def _color(val: float, good_positive: bool = True) -> str:
    if val > 0:
        c = "\033[92m" if good_positive else "\033[91m"
    elif val < 0:
        c = "\033[91m" if good_positive else "\033[92m"
    else:
        return f"{val:+.2f}"
    return f"{c}{val:+.2f}\033[0m"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30, help="Lookback window in days")
    args = parser.parse_args()

    if not PERF_CSV.exists():
        print("No performance data yet. The watchdog logs a snapshot each day at 4:30 PM ET.")
        print("You can also run:  python3 scripts/log_performance.py")
        return

    rows = []
    with open(PERF_CSV) as f:
        for row in csv.DictReader(f):
            rows.append(row)

    if not rows:
        print("performance.csv is empty.")
        return

    cutoff = (datetime.date.today() - datetime.timedelta(days=args.days)).isoformat()
    rows = [r for r in rows if r["date"] >= cutoff]

    if not rows:
        print(f"No data in the last {args.days} days.")
        return

    equities = [float(r["equity"]) for r in rows]
    day_pnls = [float(r["day_pnl"]) for r in rows]
    dates = [r["date"] for r in rows]
    positions = [int(r["open_positions"]) for r in rows]

    start_eq = equities[0]
    end_eq = equities[-1]
    total_pnl = end_eq - start_eq
    total_ret_pct = (total_pnl / start_eq * 100) if start_eq else 0.0

    # annualized return
    n_days = max(len(equities) - 1, 1)
    ann_ret = (((end_eq / start_eq) ** (252 / n_days) - 1) * 100) if start_eq > 0 else 0.0

    # max drawdown
    peak = equities[0]
    max_dd = 0.0
    for e in equities:
        if e > peak:
            peak = e
        dd = (peak - e) / peak * 100
        if dd > max_dd:
            max_dd = dd

    # annualized Sharpe
    daily_rets = [
        (equities[i] - equities[i - 1]) / equities[i - 1]
        for i in range(1, len(equities))
        if equities[i - 1] > 0
    ]
    sharpe = 0.0
    if len(daily_rets) > 1:
        mu = sum(daily_rets) / len(daily_rets)
        variance = sum((r - mu) ** 2 for r in daily_rets) / (len(daily_rets) - 1)
        sigma = math.sqrt(variance)
        sharpe = (mu / sigma * math.sqrt(252)) if sigma > 0 else 0.0

    win_days = sum(1 for p in day_pnls if p > 0)
    loss_days = sum(1 for p in day_pnls if p < 0)
    avg_pos = sum(positions) / len(positions)
    best_day = max(day_pnls)
    worst_day = min(day_pnls)

    print("\n" + "=" * 62)
    print(f"  PERFORMANCE REPORT — last {args.days} days")
    print("=" * 62)
    print(f"  Period:           {dates[0]}  →  {dates[-1]}  ({len(dates)} snapshots)")
    print(f"  Start equity:     ${start_eq:>12,.2f}")
    print(f"  End equity:       ${end_eq:>12,.2f}")
    print(f"  Total P&L:        ${total_pnl:>+12,.2f}  ({_color(total_ret_pct)}%)")
    print(f"  Ann. return:      {_color(ann_ret)}%")
    print(f"  Max drawdown:     {max_dd:.1f}%")
    print(f"  Sharpe (ann.):    {sharpe:.2f}")
    print(f"  Win / Loss days:  {win_days} / {loss_days}")
    print(f"  Best day:         ${best_day:>+12,.2f}")
    print(f"  Worst day:        ${worst_day:>+12,.2f}")
    print(f"  Avg open pos.:    {avg_pos:.1f}")
    print("=" * 62)

    # ASCII equity curve
    if len(equities) >= 3:
        print("\n  Equity Curve")
        height = 10
        min_e = min(equities)
        max_e = max(equities)
        rng = max_e - min_e or 1.0
        width = min(len(equities), 58)
        step = max(1, len(equities) // width)
        sampled = equities[::step]

        for row_i in range(height, -1, -1):
            threshold = min_e + rng * row_i / height
            bar = "".join("█" if e >= threshold else " " for e in sampled)
            if row_i == height:
                print(f"  ${max_e:>10,.0f} │{bar}")
            elif row_i == 0:
                print(f"  ${min_e:>10,.0f} │{bar}")
            else:
                print(f"               │{bar}")
        print(f"               └{'─' * len(sampled)}")
        print(f"               {dates[0][:7]}  →  {dates[-1][:7]}")
    print()


if __name__ == "__main__":
    main()
