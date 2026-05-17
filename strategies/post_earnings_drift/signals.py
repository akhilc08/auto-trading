import pandas as pd
import yfinance as yf


def get_earnings_surprise(symbol: str, lookback_days: int = 3) -> float | None:
    """
    Returns EPS surprise % (e.g. 15.5 = +15.5%) for the most recent earnings
    announcement within lookback_days, or None if no recent announcement found.
    """
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.earnings_dates
        if df is None or df.empty:
            return None
        now_utc = pd.Timestamp.now(tz="UTC")
        cutoff = now_utc - pd.Timedelta(days=lookback_days)
        recent = df[(df.index >= cutoff) & (df.index <= now_utc)]
        if recent.empty:
            return None
        # Find Surprise(%) column (yfinance may name it differently)
        for col in df.columns:
            if "surprise" in col.lower():
                val = recent[col].dropna()
                if not val.empty:
                    return float(val.iloc[0])
        # Fall back: compute from reported vs estimate
        reported_col = next((c for c in df.columns if "reported" in c.lower()), None)
        estimate_col = next((c for c in df.columns if "estimate" in c.lower()), None)
        if reported_col and estimate_col:
            row = recent.dropna(subset=[reported_col])
            if not row.empty:
                actual = float(row[reported_col].iloc[0])
                est = float(row[estimate_col].iloc[0]) if pd.notna(row[estimate_col].iloc[0]) else None
                if est is not None and abs(est) > 0.001:
                    return (actual - est) / abs(est) * 100.0
        return None
    except Exception:
        return None
