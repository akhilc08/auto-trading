import argparse
import importlib
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
    order_manager = OrderManager(client=client, logger=logger)
    strategy = strategy_class(
        client=client,
        order_manager=order_manager,
        logger=logger,
        config=config_module,
    )

    logger.info(f"Starting strategy={args.strategy} mode={args.mode} trigger={args.trigger}")

    if args.trigger == "cron":
        run_cron(strategy, client, config_module)
    else:
        run_stream(strategy, client, config_module)


if __name__ == "__main__":
    main()
