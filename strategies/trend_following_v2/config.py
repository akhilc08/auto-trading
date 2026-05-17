# Commodity/International variant — faster windows, different asset class universe.
# Non-overlapping with trend_following v1 (equity/bond focus).
SYMBOLS = ["GLD", "SLV", "USO", "UNG", "DBA", "UUP", "VEA", "EEM", "FXI", "EWJ"]

INTERVAL = "1d"
TRADE_OUTSIDE_HOURS = False

FAST_WINDOW = 10
SLOW_WINDOW = 30
ATR_WINDOW = 14
ENTRY_THRESHOLD = 0.01
VOL_LOOKBACK = 20
VOL_TARGET = 0.20
ATR_STOP_MULTIPLE = 2.5
MAX_HOLDING_DAYS = 40
POSITION_SIZE_USD = 8_000
