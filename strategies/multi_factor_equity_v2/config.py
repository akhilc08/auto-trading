# Sector/Factor ETF rotation variant — 2-month rebalance, different factor universe.
# Uses ETFs instead of individual stocks so holdings don't conflict with market_neutral.
SYMBOLS = [
    "XLI", "XLC", "XLRE", "XLP", "XLB", "XLY", "XLE",
    "IJH", "IWB", "MGK", "VYM", "MTUM", "USMV", "QUAL", "VNQ",
]

MOM_LOOKBACK = 126
REV_LOOKBACK = 5
VOL_LOOKBACK = 21
REBALANCE_FREQ = 42
TOP_PCT = 0.25
POSITION_SIZE_USD = 8_000
INTERVAL = "1d"
TRADE_OUTSIDE_HOURS = False
