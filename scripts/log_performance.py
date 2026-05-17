#!/usr/bin/env python
"""
Records a daily account snapshot to logs/performance.csv.
Called automatically by the watchdog at 4:30 PM ET, or run manually any time.
Usage: python scripts/log_performance.py [--mode paper|live]
"""
import argparse
import csv
import datetime
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from core.alpaca_client import AlpacaClient

PERF_CSV = Path(__file__).parent.parent / "logs" / "performance.csv"
FIELDNAMES = ["date", "equity", "cash", "day_pnl", "open_positions", "total_unrealized_pl"]


def main():
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["paper", "live"], default="paper")
    args = parser.parse_args()

    client = AlpacaClient(mode=args.mode)
    acct = client.get_account()
    positions = client.trading.get_all_positions()

    equity = float(acct.equity)
    last_equity = float(acct.last_equity)
    cash = float(acct.cash)
    day_pnl = equity - last_equity
    total_unrealized = sum(float(p.unrealized_pl) for p in positions)
    today = datetime.date.today().isoformat()

    row = {
        "date": today,
        "equity": f"{equity:.2f}",
        "cash": f"{cash:.2f}",
        "day_pnl": f"{day_pnl:.2f}",
        "open_positions": len(positions),
        "total_unrealized_pl": f"{total_unrealized:.2f}",
    }

    PERF_CSV.parent.mkdir(exist_ok=True)
    write_header = not PERF_CSV.exists()
    with open(PERF_CSV, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if write_header:
            writer.writeheader()
        writer.writerow(row)

    print(
        f"date={today} equity=${equity:,.2f} cash=${cash:,.2f} "
        f"day_pnl=${day_pnl:+,.2f} positions={len(positions)}"
    )


if __name__ == "__main__":
    main()
