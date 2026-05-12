# auto-trading

Multi-strategy algorithmic trading framework using [Alpaca](https://alpaca.markets). Each strategy lives in its own folder under `strategies/`. Shared infrastructure (Alpaca client, order management, scheduling, logging) lives in `core/`.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env  # fill in your Alpaca API keys
```

`.env`:
```
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
```

## Running a strategy

```bash
# Paper trading, cron-triggered (default)
python runner.py --strategy example --mode paper --trigger cron

# Live trading, streaming
python runner.py --strategy my_strategy --mode live --trigger stream
```

| Flag | Options | Default |
|------|---------|---------|
| `--strategy` | folder name under `strategies/` | required |
| `--mode` | `paper`, `live` | `paper` |
| `--trigger` | `cron`, `stream` | `cron` |

## Adding a new strategy

1. Copy `strategies/example/` to `strategies/<your_strategy>/`
2. Edit `config.py` — set symbols, interval, and any strategy params
3. Implement `on_bar()` and/or `on_quote()` in `strategy.py`
4. Run it: `python runner.py --strategy <your_strategy> --mode paper`

## Project structure

```
auto-trading/
├── runner.py                  # CLI entry point
├── requirements.txt
├── core/
│   ├── alpaca_client.py       # Alpaca API wrapper
│   ├── base_strategy.py       # abstract BaseStrategy
│   ├── order_manager.py       # buy/sell/close helpers
│   ├── logger.py              # per-strategy file + console logging
│   └── scheduler.py           # cron and stream execution modes
└── strategies/
    └── <name>/
        ├── strategy.py        # implements BaseStrategy
        └── config.py          # symbols, interval, params
```

## Strategy config options

```python
# strategies/<name>/config.py
SYMBOLS = ["AAPL", "TSLA"]       # symbols to trade
INTERVAL = "1m"                   # cron interval: 1m, 5m, 1h, etc.
TRADE_OUTSIDE_HOURS = False       # set True to bypass market hours guard
```

## Logs

Written to `logs/<strategy-name>/YYYY-MM-DD.log` at runtime. Gitignored.
