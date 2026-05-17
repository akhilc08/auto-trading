#!/usr/bin/env bash
# Starts all 9 strategies in background without a watchdog.
# For the auto-restart supervised mode, use: python scripts/watchdog.py [paper|live]
# Usage: ./scripts/run_all.sh [paper|live]
set -euo pipefail

MODE="${1:-paper}"
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SCRIPT_DIR"
mkdir -p logs

STRATEGIES=(
    stat_arb stat_arb_v2 stat_arb_v3
    trend_following trend_following_v2
    multi_factor_equity multi_factor_equity_v2
    market_neutral market_neutral_v2
)

PIDS=()
for name in "${STRATEGIES[@]}"; do
    python runner.py --strategy "$name" --mode "$MODE" --trigger cron \
        >> "logs/${name}.log" 2>&1 &
    PIDS+=($!)
    echo "Started $name (pid=$!)"
done

printf '%s\n' "${PIDS[@]}" > logs/pids.txt
echo ""
echo "${#STRATEGIES[@]} strategies running in $MODE mode."
echo "Logs:  logs/<name>.log"
echo "Stop:  pkill -f 'runner.py --strategy'"
