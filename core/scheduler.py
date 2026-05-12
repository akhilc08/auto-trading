import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

ET = ZoneInfo("America/New_York")
MARKET_OPEN = (9, 30)
MARKET_CLOSE = (16, 0)


def _parse_interval(interval: str) -> dict:
    unit_map = {"s": "seconds", "m": "minutes", "h": "hours"}
    unit = interval[-1]
    value = int(interval[:-1])
    if unit not in unit_map:
        raise ValueError(f"Unknown interval unit '{unit}' — use s, m, or h (e.g. '1m', '5m', '1h')")
    return {unit_map[unit]: value}


def _is_market_hours() -> bool:
    now = datetime.now(ET)
    if now.weekday() >= 5:
        return False
    open_dt = now.replace(hour=MARKET_OPEN[0], minute=MARKET_OPEN[1], second=0, microsecond=0)
    close_dt = now.replace(hour=MARKET_CLOSE[0], minute=MARKET_CLOSE[1], second=0, microsecond=0)
    return open_dt <= now <= close_dt


def run_cron(strategy, client, config):
    interval = getattr(config, "INTERVAL", "1m")
    trade_outside_hours = getattr(config, "TRADE_OUTSIDE_HOURS", False)
    interval_kwargs = _parse_interval(interval)

    def job():
        if not trade_outside_hours and not _is_market_hours():
            return
        try:
            bars = client.get_latest_bars(config.SYMBOLS)
            strategy.on_bar(bars)
        except Exception:
            strategy.logger.error(f"Error in on_bar:\n{traceback.format_exc()}")

    scheduler = BlockingScheduler(timezone=ET)
    scheduler.add_job(job, IntervalTrigger(**interval_kwargs))
    strategy.logger.info(f"Cron scheduler started interval={interval} symbols={config.SYMBOLS}")
    scheduler.start()


def run_stream(strategy, client, config):
    stream = client.get_stream()

    async def quote_handler(quote):
        try:
            strategy.on_quote(quote)
        except Exception:
            strategy.logger.error(f"Error in on_quote:\n{traceback.format_exc()}")

    stream.subscribe_quotes(quote_handler, *config.SYMBOLS)
    strategy.logger.info(f"Stream started symbols={config.SYMBOLS}")
    stream.run()
