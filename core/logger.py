import logging
import os
from datetime import date


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

    fh = logging.FileHandler(os.path.join(log_dir, f"{date.today()}.log"))
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    return logger
