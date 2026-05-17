# Aggressive — lower entry threshold, 2x leverage, faster rolling window
# Uses a separate pair universe from stat_arb_v1 to avoid conflicting positions.

PAIRS = [
    ("TLT", "IEF"),
    ("SLV", "GLD"),
    ("LUV", "AAL"),
    ("VTI", "ITOT"),
    ("XLE", "VDE"),
]

SYMBOLS = list({sym for pair in PAIRS for sym in pair})

INTERVAL = "1d"
TRADE_OUTSIDE_HOURS = False

FORMATION_DAYS = 252
ROLLING_WINDOW = 30

COINT_PVALUE_THRESHOLD = 0.05
HLIFE_MIN_DAYS = 2.0
HLIFE_MAX_DAYS = 30.0

KALMAN_DELTA = 1e-4
KALMAN_OBS_NOISE = 1e-3

ENTRY_ZSCORE = 1.0
EXIT_ZSCORE = 0.5
STOPLOSS_ZSCORE = 3.0
MAX_HOLDING_DAYS = 45
REENTRY_COOLDOWN_DAYS = 10

POSITION_SIZE_USD = 1_000
