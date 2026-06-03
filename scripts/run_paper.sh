#!/usr/bin/env bash
# Launches all 3 stat arb configs in paper mode.
# Each logs to logs/<strategy>.log and runs as a background process.
# Usage: ./scripts/run_paper.sh
# Stop all: kill $(cat logs/pids.txt)

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SCRIPT_DIR"

mkdir -p logs

run_strategy() {
    local name="$1"
    local log="logs/${name}.log"
    echo "Starting ${name} → ${log}"
    python3 runner.py --strategy "$name" --mode paper --trigger cron \
        >> "$log" 2>&1 &
    echo $!
}

PID1=$(run_strategy stat_arb)
PID2=$(run_strategy stat_arb_v2)
PID3=$(run_strategy stat_arb_v3)

echo "$PID1 $PID2 $PID3" > logs/pids.txt
echo "All 3 strategies running. PIDs: $PID1 $PID2 $PID3"
echo "Logs: logs/stat_arb.log  logs/stat_arb_v2.log  logs/stat_arb_v3.log"
echo "Stop: kill \$(cat logs/pids.txt)"
