_ACCOUNT_STRATEGIES: dict[str, list[str]] = {
    "stat_arb":       ["stat_arb", "stat_arb_v2", "stat_arb_v3"],
    "macro_vol":      ["trend_following", "trend_following_v2", "regime_switching", "vol_risk_premium"],
    "market_neutral": ["market_neutral", "market_neutral_v2"],
    "stock_alpha":    ["multi_factor_equity", "multi_factor_equity_v2", "post_earnings_drift"],
}

_STRATEGY_ACCOUNT: dict[str, str] = {
    s: acct
    for acct, strategies in _ACCOUNT_STRATEGIES.items()
    for s in strategies
}


def account_for(strategy: str) -> str:
    return _STRATEGY_ACCOUNT.get(strategy, "default")
