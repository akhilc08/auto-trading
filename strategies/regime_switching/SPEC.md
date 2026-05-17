# Adaptive Regime-Switching Strategy — Design Specification

**Version**: 1.0  
**Domain**: Systematic Macro / Meta-Strategy Layer  
**Classification**: Top-Level Orchestration Strategy  

---

## Table of Contents

1. [Strategy Overview and Thesis](#1-strategy-overview-and-thesis)
2. [Academic Foundations](#2-academic-foundations)
3. [Regime Taxonomy](#3-regime-taxonomy)
4. [Regime Detection Methods](#4-regime-detection-methods)
5. [Regime Classification Signal Construction](#5-regime-classification-signal-construction)
6. [Sub-Strategy Library](#6-sub-strategy-library)
7. [Switching Logic](#7-switching-logic)
8. [Regime Persistence and Transition Probabilities](#8-regime-persistence-and-transition-probabilities)
9. [Portfolio Construction Under Regime Uncertainty](#9-portfolio-construction-under-regime-uncertainty)
10. [Risk Management](#10-risk-management)
11. [Execution Considerations](#11-execution-considerations)
12. [Regime Sensitivity Meta-Analysis](#12-regime-sensitivity-meta-analysis)
13. [Key Risks and Failure Modes](#13-key-risks-and-failure-modes)
14. [Parameters and Tunable Knobs](#14-parameters-and-tunable-knobs)

---

## 1. Strategy Overview and Thesis

### 1.1 Core Concept

The adaptive regime-switching strategy is a **meta-strategy layer** — an orchestration system that does not itself generate alpha from a single market edge, but instead selects and weights a library of sub-strategies based on the current inferred market regime. The fundamental insight is that no single strategy has stable positive expected value across all market environments. Trend-following destroys capital in choppy, mean-reverting markets; statistical arbitrage bleeds during trending breakouts; volatility-selling catastrophically fails during crisis regimes.

The meta-layer inverts this problem. Rather than seeking one strategy robust to all conditions, we build a portfolio of specialized strategies — each optimized for one regime — and then solve the regime classification problem separately. The net result is a system that adapts its alpha-generation mechanism to the prevailing market structure rather than forcing a single lens onto all environments.

### 1.2 The Meta-Strategy Architecture

```
Market Data (prices, macro, breadth, credit)
        |
        v
  [Regime Detection Engine]
        |
        v
  Regime Posterior P(regime_k | data_t)
        |
        v
  [Sub-Strategy Router + Blender]
        |
        v
  Weighted Portfolio of Active Sub-Strategies
        |
        v
  [Risk Overlay and Position Sizing]
        |
        v
  Final Execution Orders
```

The detection engine runs continuously, producing a probability vector over the K defined regimes. The router maps this probability vector to sub-strategy weights via either hard switching (argmax assignment) or soft blending (probability-weighted capital allocation). A separate risk overlay applies regime-conditional stop-losses and position caps.

### 1.3 Why This Architecture Outperforms Single-Strategy Systems

Three empirical stylized facts motivate the architecture:

**Non-stationarity of market structure.** Financial markets do not generate returns from a fixed distribution. The autocorrelation structure, volatility clustering, cross-asset correlation, and momentum/reversion characteristics all shift across economic and market cycles. A strategy calibrated on one distribution will be miscalibrated when the distribution shifts.

**Regime-conditional factor premia.** Academic research confirms that factor returns — momentum, value, low volatility, quality — are strongly regime-conditional. Momentum earns its premium overwhelmingly during trending markets; value is crushed during prolonged growth regimes but recovers sharply in late-cycle and recovery phases. Exploiting this conditionality is the primary source of edge.

**Volatility of volatility (VoVol) clustering.** Volatility regimes are highly persistent. Once the market enters a high-volatility crisis regime, it tends to remain there for weeks to months. This persistence means a detection lag of days still allows substantial risk reduction relative to a static allocation. The statistical jump model literature (Aydinhan et al., 2024) confirms that regime-aware strategies reduce maximum drawdowns by approximately 30-50% relative to static baselines.

### 1.4 Scope and Boundaries

This specification covers:
- Formal regime taxonomy with five primary regimes
- Detection methodology for each of four signal families (statistical, volatility, macro, breadth)
- A composite regime score construction methodology
- Sub-strategy library mapping
- Hard and soft switching logic
- Portfolio construction mechanics
- Risk management overlays
- Implementation pitfalls

This specification does not cover:
- Individual sub-strategy implementation details (each has its own spec)
- Execution algorithm selection (handled at the execution layer)
- ML-based forecasting of future regimes (this is a detection, not prediction, system)

---

## 2. Academic Foundations

### 2.1 Hamilton (1989) — The Founding Model

James Hamilton's 1989 paper "A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle" (Econometrica, 57(2), 357-384) introduced the Markov Regime Switching (MRS) model, which remains the foundational academic framework for all regime-switching strategies.

**Core model structure.** Hamilton models a time series $y_t$ as arising from one of K discrete, unobserved states $s_t \in \{1, 2, \ldots, K\}$. In the two-state case:

$$y_t = \mu_{s_t} + \phi_1(y_{t-1} - \mu_{s_{t-1}}) + \cdots + \phi_p(y_{t-p} - \mu_{s_{t-p}}) + \epsilon_t$$

where $\epsilon_t \sim \mathcal{N}(0, \sigma^2_{s_t})$, meaning both the unconditional mean and variance shift with the regime. The state variable $s_t$ follows a first-order Markov chain with transition matrix:

$$P = \begin{pmatrix} p_{11} & 1-p_{22} \\ 1-p_{11} & p_{22} \end{pmatrix}$$

where $p_{ij} = \Pr[s_t = j \mid s_{t-1} = i]$ is the probability of transitioning from regime $i$ to regime $j$.

**Estimation via the Hamilton Filter.** Parameters are estimated by maximum likelihood using the Hamilton filter, a nonlinear filtering algorithm that computes the conditional probability of each state given the observable history. The filter iterates between a prediction step (using the transition matrix to propagate state probabilities forward) and an update step (using the observation to update probabilities via Bayes' rule). In practice, modern implementations use the EM algorithm or BFGS optimization on the concentrated likelihood.

**Key empirical finding.** Applied to post-war US GNP growth, Hamilton identified two regimes: one with positive mean growth (expansion) and one with negative mean growth (contraction), with high self-transition probabilities ($p_{11} \approx 0.90$, $p_{22} \approx 0.75$), confirming that regimes are persistent.

### 2.2 Extensions and Generalizations

**Turner, Startz, and Nelson (1989)** extended Hamilton's framework to allow both mean and variance to switch, establishing that financial return series are better described by a model where both the conditional mean and conditional variance differ across regimes. This is the Gaussian Hidden Markov Model (Gaussian HMM) used in modern applications.

**Hamilton and Susmel (1994)** demonstrated that a regime-switching ARCH model provides a better statistical fit to financial returns than a standard ARCH model without switching, establishing the interaction between volatility regime switching and conditional heteroskedasticity.

**Kim, Nelson, and Startz (1998)** developed smoothing algorithms for Markov-switching models, producing smoothed regime probabilities $\Pr[s_t = k \mid y_1, \ldots, y_T]$ that use the full sample, as opposed to filtered probabilities that use only data up to $t$.

### 2.3 Ang and Bekaert (2002) — International Regime Shifts

Ang and Bekaert's "International Asset Allocation With Regime Shifts" (Review of Financial Studies, 15(4), 1137-1187) is the pivotal paper linking regime switching to asset allocation in practice.

**Key findings:**

- Equity market return correlations increase substantially in high-volatility regimes. The US, UK, and German equity markets exhibit much higher cross-market correlations during the high-volatility regime than during the low-volatility regime.
- This means diversification benefits erode precisely when they are most needed — during bear markets and crises.
- The high-volatility regime is characterized by lower Sharpe ratios, making regime identification valuable for risk management.
- International diversification retains value even with regime shifts, but the magnitude of the diversification benefit is substantially reduced in the bad regime.

**Portfolio implications.** The optimal portfolio differs substantially across regimes. A risk-averse investor should hold more of the risk-free asset and reduce equity exposure in the high-volatility regime, regardless of the realized return in that regime. The conditional Sharpe ratio is the relevant metric for portfolio construction, not the unconditional Sharpe.

### 2.4 Ang (2011) — Regime Changes and Financial Markets

In the NBER working paper "Regime Changes and Financial Markets" (NBER w17182), Andrew Ang synthesizes the regime-switching literature and identifies the key channels through which regimes affect asset returns:

- **Risk premia are time-varying and regime-conditional.** The equity risk premium is higher in volatile regimes because investors require more compensation for bearing risk during periods of elevated uncertainty.
- **Correlation structure shifts.** In bad regimes, equity-bond correlations, cross-country equity correlations, and equity-credit correlations all increase (flight to safety in bonds, flight to quality in credit).
- **Fat tails arise from regime mixing.** A mixture of two Gaussian distributions (one low-vol, one high-vol) produces a distribution with excess kurtosis and left skewness, matching observed equity return distributions without requiring non-Gaussian innovations within each regime.

### 2.5 Statistical Jump Models (Aydinhan et al., 2024)

The sparse jump model (SJM) framework generalizes HMMs by replacing the probabilistic Markov chain with a regularized optimization approach. Rather than assuming transition probabilities are governed by a hidden Markov process, the SJM solves:

$$\min_{\{z_t\}, \{\mu_k\}} \sum_{t=1}^T \ell(x_t, \mu_{z_t}) + \lambda \sum_{t=2}^T \mathbb{1}[z_t \neq z_{t-1}]$$

where $x_t$ is the feature vector, $\mu_k$ is the centroid for regime $k$, $\ell$ is a loss function (typically squared Euclidean), and $\lambda$ is the jump penalty controlling regime persistence. This framework:

- Does not require distributional assumptions (likelihood-free when using squared Euclidean loss)
- Directly controls the transition rate via $\lambda$
- Is less sensitive to initialization than EM-based HMMs
- Produces fewer than one regime switch per year at large $\lambda$, versus 2-9 switches per year for HMMs with the same training data

### 2.6 Regime-Conditional Factor Performance Literature

**Asness, Moskowitz, and Pedersen (2013)** established that momentum has positive expected return across asset classes but is negatively exposed to market crisis events (momentum crashes). This creates the case for regime-conditioning momentum: run momentum in trending regimes, reduce or exit during crisis regime detection.

**Fama and French (1993, 2015)** five-factor model factors (market, size, value, profitability, investment) show regime-conditional behavior. Value underperforms during long growth regimes but recovers sharply; quality (low investment, high profitability) is defensive and performs relatively better in bear regimes.

**Daniel and Moskowitz (2016)** "Momentum Crashes" identifies that momentum experiences severe left-tail events specifically during market rebounds from crisis — a finding directly relevant to regime switching logic (momentum should be muted when transitioning out of a crisis regime).

---

## 3. Regime Taxonomy

This specification defines five primary market regimes. Real markets exist on a continuum; this taxonomy imposes discrete labels for operational clarity. The regime detection system (Section 4) produces a probability vector over all five regimes simultaneously.

### 3.1 Regime 1: Trending / Risk-On

**Definition:** Sustained directional price movement with improving breadth, expanding corporate credit, accommodative or neutral monetary policy, and positive economic momentum.

**Macro signature:**
- GDP growth above trend (ISM Manufacturing PMI > 53)
- Credit spreads tightening (IG OAS contracting, HY OAS below 400 bps)
- Yield curve positively sloped (2s10s spread > 50 bps)
- Unemployment stable or falling
- VIX below 15, term structure in contango

**Price/technical signature:**
- S&P 500 above 200-day SMA, 200-day SMA has positive slope
- Percentage of stocks above 50-day SMA above 70%
- ADX above 25 (trend strength confirmed)
- Hurst exponent above 0.55 (persistent trending behavior)
- Advance-Decline line making new highs concurrent with index

**Duration statistics:** Trending regimes historically last 2-5 years in secular bull markets; 3-12 months during shorter cyclical expansions. Mean duration approximately 18 months (post-WWII US equity data, Pagan and Sossounov, 2003).

**Dominant alpha sources:** Cross-sectional momentum, trend-following (CTA-style), sector rotation to growth and cyclical exposures, small-cap factor premium.

### 3.2 Regime 2: Mean-Reverting / Range-Bound

**Definition:** Absence of sustained directional price movement; price oscillates within a range bounded by support and resistance levels. Realized volatility is low to moderate but not trending. The market is in a consolidation or digestion phase.

**Macro signature:**
- GDP growth near trend (ISM PMI between 50-53)
- Credit spreads stable (not tightening or widening)
- Yield curve flat or mildly positive
- VIX in the 15-20 range, term structure in mild contango
- No clear momentum in macro data series

**Price/technical signature:**
- Price contained within a defined channel (e.g., 52-week high minus low < 15%)
- ADX below 20 (lack of directional momentum)
- Hurst exponent between 0.40-0.55 (near random walk or mild mean-reversion)
- Percentage of stocks above 50-day SMA between 40-65% (mixed internal market)
- Short-term RSI oscillating between 40-60 (not trending)

**Duration statistics:** Range-bound regimes are transitional by nature. Mean duration approximately 3-6 months. They typically resolve into either a trending regime (breakout) or a risk-off regime (breakdown).

**Dominant alpha sources:** Statistical arbitrage, pairs trading, mean-reversion within sectors, short-term RSI-based oscillator strategies, selling implied volatility (VRP capture).

### 3.3 Regime 3: High-Volatility / Risk-Off

**Definition:** Elevated realized and implied volatility accompanied by deteriorating credit conditions, weakening breadth, and risk asset underperformance. Distinct from outright crisis by the absence of liquidity seizure and the continued functioning of normal market plumbing.

**Macro signature:**
- ISM Manufacturing PMI declining (below 50 or falling sharply from above)
- HY credit spreads widening 50-200 bps above recent baseline
- VIX in the 20-30 range
- Yield curve flattening or inverting
- Falling equity markets with rising gold

**Price/technical signature:**
- S&P 500 below 200-day SMA
- Percentage of stocks above 200-day SMA below 40%
- New 52-week lows outpacing new highs on NYSE
- ADX elevated (25-40) but with downward directional movement
- VIX term structure transitioning from contango toward backwardation

**Duration statistics:** High-volatility regimes last 1-6 months. They resolve either by transitioning into a crisis regime (further deterioration) or recovering back to trending/range-bound (policy intervention, fundamental improvement).

**Dominant alpha sources:** Defensive positioning, long quality/low-volatility factors, tail risk hedges, long volatility, short beta, convertible bond arbitrage (if credit spreads not blow-out level).

### 3.4 Regime 4: Crisis / Liquidity Seizure

**Definition:** Extreme market stress characterized by VIX above 30, widespread liquidations, correlation spikes across all risk assets, flight to safety (Treasuries, gold, USD), and potential liquidity seizure in normally liquid markets.

**Historical examples:** 1987 Black Monday, 1998 LTCM/Russia, 2000-2002 tech bust, 2008-2009 GFC, March 2020 COVID crash, 2022 rate shock.

**Macro signature:**
- VIX above 30 (sustained, not a single spike)
- HY OAS above 600 bps (GFC-era saw above 2000 bps)
- Investment-grade spreads widening sharply (IG OAS above 200 bps)
- Yield curve in inversion or extreme flattening
- TED spread (3M LIBOR minus 3M T-Bill) widening
- Dollar surging (DXY rising sharply)
- Gold surging

**Price/technical signature:**
- Major indices down 15-20%+ from recent highs
- VIX term structure in deep backwardation (front-month premium over back-months)
- Advance-Decline line at multi-year lows
- Virtually all stocks (> 90%) below 50-day SMA
- Daily realized correlation across sectors near 1.0

**Duration statistics:** Crisis regimes have short but intense duration. Acute phase typically 1-3 months. Recovery from peak drawdown to prior high averages 12-18 months for moderate crises, 3-5 years for severe crises.

**Dominant alpha sources:** Extremely limited. Capital preservation is the objective. Long government bonds, long gold, short equity index via put options (expensive), long volatility strategies, cash. Tail hedges that were established pre-crisis pay off here.

### 3.5 Regime 5: Stagflation / Inflation Shock

**Definition:** Combination of above-trend inflation with below-trend or negative real growth. Distinctly different from pure risk-off (which features deflationary impulse) and from trending (which features positive real growth). The 1970s represent the canonical historical instance.

**Historical examples:** 1973-1974 oil shock, 1979-1981 Volcker disinflation period (transition), 2022 (partial — high inflation with slowing but not negative real growth).

**Macro signature:**
- CPI above 4-5% year-over-year and rising or sticky
- ISM Manufacturing PMI declining (GDP slowing)
- Real yields negative or rising (Fed hiking into slowing economy)
- Yield curve inverting (short rates rising faster than long rates)
- Energy and commodity prices elevated
- Corporate profit margins compressed by input cost inflation

**Price/technical signature:**
- Equity markets declining in nominal terms, severely in real terms
- Value stocks outperforming growth stocks
- Energy/commodity sectors outperforming
- Long-duration bonds underperforming (rising rates hurt duration)
- TIPS breakevens elevated and rising

**Duration statistics:** Stagflation regimes are rare and tend to be prolonged when they occur (the 1970s stagflation lasted nearly a decade). Modern central bank frameworks (flexible average inflation targeting) aim to prevent prolonged stagflation, but the 2022 episode shows it remains possible.

**Dominant alpha sources:** Commodities (energy, metals, agriculture), real assets (REIT inflation pass-through varies — avoid long-duration REITs), value equity over growth, short long-duration bonds, TIPS over nominal bonds, energy sector equities, commodity trend-following (CTAs historically perform well in this regime).

---

## 4. Regime Detection Methods

This section details four signal families used for regime detection. No single method is sufficient alone; the composite system (Section 5) combines signals from all four families.

### 4.1 Hidden Markov Models (Statistical Family)

#### 4.1.1 Gaussian HMM Architecture

The Gaussian HMM models the joint dynamics of a feature vector $\mathbf{x}_t$ as arising from K hidden states, where the emission distribution within each state is multivariate Gaussian:

$$\mathbf{x}_t \mid s_t = k \sim \mathcal{N}(\boldsymbol{\mu}_k, \boldsymbol{\Sigma}_k)$$

The hidden state evolves according to a first-order Markov chain with transition matrix $\mathbf{P}$, where $P_{ij} = \Pr[s_t = j \mid s_{t-1} = i]$.

**Parameters to estimate:** $\{\boldsymbol{\mu}_k, \boldsymbol{\Sigma}_k\}_{k=1}^K$ and $\mathbf{P}$ and $\boldsymbol{\pi}$ (initial state distribution), for a total of $K(2d + K - 1)$ parameters where $d$ is the feature dimension.

**Estimation:** Baum-Welch algorithm (a special case of EM). The E-step computes forward-backward probabilities; the M-step updates parameters. Modern implementations initialize with BFGS before Baum-Welch for better convergence.

#### 4.1.2 Feature Selection for HMM

The choice of features determines what the HMM "sees" and therefore what regimes it can detect. Three feature sets are relevant:

**Volatility-focused features (for volatility regime detection):**
- Daily log returns $r_t = \log(P_t / P_{t-1})$
- Exponentially weighted realized variance with 10-day halflife: $\sigma^2_t = \lambda \sigma^2_{t-1} + (1-\lambda) r_t^2$
- Sortino ratio computed over 20-day and 60-day windows (downside deviation normalized)

**Return and drawdown features (for trend/crisis detection):**
- 20-day cumulative return
- 60-day maximum drawdown from 252-day rolling peak
- 252-day Sharpe ratio (rolling)

**Multi-asset features (for macro regime detection):**
- Equity return (SPY)
- Credit spread level and change (HY OAS, IG OAS)
- Volatility level (VIX)
- Government bond return (TLT)
- Currency index return (DXY)

Including multi-asset features converts the HMM into a cross-asset regime detector sensitive to risk-on/risk-off dynamics.

#### 4.1.3 Number of States

**Two-state HMM:** Identifies bull (low vol, positive returns) vs. bear (high vol, negative/low returns). Operationally simplest, most robust, most widely validated in literature. Best for equity-only regime detection.

**Three-state HMM:** Adds a transition or sideways state. In practice, a three-state model often identifies: (1) high-momentum bull, (2) low-volatility range-bound, (3) high-volatility bear/crisis. Better for distinguishing mean-reverting from risk-off.

**Four or five-state HMM:** More granular but risks overfitting, especially on limited data. Transition matrices become noisy and parameter estimates unstable. Only appropriate if trained on 20+ years of daily data with careful model selection (BIC criterion).

**Recommendation:** Use a three-state Gaussian HMM as the primary statistical regime detector. Apply BIC to validate state count. For the five-regime taxonomy in Section 3, supplement the HMM with other signal families — the HMM alone is insufficient to distinguish stagflation from pure risk-off.

#### 4.1.4 Rolling vs. Full-Sample Training

**Full-sample training (smoothed probabilities):** Uses all available data including future observations to estimate regime probabilities. Produces the best statistical estimates but introduces look-ahead bias — these probabilities are not available in real time. Only valid for post-hoc analysis and research.

**Filtered probabilities (real-time compatible):** Uses only data up to time $t$. The Hamilton filter produces these probabilities recursively. This is the correct approach for a live trading system. Filtered probabilities are noisier than smoothed probabilities but are honest about what is knowable in real time.

**Rolling window retraining:** Re-estimates all HMM parameters on a rolling window of the most recent $W$ observations (e.g., $W = 1000$ trading days). This allows the regime structure to evolve over time, at the cost of parameter instability when the window rolls over a structural break.

**Recommendation:** Retrain HMM parameters monthly on a rolling 5-year (1250 trading day) window. Use filtered (not smoothed) probabilities for live trading signals. Require the filtered probability to exceed a threshold (e.g., 0.65) for at least 5 consecutive business days before signaling a regime change.

#### 4.1.5 Statistical Jump Model as HMM Alternative

The statistical jump model (SJM) offers superior persistence control vs. standard HMM. The SJM solves a regularized k-means problem over temporal features with a jump penalty $\lambda$:

$$\min_{\{z_t\}, \{\boldsymbol{\mu}_k\}} \sum_{t=1}^T \|\mathbf{x}_t - \boldsymbol{\mu}_{z_t}\|^2 + \lambda \sum_{t=2}^T \mathbb{1}[z_t \neq z_{t-1}]$$

The key operational advantage is that $\lambda$ directly controls regime switch frequency — setting $\lambda$ via cross-validation on a Sharpe-ratio criterion (not a statistical criterion) aligns model selection with the trading objective.

Empirical comparison (Aydinhan et al., 2024):
- HMM produces 2-9 regime switches per year
- SJM (optimally tuned $\lambda$) produces fewer than 1 switch per year
- SJM annual turnover: ~44% vs. HMM ~141-290%
- SJM maximum drawdown reduction: -55% to -27% (S&P 500)

### 4.2 VIX-Based Regime Classification (Volatility Family)

#### 4.2.1 VIX Level Thresholds

The VIX (CBOE Volatility Index) measures the 30-day implied volatility of S&P 500 options, annualized. It is a forward-looking measure of expected volatility, not a measure of current realized volatility.

| VIX Level | Regime Label | Interpretation |
|-----------|--------------|----------------|
| Below 12 | Extreme Complacency | Volatility suppression; potential bubble conditions |
| 12-15 | Low Volatility | Risk-on, trending, complacent market |
| 15-20 | Normal | Balanced; both trend-following and mean-reversion viable |
| 20-25 | Elevated | Stress building; reduce risk asset exposure |
| 25-30 | High Stress | Risk-off transition; defensive positioning |
| 30-40 | Crisis | Capital preservation mode |
| Above 40 | Acute Crisis | Extreme liquidation; near-zero gross exposure recommended |

**VIX vs. 200-day SMA crossover** provides a smoothed regime signal less sensitive to individual spikes. When VIX crosses above its 200-day SMA, it confirms a persistent volatility regime change rather than a transient spike. This crossover signal has historically accompanied market drawdowns exceeding 10% within 3-6 months.

**VIX spike vs. VIX sustain:** A single-day VIX spike (e.g., flash crash) does not constitute a regime change. Regime changes require VIX to sustain above a threshold for at least 5-10 consecutive trading days.

#### 4.2.2 VIX Term Structure as a Leading Indicator

The VIX futures term structure (VX1 through VX8) reveals market expectations about the duration and timing of volatility:

**Contango (normal):** VX1 < VX2 < ... < VX8. The market expects current volatility to be temporary and fall over time. This is the normal state, present approximately 75-80% of the time. Associated with risk-on and trending regimes.

**Backwardation (stress):** VX1 > VX2 > ... > VX8. Near-term volatility expectations exceed long-term, indicating immediate market stress. Backwardation accompanied every S&P 500 drawdown greater than 10% since 2008.

**Partial backwardation / hump structure:** The term structure is inverted in the front months but returns to contango in the back months. This indicates a specific, time-bounded risk event (earnings season, FOMC meeting) rather than a systemic crisis.

**Contango percentage metric:** $\text{Contango\%} = (VX2 - VX1) / VX1 \times 100$. Positive values indicate contango; negative values indicate backwardation. This metric can be computed daily and used as a continuous regime signal.

**VIX/VX3 ratio:** The ratio of spot VIX to the 3-month VIX future. A ratio above 1.0 indicates backwardation. The slope and magnitude of this ratio indicate the severity of term structure inversion.

**PCA on the VIX term structure:** Principal component analysis applied to daily VIX futures term structures (8 points) extracts three dominant factors: level (VIX level itself), slope (contango/backwardation), and curvature (hump shape). These three PCA components can then be fed into an HMM to detect VIX term structure regimes.

#### 4.2.3 Realized vs. Implied Volatility Spread

The spread between implied volatility (VIX) and realized volatility (measured as 21-day rolling annualized standard deviation of daily returns) is the volatility risk premium (VRP):

$$\text{VRP} = \text{IV} - \text{RV}_{21\text{d}}$$

When VRP is positive and large, it indicates the market is paying a risk premium for volatility protection — typically a risk-on signal as complacency meets elevated implied volatility. When VRP collapses or goes negative (IV < RV), it signals that realized moves are outrunning the market's expectations — a stress indicator.

### 4.3 Technical and Statistical Indicators (Price Family)

#### 4.3.1 Hurst Exponent

The Hurst exponent $H$ estimates the long-range dependence structure of a time series using rescaled range (R/S) analysis or detrended fluctuation analysis (DFA). It answers the structural question: is this market trending, random-walking, or mean-reverting?

**Interpretation:**
- $H > 0.55$: Persistent (trending) behavior — past returns predict future returns in the same direction
- $H \approx 0.50$: Random walk — no predictable serial dependence
- $H < 0.45$: Anti-persistent (mean-reverting) — past returns predict future returns in the opposite direction

**Estimation window:** Requires sufficient data for statistical reliability. Using the R/S method on daily returns, a minimum of 100 observations is needed; 250-500 is recommended for stability. A rolling 252-day Hurst exponent provides a slowly-changing regime indicator suitable for daily or weekly recalibration.

**Interpretation caveat:** The Hurst exponent measures structural tendencies, not the current direction. $H = 0.7$ on a falling market means the downtrend is persistent, not that the market will rise. Direction must be inferred from the price series itself (e.g., trend filter like 200-day SMA).

**Combined signal with ADX:** 
- $H > 0.55$ AND ADX > 25: Strong trending regime (run trend-following strategies)
- $H < 0.45$ AND ADX < 20: Mean-reverting regime (run mean-reversion strategies)
- $H \approx 0.50$ AND ADX 15-25: Ambiguous/transitional regime (reduce exposure or blend strategies)

#### 4.3.2 Average Directional Index (ADX)

The ADX, developed by Welles Wilder, measures the strength of the current directional trend without regard to direction. It is derived from the positive and negative directional movement indicators ($+\text{DI}$ and $-\text{DI}$):

$$\text{ADX}_t = \text{EMA}_{14}\left(\frac{|\text{DI}^+_t - \text{DI}^-_t|}{\text{DI}^+_t + \text{DI}^-_t} \times 100\right)$$

**Regime classification using ADX:**
- ADX below 20: No trend; mean-reverting or range-bound regime
- ADX 20-25: Weak trend emerging
- ADX 25-40: Moderate trend; trend-following strategies viable
- ADX above 40: Strong trend; momentum strategies fully deployed

The ADX does not indicate trend direction — combine with the directional indicators (+DI, -DI) or simple moving averages to determine if the trend is bullish or bearish.

**Key limitation:** The ADX is a lagging indicator — it confirms trend strength after the trend has begun. This creates an inherent detection lag of approximately 5-10 trading days for regime confirmation.

#### 4.3.3 Moving Average Regime Filters

Simple and exponential moving average crossovers are the most widely used price-based regime filters for their simplicity, robustness, and interpretability.

**200-day SMA filter (long-term regime):**
- Price above 200-day SMA: Bullish/trending regime
- Price below 200-day SMA: Bearish/defensive regime
- 200-day SMA slope positive: Entrenched bull market
- 200-day SMA slope negative: Entrenched bear market

**50-day vs. 200-day SMA (golden/death cross):**
- Golden cross (50d > 200d): Cyclical bull market transition signal
- Death cross (50d < 200d): Cyclical bear market transition signal
Both crosses are lagging by nature; they confirm regime changes well after the fact.

**Drawdown from 52-week high:**
- 0-5% from high: Trending regime
- 5-10% from high: Mild stress
- 10-20% from high: Risk-off regime threshold
- > 20% from high: Bear market / crisis regime

This drawdown-based approach has the advantage of being simple, robust, and entirely real-time with no parameter estimation.

#### 4.3.4 Rolling Autocorrelation

The 1-lag autocorrelation of daily returns, computed over a rolling 60-day window, provides a direct statistical test of trending vs. mean-reverting behavior:

$$\rho_1^{(t)} = \text{corr}(r_t, r_{t-1})_{60\text{d rolling}}$$

- $\rho_1 > 0.10$ (statistically significant): Momentum/trending behavior
- $\rho_1 \approx 0$: Random walk
- $\rho_1 < -0.10$ (statistically significant): Mean-reversion behavior

This measure is more directly interpretable than the Hurst exponent for short lookback windows, though it captures only linear serial dependence.

### 4.4 Market Breadth Indicators (Breadth Family)

Market breadth measures the participation of individual stocks in market moves. Broad participation confirms a regime; divergence between index and breadth anticipates regime transitions.

#### 4.4.1 Advance-Decline Line

The NYSE Advance-Decline (AD) Line is computed as the cumulative sum of the daily difference between advancing and declining issues on the NYSE:

$$\text{ADL}_t = \text{ADL}_{t-1} + (\text{Advances}_t - \text{Declines}_t)$$

**Regime signals from the AD line:**
- AD line making new highs with the index: Broad-based bull market; trending regime confirmed
- AD line diverging negatively from a new index high (index makes new high but AD line does not): Distribution top; risk-off regime approaching
- AD line making new lows with the index: Broad-based bear market; crisis regime confirmed
- AD line recovering before the index: Internal market health improving; transition from bear to bull

The AD line is best used as a confirming or divergence indicator rather than a timing signal on its own. Divergences can persist for weeks to months before resolving.

#### 4.4.2 Percentage of Stocks Above Moving Average

The percentage of constituents of the S&P 500 (or Russell 3000) trading above their 50-day or 200-day SMA provides a breadth gauge that normalizes for index cap-weight concentration:

| Metric | Threshold | Regime Signal |
|--------|-----------|---------------|
| % above 200d SMA | > 75% | Strong trending bull regime |
| % above 200d SMA | 50-75% | Mixed; trend ongoing but weakening |
| % above 200d SMA | 30-50% | Transitional; risk-off building |
| % above 200d SMA | < 30% | Bear market / crisis regime |
| % above 50d SMA | > 70% | Short-term momentum confirming |
| % above 50d SMA | < 30% | Short-term oversold; potential mean reversion |

**McClellan Oscillator and Summation Index:** Derived from the AD line using two exponential moving averages, the McClellan Oscillator captures short-term breadth momentum (19-EMA minus 39-EMA of net advances). The McClellan Summation Index (running sum of the Oscillator) captures medium-term breadth trends and provides an early-warning signal for regime transitions.

#### 4.4.3 New Highs vs. New Lows

The ratio of 52-week new highs to new lows on the NYSE is a powerful internal market indicator:

- New highs overwhelmingly outnumbering new lows: Broad-based bull; trending regime
- New lows outnumbering new highs during index advance: Classic breadth divergence; distribution phase
- New lows significantly outnumbering new highs (e.g., > 100:1): Bear market; crisis regime

**New high/new low ratio smoothed over 10 days** removes day-to-day noise while preserving the regime signal. Monitoring the trend of this ratio (the ratio improving while negative vs. deteriorating from positive) provides an early leading indicator of regime transition.

### 4.5 Macro and Credit Indicators (Macro Family)

#### 4.5.1 Credit Spreads

Investment-grade (IG) and high-yield (HY) credit spreads are the most reliable cross-asset macro regime indicators, with a typical lead time of 3-7 trading days over equity markets.

**Credit spread thresholds (approximate; recalibrate with current central tendency):**

| Spread | Tight (Risk-On) | Normal | Wide (Stress) | Crisis |
|--------|----------------|--------|---------------|--------|
| IG OAS (bps) | < 80 | 80-130 | 130-200 | > 200 |
| HY OAS (bps) | < 300 | 300-450 | 450-600 | > 600 |
| HY-IG spread (bps) | < 200 | 200-300 | 300-400 | > 400 |

**Credit spread dynamics:**
- Spreads tightening (narrowing): Risk-on signal; trending regime
- Spreads stable: Range-bound; no macro stress
- Spreads widening 50 bps over 30 days: Risk-off regime beginning
- Spreads widening 150+ bps over 60 days: Crisis regime

**Credit vs. equity divergence:** When credit spreads widen while equities hold steady, it is a high-conviction risk-off signal. Credit markets typically price stress before equities because institutional credit investors manage more precise risk mandates and are quicker to reduce exposure.

#### 4.5.2 Yield Curve Shape (Business Cycle Regime Indicator)

The shape of the US Treasury yield curve is the most historically reliable leading indicator of economic recession and therefore the most powerful macro regime signal.

**2-Year vs. 10-Year Treasury Spread (2s10s):**
- 2s10s > 100 bps: Steep yield curve; early expansion; risk-on
- 2s10s 50-100 bps: Normal; mid-cycle; trending to range-bound
- 2s10s 0-50 bps: Flat curve; late-cycle; risk-off regime building
- 2s10s < 0 bps (inverted): Pre-recession signal; has preceded every US recession since 1955 with a 6-24 month lead time
- 2s10s deeply negative (below -75 bps): Imminent recession risk; defensive positioning

**Practical regime mapping:**
- Steep and steepening: Early expansion (bull regime; trending)
- Flat and flattening: Late cycle (watch for risk-off transition)
- Inverted: Recession approaching (risk-off; consider crisis hedging)
- Re-steepening from inversion: Economic contraction already underway; early bear regime

**5-Year/30-Year spread:** Captures the intermediate-to-long end of the curve, sensitive to inflation expectations and long-term growth outlook. Useful for distinguishing stagflation (short rates rising fast, long rates less so, flattening) from deflationary crisis (long rates falling sharply, all rates compressing).

#### 4.5.3 ISM Manufacturing PMI as Macro Regime Indicator

The Institute for Supply Management (ISM) Manufacturing PMI is a monthly survey of US manufacturing sector conditions. Readings above 50 indicate expansion; below 50 indicate contraction.

**Regime mapping from PMI levels and direction:**
- PMI > 55 and rising: Strong expansion; trending risk-on regime
- PMI 50-55 and stable: Modest expansion; range-bound or mild trending
- PMI 45-50 and declining: Slowdown; risk-off building
- PMI < 45: Contraction; risk-off or early crisis regime
- PMI < 42: Deep contraction; historically associated with crisis regimes and severe bear markets

**PMI direction matters more than level:** A PMI declining from 60 to 55 (still above 50 but falling) is a more bearish signal than a PMI rising from 45 to 48 (below 50 but improving). Second-derivative (momentum of PMI) is the key signal.

**Data frequency limitation:** PMI is published monthly, with a 1-2 business day release lag after month-end. This creates a maximum signal latency of 30 days for macro-based regime detection. The Markit/S&P Global flash PMI (released 10 days before month-end) partially addresses this.

#### 4.5.4 Flight-to-Safety Indicators

Risk-off episodes are characterized by correlated flows into safe-haven assets. Monitoring these flows provides a real-time confirmation of risk-off regime transitions:

**Gold/S&P 500 ratio:** When gold rises relative to equities, it indicates risk-off sentiment. A 30-day rolling correlation between gold and equity returns that turns sharply negative (simultaneous rally in gold and fall in equities) is a crisis regime indicator.

**US Dollar Index (DXY):** The dollar strengthens in acute risk-off episodes as global investors repatriate to USD-denominated assets. However, this relationship is complex: the dollar also strengthens in strong US growth regimes (trending). The key distinguisher is whether the dollar is rising with equities (trending regime) or against equities (risk-off regime).

**TLT/SPY ratio:** The ratio of 20-year Treasury bond ETF to S&P 500 ETF. When this ratio rises, it indicates capital flowing from equities to long-duration government bonds — a classic risk-off signal.

**TED Spread (T-bill vs. LIBOR/SOFR):** The spread between 3-month LIBOR (or SOFR) and 3-month T-bill yield captures interbank lending stress. A rising TED spread (above 30-50 bps) signals funding stress in the banking system, often preceding broader crisis regimes.

---

## 5. Regime Classification Signal Construction

### 5.1 Multi-Factor Composite Architecture

The four signal families (HMM/Statistical, Volatility, Breadth, Macro) are combined into a composite regime score using a hierarchical aggregation approach. The goal is to produce a probability vector $\mathbf{p}_t = (p_{t,1}, p_{t,2}, p_{t,3}, p_{t,4}, p_{t,5})$ where $p_{t,k}$ is the probability that the market is in regime $k$ at time $t$, with $\sum_k p_{t,k} = 1$.

### 5.2 Sub-Indicator Normalization

Each individual indicator is normalized to a score between -2 and +2, where +2 represents the strongest possible risk-on/trending signal and -2 represents the strongest possible crisis/risk-off signal.

**Normalization procedure for continuous indicators:**

$$z_i = \text{clip}\left(\frac{x_i - \mu_i}{\sigma_i}, -2, 2\right)$$

where $\mu_i$ and $\sigma_i$ are the rolling 252-day mean and standard deviation of indicator $i$. This z-score normalization ensures each indicator contributes equally before weighting.

**Normalization procedure for threshold-based indicators (VIX, PMI):**

Use a piecewise linear mapping from the raw indicator value to the $[-2, +2]$ score range based on the thresholds defined in Section 4.

### 5.3 Signal Family Aggregation

Within each signal family, sub-indicators are averaged with equal weights (unless domain knowledge suggests differential weighting):

$$S_{\text{vol}} = \frac{1}{N_{\text{vol}}} \sum_{i \in \text{vol}} z_i$$

$$S_{\text{stat}} = \frac{1}{N_{\text{stat}}} \sum_{i \in \text{stat}} z_i$$

$$S_{\text{breadth}} = \frac{1}{N_{\text{breadth}}} \sum_{i \in \text{breadth}} z_i$$

$$S_{\text{macro}} = \frac{1}{N_{\text{macro}}} \sum_{i \in \text{macro}} z_i$$

The volatility family score $S_{\text{vol}}$ is the most real-time and responsive. The macro family score $S_{\text{macro}}$ has the longest lag but the most structural validity.

### 5.4 Cross-Family Composite Score

The family scores are combined into a single composite regime score $S_{\text{composite}}$ using weights that balance responsiveness against noise:

$$S_{\text{composite}} = w_{\text{vol}} \cdot S_{\text{vol}} + w_{\text{stat}} \cdot S_{\text{stat}} + w_{\text{breadth}} \cdot S_{\text{breadth}} + w_{\text{macro}} \cdot S_{\text{macro}}$$

**Default weights:**
- $w_{\text{vol}} = 0.30$ (VIX/volatility signals; most responsive)
- $w_{\text{stat}} = 0.30$ (HMM/price-based; medium responsiveness)
- $w_{\text{breadth}} = 0.25$ (breadth; medium responsiveness)
- $w_{\text{macro}} = 0.15$ (macro fundamentals; slowest, but most regime-structural)

The higher weight on volatility and statistical signals reflects their daily availability and responsiveness. The lower macro weight reflects the monthly publication lag of PMI and other fundamental data.

### 5.5 Composite Score to Regime Probability Mapping

The composite score is mapped to a five-regime probability vector via a softmax transformation with regime-specific centroids:

**Regime centroids in composite score space:**
- Trending (Regime 1): centroid at $c_1 = +1.5$
- Mean-Reverting (Regime 2): centroid at $c_2 = 0.0$
- Risk-Off (Regime 3): centroid at $c_3 = -1.0$
- Crisis (Regime 4): centroid at $c_4 = -1.8$
- Stagflation (Regime 5): centroid at $c_5 = -0.8$ (but with elevated inflation sub-score)

The probability of regime $k$ is:

$$p_{t,k} = \frac{\exp(-\gamma \cdot (S_{\text{composite}} - c_k)^2)}{\sum_{j=1}^5 \exp(-\gamma \cdot (S_{\text{composite}} - c_j)^2)}$$

where $\gamma$ controls the sharpness of the mapping (higher $\gamma$ produces sharper regime assignments). Stagflation is differentiated from pure risk-off by additionally requiring elevated inflation indicators (CPI, TIPS breakevens, commodity complex breadth) above their rolling 90th percentile.

### 5.6 Regime Confirmation Window

Raw regime signals are subject to whipsaw — short-lived, incorrect regime classifications that trigger costly strategy switches. A confirmation window requires the composite score to remain in a new regime zone for a minimum number of consecutive days before the regime classification is updated:

**Confirmation period:**
- Trending to Range-Bound: 5 business days
- Range-Bound to Risk-Off: 3 business days (faster confirmation to limit losses)
- Risk-Off to Crisis: 1-2 business days (immediate action required)
- Crisis to Risk-Off: 5 business days (require sustained recovery before re-risking)
- Risk-Off to Range-Bound: 5 business days
- Any to Stagflation: 10 business days (requires macro confirmation; monthly PMI/CPI)

The asymmetric confirmation windows reflect the asymmetric cost of type I vs. type II errors: failing to exit in a crisis is more costly than a premature partial re-risk.

---

## 6. Sub-Strategy Library

Each regime is mapped to a primary sub-strategy and a secondary sub-strategy. The secondary sub-strategy runs at reduced allocation during regime uncertainty (soft blending regime, described in Section 7).

### 6.1 Regime 1 (Trending): Primary — Cross-Sectional Momentum

**Logic:** In trending markets, price momentum is the dominant alpha factor. The cross-sectional momentum strategy goes long the top quartile of 12-1 month momentum and short the bottom quartile across a liquid equity universe.

**Sizing:** Full risk budget deployed. Target 10-15% annualized portfolio volatility. Net long bias of 50-70% of gross exposure.

**Secondary:** Sector rotation (overweight cyclicals, underweight defensives; MSCI quality momentum factor).

**Risk control:** Stop-loss at -5% from entry at the strategy level. Reduce gross exposure if ADX falls below 20 (trend weakening signal).

### 6.2 Regime 1 (Trending): Tertiary — Trend-Following (CTA-style)

**Logic:** Multi-asset trend-following across equities, fixed income, FX, and commodities using 50-day and 200-day exponential moving average signals.

**Sizing:** 20-30% of total risk budget during trending regime, scaled by regime probability.

### 6.3 Regime 2 (Range-Bound): Primary — Statistical Arbitrage / Pairs Trading

**Logic:** In range-bound markets with low Hurst exponent, mean reversion is the dominant dynamic. Statistical arbitrage strategies identify co-integrated pairs and trade the spread when it deviates beyond 1.5 standard deviations from its historical mean.

**Sizing:** Full risk budget. Equal gross long/short (market-neutral). Target 8-12% annualized portfolio volatility.

**Secondary:** Volatility risk premium capture (selling at-the-money straddles on major indices, targeting the structural VIX > realized vol premium). Only execute when VIX term structure is in contango and VRP is positive.

### 6.4 Regime 3 (Risk-Off): Primary — Low Beta / Quality Factor

**Logic:** Reduce gross exposure and tilt strongly toward low-beta, high-quality equities that show defensive characteristics (high Piotroski score, negative beta to HY credit spreads, low debt/equity).

**Sizing:** 50% of normal risk budget. Net long but heavily defensive. Stop adding to positions when HY OAS is widening.

**Secondary:** Long put optionality on major indices (funded by reduced equity exposure). Not raw delta hedging — buy convexity by purchasing slightly out-of-the-money puts.

### 6.5 Regime 4 (Crisis): Primary — Capital Preservation

**Logic:** When the crisis regime is confirmed, the priority is preservation of capital, not alpha generation. The crisis regime represents the worst environment for most strategies including statistical arbitrage (spread blow-up during liquidity crises), momentum (momentum crashes in reversals), and even low-beta (correlation spikes towards 1.0 eliminate diversification).

**Sizing:** Maximum 25-50% of normal gross exposure. Strong bias toward cash, short-duration government bonds, gold.

**Tactical positions:**
- Long US Treasuries (TLT or futures)
- Long gold (GLD or front-month futures)
- Short equity index (via puts or futures; limited notional)
- Long volatility (VIX calls or VIX futures; expensive but effective as insurance)
- Reduce all equity long/short books by 70-80%

**Secondary:** Merger arbitrage selectively (cash-funded deals with low deal-break risk are defensive; leveraged buyouts are not). Liquidation proceeds should sit in overnight repo or T-bills, not prime money market funds.

### 6.6 Regime 5 (Stagflation): Primary — Commodity Trend-Following

**Logic:** In stagflation, real assets and commodity producers preserve value while financial assets (long-duration bonds, growth equities) underperform in real terms. The primary alpha source is commodity trend-following.

**Allocation tilts:**
- Energy sector equities (30% of equity book)
- Materials and commodity producers (20% of equity book)
- TIPS over nominal Treasuries
- Short long-duration government bonds
- Short growth/technology equities (high duration assets)
- Value equities over growth equities

**Secondary:** Commodity futures trend-following (carry + momentum on crude, natural gas, metals, agricultural commodities).

---

## 7. Switching Logic

### 7.1 Hard Switching vs. Soft Blending

**Hard switching** assigns all capital to the sub-strategy corresponding to the maximum probability regime (argmax decision rule):

$$k^* = \argmax_k p_{t,k}$$

Allocate 100% of risk budget to sub-strategy $k^*$.

**Advantages:** Simple; full exploitation of regime-specific edge; clear mandate for each sub-strategy operator.

**Disadvantages:** Binary transitions create large turnover events; misses the value of partial regime overlap; sensitive to misclassification near regime boundaries.

**Soft blending** allocates risk budget to multiple sub-strategies proportional to their regime probabilities:

$$\text{Allocation to strategy } k = p_{t,k} \times \text{Total Risk Budget}$$

This produces a continuously time-varying portfolio of sub-strategies, with smooth transitions as regime probabilities shift.

**Advantages:** Lower turnover; exploits partial regime overlap (e.g., 60% trending + 40% range-bound is reasonable when evidence is mixed); more robust to misclassification.

**Disadvantages:** Dilutes the regime-specific alpha by always holding some exposure to the wrong regime; more complex to explain and monitor; strategies may partially cancel each other.

**Recommendation:** Use soft blending as the baseline approach. However, when any single regime probability exceeds 0.80, move toward hard switching — effectively allocate 80-100% to the dominant regime strategy. The 0.80 threshold creates a hybrid approach: blending during uncertainty, hard-switching during high-confidence regime identification.

### 7.2 Transition Rules and Minimum Holding Periods

To prevent excessive churning at regime boundaries, impose minimum holding period constraints:

**Minimum time-in-regime:** Once a regime switch is confirmed and the sub-strategy allocation has been adjusted, require a minimum of 10 business days before any further regime switch can be executed. Exception: crisis regime entry (Regime 4) bypasses the minimum holding period due to the urgency of capital preservation.

**Transition cost budget:** Each regime switch incurs transaction costs from liquidating current positions and establishing new ones. Budget a maximum of 15 basis points per annum for regime-switch-driven turnover. If switching frequency exceeds this budget, increase the confirmation window (Section 5.6).

**Graduated transition:** Rather than switching the full allocation at once, transition at a rate of 20-30% of the delta per day over 3-5 business days. This reduces market impact and execution risk during large re-allocations.

### 7.3 Transition Guards Specific to Each Regime Pair

**Trending to Range-Bound:** Close momentum positions at full size over 3 days. Open stat-arb book at 50% size initially; expand to full size after 5 more days of range-bound confirmation.

**Trending to Risk-Off:** Immediate reduction of all momentum longs by 50%. Move remaining long book to quality/low-beta names. This transition can happen quickly (2-3 days) given the speed at which risk-off regimes emerge.

**Risk-Off to Crisis:** Emergency protocol. Reduce gross exposure by 50% in day 1, reduce to 25% of normal in days 2-3. Move to capital preservation allocation immediately.

**Crisis to Risk-Off / Recovery:** Extremely cautious re-risking. Historical evidence (Daniel and Moskowitz, 2016) shows that momentum strategies experience their worst drawdowns precisely when markets rebound strongly from a crisis — a "momentum crash." During the first 30-60 days after a confirmed crisis exit, do not run momentum strategies. Instead, operate a quality-biased long book with limited gross exposure, then gradually add momentum exposure as the recovery is confirmed.

### 7.4 Anti-Whipsaw Protection

**Regime persistence requirement:** A newly detected regime must maintain its regime signal for at least 10 consecutive business days before being committed to in the strategy allocation. This eliminates the vast majority of false signals.

**Minimum probability delta:** Only execute a regime switch when the new dominant regime probability exceeds the outgoing regime probability by at least 0.25 (i.e., the new regime must be clearly more probable, not just marginally more so).

**Signal family consensus:** Require at least 3 of the 4 signal families to agree on the regime transition direction. A regime switch confirmed by only one signal family (e.g., VIX spike but PMI and breadth still healthy) is treated as a partial risk reduction rather than a full regime switch.

**Hysteresis bands:** Apply hysteresis to regime boundaries — the score threshold to enter a regime is stricter than the threshold to exit. For example, the crisis regime requires a composite score below -1.5 to enter but allows exit when the score rises above -0.8. This prevents oscillation around boundary values.

---

## 8. Regime Persistence and Transition Probabilities

### 8.1 Historical Regime Duration Statistics

Based on post-WWII US equity and macro data, the following approximate regime duration statistics are observed:

| Regime | Median Duration | Mean Duration | 10th Percentile | 90th Percentile |
|--------|----------------|---------------|-----------------|-----------------|
| Trending (Bull) | 14 months | 18 months | 4 months | 48 months |
| Range-Bound | 3 months | 4 months | 1 month | 10 months |
| Risk-Off | 2 months | 3 months | 0.5 months | 8 months |
| Crisis | 3 months | 4 months | 1 month | 12 months |
| Stagflation | 18 months | 24 months | 6 months | 60 months |

These statistics reflect aggregate historical experience. Individual regime episodes vary considerably. The 2000-2002 bear market lasted ~30 months; March 2020 crash lasted ~1 month before beginning recovery.

### 8.2 Markov Transition Probability Matrix

A stylized five-state transition probability matrix based on historical data calibration (approximate; requires re-estimation from data):

|           | Trending | Mean-Rev | Risk-Off | Crisis | Stagflation |
|-----------|----------|----------|----------|--------|-------------|
| **Trending** | 0.96 | 0.02 | 0.01 | 0.00 | 0.01 |
| **Mean-Rev** | 0.15 | 0.72 | 0.10 | 0.01 | 0.02 |
| **Risk-Off** | 0.05 | 0.25 | 0.55 | 0.12 | 0.03 |
| **Crisis** | 0.00 | 0.05 | 0.35 | 0.58 | 0.02 |
| **Stagflation** | 0.02 | 0.03 | 0.15 | 0.05 | 0.75 |

Reading: A cell at row $i$, column $j$ gives the probability of transitioning from regime $i$ to regime $j$ in one month.

**Key observations from this matrix:**
- The trending regime is highly self-persistent (0.96 monthly self-transition) — once in a bull market, it tends to persist
- Crisis does not directly transition to trending — it almost always goes through risk-off or range-bound first
- Stagflation is also highly persistent (0.75) — consistent with the 1970s experience
- Mean-reverting is the most transitional state (lowest self-persistence) — it resolves into other regimes relatively quickly

**Expected duration implied by self-transition probability:**

$$E[\text{duration in regime } k] = \frac{1}{1 - p_{kk}} \text{ months}$$

For trending: $1 / (1 - 0.96) = 25$ months. For range-bound: $1 / (1 - 0.72) = 3.6$ months. These match the empirical duration statistics above.

### 8.3 Duration Dependence

Standard Markov models assume time-homogeneous transition probabilities — the probability of leaving a regime does not depend on how long you have been in it. Empirical evidence (Maheu and McCurdy, 2000) suggests this assumption is violated for bull markets, where duration dependence is present: longer bull markets have a slightly higher probability of ending per unit time.

For practical purposes, incorporate a duration-adjusted transition probability for the trending regime:

$$p_{11}^{(\tau)} = p_{11} \cdot \exp(-\delta \cdot \tau)$$

where $\tau$ is the number of months spent in the trending regime and $\delta$ is a small positive constant (e.g., 0.005). This creates a subtle "late-cycle" correction — the longer a bull market has run, the slightly higher the probability of transition into risk-off, all else equal.

### 8.4 Regime Change Drivers

Understanding what drives regime transitions enables more proactive detection:

**Trending to Risk-Off transition drivers:**
- Fed rate hike cycle reaching restrictive territory (real Fed funds rate > neutral)
- Credit spread widening (corporate bond market pricing stress before equity)
- Earnings expectations downward revisions (EPS estimate cuts begin)
- Geopolitical shock or external event (oil embargo, war, pandemic)

**Risk-Off to Crisis transition drivers:**
- Liquidity seizure in credit markets (primary issuance markets closed)
- Bank solvency concerns or systemic credit event (counterparty failure)
- Forced liquidations (margin calls, redemptions from risk parity or leveraged funds)
- Policy error (central bank behind the curve or making wrong policy response)

**Crisis to Recovery transition drivers:**
- Coordinated fiscal + monetary policy response (the "Fed put")
- Credit market stabilization (primary markets re-open; spreads stop widening)
- VIX term structure returning to contango
- Credit spread compression from central bank intervention (QE, facilities)

---

## 9. Portfolio Construction Under Regime Uncertainty

### 9.1 The Regime Uncertainty Problem

Even with a sophisticated detection system, regime classification carries irreducible uncertainty. At any given time, the true regime is unobservable — only the filtered probability vector is known. Portfolio construction must account for this uncertainty rather than treating the argmax regime as truth.

### 9.2 Regime-Weighted Portfolio Construction

**Step 1 — Sub-strategy return forecasts:** Each sub-strategy $k$ produces a return forecast vector $\boldsymbol{\mu}_k$ (expected returns by position) and a covariance matrix $\boldsymbol{\Sigma}_k$ estimated from regime-specific historical data.

**Step 2 — Regime-weighted expected return:**

$$\boldsymbol{\mu}_{\text{composite}} = \sum_{k=1}^K p_{t,k} \cdot \boldsymbol{\mu}_k$$

**Step 3 — Regime-weighted covariance:**

$$\boldsymbol{\Sigma}_{\text{composite}} = \sum_{k=1}^K p_{t,k} \cdot \boldsymbol{\Sigma}_k + \sum_{k=1}^K p_{t,k} \cdot (\boldsymbol{\mu}_k - \boldsymbol{\mu}_{\text{composite}})(\boldsymbol{\mu}_k - \boldsymbol{\mu}_{\text{composite}})^\top$$

The second term adds variance from disagreement between regime-specific forecasts — the more uncertain the regime (flat probability distribution), the more this term adds to the composite covariance estimate. This naturally leads to reduced position sizes during regime uncertainty.

**Step 4 — Mean-variance optimization on composite estimates:**

$$\mathbf{w}^* = \argmax_{\mathbf{w}} \left[\mathbf{w}^\top \boldsymbol{\mu}_{\text{composite}} - \frac{\gamma}{2} \mathbf{w}^\top \boldsymbol{\Sigma}_{\text{composite}} \mathbf{w}\right]$$

subject to constraints (leverage, sector limits, net exposure). The risk aversion parameter $\gamma$ is calibrated to produce the target volatility under normal regime conditions.

### 9.3 Risk Parity Across Regime States

An alternative to mean-variance optimization is regime-conditional risk parity: allocate risk budget equally across active sub-strategies, where the risk contribution of each sub-strategy is measured within its own regime-conditional covariance.

This approach is more robust to estimation error in expected returns (which are notoriously difficult to estimate) while still achieving regime-adaptive risk allocation. The implementation:

$$\text{Allocation to strategy } k = p_{t,k} \cdot \frac{\text{Target Risk}}{K \cdot \sigma_k^{\text{regime}}}$$

where $\sigma_k^{\text{regime}}$ is the historical volatility of sub-strategy $k$ when regime $k$ is active.

### 9.4 Regime Transition Hedging

During regime transitions (when composite probability is shifting from one state to another), add explicit hedging positions to protect against the transition risk:

**Trending to Risk-Off transition hedge:** When the risk-off signal is building but not confirmed, buy protective puts on the equity index (3-month, 5% out-of-the-money). Cost: approximately 20-30 bps per month. This is regime-transition insurance, not a persistent position.

**Risk-Off to Crisis transition hedge:** When crisis signals are building, add long VIX calls (30-day, strike 5 VIX points above current level). These are cheap when VIX is in the 20-25 range but pay off significantly if VIX spikes to 40+.

**Stagflation insurance:** During late-cycle macro signals (inverted curve, rising CPI, PMI declining), add commodity exposure via GSCI or BCOM index options (calls on commodity indices) as a tail hedge.

### 9.5 Correlation Regime Adjustment

In bad regimes (risk-off, crisis), realized cross-asset correlations increase (Ang and Bekaert, 2002). Naive diversification calculations using unconditional correlations will overestimate the diversification benefit during precisely the periods when it is most needed.

Adjust correlation estimates by regime:
- In the trending regime: Use unconditional correlations estimated from full-sample data
- In the risk-off regime: Scale correlations upward by a factor of 1.3-1.5 (i.e., blend toward a correlation matrix where all equity-like assets have correlations of 0.7+)
- In the crisis regime: Use a "stress correlation" matrix where equity correlations approach 0.9 and equity-bond correlations invert to negative (flight to quality)

This regime-conditional correlation adjustment reduces portfolio construction overconfidence during stressed regimes.

---

## 10. Risk Management

### 10.1 Regime Detection Failure Modes

**False positive (spurious regime change detection):** The system detects a regime change that does not reflect a true shift in market structure. Example: a VIX spike from 15 to 25 due to a single geopolitical headline that reverses the next day. Mitigation: confirmation window (Section 5.6), signal family consensus requirement (Section 7.4).

**False negative (missed regime change):** The system fails to detect a genuine regime transition until well after it has occurred. Example: gradual credit spread widening that the HMM incorrectly classifies as trending range expansion. Mitigation: weight faster-reacting signals (VIX, credit spreads) more heavily; maintain stop-loss rules independent of regime classification.

**Regime misclassification at boundaries:** The system correctly identifies that a regime transition is occurring but misidentifies the destination regime. Example: detecting risk-off when the market is actually entering a stagflation regime. Mitigation: stagflation requires additional inflation indicators (TIPS breakevens, CPI momentum) not captured by price/volatility signals alone.

**HMM parameter instability:** Rolling-window re-estimation of HMM parameters can cause sudden jumps in regime probabilities when a structural break enters or exits the rolling window. Mitigation: smooth the filtered probabilities with an exponential moving average (halflife = 3 business days) before using them for strategy switching.

### 10.2 Strategy-Level Stop-Losses

Each sub-strategy operates with its own stop-loss independent of the regime detection system:

| Sub-Strategy | Stop-Loss Trigger |
|-------------|-------------------|
| Momentum | -7% from inception of position |
| Stat Arb / Pairs | -3 standard deviations on spread; -5% at strategy level |
| Low Beta / Defensive | -10% at strategy level |
| Capital Preservation | -5% at strategy level (mostly cash/T-bills; very tight) |
| Commodity Trend | -8% from inception |

**Crisis emergency stop:** If total portfolio drawdown exceeds 12% peak-to-trough within any rolling 60-day window, regardless of regime classification, reduce gross exposure by 50% immediately. This is a circuit breaker independent of all regime logic.

### 10.3 Regime Transition Risk Management

The highest-risk periods are regime transitions, when the detection system is uncertain and the existing sub-strategy is becoming misaligned with market conditions. During transition periods (regime probability of dominant regime between 0.50-0.70):

- Reduce gross exposure of current primary sub-strategy to 60% of normal
- Do not fully deploy the new sub-strategy until probability exceeds 0.70
- Widen stop-losses by 20% to avoid being stopped out by transition volatility
- Increase cash allocation to 20-30% as a buffer

### 10.4 Tail Risk Budget

Maintain a dedicated tail risk budget of 2-3% of NAV per annum allocated to convex instruments:
- OTM S&P 500 put options (3-6 month duration, 10% OTM strike)
- VIX call options during risk-off regime buildup
- Long-dated Treasury options (receivers in case of deflationary crash)

This tail risk budget acts as a portfolio "insurance policy" that is cheap in calm regimes but pays off significantly in crisis regimes, reducing the maximum drawdown impact of failed regime detection.

### 10.5 Volatility Targeting Overlay

Apply a top-level volatility targeting overlay across all sub-strategies: if realized 20-day portfolio volatility exceeds the target by more than 20%, scale down all positions proportionally until realized volatility returns to target. This provides a systematic risk de-risking mechanism that operates independent of regime classification, ensuring the total portfolio risk stays within mandate boundaries.

---

## 11. Execution Considerations

### 11.1 Turnover from Regime Transitions

Regime transitions generate elevated turnover as old sub-strategy positions are liquidated and new sub-strategy positions are established. Approximate turnover estimates:

| Transition Type | Estimated One-Way Turnover |
|----------------|---------------------------|
| Trending to Range-Bound | 40-60% of book |
| Trending to Risk-Off | 60-80% of book |
| Risk-Off to Crisis | 70-90% of book |
| Crisis to Risk-Off | 30-50% of book (rebuilding positions) |
| Regime maintenance rebalancing | 10-20% per month |

At 8 bps average round-trip commission + market impact cost, a full transition costing 70% one-way turnover costs approximately 11 bps (0.11% of NAV). Across 2-3 major transitions per year, this is 25-35 bps of annual drag — manageable but not negligible for a strategy targeting 50-150 bps of annual alpha.

### 11.2 Market Impact and Execution Scheduling

Large regime transition orders should be executed using VWAP or TWAP algorithms over 3-5 days to minimize market impact:

**Urgency classification:**
- Trending to Range-Bound: Low urgency; execute over 5 business days
- Trending to Risk-Off: Medium urgency; execute over 3 business days
- Risk-Off to Crisis: High urgency; execute over 1-2 business days using VWAP
- Crisis emergency stop: Immediate; use market orders for liquid instruments; limit orders for illiquid positions

**Liquidity-aware sizing:** In the crisis regime, market liquidity for individual equity positions can deteriorate significantly. Position sizing during the capital preservation allocation must use crisis liquidity estimates (bid-ask spreads 5-10x normal; market depth 20-30% of normal). Reduce position sizes accordingly.

### 11.3 Short Selling Constraints

Regime switching strategies may require significant short positions during risk-off and crisis regimes. Key constraints:

- Borrow availability: Hard-to-borrow stocks may be unavailable during peak stress periods when demand for shorts surges
- Short-selling bans: Some regulators have imposed temporary short-selling bans during acute crises (SEC 2008, various European markets)
- Recall risk: Borrowed shares can be recalled, forcing position liquidation at inopportune times

Mitigation: Use equity index futures or ETF shorts as proxies for broad market shorts during crisis regimes. Index futures have no borrow constraint and very high liquidity.

### 11.4 Rebalancing Costs and Minimum Trade Threshold

To avoid frequent small rebalancing trades driven by minor fluctuations in regime probabilities:

**Minimum position change threshold:** Only execute rebalancing trades when a position's target weight changes by more than 1% of NAV. Smaller changes accumulate and are executed in batch at weekly intervals.

**Net netting:** When regime transition requires both selling position A (old regime) and buying position B (new regime), check if any positions in the new sub-strategy book overlap with the old sub-strategy book (same underlying) and net the trades before execution to minimize round-trip costs.

---

## 12. Regime Sensitivity Meta-Analysis

### 12.1 Historical Return Attribution by Regime

Based on post-WWII US equity market data and academic literature, approximate average annualized returns by regime for a diversified equity long/short strategy:

| Regime | Avg Annual Strategy Return | Avg Market Return | Relative Contribution |
|--------|--------------------------|-------------------|----------------------|
| Trending | +15 to +25% | +15 to +20% | Strategy ≈ Market |
| Mean-Reverting | +8 to +12% | +5 to +8% | Strategy > Market |
| Risk-Off | -2 to +5% | -5 to -15% | Strategy >> Market |
| Crisis | -5 to -15% | -20 to -50% | Strategy >> Market (loss mitigation) |
| Stagflation | +0 to +8% | -5 to +5% real | Regime-specific alpha |

The key insight: the regime-switching meta-layer earns its keep primarily by avoiding catastrophic losses during crisis regimes, not by generating extraordinary alpha in trending regimes. A regime-aware strategy that earns 70% of market beta in good times but only 20-30% in bad times dramatically outperforms on a Sharpe ratio basis.

### 12.2 The Most Profitable Regimes

**Trending regime:** The highest absolute return environment. Most sub-strategies produce positive returns; the momentum sub-strategy specifically earns its strongest risk-adjusted performance here. However, the key risk is overstaying — transitioning to risk-off before the momentum book fully unwinds is critical.

**Late risk-off / crisis transition:** Arguably the highest alpha-generating period for the regime-switching system (though with limited capacity). Correctly identifying the transition from risk-off to crisis and deploying tail hedges that were accumulated during the risk-off period generates asymmetric payoffs. The timing is extremely difficult, however.

**Recovery from crisis (first 6-12 months):** Value and quality factors perform strongly in early recovery. However, momentum is dangerous here (momentum crash risk). The regime system should be in a hybrid state — starting to deploy equity longs but biased toward value and quality, not momentum.

### 12.3 The Most Dangerous Regimes (Traps)

**Regime 2 (Range-Bound) → Regime 3 (Risk-Off) transition:** The range-bound regime can mask early deterioration. Stat-arb books (the primary Regime 2 strategy) are particularly vulnerable if a range-bound regime breaks down into a risk-off environment — spreads widen rather than converting (the stat-arb assumption fails during credit-driven selloffs). Close the stat-arb book immediately upon risk-off confirmation.

**False crisis recovery:** After an acute crisis spike, VIX often falls sharply before the underlying fundamental problems have resolved. A system that detects the VIX fall as a crisis-to-risk-off transition and begins re-deploying capital can be caught in a "relief rally" that is followed by a second leg down. Require the full battery of macro and credit signals to confirm crisis exit, not just VIX normalization.

**Late-trending regime momentum crash:** The last 3-6 months of a major bull market often show the strongest momentum signals, as late-cycle investors chase performance. The momentum book will be at maximum deployment precisely when the trend is about to reverse. This is the most common cause of catastrophic drawdowns in trend-following strategies. Mitigation: monitor the yield curve inversion, credit spread widening, and PMI deceleration signals as late-cycle warning indicators even while the price signals remain bullish.

**Stagflation misidentification:** Stagflation looks similar to risk-off in price terms but requires completely different strategy response (long commodities rather than long bonds). Misidentifying stagflation as deflationary risk-off and deploying long duration bonds will produce severe losses. The inflation indicators (CPI, TIPS breakevens, commodity prices) must be integrated to distinguish the two regimes.

---

## 13. Key Risks and Failure Modes

### 13.1 Look-Ahead Bias in Regime Detection

**The risk:** Regime labels applied during backtesting are often constructed using the full historical sample (smoothed regime probabilities), which uses future observations to classify past regimes. A strategy that looks excellent in backtest because it "knew" regime labels that were only identifiable ex-post will fail in live trading.

**How it manifests:** HMM smoothed probabilities (using the Viterbi algorithm or forward-backward smoothing) look much cleaner than real-time filtered probabilities. Backtests using smoothed probabilities show regime transitions that are perfectly timed; live trading using filtered probabilities shows transitions that lag the optimal point by weeks.

**Mitigation:**
- Build and backtest exclusively using filtered (not smoothed) regime probabilities
- Add an explicit detection lag assumption of at least 5-10 business days in backtests
- Use walk-forward validation: calibrate the HMM on data through year $T$, backtest on year $T+1$, never using future data within the estimation window
- Apply Combinatorial Purged Cross-Validation (CPCV) for robust out-of-sample performance assessment

### 13.2 Overfitting to Historical Regimes

**The risk:** With five regimes, four detection signal families, dozens of sub-indicators, and multiple tunable parameters, the system has extraordinary degrees of freedom. Historical optimization will exploit spurious correlations between indicator combinations and past regime transitions.

**Specific overfitting mechanisms:**
- Optimizing the signal family weights ($w_{\text{vol}}, w_{\text{stat}}, w_{\text{breadth}}, w_{\text{macro}}$) on historical performance
- Selecting indicator thresholds (VIX levels, PMI cutoffs, ADX thresholds) based on which values perform best in backtest
- Choosing the number of HMM states to maximize historical Sharpe ratio
- Fitting transition probability assumptions to past market cycles

**Mitigation:**
- Use academically motivated parameter values (e.g., VIX > 20 for elevated stress is from literature, not optimization)
- Fix architecture decisions (number of states, signal family structure) before any historical performance analysis
- Reserve a held-out validation period (e.g., 2015-2020) that is never used for calibration
- Penalize complexity: prefer simpler signal combinations over complex ones when performance difference is small
- Target a Deflated Sharpe Ratio (DSR) — adjust Sharpe ratio for the number of parameters tested

### 13.3 Regime Changes Mid-Position

**The risk:** The system is positioned for Regime A (e.g., deeply invested in momentum longs). A rapid regime transition to Regime B (risk-off) occurs before the detection system has time to respond (within the detection lag window). During this window, the Regime A sub-strategy continues operating in a hostile environment.

**Quantification:** With a detection lag of 10 business days and a 3% per day drawdown during a fast bear market, the strategy can lose 30% of NAV from the position book before regime detection triggers de-risking. The 2020 COVID crash moved from normal to crisis in approximately 20 trading days — faster than most regime detection systems can respond.

**Mitigation:**
- Strategy-level stop-losses (Section 10.2) that operate independently of regime detection
- Maximum position concentration limits (no single sub-strategy book can represent more than 60% of gross NAV)
- Constant partial hedging: maintain 5-10% of NAV in persistent tail hedges regardless of regime
- Volatility targeting overlay (Section 10.5) that automatically reduces exposure when realized volatility spikes

### 13.4 Correlation Structure Breakdown During Stress

**The risk:** Diversification calculations rely on correlation estimates. In crisis regimes, correlations between previously uncorrelated assets spike toward 1.0 (all risk assets fall together). The regime-conditional covariance matrix used for portfolio construction is based on historical data and may underestimate the severity of correlation spikes in novel stress events.

**The Ang-Bekaert problem:** Correlations increase in bad regimes precisely when diversification is most needed. A strategy that estimates its portfolio risk using the blend of all-regime correlations will systematically underestimate crisis-regime risk.

**Mitigation:** Use stress-test correlation matrices (as described in Section 9.5). Apply regular scenario analysis using historical crisis correlation matrices (2008, 2020) as stress scenarios, and ensure the portfolio can survive these scenarios within the drawdown tolerance.

### 13.5 Structural Breaks and Regime Stationarity

**The risk:** The regime taxonomy and detection thresholds are calibrated on historical data. If the fundamental nature of market regimes changes structurally (e.g., central bank quantitative easing permanently suppresses volatility; algorithmic trading changes the autocorrelation structure), the historical calibration becomes invalid.

**Examples of structural changes:**
- Post-2008 QE: VIX structurally lower for extended periods; a VIX threshold of > 20 for stress may be too conservative
- Passive investing growth: Increased market-cap concentration in index products changes breadth indicator behavior
- Zero-interest-rate policy (ZIRP): The yield curve's predictive power for recession may be altered when the zero lower bound is binding

**Mitigation:** Re-estimate HMM parameters on a rolling window to adapt to structural changes. Monitor the predictive accuracy of each signal family on a rolling basis and down-weight signals whose historical regime-to-outcome relationship appears to have broken down.

---

## 14. Parameters and Tunable Knobs

This section catalogs all adjustable parameters in the regime-switching system, with recommended default values and the rationale for each.

### 14.1 HMM / Statistical Signal Parameters

| Parameter | Default Value | Range | Description |
|-----------|---------------|-------|-------------|
| Number of HMM states (K) | 3 | 2-5 | Number of latent states; select via BIC |
| HMM rolling training window | 1250 days (5yr) | 500-2500 | Days of data used to re-estimate parameters |
| HMM retraining frequency | Monthly | Weekly-Quarterly | How often HMM parameters are re-estimated |
| HMM covariance type | Full | Diagonal, Tied | Covariance structure of Gaussian emissions |
| EM algorithm iterations | 1000 | 500-5000 | Max iterations for Baum-Welch convergence |
| SJM jump penalty (λ) | CV-optimized | 0-100 | Penalizes regime transitions; higher = more persistence |
| Filtered probability EMA halflife | 3 days | 1-10 | Smoothing applied to raw filtered regime probabilities |

### 14.2 VIX / Volatility Signal Parameters

| Parameter | Default Value | Range | Description |
|-----------|---------------|-------|-------------|
| VIX threshold: normal upper | 20 | 15-25 | VIX above this triggers risk-off monitoring |
| VIX threshold: stress upper | 30 | 25-40 | VIX above this triggers crisis monitoring |
| VIX 200-day SMA window | 200 days | 100-250 | Window for VIX long-run average |
| VX1/VX3 backwardation threshold | 1.0 | 0.90-1.05 | Ratio above this confirms backwardation |
| VIX spike confirmation days | 5 days | 3-10 | Consecutive days above threshold required |

### 14.3 Technical / Price Signal Parameters

| Parameter | Default Value | Range | Description |
|-----------|---------------|-------|-------------|
| Hurst exponent window | 252 days | 100-500 | Rolling window for R/S analysis |
| Hurst trending threshold | 0.55 | 0.52-0.60 | H above this = trending regime |
| Hurst mean-rev threshold | 0.45 | 0.40-0.48 | H below this = mean-reverting regime |
| ADX window | 14 days | 10-21 | Standard Wilder ADX lookback |
| ADX trend confirmation | 25 | 20-30 | ADX above this confirms trend |
| 200-day SMA window | 200 days | Fixed | Long-term trend filter |
| Drawdown crisis threshold | 20% | 15-25% | Drawdown from 52-week high for risk-off signal |

### 14.4 Breadth Signal Parameters

| Parameter | Default Value | Range | Description |
|-----------|---------------|-------|-------------|
| % above 200d SMA bull threshold | 75% | 65-80% | Above this = strong bull breadth |
| % above 200d SMA bear threshold | 35% | 25-45% | Below this = bear breadth confirmed |
| AD line EMA window | 10 days | 5-20 | Smoothing on AD line for signal extraction |
| New H/L ratio smoothing | 10 days | 5-20 | EMA window on new high/new low ratio |

### 14.5 Macro Signal Parameters

| Parameter | Default Value | Range | Description |
|-----------|---------------|-------|-------------|
| HY OAS risk-off threshold | 450 bps | 350-550 | HY spread above this = risk-off signal |
| HY OAS crisis threshold | 650 bps | 550-750 | HY spread above this = crisis signal |
| IG OAS stress threshold | 150 bps | 120-200 | IG spread above this = stress signal |
| Yield curve inversion threshold | 0 bps (2s10s) | 0 to -25 | Inversion depth for recession signal |
| PMI contraction threshold | 50 | Fixed | ISM below this = manufacturing contraction |
| PMI stress threshold | 47 | 44-49 | ISM below this = recessionary territory |
| Inflation signal threshold | CPI > 4% | 3-5% | CPI above this activates stagflation monitoring |
| TIPS breakeven stagflation threshold | 2.75% | 2.5-3.5% | Breakevens above this supports stagflation classification |

### 14.6 Composite Signal Construction Parameters

| Parameter | Default Value | Range | Description |
|-----------|---------------|-------|-------------|
| Volatility family weight | 0.30 | 0.20-0.40 | Weight of VIX/vol signals in composite |
| Statistical family weight | 0.30 | 0.20-0.40 | Weight of HMM/price signals in composite |
| Breadth family weight | 0.25 | 0.15-0.35 | Weight of breadth signals in composite |
| Macro family weight | 0.15 | 0.10-0.25 | Weight of macro/fundamental signals |
| Softmax sharpness (γ) | 2.0 | 1.0-5.0 | Sharpness of regime probability distribution |
| Regime confirmation window | 5-10 days | 3-15 | Days required in new regime zone for confirmation |
| Minimum probability delta | 0.25 | 0.15-0.35 | Min probability lead for a regime switch |

### 14.7 Switching Logic Parameters

| Parameter | Default Value | Range | Description |
|-----------|---------------|-------|-------------|
| Hard-switch probability threshold | 0.80 | 0.70-0.90 | Above this, move toward hard switching |
| Minimum time-in-regime (days) | 10 | 5-20 | Min holding period before another regime switch |
| Transition speed (% per day) | 25% | 15-50% | Rate of portfolio transition during regime change |
| Max annual turnover budget | 300% | 200-500% | Maximum tolerable annual one-way turnover |

### 14.8 Risk Management Parameters

| Parameter | Default Value | Range | Description |
|-----------|---------------|-------|-------------|
| Portfolio circuit breaker | -12% 60-day DD | -8% to -15% | Emergency gross exposure reduction trigger |
| Crisis gross exposure cap | 25% of normal | 15-35% | Max gross exposure in crisis regime |
| Tail risk budget | 2.5% of NAV | 1-4% | Annual budget for convex tail protection |
| Volatility target | 10% annualized | 8-15% | Target realized portfolio volatility |
| Volatility target tolerance | +20% | 15-30% | Overshoot before position scaling |
| Transition uncertainty exposure | 60% of normal | 50-75% | Gross exposure during uncertain regime transition |

---

## References and Further Reading

### Foundational Academic Papers

- Hamilton, J.D. (1989). "A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle." *Econometrica*, 57(2), 357-384.
- Ang, A. and Bekaert, G. (2002). "International Asset Allocation With Regime Shifts." *Review of Financial Studies*, 15(4), 1137-1187.
- Ang, A. (2011). "Regime Changes and Financial Markets." NBER Working Paper No. 17182.
- Kim, C.J., Nelson, C.R. and Startz, R. (1998). "Testing for Mean Reversion in Heteroskedastic Data Based on Gibbs-Sampling-Augmented Randomization." *Journal of Empirical Finance*, 5(2), 131-154.
- Daniel, K. and Moskowitz, T. (2016). "Momentum Crashes." *Journal of Financial Economics*, 122(2), 221-247.

### Regime Detection Methodology

- Aydinhan, A.O., Kolm, P.N., Mulvey, J.M. and Shu, Y. (2024). "Identifying Patterns in Financial Markets: Extending the Statistical Jump Model for Regime Identification." *Annals of Operations Research*.
- Shu, Y. and Mulvey, J.M. (2024). "Dynamic Factor Allocation Leveraging Regime-Switching Signals." *Journal of Portfolio Management*, 51(3).
- Nystrup, P. (2018). "Dynamic Asset Allocation." PhD Thesis, Technical University of Denmark.

### Factor Performance and Regime Conditioning

- Asness, C., Moskowitz, T. and Pedersen, L.H. (2013). "Value and Momentum Everywhere." *Journal of Finance*, 68(3), 929-985.
- Fama, E. and French, K. (2015). "A Five-Factor Asset Pricing Model." *Journal of Financial Economics*, 116(1), 1-22.
- MSCI Research (2018). "Adaptive Multi-Factor Allocation." MSCI Research Insights.

### Practical Implementation

- Quantstart: "Market Regime Detection Using Hidden Markov Models in QSTrader" (quantstart.com)
- Volatility Box: "Volatility Regimes Explained" (volatilitybox.com)
- Macrosynergy: "Detecting Trends and Mean Reversion with the Hurst Exponent" (macrosynergy.com)
- BSIC: "Regime Detection and Risk Allocation Using Hidden Markov Models" (bsic.it)
