# Meta-strategy: detects market regime (trending/mean-rev/risk-off/crisis) and
# allocates to regime-appropriate instruments. Requires 3 consecutive confirmation
# days before switching to prevent whipsawing.
SYMBOLS = ["SPY", "QQQ", "TLT", "GLD", "USMV"]
TRADEABLE_SYMBOLS = ["QQQ", "TLT", "GLD", "USMV"]  # SPY is read-only for regime detection

INTERVAL = "1d"
TRADE_OUTSIDE_HOURS = False

VIX_CRISIS = 30.0       # VIX above this → CRISIS (all cash)
VIX_RISK_OFF = 20.0     # VIX above this → RISK_OFF (bonds + gold)

REGIME_CONFIRM_DAYS = 3  # consecutive days the regime must hold before committing (reconstructed
                         # from recent VIX history each run, not from in-process call counts)

MIN_BARS = 1             # one-shot Flight calls on_bar once per fire; history is loaded inside
                         # the strategy, so no live warm-up bars need to accumulate first
POSITION_SIZE_USD = 10_000
