SYMBOLS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA",
    "JPM", "BAC", "GS", "V",
    "JNJ", "PFE", "UNH",
    "WMT", "HD", "MCD",
    "CAT", "HON", "NFLX",
]
INTERVAL = "1d"
TRADE_OUTSIDE_HOURS = False
SURPRISE_MIN_PCT = 5.0       # min EPS surprise % to trigger entry
HOLDING_DAYS = 25
STOP_LOSS_PCT = 0.08         # 8% stop loss per position
MAX_NEW_POSITIONS_PER_DAY = 3
LOOKBACK_DAYS = 3            # days to look back for recent earnings
POSITION_SIZE_USD = 10_000
