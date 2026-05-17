#!/usr/bin/env python
"""
Watchdog: starts all 9 strategies as subprocesses and keeps them running indefinitely.
Restarts any that crash with exponential backoff. Logs a performance snapshot daily at 4:30 PM ET.
Usage:  python scripts/watchdog.py [--mode paper|live]
Setup:  run scripts/setup_autostart.sh once to have this launch automatically on boot.
Stop:   Ctrl-C or kill the watchdog PID (it will cleanly terminate all child processes).
"""
import argparse
import datetime
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
PROJECT_ROOT = Path(__file__).parent.parent
LOG_DIR = PROJECT_ROOT / "logs"

STRATEGIES = [
    "stat_arb",
    "stat_arb_v2",
    "stat_arb_v3",
    "trend_following",
    "trend_following_v2",
    "multi_factor_equity",
    "multi_factor_equity_v2",
    "market_neutral",
    "market_neutral_v2",
]

CHECK_INTERVAL = 30       # seconds between health checks
SNAPSHOT_HOUR = 16        # 4:30 PM ET daily snapshot
SNAPSHOT_MINUTE = 30
STABLE_UPTIME = 600       # seconds before backoff resets
BACKOFF_BASE = 30         # first retry wait in seconds
BACKOFF_MAX = 3_600       # max wait between retries (1 hour)
MAX_RETRIES = 20

LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [watchdog] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_DIR / "watchdog.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("watchdog")


class ProcessWatcher:
    def __init__(self, name: str, mode: str):
        self.name = name
        self.mode = mode
        self.process: subprocess.Popen | None = None
        self.retries: int = 0
        self.start_time: float = 0.0
        self.restart_after: float = 0.0

    def start(self):
        log_path = LOG_DIR / f"{self.name}.log"
        log_file = open(log_path, "a")
        self.process = subprocess.Popen(
            [sys.executable, str(PROJECT_ROOT / "runner.py"),
             "--strategy", self.name, "--mode", self.mode, "--trigger", "cron"],
            cwd=str(PROJECT_ROOT),
            stdout=log_file,
            stderr=log_file,
        )
        log_file.close()
        self.start_time = time.monotonic()
        self.restart_after = 0.0
        log.info(f"[{self.name}] started pid={self.process.pid}")

    def tick(self, now: float):
        if self.process is None:
            return

        if self.process.poll() is None:
            # healthy — reset backoff counter once the process has been stable a while
            if self.retries > 0 and (now - self.start_time) > STABLE_UPTIME:
                log.info(f"[{self.name}] stable, backoff reset")
                self.retries = 0
            return

        # process has exited
        if self.restart_after == 0.0:
            rc = self.process.returncode
            backoff = min(BACKOFF_BASE * (2 ** self.retries), BACKOFF_MAX)
            self.restart_after = now + backoff
            self.retries = min(self.retries + 1, MAX_RETRIES)
            log.warning(
                f"[{self.name}] exited (code={rc}), retry #{self.retries} in {backoff:.0f}s"
            )
            return

        if now >= self.restart_after:
            log.info(f"[{self.name}] restarting (retry #{self.retries})")
            self.start()

    def terminate(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()


def _snapshot(mode: str):
    script = PROJECT_ROOT / "scripts" / "log_performance.py"
    try:
        result = subprocess.run(
            [sys.executable, str(script), "--mode", mode],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            log.info(f"Snapshot: {result.stdout.strip()}")
        else:
            log.error(f"Snapshot failed: {result.stderr.strip()}")
    except Exception as exc:
        log.error(f"Snapshot error: {exc}")


def main():
    parser = argparse.ArgumentParser(description="Strategy watchdog")
    parser.add_argument("--mode", choices=["paper", "live"], default="paper")
    args = parser.parse_args()

    sys.path.insert(0, str(PROJECT_ROOT))
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")

    watchers = {name: ProcessWatcher(name, args.mode) for name in STRATEGIES}
    last_snapshot_date: datetime.date | None = None

    def _shutdown(sig, frame):
        log.info("Shutdown signal received, stopping all strategies...")
        for w in watchers.values():
            w.terminate()
        log.info("All strategies stopped.")
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    # stagger starts to avoid hammering the API
    for i, w in enumerate(watchers.values()):
        w.start()
        if i < len(watchers) - 1:
            time.sleep(2)

    log.info(f"Watchdog running — monitoring {len(STRATEGIES)} strategies (mode={args.mode})")

    while True:
        time.sleep(CHECK_INTERVAL)
        now = time.monotonic()

        for w in watchers.values():
            w.tick(now)

        # daily snapshot at 4:30 PM ET
        now_et = datetime.datetime.now(ET)
        today = now_et.date()
        if (
            now_et.hour == SNAPSHOT_HOUR
            and now_et.minute >= SNAPSHOT_MINUTE
            and last_snapshot_date != today
        ):
            _snapshot(args.mode)
            last_snapshot_date = today


if __name__ == "__main__":
    main()
