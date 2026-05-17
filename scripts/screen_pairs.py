#!/usr/bin/env python
"""
ETF pair screener: downloads 3 years of daily prices and tests every pair for
cointegration using Engle-Granger. Results saved to data/screened_pairs.csv.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import yfinance as yf

from strategies.stat_arb.pair_selector import cointegration_test

UNIVERSE = [
    "SPY", "IVV", "VOO", "QQQ", "IWM", "VTI", "DIA", "MDY",
    "VTV", "VUG", "IWD", "IWF", "MTUM", "USMV", "QUAL",
    "XLF", "XLK", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB",
    "VFH", "VGT", "VDE", "VHT", "VIS", "VCR", "VDC", "VPU", "VAW",
    "EFA", "EEM", "VEA", "VWO", "IEFA", "EWJ",
    "TLT", "IEF", "SHY", "BND", "AGG", "LQD", "HYG", "JNK", "TIP",
    "GLD", "SLV", "GDX", "GDXJ", "USO", "UNG", "DBA",
    "VNQ", "IYR",
    "DAL", "UAL", "LUV", "AAL",
    "XOM", "CVX",
    "MSFT", "AAPL", "NVDA",
]

PVALUE_THRESHOLD = 0.05
HLIFE_MIN = 2.0
HLIFE_MAX = 30.0
MIN_ROWS = 504
MAX_MISSING_FRAC = 0.10
MAX_FFILL_DAYS = 3
OUTPUT_CSV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "screened_pairs.csv")
MAX_RESULTS = 50


def download_prices() -> pd.DataFrame:
    raw = yf.download(UNIVERSE, period="3y", auto_adjust=True, progress=False)["Close"]
    n_rows = len(raw)
    keep = [c for c in raw.columns if raw[c].isna().sum() / n_rows <= MAX_MISSING_FRAC]
    raw = raw[keep].ffill(limit=MAX_FFILL_DAYS).dropna()
    return raw


def screen(prices: pd.DataFrame) -> list[dict]:
    symbols = list(prices.columns)
    n = len(symbols)
    log_prices = {s: np.log(prices[s].to_numpy()) for s in symbols}

    pairs_tested = 0
    passing = []

    for i in range(n):
        for j in range(i + 1, n):
            sa, sb = symbols[i], symbols[j]
            la, lb = log_prices[sa], log_prices[sb]
            if len(la) < MIN_ROWS:
                continue
            pairs_tested += 1
            pval, hlife = cointegration_test(la, lb)
            if pval < PVALUE_THRESHOLD and HLIFE_MIN <= hlife <= HLIFE_MAX:
                passing.append({"symbol_a": sa, "symbol_b": sb, "pvalue": pval, "half_life": hlife})

    return pairs_tested, passing


def main():
    print("Downloading ETF prices (3y)…", flush=True)
    prices = download_prices()
    print(f"Downloaded {len(prices.columns)} symbols × {len(prices)} rows", flush=True)

    total_pairs = len(prices.columns) * (len(prices.columns) - 1) // 2
    print(f"Testing {total_pairs} pairs…", flush=True)

    pairs_tested, passing = screen(prices)

    passing.sort(key=lambda x: x["half_life"])
    top = passing[:MAX_RESULTS]

    print(f"\nScreened {pairs_tested} pairs from {len(prices.columns)} symbols")
    print(f"Found {len(passing)} cointegrated pairs (pvalue < {PVALUE_THRESHOLD}, half_life {HLIFE_MIN}-{HLIFE_MAX} days)")
    print()
    print(f"{'Rank':>5}  {'Pair':<20}  {'p-val':>7}  {'Half-life':>10}")

    for rank, p in enumerate(top, 1):
        pair_str = f"{p['symbol_a']} / {p['symbol_b']}"
        print(f"  {rank:3d}  {pair_str:<20}  {p['pvalue']:7.3f}  {p['half_life']:8.1f} days")

    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    df = pd.DataFrame(passing, columns=["symbol_a", "symbol_b", "pvalue", "half_life"])
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\nSaved {len(passing)} pairs to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
