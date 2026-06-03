import argparse
import importlib
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from core.accounts import account_for
from core.alpaca_client import AlpacaClient
from core.base_strategy import BaseStrategy
from core.logger import get_logger
from core.order_manager import OrderManager
from core.scheduler import run_cron, run_stream

_ROOT = Path(__file__).parent


def _load_env(strategy: str) -> None:
    account = account_for(strategy)
    account_env = _ROOT / f".env.{account}"
    if account_env.exists():
        load_dotenv(account_env, override=True)
    else:
        load_dotenv(_ROOT / ".env")


def main():
    parser = argparse.ArgumentParser(description="Run a trading strategy")
    parser.add_argument("--strategy", required=True, help="Strategy folder name under strategies/")
    parser.add_argument("--mode", choices=["paper", "live"], default="paper")
    parser.add_argument("--trigger", choices=["cron", "stream"], default="cron")
    args = parser.parse_args()

    _load_env(args.strategy)

    try:
        strategy_module = importlib.import_module(f"strategies.{args.strategy}.strategy")
        config_module = importlib.import_module(f"strategies.{args.strategy}.config")
    except ModuleNotFoundError as e:
        print(f"Error: could not load strategy '{args.strategy}': {e}")
        sys.exit(1)

    strategy_class = None
    for name in dir(strategy_module):
        obj = getattr(strategy_module, name)
        if isinstance(obj, type) and issubclass(obj, BaseStrategy) and obj is not BaseStrategy:
            strategy_class = obj
            break

    if strategy_class is None:
        print(f"Error: no BaseStrategy subclass found in strategies/{args.strategy}/strategy.py")
        sys.exit(1)

    logger = get_logger(args.strategy)
    client = AlpacaClient(mode=args.mode)
    account_name = account_for(args.strategy)
    token = os.environ.get("MOTHERDUCK_TOKEN")
    md_logger = None
    if token:
        from core.motherduck_logger import MotherDuckLogger
        md_logger = MotherDuckLogger(token=token)
    order_manager = OrderManager(
        client=client, logger=logger, md_logger=md_logger,
        strategy_name=args.strategy, account_name=account_name,
    )
    strategy = strategy_class(
        client=client,
        order_manager=order_manager,
        logger=logger,
        config=config_module,
    )

    logger.info(f"Starting strategy={args.strategy} mode={args.mode} trigger={args.trigger}")

    try:
        if args.trigger == "cron":
            run_cron(strategy, client, config_module)
        else:
            run_stream(strategy, client, config_module)
    finally:
        if md_logger:
            positions = client.trading.get_all_positions()
            md_logger.snapshot_positions(positions, args.strategy, account_name)
            account = client.trading.get_account()
            md_logger.snapshot_portfolio(account, args.strategy, account_name)
            # Poll fills for today and record them; pnl=None in Phase 1 — trades.pnl
            # column is NULLABLE per SCHEMA-07; P&L deferred to Phase 2 daily_pnl Flight.
            from alpaca.trading.requests import GetOrdersRequest
            from alpaca.trading.enums import QueryOrderStatus
            import datetime as dt
            today = dt.date.today()
            orders = client.trading.get_orders(GetOrdersRequest(
                status=QueryOrderStatus.CLOSED,
                after=dt.datetime.combine(today, dt.time.min, tzinfo=dt.timezone.utc),
            ))
            for o in orders:
                if o.filled_at and o.filled_avg_price:
                    md_logger.update_fill(str(o.id), o.filled_at, float(o.filled_avg_price), None)


if __name__ == "__main__":
    main()
