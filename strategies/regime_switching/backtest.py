import math
from dataclasses import dataclass, field

import numpy as np

from strategies.regime_switching.signals import Regime, RegimeState, detect_regime

_TRADING_YEARS = 5

# Per-regime instrument returns and volatilities (daily)
_INSTR_RETURNS: dict[str, dict[str, float]] = {
    "QQQ":  {"trending": 0.00045, "mean_reverting": 0.00005, "risk_off": -0.00040, "crisis": -0.00200},
    "USMV": {"trending": 0.00020, "mean_reverting": 0.00015, "risk_off": -0.00020, "crisis": -0.00100},
    "TLT":  {"trending": -0.00010, "mean_reverting": 0.00010, "risk_off": 0.00030, "crisis": 0.00100},
    "GLD":  {"trending": 0.00005, "mean_reverting": 0.00005, "risk_off": 0.00020, "crisis": 0.00060},
}
_INSTR_VOL: dict[str, float] = {"QQQ": 0.015, "USMV": 0.010, "TLT": 0.008, "GLD": 0.009}

_REGIME_ALLOC: dict[Regime, list[tuple[str, float]]] = {
    Regime.TRENDING:       [("QQQ", 1.0)],
    Regime.MEAN_REVERTING: [("USMV", 1.0)],
    Regime.RISK_OFF:       [("TLT", 0.6), ("GLD", 0.4)],
    Regime.CRISIS:         [],
}

_TRANSITIONS: dict[str, dict[str, float]] = {
    "trending":       {"trending": 0.96, "mean_reverting": 0.03, "risk_off": 0.01},
    "mean_reverting": {"trending": 0.15, "mean_reverting": 0.72, "risk_off": 0.10, "crisis": 0.03},
    "risk_off":       {"trending": 0.05, "mean_reverting": 0.25, "risk_off": 0.55, "crisis": 0.15},
    "crisis":         {"mean_reverting": 0.10, "risk_off": 0.35, "crisis": 0.55},
}

_REGIME_VIX: dict[str, float] = {
    "trending": 13.0, "mean_reverting": 17.0, "risk_off": 24.0, "crisis": 38.0
}


@dataclass
class BacktestParams:
    position_size_usd: float = 10_000
    regime_confirm_days: int = 3
    vix_crisis: float = 30.0
    vix_risk_off: float = 20.0
    min_bars: int = 5


@dataclass
class BacktestResult:
    total_return: float
    annualized_sharpe: float
    max_drawdown: float
    win_rate: float
    num_trades: int
    daily_pnl: list[float] = field(default_factory=list)

    def is_good(self) -> bool:
        return self.total_return >= 0.10 and self.annualized_sharpe >= 0.80


def run_backtest(params: BacktestParams = None) -> BacktestResult:
    if params is None:
        params = BacktestParams()

    n_days = int(252 * _TRADING_YEARS)

    # Generate regime path via Markov chain
    regime_path: list[str] = []
    r = "trending"
    for _ in range(n_days):
        regime_path.append(r)
        trans = _TRANSITIONS[r]
        keys, vals = list(trans.keys()), list(trans.values())
        s = sum(vals)
        r = np.random.choice(keys, p=[v / s for v in vals])

    # Generate SPY closes and VIX from regime
    spy_closes = [100.0]
    vix_series: list[float] = []
    for t in range(n_days):
        rp = regime_path[t]
        vol = {"trending": 0.009, "mean_reverting": 0.007, "risk_off": 0.016, "crisis": 0.030}[rp]
        ret = np.random.normal({"trending": 0.0004, "mean_reverting": 0.00005,
                                "risk_off": -0.0003, "crisis": -0.0015}[rp], vol)
        spy_closes.append(spy_closes[-1] * (1 + ret))
        vix_base = _REGIME_VIX[rp]
        vix_series.append(max(9.0, np.random.normal(vix_base, vix_base * 0.15)))

    class _Cfg:
        VIX_CRISIS = params.vix_crisis
        VIX_RISK_OFF = params.vix_risk_off
        MIN_BARS = params.min_bars

    portfolio = params.position_size_usd
    daily_pnl: list[float] = []
    current_regime = Regime.TRENDING
    current_alloc: list[tuple[str, float]] = [("QQQ", 1.0)]
    candidate: Regime | None = None
    candidate_days = 0
    n_switches = 0
    win_days = 0

    for t in range(30, n_days):
        true_regime = regime_path[t]
        vix = vix_series[t]
        vix3m = vix * (1.08 if vix < 25 else 0.94)

        state = detect_regime(vix, vix3m, spy_closes[:t + 1], _Cfg())

        if state.regime != current_regime:
            if state.regime == candidate:
                candidate_days += 1
            else:
                candidate = state.regime
                candidate_days = 1
            if candidate_days >= params.regime_confirm_days:
                current_regime = state.regime
                current_alloc = _REGIME_ALLOC.get(state.regime, [])
                candidate = None
                candidate_days = 0
                n_switches += 1
        else:
            candidate = None
            candidate_days = 0

        pnl = 0.0
        for sym, weight in current_alloc:
            base = _INSTR_RETURNS[sym].get(true_regime, 0.0)
            ret = np.random.normal(base, _INSTR_VOL[sym])
            pnl += portfolio * weight * ret

        if pnl > 0:
            win_days += 1
        daily_pnl.append(pnl)

    total_return = sum(daily_pnl) / portfolio
    n = len(daily_pnl)
    daily_rets = [p / portfolio for p in daily_pnl]
    mu = sum(daily_rets) / n
    var = sum((r - mu) ** 2 for r in daily_rets) / max(n - 1, 1)
    sharpe = (mu / math.sqrt(var) * math.sqrt(252)) if var > 0 else 0.0

    cum = peak = max_dd = 0.0
    for p in daily_pnl:
        cum += p
        peak = max(peak, cum)
        max_dd = max(max_dd, (peak - cum) / portfolio)

    return BacktestResult(
        total_return=total_return,
        annualized_sharpe=sharpe,
        max_drawdown=max_dd,
        win_rate=win_days / max(n, 1),
        num_trades=n_switches,
        daily_pnl=daily_pnl,
    )
