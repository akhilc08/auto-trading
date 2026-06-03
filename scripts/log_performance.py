#!/usr/bin/env python3
"""
Records a daily account snapshot to logs/performance.csv.
Called automatically by the watchdog at 4:30 PM ET, or run manually any time.
Usage: python3 scripts/log_performance.py [--mode paper|live]
"""
import argparse
import csv
import datetime
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from core.accounts import all_accounts
from core.alpaca_client import AlpacaClient

PERF_CSV = PROJECT_ROOT / "logs" / "performance.csv"
FIELDNAMES = ["date", "equity", "cash", "day_pnl", "open_positions", "total_unrealized_pl"]


def _client_for_account(account: str, mode: str):
    """Load the per-account env file and build a client, or None if the env file is absent."""
    env_path = PROJECT_ROOT / f".env.{account}"
    if not env_path.exists():
        return None
    load_dotenv(env_path, override=True)
    return AlpacaClient(mode=mode)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["paper", "live"], default="paper")
    parser.add_argument(
        "--account", choices=all_accounts(),
        help="Limit to one account; default aggregates across all accounts.",
    )
    args = parser.parse_args()

    accounts = [args.account] if args.account else all_accounts()

    # Aggregate a single portfolio-wide snapshot across the per-account Alpaca
    # accounts. Each account has its own keys in .env.<account>; load them one at
    # a time (override=True) and build the client immediately after.
    equity = cash = day_pnl = total_unrealized = 0.0
    open_positions = 0
    covered: list[str] = []
    for account in accounts:
        client = _client_for_account(account, args.mode)
        if client is None:
            print(f"skip {account}: .env.{account} not found")
            continue
        acct = client.get_account()
        positions = client.trading.get_all_positions()
        equity += float(acct.equity)
        cash += float(acct.cash)
        day_pnl += float(acct.equity) - float(acct.last_equity)
        open_positions += len(positions)
        total_unrealized += sum(float(p.unrealized_pl) for p in positions)
        covered.append(account)

    if not covered:
        print("ERROR: no account env files found (.env.<account>); nothing logged.")
        sys.exit(1)

    today = datetime.date.today().isoformat()
    row = {
        "date": today,
        "equity": f"{equity:.2f}",
        "cash": f"{cash:.2f}",
        "day_pnl": f"{day_pnl:.2f}",
        "open_positions": open_positions,
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
        f"date={today} accounts={','.join(covered)} equity=${equity:,.2f} "
        f"cash=${cash:,.2f} day_pnl=${day_pnl:+,.2f} positions={open_positions}"
    )


if __name__ == "__main__":
    main()
