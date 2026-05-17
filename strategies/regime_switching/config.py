# Meta-strategy: detects market regime (trending/mean-rev/risk-off/crisis) and
# allocates to regime-appropriate instruments. Requires 3 consecutive confirmation
# days before switching to prevent whipsawing.
SYMBOLS = ["SPY", "QQQ", "TLT", "GLD", "USMV"]
TRADEABLE_SYMBOLS = ["QQQ", "TLT", "GLD", "USMV"]  # SPY is read-only for regime detection

INTERVAL = "1d"
TRADE_OUTSIDE_HOURS = False

VIX_CRISIS = 30.0       # VIX above this → CRISIS (all cash)
VIX_RISK_OFF = 20.0     # VIX above this → RISK_OFF (bonds + gold)

REGIME_CONFIRM_DAYS = 3  # consecutive days before committing to a new regime

MIN_BARS = 5             # on_bar calls before first regime check (history loaded externally)
POSITION_SIZE_USD = 10_000
