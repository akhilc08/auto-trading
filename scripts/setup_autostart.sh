#!/usr/bin/env bash
# Installs the watchdog as a macOS launchd agent so it starts automatically at login
# and restarts itself if it ever crashes.
#
# Usage:  ./scripts/setup_autostart.sh [paper|live]
# Remove: launchctl unload ~/Library/LaunchAgents/com.autotrading.watchdog.plist
set -euo pipefail

MODE="${1:-paper}"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$(which python3)"
LABEL="com.autotrading.watchdog"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
LOG_DIR="$PROJECT_DIR/logs"

MISSING=()
for account in stat_arb macro_vol stock_alpha; do
    [[ ! -f "$PROJECT_DIR/.env.$account" ]] && MISSING+=(".env.$account")
done
if [[ ${#MISSING[@]} -gt 0 ]]; then
    echo "ERROR: missing account env files: ${MISSING[*]}"
    echo "Create each file from its .example counterpart and fill in your Alpaca keys."
    exit 1
fi

mkdir -p "$LOG_DIR" "$HOME/Library/LaunchAgents"

cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL}</string>

    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${PROJECT_DIR}/scripts/watchdog.py</string>
        <string>--mode</string>
        <string>${MODE}</string>
    </array>

    <key>WorkingDirectory</key>
    <string>${PROJECT_DIR}</string>

    <!-- launchd restarts watchdog automatically if it exits for any reason -->
    <key>KeepAlive</key>
    <true/>

    <!-- Start immediately when plist is loaded / at login -->
    <key>RunAtLoad</key>
    <true/>

    <!-- Prevent rapid restart loops -->
    <key>ThrottleInterval</key>
    <integer>30</integer>

    <key>StandardOutPath</key>
    <string>${LOG_DIR}/watchdog_stdout.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/watchdog_stderr.log</string>
</dict>
</plist>
PLIST_EOF

# Reload (unload first in case it was already installed)
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo ""
echo "Auto-start installed successfully."
echo ""
echo "  Project: $PROJECT_DIR"
echo "  Python:  $PYTHON"
echo "  Mode:    $MODE"
echo ""
echo "The watchdog is running now and will restart automatically after reboot."
echo ""
echo "Useful commands:"
echo "  Status:   launchctl list | grep autotrading"
echo "  Logs:     tail -f $LOG_DIR/watchdog.log"
echo "  Report:   python3 $PROJECT_DIR/scripts/report_30d.py"
echo "  Dashboard:python3 $PROJECT_DIR/scripts/status.py"
echo "  Stop all: launchctl unload $PLIST"
