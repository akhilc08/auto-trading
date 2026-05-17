# Conservative — higher entry threshold, no leverage, longer holding window
# Uses a separate pair universe from v1/v2 to avoid conflicting positions.

PAIRS = [
    ("XLF", "VFH"),
    ("XLK", "VGT"),
    ("XLV", "VHT"),
    ("XLU", "VPU"),
    ("DIA", "MDY"),
]

SYMBOLS = list({sym for pair in PAIRS for sym in pair})

INTERVAL = "1d"
TRADE_OUTSIDE_HOURS = False

FORMATION_DAYS = 252
ROLLING_WINDOW = 60

COINT_PVALUE_THRESHOLD = 0.05
HLIFE_MIN_DAYS = 2.0
HLIFE_MAX_DAYS = 30.0

KALMAN_DELTA = 1e-4
KALMAN_OBS_NOISE = 1e-3

ENTRY_ZSCORE = 1.6
EXIT_ZSCORE = 0.5
STOPLOSS_ZSCORE = 3.5
MAX_HOLDING_DAYS = 90
REENTRY_COOLDOWN_DAYS = 10

POSITION_SIZE_USD = 1_000
