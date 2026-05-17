#!/usr/bin/env python
"""
Portfolio status dashboard — shows account summary, open positions, and recent orders.
Usage: python scripts/status.py [--mode paper|live]
"""
import sys
import os
import argparse
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from core.alpaca_client import AlpacaClient

STRATEGIES = [
    "stat_arb", "stat_arb_v2", "stat_arb_v3",
    "trend_following", "trend_following_v2",
    "multi_factor_equity", "multi_factor_equity_v2",
    "market_neutral", "market_neutral_v2",
    "vol_risk_premium", "post_earnings_drift", "regime_switching",
]


def _color(val: float, good_positive: bool = True) -> str:
    if val > 0:
        return f"\033[92m{val:+.2f}%\033[0m" if good_positive else f"\033[91m{val:+.2f}%\033[0m"
    if val < 0:
        return f"\033[91m{val:+.2f}%\033[0m" if good_positive else f"\033[92m{val:+.2f}%\033[0m"
    return f"{val:+.2f}%"


def show_account(client: AlpacaClient) -> None:
    acct = client.get_account()
    equity = float(acct.equity)
    last_equity = float(acct.last_equity)
    cash = float(acct.cash)
    buying_power = float(acct.buying_power)
    day_pnl = equity - last_equity
    day_pct = (day_pnl / last_equity * 100) if last_equity else 0.0

    print("\n" + "=" * 60)
    print("  ACCOUNT SUMMARY")
    print("=" * 60)
    print(f"  Equity:        ${equity:>12,.2f}")
    print(f"  Cash:          ${cash:>12,.2f}")
    print(f"  Buying Power:  ${buying_power:>12,.2f}")
    print(f"  Day P&L:       ${day_pnl:>+12,.2f}  ({_color(day_pct)})")
    print("=" * 60)


def show_positions(client: AlpacaClient) -> None:
    positions = client.trading.get_all_positions()
    if not positions:
        print("\n  No open positions.\n")
        return

    print(f"\n  OPEN POSITIONS ({len(positions)})")
    print(f"  {'Symbol':<8} {'Side':<6} {'Qty':>8} {'Entry':>10} {'Current':>10} {'P&L':>10} {'P&L%':>8}")
    print("  " + "-" * 62)
    total_pnl = 0.0
    for p in sorted(positions, key=lambda x: x.symbol):
        qty = float(p.qty)
        entry = float(p.avg_entry_price)
        current = float(p.current_price)
        pnl = float(p.unrealized_pl)
        pnl_pct = float(p.unrealized_plpc) * 100
        side = p.side.value if hasattr(p.side, "value") else str(p.side)
        total_pnl += pnl
        pnl_str = _color(pnl_pct)
        print(f"  {p.symbol:<8} {side:<6} {qty:>8.0f} {entry:>10.2f} {current:>10.2f} {pnl:>+10.2f} {pnl_str:>8}")
    print(f"\n  Total unrealized P&L: ${total_pnl:>+,.2f}\n")


def show_recent_orders(client: AlpacaClient, hours: int = 24) -> None:
    from alpaca.trading.requests import GetOrdersRequest
    from alpaca.trading.enums import QueryOrderStatus

    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    request = GetOrdersRequest(status=QueryOrderStatus.ALL, after=since, limit=50)
    orders = client.trading.get_orders(filter=request)

    if not orders:
        print(f"  No orders in the last {hours}h.\n")
        return

    print(f"  RECENT ORDERS — last {hours}h ({len(orders)} orders)")
    print(f"  {'Time':<20} {'Symbol':<8} {'Side':<10} {'Qty':>6} {'Status':<12}")
    print("  " + "-" * 58)
    for o in sorted(orders, key=lambda x: x.submitted_at, reverse=True)[:20]:
        t = o.submitted_at.strftime("%m-%d %H:%M") if o.submitted_at else "?"
        side = o.side.value if hasattr(o.side, "value") else str(o.side)
        status = o.status.value if hasattr(o.status, "value") else str(o.status)
        qty = float(o.qty) if o.qty else 0
        print(f"  {t:<20} {o.symbol:<8} {side:<10} {qty:>6.0f} {status:<12}")
    print()


def show_strategy_logs(tail: int = 5) -> None:
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    if not os.path.isdir(log_dir):
        return

    running = []
    for name in STRATEGIES:
        log_path = os.path.join(log_dir, f"{name}.log")
        if os.path.exists(log_path):
            running.append((name, log_path))

    if not running:
        return

    print("  STRATEGY LOGS (last 5 lines each)")
    print("  " + "-" * 58)
    for name, path in running:
        print(f"\n  [{name}]")
        try:
            with open(path) as f:
                lines = f.readlines()
            for line in lines[-tail:]:
                print(f"    {line.rstrip()}")
        except Exception as e:
            print(f"    (could not read log: {e})")
    print()


def main():
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["paper", "live"], default="paper")
    parser.add_argument("--hours", type=int, default=24, help="Order history window in hours")
    args = parser.parse_args()

    client = AlpacaClient(mode=args.mode)

    show_account(client)
    show_positions(client)
    show_recent_orders(client, hours=args.hours)
    show_strategy_logs()


if __name__ == "__main__":
    main()
