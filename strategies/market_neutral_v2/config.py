# Financials/Consumer variant — shorter lookback, lower entry threshold.
# Non-overlapping universe vs market_neutral v1 (tech mega-caps).
SYMBOLS = ["BAC", "WFC", "C", "GS", "AXP", "WMT", "TGT", "COST", "CVS", "DG"]
MARKET_PROXY = "SPY"

INTERVAL = "1d"
TRADE_OUTSIDE_HOURS = False

FORMATION_DAYS = 252
ROLLING_WINDOW = 30
ENTRY_ZSCORE = 1.5
EXIT_ZSCORE = 0.3
STOPLOSS_ZSCORE = 3.0
MAX_HOLDING_DAYS = 45
REENTRY_COOLDOWN_DAYS = 7
POSITION_SIZE_USD = 8_000
