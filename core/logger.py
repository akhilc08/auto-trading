import logging
import os
from logging.handlers import TimedRotatingFileHandler


def get_logger(strategy_name: str) -> logging.Logger:
    log_dir = os.path.join("logs", strategy_name)
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger(strategy_name)
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Roll at local midnight so a long-running scheduler process produces one
    # file per day (a static date-in-name FileHandler would keep writing to the
    # process's start-date file forever). Rolled files get a YYYY-MM-DD suffix.
    fh = TimedRotatingFileHandler(
        os.path.join(log_dir, "strategy.log"), when="midnight", backupCount=30
    )
    fh.suffix = "%Y-%m-%d"
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    return logger
