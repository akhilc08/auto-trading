# Multi-Factor Cross-Sectional Equity Strategy — Design Specification

**Version**: 1.0  
**Status**: Draft  
**Scope**: Long/Short U.S. Large-Cap Equity  
**Target Gross Exposure**: 200% (100L / 100S notional)  
**Target Annualized Volatility**: 10% (range: 8–15%)

---

## Table of Contents

1. [Strategy Overview & Thesis](#1-strategy-overview--thesis)
2. [Academic Foundations](#2-academic-foundations)
3. [Factor Definitions](#3-factor-definitions)
4. [Signal Construction](#4-signal-construction)
5. [Portfolio Construction](#5-portfolio-construction)
6. [Risk Management](#6-risk-management)
7. [Execution Considerations](#7-execution-considerations)
8. [Regime Sensitivity](#8-regime-sensitivity)
9. [Key Risks & Failure Modes](#9-key-risks--failure-modes)
10. [Parameters & Tunable Knobs](#10-parameters--tunable-knobs)

---

## 1. Strategy Overview & Thesis

### Core Premise

No single factor predicts cross-sectional equity returns reliably enough to survive transaction costs, factor crashes, and changing market regimes. The central insight of multi-factor investing is that individually weak predictors — each with an information coefficient (IC) of 0.02–0.06 — can be combined into a composite signal with meaningfully higher IC (0.10–0.18) when their prediction errors are largely independent. The aggregated signal improves the signal-to-noise ratio, reduces drawdown severity during any single factor's regime of underperformance, and produces a smoother, more consistent alpha stream.

### Strategy Design

This strategy operates as a **cross-sectional, market-neutral, sector-neutral** long/short equity portfolio. At each rebalancing interval, every security in the investable universe receives a composite score derived from six factor families. Securities are ranked by this composite score. The top quintile is bought; the bottom quintile is sold short. The portfolio is constructed to be approximately dollar-neutral and sector-neutral, with beta targeting close to zero via beta-hedge overlays.

Position sizes are scaled to hit a target annualized realized volatility of 10%, adjusted dynamically as realized volatility changes. Turnover is managed explicitly: rebalance trades are executed only when the incremental alpha from trading exceeds the estimated transaction cost.

### Expected Return Profile

- Gross annualized alpha (before costs): 4–8%, depending on market conditions and factor efficacy
- Net alpha (after estimated costs): 2–5%
- Sharpe Ratio (net): 0.6–1.2
- Maximum drawdown (historical analog): 15–30% (severe in 2009 momentum crash, Q4 2018 quality selloff)
- Correlation to S&P 500: target < 0.15; typically achievable at sector-neutral construction

### What This Strategy Is Not

This is not a statistical arbitrage strategy exploiting mean-reversion at the tick level. It is not a fundamental long/short strategy driven by analyst conviction on individual names. It is a systematic, rules-based, cross-sectional ranking strategy that derives its edge from the persistent and academically documented risk premia embedded in the equity market.

---

## 2. Academic Foundations

### 2.1 The CAPM Failure and the Birth of Factor Investing

The Capital Asset Pricing Model (Sharpe 1964, Lintner 1965, Black 1972) predicted that only systematic market beta should explain cross-sectional variation in expected returns. Empirical tests throughout the 1970s and 1980s found this prediction consistently rejected: small-cap stocks outperformed large-cap stocks even after controlling for beta (Banz 1981); low price-to-book stocks earned higher returns than high price-to-book stocks (Rosenberg, Reid, and Lanstein 1985; Stattman 1980). These anomalies were persistent, pervasive across markets, and unexplained by the CAPM framework.

### 2.2 Fama-French Three-Factor Model (1992–1993)

Eugene Fama and Kenneth French published two landmark papers — "The Cross-Section of Expected Stock Returns" (Journal of Finance, 1992) and "Common Risk Factors in the Returns on Stocks and Bonds" (Journal of Financial Economics, 1993) — that crystallized the multi-factor framework. Their three-factor model augments CAPM with:

- **SMB** (Small Minus Big): long small-cap, short large-cap. Captures the size premium.
- **HML** (High Minus Low): long high book-to-market, short low book-to-market. Captures the value premium.

The model explains approximately 90–95% of cross-sectional variation in diversified portfolio returns versus roughly 70% for CAPM alone. The original interpretation was risk-based: small firms and distressed (high B/M) firms are riskier in a way not captured by beta. Behavioral interpretations (investor neglect, overextrapolation of growth) also explain a portion of the premia.

### 2.3 Momentum: Jegadeesh & Titman (1993) and Carhart (1997)

Jegadeesh and Titman (1993, Journal of Finance) documented that buying 12-month winners and selling 12-month losers (skipping the most recent month to avoid reversal) generates approximately 1% per month gross over 3–12 month holding periods. This momentum effect could not be explained by the Fama-French three factors. Mark Carhart (1997) formalized the four-factor model by adding **UMD** (Up Minus Down, also called WML — Winners Minus Losers) to account for mutual fund persistence.

The mechanism behind momentum remains debated. Behavioral explanations include investor underreaction to firm-specific information (Barberis, Shleifer, Vishny 1998), gradual information diffusion (Hong and Stein 1999), and the disposition effect (Grinblatt and Han 2005). Risk-based explanations center on time-varying risk premia and investor funding constraints.

### 2.4 Quality: Sloan (1996), Piotroski (2000), Novy-Marx (2013)

**Sloan (1996)** documented that the accruals component of earnings — the portion not backed by cash flow — negatively predicts future returns. Firms with high accruals tend to have overstated earnings and subsequently disappoint. This was among the first published demonstrations that earnings quality, not just earnings level, matters for returns.

**Piotroski (2000)** constructed the F-score, a nine-point composite of profitability, leverage, and efficiency signals applied to value stocks, separating "winners" from "value traps." The strategy of going long on high F-score value stocks and shorting low F-score value stocks generated approximately 23% annualized returns in the original sample.

**Novy-Marx (2013, Journal of Financial Economics, "The Other Side of Value")** showed that gross profitability — revenues minus cost of goods sold, scaled by total assets — has as much power in predicting the cross-section of returns as the book-to-market ratio, but on the opposite side: value (high B/M) and quality (high GP/A) strategies are negatively correlated, meaning they complement each other excellently in a combined portfolio.

### 2.5 Low Volatility: Black (1972), Frazzini & Pedersen (2014)

Fischer Black (1972) noted early that the Security Market Line is flatter than CAPM predicts: low-beta stocks earn higher risk-adjusted returns than high-beta stocks. This observation lay dormant for decades.

**Frazzini and Pedersen (2014, Journal of Financial Economics, "Betting Against Beta")** formalized this into the BAB factor: a portfolio long low-beta stocks (leveraged to market beta = 1) and short high-beta stocks (de-leveraged to market beta = 1). The mechanism is leverage constraints: investors who cannot use leverage tilt toward high-beta stocks as a substitute, bidding up their prices and depressing their subsequent returns.

**Ang, Hodrick, Xing, and Zhang (2006)** documented a separate but related anomaly: stocks with high idiosyncratic volatility (IVOL) — volatility unexplained by common factors — earn persistently lower future returns. This finding is robust across 23 developed markets (Ang et al. 2009) and is sometimes called the "idiosyncratic volatility puzzle" because it contradicts simple diversification arguments.

### 2.6 Post-Earnings Announcement Drift (PEAD): Ball & Brown (1968), Bernard & Thomas (1989)

Ball and Brown (1968) first observed that stock prices continue drifting in the direction of earnings surprises for months after announcement. Bernard and Thomas (1989) formalized this as a failure of prices to fully incorporate the time-series properties of earnings: investors under-respond to the implications of current earnings for future earnings.

**SUE (Standardized Unexpected Earnings)** = (Actual EPS − Expected EPS) / standard deviation of historical surprises, where expected EPS uses either a seasonal random walk with drift or analyst consensus estimates. High SUE stocks drift upward; low SUE stocks drift downward, typically over a 60–90 day window.

This signal has weakened significantly in large-cap equities since decimalization (2001) and Regulation NMS (2005) enabled faster price discovery. It retains more power in smaller-cap names and when measured using text-based surprise metrics.

### 2.7 Fama-French Five-Factor Model (2015)

Fama and French (2015, Journal of Financial Economics) extended the three-factor model with:

- **RMW** (Robust Minus Weak): long profitable firms, short unprofitable firms (operating profitability)
- **CMA** (Conservative Minus Aggressive): long firms with low asset growth, short firms with high asset growth

A critical finding: in the five-factor model, the HML value factor becomes largely redundant. Value exposure is subsumed by the profitability and investment factors, which together explain the book-to-market premium through the lens of the dividend discount model. This has significant implications for factor design: a pure value signal may be capturing a mix of quality and investment signals that can be decomposed more cleanly.

### 2.8 Institutional Practice: Barra, AQR, D.E. Shaw

**MSCI Barra** industrialized multi-factor risk models beginning in the 1970s. The Barra E3 (U.S. Equity Model) and subsequent USE4 model decompose equity returns into factor and specific (idiosyncratic) components across style factors (momentum, value, size, volatility, quality, leverage, liquidity) and industry factors. The covariance matrix of factor returns, combined with factor exposures, produces ex-ante risk estimates for any portfolio. This infrastructure became the foundation for institutional portfolio construction worldwide.

**AQR Capital Management** (Asness, Moskowitz, Pedersen and colleagues) runs systematic multi-factor equity strategies at scale, combining value, momentum, quality, and defensive (low-beta) factors globally. Their published research, particularly "Value and Momentum Everywhere" (Asness, Moskowitz, Pedersen, 2013, Journal of Finance) and "Quality Minus Junk" (Asness, Frazzini, Pedersen, 2019), provides the clearest public articulation of how these factors are combined in practice. AQR emphasizes that factors with low or negative correlations — particularly value and momentum — provide the most diversification benefit when combined.

**D.E. Shaw** deploys a systematic, risk-aware stock selection approach combining quantitative tools and macro-driven overlays across global equity markets. Though proprietary, their methodology is understood to integrate price, fundamental, and alternative data signals at scale, with explicit risk model constraints at the portfolio level.

---

## 3. Factor Definitions

All factor signals are computed in the cross-section: each stock receives a score, which is then ranked and standardized within the investable universe. Ranks are winsorized at the 1st and 99th percentile before normalization. Each factor outputs a z-score with mean zero and unit standard deviation across the universe.

### 3.1 Momentum (MOM)

**Thesis**: Stocks that have outperformed over the intermediate horizon continue to outperform over the next 1–3 months due to investor underreaction and gradual information diffusion.

**Lookback Window**: 12-1 month (months t-12 through t-2, skipping month t-1)

The skip of the most recent month is essential. Month t-1 exhibits short-term reversal (Jegadeesh 1990) due to bid-ask bounce and liquidity effects, which would pollute a pure momentum signal with mean-reversion noise if included.

**Computation**:

```
MOM_raw(i) = [P(t-1) / P(t-12)] - 1
```

Where P(t-1) is the total-return adjusted price at the end of the prior month and P(t-12) is the price 12 months ago. Total return adjustment includes dividends and splits.

**Variants and Enhancements**:

- *Residual Momentum*: Regress each stock's 12-1 month return on the Fama-French three-factor returns over the same period. Use the residual (stock-specific momentum) as the signal. This removes factor-timing content from momentum and produces a purer idiosyncratic signal with lower factor loading on market beta.
- *52-Week High*: The ratio of current price to 52-week high (George and Hwang 2004) captures a related phenomenon with somewhat different crash risk properties — stocks near their highs tend to outperform.
- *Industry-Adjusted Momentum*: Subtract industry median return from raw momentum before ranking, isolating firm-specific momentum from sector drift.

**Holding Frequency**: Monthly rebalance is standard. Signal half-life is approximately 3–6 months; returns decay substantially beyond 12 months (long-run reversal sets in at 3–5 years).

**Known Weakness**: Subject to severe crashes during sharp market reversals. During the March–May 2009 market recovery, momentum lost over 73% in three months. The mechanism: high-momentum stocks had been short-sellers' favorites; when credit conditions normalized, short covering and forced liquidation of leveraged momentum books caused a violent unwind.

### 3.2 Value (VAL)

**Thesis**: Stocks priced cheaply relative to their fundamental earnings power or book value earn a premium due to a combination of systematic risk (distress risk) and behavioral mispricing (excessive pessimism, extrapolation of bad fundamentals).

**Sub-signals** (all are summed into a composite value z-score using equal weights as a default, IC weights optionally):

**a) Earnings Yield (E/P)**:

```
EY(i) = Trailing Twelve Month (TTM) EPS / Current Price
```

Use TTM EPS from the most recently reported four quarters. Prefer operating EPS or EPS before extraordinary items. For firms with negative EPS, either exclude or apply a "capped" variant where negative EPS is floored at zero (resulting in E/P = 0).

**b) Book-to-Price (B/P)**:

```
B/P(i) = Book Value of Common Equity (most recent annual) / Market Cap
```

Book value = total stockholders' equity minus preferred stock. Use the most recently filed 10-K or 10-Q. This is the original Fama-French HML signal. Note: financial companies (banks, insurance) have meaningfully different book value constructions and require separate handling or exclusion.

**c) Forward Earnings Yield (FEY)**:

```
FEY(i) = Consensus 1-Year Forward EPS Estimate / Current Price
```

Requires analyst estimate data (I/B/E/S or equivalent). Forward-looking and therefore less subject to accounting distortions; however, analyst estimates themselves are subject to systematic biases (anchoring, optimism) that can introduce noise.

**d) Cash Flow Yield (CFY)** (optional, use as tiebreaker):

```
CFY(i) = Operating Cash Flow (TTM) / Enterprise Value
```

Enterprise Value = Market Cap + Debt - Cash. Less susceptible to earnings management than EPS-based metrics.

**Value Composite**:

```
VAL(i) = z(EY) + z(B/P) + z(FEY) + z(CFY)   [then re-standardize]
```

**Lookback**: Annual fundamentals, refreshed quarterly on earnings release dates. Price is current.

**Signal Half-Life**: 12–36 months. Value is the slowest-decaying factor; median half-life in global equity research is approximately 25–30 months. This implies value strategies benefit less from high-frequency rebalancing and more from patience.

**Known Weakness**: Value has experienced extended periods of underperformance (2017–2020 growth vs. value spread widened dramatically; value also suffered in rising-rate environments where growth stocks with long cash flow duration benefited from duration pricing). Value traps — cheap stocks that stay cheap because their businesses deteriorate — are a recurring failure mode addressed by quality overlays.

### 3.3 Quality (QUAL)

**Thesis**: High-quality firms — those with sustainable competitive advantages, conservative balance sheets, and efficient capital allocation — are systematically underpriced because investors underweight the persistence of profitability and overweight near-term earnings volatility.

**Sub-signals**:

**a) Return on Equity (ROE)**:

```
ROE(i) = Net Income (TTM) / Average Shareholders' Equity (beginning + ending, /2)
```

Measures profitability per unit of book equity. High ROE with stable trajectory is preferred over episodic ROE spikes. Use a 3-year average to smooth noise.

**b) Gross Profitability (GP/A)** — Novy-Marx measure:

```
GP/A(i) = (Revenue - COGS) / Total Assets
```

This measure is deliberately simple and less susceptible to accounting manipulation than net income or operating income. Gross profit is the portion of the income statement least affected by management discretion (depreciation schedules, R&D capitalization, etc.). Assets in the denominator scale it to firm size.

**c) Accruals** — Sloan measure (lower accruals = higher quality):

```
Accruals(i) = (Net Income - Operating Cash Flow) / Average Total Assets
```

Higher accruals indicate a larger non-cash component of earnings. The signal is inverted for ranking: lower accruals → higher quality z-score.

**d) Piotroski F-Score** (optional, as a summary quality gate):

Sum of 9 binary signals across three domains:
- Profitability: ROA > 0; ΔROA > 0; Operating Cash Flow / Assets > 0; Cash Flow > ROA (accrual signal)
- Leverage/Liquidity: ΔLong-term Debt/Assets < 0; ΔCurrent Ratio > 0; no new equity issuance
- Efficiency: ΔGross Margin > 0; ΔAsset Turnover > 0

Score range: 0–9. Stocks scoring 7–9 are high quality; 0–2 are low quality (candidate shorts).

**e) Earnings Stability** (optional):

```
EarningsStability(i) = 1 - (StdDev of EPS over prior 5 years / |Mean EPS over prior 5 years|)
```

High stability scores indicate predictable earnings trajectories, which markets tend to pay premium multiples for.

**Quality Composite**:

```
QUAL(i) = z(ROE_3yr) + z(GP/A) + z(-Accruals) + z(EarningsStability)   [re-standardize]
```

**Signal Half-Life**: 18–36 months. Quality is slow-decaying; once established, high-quality competitive positions tend to persist.

**Known Weakness**: Quality stocks traded at elevated multiples into 2020–2022, making the quality long book simultaneously exposed to value-style factor risk (expensive). During rising-rate regimes, high-quality growth companies can experience duration-driven multiple compression that overrides quality fundamentals.

### 3.4 Low Volatility (LVOL)

**Thesis**: Stocks with lower realized beta and lower idiosyncratic volatility earn higher risk-adjusted returns because leverage-constrained investors systematically overpay for high-beta (high-octane) stocks as a substitute for prohibited leverage. The BAB factor exploits this mispricing by going long low-beta and short high-beta, levering and de-levering to beta-neutrality.

**Sub-signals**:

**a) Market Beta (β)**:

```
β(i) = Cov(R_i, R_m) / Var(R_m)
```

Estimated using 1-year (252-day) trailing daily excess returns, with the market being the cap-weighted investable universe or the S&P 500. Beta is winsorized between 0.1 and 3.0 to avoid extremes. For the BAB signal, low-beta stocks receive high scores (signal is the negative of estimated beta).

Shrinkage toward the cross-sectional mean (Blume 1975) or Bayesian shrinkage (Vasicek 1973) reduces estimation error:

```
β_shrunk(i) = w * β_OLS(i) + (1-w) * β_cross_mean
```

Where w ≈ 0.6 (Blume coefficient for monthly rebalance horizon).

**b) Idiosyncratic Volatility (IVOL)**:

```
IVOL(i) = StdDev of daily residuals from Fama-French 3-factor regression over prior 60 days
```

Residuals are the portion of daily returns not explained by the market, SMB, and HML factors. High IVOL stocks (lotteries) are persistently overpriced due to investor preference for positive skewness (Kumar 2009). Signal is the negative of IVOL.

**c) Realized Total Volatility** (simpler alternative):

```
TotalVol(i) = StdDev of daily returns over prior 252 trading days (annualized)
```

Signal is the negative of TotalVol. Less precise than IVOL but requires no factor model.

**Low Volatility Composite**:

```
LVOL(i) = z(-β_shrunk) + z(-IVOL) + z(-TotalVol)   [re-standardize]
```

**Lookback**: Beta estimation: 1 year (252 days) daily. IVOL: 60 days daily. TotalVol: 252 days daily.

**Signal Half-Life**: 6–12 months for beta; 1–3 months for IVOL (faster-decaying).

**Known Weakness**: Low-volatility stocks became significantly crowded between 2010–2020 as factor ETFs proliferated, which compressed forward-looking returns. Additionally, during rising-rate environments, low-vol stocks (often utility and consumer staples proxies) underperform significantly due to their bond-like characteristics and rate sensitivity.

### 3.5 Earnings Drift (DRIFT)

**Thesis**: Markets fail to fully incorporate the implications of earnings surprises at announcement, resulting in a drift in the direction of the surprise over the subsequent 1–3 months.

**Signal Construction**:

**a) SUE (Standardized Unexpected Earnings)**:

```
UE(i) = Actual EPS(q) - Expected EPS(q)
SUE(i) = UE(i) / StdDev(UE(i), prior 8 quarters)
```

Where Expected EPS is either (i) analyst consensus estimate from I/B/E/S N days before announcement or (ii) a seasonal random walk: Expected EPS(q) = EPS(q-4) + drift, where drift = mean(EPS(q) - EPS(q-4) over prior 8 quarters).

**b) Earnings Revision Momentum**:

```
ERM(i) = [Consensus_FY1_EPS(t) - Consensus_FY1_EPS(t-4wk)] / |Consensus_FY1_EPS(t-4wk)|
```

Captures the direction of analyst estimate revisions over the prior four weeks. Upward revisions predict positive price drift; downward revisions predict negative drift.

**c) Guidance/Tone** (alternative data, optional):

Management tone on earnings calls — measured via NLP/LLM-derived sentiment on guidance language — provides incremental signal on the direction of future earnings surprises beyond the quantitative SUE measure. This is the basis of the PEAD.txt research (Philadelphia Fed, 2021).

**DRIFT Composite**:

```
DRIFT(i) = z(SUE) + z(ERM)   [re-standardize]
```

**Critical implementation note**: DRIFT is time-stamped by announcement date. After 90 days, the signal's weight must decay or the stock must be refreshed with a new announcement's data. Stocks without an earnings announcement in the prior 90 days should receive a score of zero (or be excluded from DRIFT ranking).

**Lookback**: Most recent earnings announcement date, but signal degrades after ~60 days.

**Signal Half-Life**: 1–3 months. DRIFT is the fastest-decaying factor in the model. In large-cap equities, much of the drift resolves within 30 days as algorithmic traders rapidly exploit it. The signal is more durable in small and mid-cap.

**Known Weakness**: Largely arbitraged away in large-cap liquid equities since approximately 2006. The signal is most useful as a filter (do not go long a stock with very negative SUE) and as a short-term alpha enhancer for names recently reporting positive surprises.

### 3.6 Size (SIZE)

**Thesis**: Small-cap stocks earn a size premium (Banz 1981; Fama-French 1992) historically, although much of the raw size premium appears to be concentrated in microcaps, January effects, and periods of elevated liquidity premia.

**Signal**:

```
SIZE(i) = -log(Market Cap(i))
```

The negative log of market cap, so smaller stocks receive higher scores. This is the raw SMB loading. In practice, a pure size signal is rarely used in isolation — it is too noisy, too correlated with illiquidity, and too concentrated in microcaps.

**Usage in this strategy**: SIZE is not used as a standalone composite signal at equal weight to the other factors. Instead:

1. Use SIZE as a **control variable** in factor construction: compute all other factor signals within size buckets (large-cap vs. small-cap) to avoid inadvertently taking large size bets.
2. Use SIZE as a **tilt** applied to the composite if the investment mandate explicitly includes a size premium tilt.
3. Apply a **universe exclusion** based on market cap (see Section 5.1) rather than a direct ranking signal.

---

## 4. Signal Construction

### 4.1 Factor Standardization

Before any combination step, each factor is standardized cross-sectionally at each rebalancing date:

```
z(F_i) = [F_raw(i) - median(F)] / (1.4826 * MAD(F))
```

Where MAD is the median absolute deviation. Using robust statistics (median, MAD) rather than mean and standard deviation prevents outliers from distorting z-scores. The constant 1.4826 scales MAD to be comparable to standard deviation for a Gaussian distribution.

After computing z-scores, **winsorize** at ±3 standard deviations to prevent extreme outlier stocks from dominating the composite.

### 4.2 Equal-Weight Composite (Baseline)

The simplest defensible approach to combination is equal weighting:

```
COMP(i) = (1/N) * Σ z(F_k, i)   for k = {MOM, VAL, QUAL, LVOL, DRIFT}
```

Where N = number of active factors (typically 5, excluding SIZE as standalone). Re-standardize COMP to unit variance after combination.

**Justification for equal weighting**: Historical IC estimates for each factor are noisy. Given parameter uncertainty, equal weighting is often as good or better out-of-sample than optimized weights (DeMiguel, Garlappi, Uppal 2009). Equal weighting also avoids overfitting to a specific backtest period and is operationally transparent.

### 4.3 IC-Weighted Composite

The information coefficient (IC) measures the cross-sectional rank correlation between a factor signal and forward returns:

```
IC(k, t) = RankCorr(z(F_k, t), R_forward(t, t+1))
```

Where R_forward is the 1-month forward total return. IC is computed rolling over the prior T months.

**IC-weighted composite**:

```
w_k = IC_k / Σ |IC_k|          (proportional to IC)
COMP(i) = Σ w_k * z(F_k, i)   [re-standardize]
```

An enhancement is to use the **IC Information Ratio** (ICIR) as the weight: ICIR_k = mean(IC_k, rolling T) / std(IC_k, rolling T). ICIR penalizes factors whose IC is unstable (high volatility of IC), not just high average IC.

```
w_k ∝ ICIR_k = mean(IC_k) / std(IC_k)
```

**Practical benchmarks**: A single strong factor has IC ≈ 0.04–0.06 monthly. A well-combined multi-factor composite typically achieves IC ≈ 0.10–0.14. Values above 0.15 are exceptional and should trigger scrutiny for data snooping.

**Rolling window for IC estimation (T)**: 24–60 months. Shorter windows are more responsive to regime changes but noisier. Longer windows are more stable but may be stale. A 36-month rolling window is the default.

### 4.4 Risk-Model-Weighted Composite (Advanced)

A third approach treats the composite signal as an expected return vector and plugs it directly into a risk-model-constrained optimization:

**Inputs**:
- Alpha vector: **α** = COMP scores for all N securities
- Factor covariance matrix: **F** (K×K, from Barra or in-house factor risk model)
- Factor exposures: **X** (N×K)
- Specific risk diagonal: **Δ** (N×N, diagonal)
- Total covariance matrix: **Σ** = X F X' + Δ

**Objective**:

```
max  α' h - λ * h' Σ h
s.t. constraints (gross exposure, net exposure, sector neutrality, position limits)
```

Where **h** is the portfolio holdings vector and λ is the risk aversion parameter. This approach naturally accounts for factor correlations when combining signals: if two factors are highly correlated in a given regime, their joint weight is reduced without requiring explicit pairwise constraints.

**Practical note**: Full mean-variance optimization is sensitive to input estimation error. In practice, firms combine the analytical optimization with hard constraint overlays (position limits, turnover constraints) and prefer robust optimization techniques that maximize alpha net of constraints without placing excessive weight on precise covariance estimates.

### 4.5 Factor Correlation Considerations

The diversification benefit of multi-factor combination depends on low or negative pairwise factor correlations:

| Factor Pair | Typical Correlation | Insight |
|---|---|---|
| MOM vs. VAL | -0.3 to -0.5 | Momentum winners are often growth (expensive); value is cheap — natural hedge |
| QUAL vs. VAL | -0.1 to -0.2 | Quality stocks tend to trade at premium; value stocks tend to be lower quality |
| QUAL vs. MOM | +0.0 to +0.2 | Mild positive: quality firms tend to have better momentum due to persistent earnings |
| LVOL vs. VAL | +0.1 to +0.3 | Low-vol stocks often have moderate value characteristics |
| DRIFT vs. MOM | +0.2 to +0.4 | Positive earnings surprises contribute to momentum; overlap manageable |
| LVOL vs. MOM | -0.2 to -0.3 | Momentum winners are often volatile; low-vol favors stability |

The negative MOM-VAL correlation is the most important: it is the primary source of diversification in combined portfolios. AQR's research demonstrates that a 50/50 MOM-VAL portfolio has a Sharpe ratio substantially higher than either factor alone, precisely because value outperforms when momentum crashes (sharp reversals) and momentum outperforms when value stagnates (growth bull markets).

### 4.6 Factor Decay and Signal Freshness

Not all factors should receive equal weight at every point in time. A signal freshness adjustment accounts for the time elapsed since the underlying data was observed:

- **MOM**: Refresh monthly. Signal is current price-based, always fresh.
- **VAL**: Refresh quarterly (on new earnings release). Book value is annual; price is daily.
- **QUAL**: Refresh quarterly (on new earnings release). Accruals and ROE require TTM data.
- **LVOL**: Refresh monthly. Volatility estimates are rolling and update continuously.
- **DRIFT**: Refresh event-driven (each new earnings announcement). Signal decays after 60–90 days.

For DRIFT specifically, implement a time-decay weight on the SUE signal:

```
DRIFT_decayed(i, t) = SUE(i, t_announce) * exp(-λ * (t - t_announce))
```

Where λ is a decay rate calibrated so that the signal half-life is approximately 45 days (λ ≈ 0.015 per day).

---

## 5. Portfolio Construction

### 5.1 Universe Selection

**Step 1 — Eligible exchange filter**: Include only ordinary common shares listed on NYSE, NASDAQ, AMEX. Exclude ADRs (different governance and reporting), REITs (different financial structure), closed-end funds, MLPs, BDCs, ETFs, and preferred shares.

**Step 2 — Market capitalization minimum**: Exclude stocks below $500M market cap (default; tunable). This prevents dominance of illiquid microcaps whose factor premia often exist on paper but cannot be captured net of transaction costs. For a large-fund implementation (>$1B), raise to $1B–$2B.

**Step 3 — Liquidity filter**: Require 30-day average daily dollar volume (ADDV) ≥ $5M. For capacity-constrained funds, apply position size ≤ 10% of 30-day ADDV to ensure trades can be executed within 1–5 days without meaningful market impact.

**Step 4 — Price minimum**: Exclude stocks trading below $5 per share to avoid bid-ask spread distortions (percentage cost is very high for low-price stocks) and exchange compliance issues.

**Step 5 — Survivorship bias prevention**: CRITICAL. All historical backtesting must use a point-in-time (PIT) data set that includes stocks that were subsequently delisted due to bankruptcy, merger, or deregistration. Excluding these inflates backtest returns by 1–3% annually. Use Compustat/CRSP merged databases with delisting returns properly applied.

**Step 6 — Sector exclusions (optional)**: Financial stocks (SIC 6000–6999) require special treatment due to the meaninglessness of book value and the regulatory capital structure. Either exclude financials entirely, or build a separate financial-sector model with adapted signal definitions.

**Typical universe size**: 500–1,500 securities for a U.S. large/mid-cap universe.

### 5.2 Ranking and Basket Formation

At each rebalancing date:

1. Compute COMP(i) for all securities in the universe.
2. Assign each security to a quintile (Q1 through Q5) based on COMP rank.
   - Q1 = top 20% composite score → **Long basket**
   - Q5 = bottom 20% composite score → **Short basket**
   - Q2–Q4 = neutral, not traded (used for performance attribution)
3. Within each basket, assign equal dollar weight unless using volatility-scaled weighting (see Section 5.5).

**Quintile vs. decile baskets**: Quintiles (top/bottom 20%) offer better diversification; deciles (top/bottom 10%) offer higher signal concentration but higher idiosyncratic risk. The default is quintiles.

### 5.3 Sector Neutralization

Sector neutralization ensures the portfolio has no net exposure to GICS sector factors. Without neutralization, the composite score may heavily favor, say, Energy or Technology based on current factor regimes, introducing large sector bets that are not compensated by the factors.

**Implementation — Rank Within Sector**:

For each security, compute the composite z-score within its GICS sector. This is equivalent to demeaning COMP by the sector median:

```
COMP_neutral(i) = COMP(i) - median(COMP, sector(i))
```

Then re-rank globally using COMP_neutral. The resulting portfolio will be approximately dollar-balanced within each sector.

**Alternative implementation — Sector-neutral optimization**: In the mean-variance framework, add a constraint that sector exposures are bounded:

```
|Σ_{i in sector s} h(i)| ≤ sector_cap   for all sectors s
```

Where sector_cap might be 2–3% of net asset value.

**Trade-offs**: Sector neutralization reduces the information ratio of momentum specifically, because momentum has genuine sector-level content (entire sectors rotate). The decision to sector-neutralize should be explicit: do so if the mandate is purely stock-picking alpha; relax it if sector rotation return is acceptable.

### 5.4 Beta Neutralization

**Dollar-neutral**: Ensure long market value = short market value. This eliminates first-order market exposure.

**Beta-neutral**: Dollar neutrality does not suffice because high-beta shorts and low-beta longs produce a portfolio with negative net beta (short market). Correct this by computing:

```
β_portfolio = Σ h(i) * β(i)
```

If β_portfolio ≠ 0, apply a beta hedge via index futures (S&P 500 or Russell 1000 futures):

```
futures_notional = -β_portfolio * portfolio_NAV / futures_multiplier
```

This brings β_portfolio to approximately zero without transacting in individual stocks.

**Industry/country beta**: In addition to market beta, verify that the portfolio has minimal loading on other systematic factors (sector betas, rate sensitivity). These can be controlled in the optimization step with bounds on Barra-style factor exposures.

### 5.5 Position Sizing

**Approach A — Equal Dollar Weighting within Basket**:

```
h(i) = ±(1 / N_basket) * Target_Gross_Notional / 2
```

Simple, transparent, and robust. N_basket = number of stocks in the long or short basket.

**Approach B — Volatility-Scaled Weighting** (preferred):

Assign weights inversely proportional to each stock's idiosyncratic volatility or total volatility:

```
w(i) ∝ 1 / IVOL(i)   [normalized to sum to 1 within basket]
```

This ensures that high-volatility stocks do not dominate portfolio risk. The resulting portfolio is closer to risk parity within each basket.

**Approach C — Score-Proportional Weighting**:

Assign weights proportional to composite score distance from the median:

```
w(i) ∝ |COMP(i) - median(COMP)|   [normalized within basket]
```

This concentrates more weight in highest-conviction names. Creates more portfolio concentration risk.

**Default**: Approach B (volatility-scaled) is recommended for the primary implementation.

### 5.6 Portfolio-Level Volatility Targeting

Compute the realized portfolio volatility over a rolling window:

```
σ_realized = StdDev(R_portfolio(t), rolling 60-day window) * sqrt(252)
```

Scale the entire portfolio by:

```
leverage_scalar = σ_target / σ_realized
```

Apply bounds: minimum leverage_scalar = 0.5, maximum = 2.0 (prevent over-leverage in very low-vol periods or extreme de-risking in high-vol periods).

The effect: during calm markets, the portfolio may run at 1.2x target gross exposure; during volatile periods (VIX > 30), it reduces to 0.7x or less. This automatic de-risking during stress is a key risk management property and reduces the severity of drawdowns during factor crashes.

**Implementation note**: The scalar is updated at each rebalancing event, not continuously. Continuous scaling would create excessive turnover from leverage adjustments.

---

## 6. Risk Management

### 6.1 Position-Level Limits

| Limit | Default | Range | Rationale |
|---|---|---|---|
| Max single stock gross weight | 2.0% of NAV | 1.0–3.0% | Prevent idiosyncratic blow-ups |
| Max single stock net weight | ±1.5% of NAV | ±0.75–2.0% | Directional concentration |
| Max position as % of ADDV | 10% | 5–15% | Liquidity constraint |
| Min position size (for inclusion) | 0.1% of NAV | 0.05–0.25% | Transaction cost efficiency |

### 6.2 Factor Exposure Caps

Measured in units of cross-sectional z-score, the portfolio's net factor loading should stay within bounds:

| Factor | Max Net Long Exposure | Max Net Short Exposure |
|---|---|---|
| Market Beta | +0.10 | -0.10 |
| SMB (Size) | +0.20 | -0.20 |
| HML (Value) | +0.30 | -0.30 |
| UMD (Momentum) | +0.30 | -0.30 |
| Quality | +0.30 | -0.30 |
| Low Volatility | +0.30 | -0.30 |
| Any single GICS sector | ±5% net notional | ±5% net notional |

Factor exposures exceeding these limits trigger a soft constraint: the optimization adds a penalty for out-of-bound exposures. Hard stops are applied if exposures breach 1.5x the soft limit.

### 6.3 Gross and Net Leverage Limits

| Measure | Default | Maximum |
|---|---|---|
| Target gross exposure | 200% (100L / 100S) | 250% |
| Net equity exposure | ±10% of NAV | ±20% |
| Maximum leverage scalar (vol targeting) | 2.0x | 2.5x |

### 6.4 Drawdown Stop-Losses

Multi-factor strategies do not use stock-level stop-losses in the traditional sense — selling individual losers on price movement would degrade mean-reversion signals and introduce negative momentum alpha. However, portfolio-level risk limits apply:

**Portfolio-level drawdown triggers**:

| Drawdown from High-Water Mark | Action |
|---|---|
| 5% | Review factor exposures; check for crowding signals |
| 10% | Reduce gross exposure by 20% (vol targeting typically achieves this automatically) |
| 15% | Reduce gross exposure by 40%; escalate to risk committee |
| 20% | Emergency de-risk: cut to 50% of target gross; conduct full factor diagnosis |

**Factor-specific drawdown monitoring**: Track the running P&L attribution by factor daily. If any single factor generates a loss exceeding 3× its expected monthly standard deviation, investigate whether a factor crash (momentum) or regime shift (value) is occurring.

### 6.5 Crowding Risk Monitoring

Factor crowding — when many systematic funds hold similar positions — amplifies the severity of factor crashes during liquidation events. Monitor via:

1. **Ownership-based crowding**: Track hedge fund 13-F filings (quarterly). Compute the fraction of outstanding shares held by known quant funds for each position. Flag stocks where quant ownership > 15% of float.

2. **Price-based crowding signals (daily)**: Compute the average correlation of returns between the long book and the short book within each sector. Elevated intra-book correlations indicate clustering. Alternatively, use the MSCI Crowding Score (a commercial product combining short interest, ownership, and factor exposure data).

3. **Short interest**: For short-side positions, track days-to-cover (short interest / ADDV). Positions with days-to-cover > 10 are at elevated short-squeeze risk.

4. **Factor spread history**: Compare the current value-minus-growth spread, or current momentum book return, to historical percentiles. Extreme spreads (> 2σ) may indicate overcrowding or a pending reversion.

### 6.6 Correlation and Scenario Monitoring

Run the following scenario analyses monthly:

- **2008 Credit Crisis**: A 40% equity drawdown scenario. Long book typically loses more in a high-quality/low-vol tilt; market-neutral structure should dampen most market loss.
- **2009 Momentum Crash**: A momentum factor crash of 15–25% in one month. Estimate loss from momentum exposure net of diversification.
- **2020 COVID Risk-Off**: Factor dispersion collapses; all-factor correlations spike; liquidity premium expands.
- **Value Rally (2020 Nov)**: A sudden rotation from growth to value. Long/short book reversal potential.
- **Rate Shock**: 100bp rapid rate increase. Impact on low-vol stocks (bond proxies) and growth-oriented quality names.

---

## 7. Execution Considerations

### 7.1 Rebalancing Cadence

The optimal rebalancing frequency balances the trade-off between signal freshness (captured by rebalancing more often) and transaction costs (minimized by rebalancing less often). Academic research (Flint and Vermaak 2022; Quantpedia research) indicates:

| Factor | Optimal Rebalance Cadence | Reason |
|---|---|---|
| Momentum | Monthly | Signal half-life ~3–6 months; faster decay than value |
| Value | Quarterly | Slow-decaying; annual/quarterly fundamental updates |
| Quality | Quarterly | Fundamental data; slow-decaying |
| Low Volatility | Monthly | Volatility estimates update monthly; weekly would be over-trading |
| DRIFT | Event-driven + monthly | SUE signal is event-triggered; must refresh on announcement dates |

**Combined strategy default**: Monthly rebalancing for the portfolio, with intra-month refreshes for DRIFT on earnings announcement dates.

**Staggered rebalancing**: To reduce market impact, divide the portfolio into three sub-portfolios and rebalance one-third of positions on each of three monthly rebalancing dates (Week 1, Week 2, Week 3). This converts a concentrated monthly rebalancing event into a continuous average, reducing price impact from correlated order flow.

### 7.2 Transaction Cost Model

Use a pre-trade cost model to estimate implementation shortfall before executing any rebalance:

**Cost components**:

1. **Bid-ask spread**: 0.01–0.05% one-way for large-cap liquid stocks; 0.10–0.50% for mid-cap.
2. **Market impact**: For an order of size Q as a fraction of ADDV, the linear impact estimate:

   ```
   Impact(i) = σ(i) * sqrt(Q / ADDV(i)) * participation_rate_factor
   ```

   Where σ(i) is daily volatility. A more precise estimate uses the square-root model: impact ≈ 0.1% for 1% of ADDV participation.

3. **Commission**: ~$0.003–$0.005 per share for DMA execution; assume 0.01% of notional.
4. **Borrow cost (for shorts)**: 0.25–2.5% annualized for large-cap liquid stocks; 2–10%+ for hard-to-borrow names. Short availability and borrow cost must be checked before any short position is established.

**Total estimated round-trip cost**: 0.10–0.30% for liquid large-cap; 0.30–0.75% for less liquid mid-cap names.

### 7.3 Turnover Management

**Turnover budget**: Target 300–500% annual two-way turnover (150–250% one-way). This corresponds to approximately 25–40% portfolio turnover per month.

**Trade filter — Alpha-cost threshold**: Only execute a trade if the incremental alpha from trading exceeds the estimated transaction cost:

```
Execute trade if: IC_factor * z_score_improvement > trade_cost_estimate
```

Equivalently, maintain a "buffer zone": do not rebalance a position if it has drifted no more than 0.5 z-score units from the target weight. Only trade when drift exceeds 1.0 z-score units or when a position has crossed quintile boundaries.

**Optimization-based turnover control**: Add an explicit turnover penalty to the portfolio optimization:

```
max  α' h - λ * h' Σ h - γ * ||h - h_prev||_1
```

Where γ is the turnover aversion parameter. Higher γ increases persistence of existing positions. Calibrate γ so that expected turnover matches the turnover budget.

### 7.4 Execution Venues and Timing

- **Primary venue**: Use algorithmic execution via VWAP or Implementation Shortfall algorithms on lit exchanges (NYSE, NASDAQ).
- **Dark pools**: For block trades (> 0.5% of ADDV), route to dark pools (IEX, Liquidnet) to minimize market impact.
- **Timing**: Avoid first 30 minutes and last 30 minutes of the trading day for rebalancing trades due to elevated bid-ask spreads and volatility.
- **Earnings announcement windows**: Do not trade stocks within 2 trading days before or after their earnings announcement. Spreads widen and price impact estimates are unreliable.

### 7.5 Short-Side Execution

Short selling requires:

1. **Borrow availability confirmation** before order submission. Fail-to-borrow events create forced buybacks at inopportune times.
2. **Borrow cost awareness**: If estimated annual borrow cost > 200 bps, discount the short-side signal by borrow cost before including the position. The net alpha on the short must exceed borrow.
3. **Recall risk**: Prime brokers can recall lent shares on demand. Monitor recall risk (particularly around proxy record dates, corporate events) and maintain 110–120% of the required short quantity as available borrow headroom.

---

## 8. Regime Sensitivity

### 8.1 Favorable Regimes

The multi-factor strategy tends to perform well under the following market conditions:

**Stable, moderately trending equity markets** (2003–2007, 2013–2018):
- Momentum works cleanly when trends persist.
- Value and quality provide steady alpha from fundamental differentiation.
- Low volatility provides consistent positive carry.

**Post-crisis recoveries with gradual normalization** (2010–2012):
- Quality outperforms as investors seek safety.
- Value recovers from crisis discounts.

**High factor dispersion environments**:
- When inter-stock return dispersion is high, there is more room for factors to differentiate winners from losers, and the spread between the long book and short book is wide.

**Low macro correlation environments**:
- When stock returns are more driven by idiosyncratic fundamentals than macro sentiment, factor-based signals are more reliable.

### 8.2 Adverse Regimes

**Sharp market reversals with high short-term correlations** (2009 Q1, 2020 March):
- Momentum crashes violently when markets reverse sharply.
- All correlations spike to 1; factor diversification breaks down temporarily.
- Long/short portfolio suffers from "crowded exit" dynamics as many quant funds unwind simultaneously.
- Duration: weeks to months. Recovery can be rapid but P&L hit is severe.

**Prolonged value underperformance** (2010–2020 growth vs. value spread):
- Value factor consistently loses; momentum partially compensates.
- Portfolio suffers if value is not balanced against momentum.
- Root cause: ultra-low interest rates compressed discount rates, disproportionately benefiting growth/quality stocks over value.

**Rising interest rate environment** (2022):
- Low-volatility factor underperforms severely (bond proxy equities reprice with rate shock).
- Quality/growth stocks suffer from duration-driven multiple compression.
- Value factor outperforms — partially compensating if value weight is meaningful.

**Liquidity crises** (2008, March 2020):
- Market-impact costs spike 5–10× normal; bid-ask spreads blow out.
- Short-side positions suffer from forced buybacks and short squeezes.
- The volatility targeting mechanism helps: σ_realized spikes → leverage scalar drops → gross exposure automatically reduced.

**Factor crowding unwind** (August 2007 "Quant Quake", Q4 2018):
- When a large quant fund is forced to liquidate, selling pressure hits the exact long positions and buying pressure hits the exact short positions of similar funds running the same factors.
- Portfolio suffers even though fundamental factors still predict returns.
- Resolution: typically 1–3 weeks; strong recovery follows once forced selling exhausts.

**Regime detection signals** (leading indicators of adverse regimes):

| Signal | Adverse Condition |
|---|---|
| VIX level | > 25 (elevated vol regime → reduce gross exposure) |
| Factor volatility | MOM or VAL 1-month return > 2σ negative → factor crash risk |
| Cross-stock correlation | Average pairwise correlation > 0.50 → macro-driven, factors less useful |
| Crowding score | > 80th percentile → consider reducing factor exposures |
| Rate sensitivity | 30-day rolling correlation between portfolio and TLT > 0.30 → LVOL over-exposed |

---

## 9. Key Risks & Failure Modes

### 9.1 Momentum Crashes

**Description**: The momentum factor can lose 20–75% of its value within a single month during sharp equity market reversals. The mechanism: high-momentum stocks carry short interest from contrarians and leverage from trend-following funds. When the market reverses sharply (often from oversold conditions), short covering and forced deleveraging create a violent feedback loop.

**Documented instances**: May 2009 (−73% in 3 months), September–November 1932 (extreme historical crash), and multiple smaller crashes in other reversal events.

**Mitigation**: (1) Volatility targeting reduces momentum exposure before crashes (high-vol stocks have lower weights in the low-vol framework). (2) Residual momentum (factor-adjusted) has lower crash risk than raw price momentum. (3) Monitoring "momentum crowding" via concentration of quant fund holdings in momentum names. (4) Explicitly modeling the conditional skewness of momentum: Daniel and Moskowitz (2016) show that momentum crashes are predictable — they are more likely when market volatility is high, the market has recently fallen, and momentum has recently outperformed. A crash risk-adjusted momentum signal (BAM — Betting Against Momentum Crash) can reduce exposure in these predicted high-crash-risk periods.

### 9.2 Factor Crowding and Quant Quakes

**Description**: When many systematic funds run similar factor models on similar universes, their portfolios overlap. A forced liquidation by one fund creates price pressure on all funds' books simultaneously. The August 2007 "Quant Quake" saw statistically unprecedented multi-sigma losses in systematic equity strategies over 3–5 days.

**Mitigation**: (1) Monitor crowding scores continuously. (2) Include "alternative factors" with lower quant fund penetration (e.g., text-based signals, alternative data) to maintain differentiation. (3) Size positions as a fraction of ADV to maintain the ability to exit within a 3–5 day window. (4) Maintain cash reserves (5–10% of NAV) as a buffer during liquidation events.

### 9.3 Value Traps

**Description**: Stocks that screen as cheap (high B/P, high E/P) often remain cheap because their fundamentals are genuinely deteriorating. Pure value strategies buy these and hold them through prolonged periods of fundamental disappointment.

**Mitigation**: (1) Quality overlay: use the quality composite to exclude "cheap but deteriorating" stocks from the long book and "expensive but improving" stocks from the short book. (2) Piotroski F-score as a quality gate on value longs. (3) Momentum filter: avoid going long on value stocks with strongly negative momentum (falling knives).

### 9.4 Short-Side Squeeze Risk

**Description**: The short book is exposed to short squeezes — coordinated retail buying (as in the 2021 GameStop event) or forced covering by other funds can cause rapid price increases in heavily shorted stocks regardless of fundamental quality.

**Mitigation**: (1) Monitor short interest / float for each short position. (2) Cap position size in high-short-interest names (days-to-cover > 7 → reduce to 50% of standard position size). (3) Avoid names with active short-seller campaigns in the media (elevated squeeze risk). (4) Retail coordination risk is harder to monitor; track WallStreetBets-type forums via text monitoring systems.

### 9.5 Survivorship Bias and Data Snooping

**Description**: Backtests using data that excludes delisted stocks overstate factor returns by 1–3% annually. Additionally, the academic literature has documented hundreds of "factors" — using many of these to construct a composite inflates backtest performance through factor selection bias.

**Mitigation**: (1) Use point-in-time databases with delisting returns. (2) Limit factor selection to those with out-of-sample international evidence (Fama-French factors work globally, not just in the U.S.). (3) Apply a multiple testing adjustment when evaluating new factor candidates (Harvey, Liu, and Zhu 2016 suggest a t-statistic threshold of 3.0 for new factor claims, versus the conventional 2.0). (4) Reserve a true holdout period (last 5 years of data not seen during model development) for final validation.

### 9.6 Earnings Quality Deterioration

**Description**: Corporate earnings management can corrupt quality and value signals. Firms manipulate accruals, channel-fill, and time restructuring charges to beat consensus estimates, making reported earnings an unreliable signal.

**Mitigation**: (1) Emphasize cash-flow-based metrics (Operating Cash Flow / Assets) over net income-based metrics. (2) Use the Sloan accruals measure specifically to detect earnings manipulation. (3) Monitor earnings restatements in the portfolio; any restatement triggers immediate position review.

### 9.7 Regulatory and Market Structure Changes

**Description**: Regulatory changes (e.g., new short-selling restrictions in a crisis, changes to reporting requirements, or exchange fee structure changes) can alter the efficacy of factor signals.

**Mitigation**: Monitor regulatory calendars. Maintain awareness of short-selling circuit breakers. Update transaction cost models after major exchange fee changes (e.g., SEC Regulation NMS amendments).

---

## 10. Parameters & Tunable Knobs

The following table enumerates all tunable parameters, their default values, and the reasonable calibration range. Parameters should be re-evaluated annually or when there is evidence of structural market change. Changes to parameters mid-period require documentation and performance attribution to verify the change is not data-snooping.

### 10.1 Universe Parameters

| Parameter | Default | Range | Notes |
|---|---|---|---|
| Minimum market cap | $500M | $200M–$2B | Scale up for larger AUM |
| Minimum 30-day ADDV | $5M | $2M–$20M | Scale up for larger AUM |
| Minimum stock price | $5.00 | $2.00–$10.00 | Lower for small-cap expansion |
| Max position as % ADDV | 10% | 5%–20% | Liquidity constraint |
| Include financials | No (default) | Yes/No | Requires separate model if yes |
| Include REITs | No | Yes/No | Different factor behavior |
| Universe size target | 800–1,200 | 400–2,000 | |

### 10.2 Factor Construction Parameters

| Parameter | Default | Range | Notes |
|---|---|---|---|
| **Momentum** | | | |
| Lookback window | 12-1 month | 6-1 to 18-1 month | Longer captures slower drift |
| Use residual vs. raw | Residual | Raw / Residual | Residual has lower crash risk |
| **Value** | | | |
| E/P data frequency | TTM | TTM / FY0 / FY1 | FY1 is forward-looking |
| B/P reporting lag | Most recent quarter | Annual / Quarterly | Quarterly more responsive |
| **Quality** | | | |
| ROE averaging period | 3-year average | 1–5 years | Longer reduces noise |
| Accruals method | Sloan (1996) | Sloan / Richardson et al. | Richardson adjusts for WC items |
| **Low Volatility** | | | |
| Beta estimation window | 252 days | 126–504 days | Shorter = more responsive |
| Beta shrinkage weight | 0.6 | 0.4–0.8 | Blume coefficient |
| IVOL estimation window | 60 days | 30–126 days | Shorter = noisier |
| **Drift (PEAD)** | | | |
| SUE expected EPS | Analyst consensus | Analyst / seasonal RW | |
| Signal decay half-life | 45 days | 30–90 days | Decay rate λ |

### 10.3 Signal Combination Parameters

| Parameter | Default | Range | Notes |
|---|---|---|---|
| Combination method | Equal weight | Equal / IC-weight / ICIR-weight | IC-weight requires sufficient history |
| IC rolling window | 36 months | 24–60 months | |
| Winsorization threshold | ±3 z-scores | ±2–4 | |
| Standardization method | Median/MAD | Mean/Std / Median/MAD | MAD is more robust |
| Factor weights (equal-weight baseline) | MOM:20%, VAL:20%, QUAL:20%, LVOL:20%, DRIFT:20% | Each: 10%–40% | Must sum to 100% |

### 10.4 Portfolio Construction Parameters

| Parameter | Default | Range | Notes |
|---|---|---|---|
| Basket definition | Top/bottom quintile | Top/bottom decile–tercile | Decile = more concentrated |
| Position sizing | Volatility-scaled | Equal / Vol-scaled / Score-proportional | |
| Sector neutralization | Within-sector ranking | Global ranking / Optimization constraint | |
| Beta neutralization | Futures overlay | Hard constraint / Futures overlay | Futures overlay is more flexible |
| Target gross exposure | 200% | 150%–250% | |
| Target net exposure | 0% | ±10% | |

### 10.5 Risk Management Parameters

| Parameter | Default | Range | Notes |
|---|---|---|---|
| Target annualized vol | 10% | 8%–15% | Higher = more return and risk |
| Vol estimation window | 60 days | 21–252 days | |
| Min leverage scalar | 0.5 | 0.25–0.75 | Floor on de-risking |
| Max leverage scalar | 2.0 | 1.5–3.0 | Cap on leverage |
| Max position weight (gross) | 2.0% | 1.0%–3.0% | |
| Max sector net exposure | ±5% of NAV | ±2%–10% | |
| Drawdown stop (portfolio) | 15% | 10%–20% | Triggers gross reduction |
| Max single-factor crowding score | 80th pctile | 70th–90th | |

### 10.6 Execution Parameters

| Parameter | Default | Range | Notes |
|---|---|---|---|
| Rebalance frequency | Monthly | Bi-weekly–Quarterly | Monthly is standard |
| Trade filter threshold | 1.0 z-score drift | 0.5–1.5 | Below this, don't rebalance |
| Turnover budget (annual, two-way) | 400% | 200%–600% | Caps transaction costs |
| Turnover penalty (γ) | 0.002 | 0.001–0.010 | In optimization objective |
| Max participation rate | 10% of ADDV/day | 5%–20% | Market impact control |
| Earnings blackout window | ±2 days | ±1–5 days | |
| Max borrow cost inclusion | 200 bps/year | 100–400 bps | Above this, exclude short |

---

## Appendix A: Key Academic References

| Paper | Authors | Year | Contribution |
|---|---|---|---|
| The Cross-Section of Expected Stock Returns | Fama, French | 1992 | Foundational three-factor evidence |
| Common Risk Factors in the Returns on Stocks and Bonds | Fama, French | 1993 | SMB, HML factor construction |
| Returns to Buying Winners and Selling Losers | Jegadeesh, Titman | 1993 | Documented momentum effect (1%/month) |
| On Persistence in Mutual Fund Performance | Carhart | 1997 | Four-factor model with UMD |
| Do Stock Prices Fully Reflect Information in Accruals and Cash Flows About Future Earnings? | Sloan | 1996 | Accruals quality signal |
| Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers | Piotroski | 2000 | F-score quality composite |
| The Other Side of Value: The Gross Profitability Premium | Novy-Marx | 2013 | GP/A quality factor |
| Betting Against Beta | Frazzini, Pedersen | 2014 | BAB factor, leverage constraints |
| The Cross-Section of Volatility and Expected Returns | Ang, Hodrick, Xing, Zhang | 2006 | IVOL anomaly |
| A Five-Factor Asset Pricing Model | Fama, French | 2015 | RMW, CMA extensions |
| Value and Momentum Everywhere | Asness, Moskowitz, Pedersen | 2013 | Multi-asset factor universality |
| Momentum Crashes | Daniel, Moskowitz | 2016 | Crash risk and predictability |
| Post-Earnings Announcement Drift | Bernard, Thomas | 1989 | PEAD mechanism |
| Factor Information Decay: A Global Study | Flint, Vermaak | 2022 | Factor half-lives, optimal rebalancing |
| Taming Momentum Crashes | Bianchi, De Polis, Petrella | 2022 | Volatility-conditional momentum sizing |
| Fact, Fiction and Factor Investing | AQR | 2023 | Practitioner synthesis of academic factors |

---

## Appendix B: Factor Summary Table

| Factor | Signal | Lookback | Rebalance | Half-Life | Key Weakness |
|---|---|---|---|---|---|
| Momentum (MOM) | 12-1 month total return | 12 months | Monthly | 3–6 months | Crash risk during reversals |
| Value (VAL) | E/P + B/P + FEY composite | TTM / Annual | Quarterly | 18–30 months | Value traps, prolonged growth regimes |
| Quality (QUAL) | ROE + GP/A + (-Accruals) | TTM / 3-year | Quarterly | 18–36 months | Premium valuation; rate sensitivity |
| Low Volatility (LVOL) | (-Beta) + (-IVOL) | 252 / 60 days | Monthly | 6–12 months | Crowding; rate sensitivity |
| Earnings Drift (DRIFT) | SUE + ERM | Most recent EPS | Event-driven | 1–3 months | Largely arbitraged in large-cap |

---

*End of Specification*
