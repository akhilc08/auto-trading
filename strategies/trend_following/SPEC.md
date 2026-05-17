# Trend Following / Time-Series Momentum Strategy Specification

**Version**: 1.0  
**Status**: Design Specification  
**Asset Class**: Multi-Asset Futures (Equities, Fixed Income, FX, Commodities) with ETF Proxies  
**Strategy Type**: Systematic Directional / Alternative Risk Premium  

---

## Table of Contents

1. [Strategy Overview and Thesis](#1-strategy-overview-and-thesis)
2. [Academic Foundations](#2-academic-foundations)
3. [Signal Construction](#3-signal-construction)
4. [Multi-Timeframe Signal Blending](#4-multi-timeframe-signal-blending)
5. [Universe Selection](#5-universe-selection)
6. [Position Sizing and Volatility Targeting](#6-position-sizing-and-volatility-targeting)
7. [Portfolio Construction](#7-portfolio-construction)
8. [Risk Management](#8-risk-management)
9. [Execution Considerations](#9-execution-considerations)
10. [Regime Sensitivity](#10-regime-sensitivity)
11. [Key Risks and Failure Modes](#11-key-risks-and-failure-modes)
12. [Parameters and Tunable Knobs](#12-parameters-and-tunable-knobs)

---

## 1. Strategy Overview and Thesis

### 1.1 Core Thesis

Trend following is the oldest and most robustly documented systematic strategy in financial markets. The central claim is simple: assets that have risen over the recent past tend to continue rising; assets that have fallen tend to continue falling. This serial correlation in returns — persistence — is the raw material the strategy harvests.

Unlike cross-sectional momentum (which bets on *relative* winners versus losers within an asset class), time-series momentum (TSMOM) is an *absolute* directional bet. Each instrument is evaluated independently against its own history. A positive past return generates a long position; a negative past return generates a short position. The magnitude of the signal determines position size, scaled by volatility.

The strategy is not predicated on any single causal mechanism. Multiple, reinforcing explanations make the premium durable:

- **Behavioral anchoring and under-reaction**: Investors are slow to incorporate new fundamental information, causing gradual price adjustment rather than immediate repricing. The trend is the price moving toward fair value over weeks or months.
- **Herding and over-reaction in the late stage**: As a trend matures, momentum chasers pile in, extending the move beyond fundamental value. This creates the eventual reversal that the strategy must exit before or during.
- **Central bank and institutional policy responses**: Monetary tightening and loosening cycles play out over years. Bond yields, FX rates, and commodity prices trend for sustained periods tied to macro regime changes.
- **Supply/demand structural lags**: Physical commodity markets adjust supply slowly. Oil, metals, and agriculture exhibit persistent multi-year trends tied to production lead times.
- **Risk premium for liquidity provision**: Trend followers are effectively providing liquidity in the direction opposite to distressed sellers or forced buyers. They are compensated for bearing this risk.

### 1.2 Practitioner Lineage

The strategy has deep roots among the original Commodity Trading Advisors (CTAs):

**Richard Donchian (1950s–1980s)**: The intellectual grandfather of trend following. Developed the channel breakout system — go long when price exceeds its N-day high, go short when it breaks the N-day low. Managed futures from the 1950s and proved systematic rules outperform discretion.

**Richard Dennis and the Turtles (1983)**: Dennis conducted the famous experiment — can trading be taught? He trained 13 novices (the Turtles) in a complete mechanical trend following system using 20-day and 55-day Donchian breakouts, N-based position sizing, and 2N stop losses. The experiment succeeded spectacularly, validating the rules-based approach. The complete Turtle rules: enter on 55-day breakout (System 2) or 20-day breakout (System 1), size positions as 1 unit = 1% account risk per N of price movement (where N = 20-day Average True Range), add to winning positions in increments of 0.5N up to 4 units, exit System 2 longs on 20-day low.

**Bill Dunn / Dunn Capital Management (1974–present)**: One of the longest continuously running CTA programs. Dunn's WMA (World Monetary and Agriculture) program has been trading since 1984. Pure mechanical trend following across currencies, bonds, and commodities. Known for very high volatility targeting (often 20–30% annualized), extreme position concentration in strong trends, and brutal drawdowns in choppy years. The program's longevity across multiple decades — spanning the 1987 crash, 2000 dot-com bust, 2008 crisis, and beyond — is the strongest live proof that systematic trend following is a persistent strategy.

**Campbell & Company (Keith Campbell, 1972)**: One of the pioneering multi-market systematic managers. Track record extends to 1972, among the oldest in the industry. Combines trend signals across futures markets globally.

**John W. Henry & Associates (JWM, 1981–)**: Another early CTA with quantitative trend following as the core methodology. Henry later became famous for purchasing the Boston Red Sox. JWM demonstrated the strategy's scalability to institutional AUM.

**AHL (Adam, Harding, Lueck — 1987)**: Founded by Michael Adam, David Harding, and Martin Lueck. Man Group acquired a majority stake in 1989. AHL became the proving ground for academic quantitative research applied to trend following at scale. Their approach introduced multi-timeframe signal blending using EWMAs, rigorous risk management, and diversification across 300+ markets. AHL's core is a diversified EWMA-crossover system; they simultaneously run signals with short (1–2 month), medium (3–6 month), and long (6–12+ month) lookbacks, blending them into a composite signal. Volatility targeting is central — each instrument receives a position sized to deliver an equal risk contribution.

**Winton Group (David Harding, 1997)**: Harding departed AHL to found Winton, which grew to manage over $20 billion at its peak. Winton added heavy statistical research and machine learning elements to trend following while keeping the core momentum signal as the dominant alpha source. Winton's research emphasized the value of diversification — they traded 100+ markets — and the critical role of volatility normalization in position sizing.

**Aspect Capital (Adam and Lueck, 1998)**: The third firm to emerge from the AHL breakup. Like Winton, combines systematic trend across many markets with proprietary research into the signal construction and risk management.

### 1.3 What the Strategy Is Not

- It is not a value strategy. It does not care whether an asset is cheap or expensive — only whether it is moving.
- It is not a carry strategy. Yield differentials and roll yields matter for implementation but are not the alpha source.
- It is not a high-frequency strategy. Signals update daily. Turnover is moderate (30–100% per year depending on speed).
- It does not require forecasting macroeconomic variables. It is purely price-reactive.

---

## 2. Academic Foundations

### 2.1 Primary Literature

#### Moskowitz, Ooi, and Pedersen (2012) — "Time Series Momentum"

Published in the *Journal of Financial Economics* (Volume 104, Issue 2, May 2012). This is the foundational academic paper establishing TSMOM as a distinct, documented anomaly.

**Dataset**: 58 futures and forward contracts across equity index futures, currency forwards, commodity futures, and sovereign bond futures. Data spans January 1985 to December 2009 (25 years).

**Core Finding**: Past 12-month excess return of each instrument positively predicts its future 1-month return. This relationship holds across all four asset classes and is statistically highly significant (t-statistics in excess of 5).

**Signal Definition**: The TSMOM signal for instrument i at time t is:

```
r_{t-12, t-1}   (excess return over the past 12 months, skipping the last month)
```

A position is taken proportional to the sign and magnitude of this return, scaled by ex-ante volatility:

```
Signal_i,t = r_{i, t-12:t-1} / σ_i,t
```

where σ_i,t is the ex-ante annualized volatility estimate of instrument i at time t.

**Portfolio Construction**: The full TSMOM portfolio assigns a position to each instrument proportional to its normalized past return, targeting a fixed portfolio volatility level.

**Economic Magnitude**: The diversified TSMOM portfolio delivers an annualized Sharpe ratio of approximately 1.3 before costs over the sample period, with near-zero correlation to equities, bonds, and standard risk factors.

**Crisis Alpha**: The strategy's returns are positively correlated with the absolute magnitude of equity market moves. It performs best during the most extreme up and down equity markets. This "crisis alpha" property — large positive returns when equities crash — is one of the most important features of the strategy.

**Reversal**: The momentum signal reverses at horizons longer than 12 months. The same past return that predicts positive future returns over a 1-month horizon predicts negative future returns over 3–5 year horizons.

#### Hurst, Ooi, and Pedersen (2017) — "A Century of Evidence on Trend-Following Investing"

Published in the *Journal of Portfolio Management* (Volume 44, Number 1, Fall 2017). Extends Moskowitz et al. (2012) by over 100 years using a novel historical dataset.

**Dataset**: 67 markets across 4 asset classes (29 commodities, 11 equity indices, 15 bond markets, 12 currency pairs). Data from January 1880 to December 2016 — 136 years of evidence.

**Core Finding**: Time-series momentum delivered positive average returns with low correlations to traditional assets in each decade since 1880. The strategy performed well (positive returns) in 8 of the 10 largest crisis periods over the century, including the Great Depression, World War II, the 1970s oil shock, the 1987 crash, the 2000 dot-com bust, and the 2008 financial crisis.

**Robustness**: The premium persisted across:
- Different asset classes
- Different countries and currencies
- Different decades and economic regimes
- Different lookback windows (1, 3, 6, 12 months all positive)

This century-long persistence is the strongest evidence that trend following is a genuine risk premium rather than a statistical artifact from data mining.

#### Fung and Hsieh (2001) — "The Risk in Hedge Fund Strategies: Theory and Evidence from Trend Followers"

Published in *Review of Financial Studies* (Volume 14, Issue 2, 2001). This paper provided the theoretical framework for understanding why trend following generates an option-like payoff.

**Key Insight**: A simple trend following strategy has the same payoff as a "lookback straddle." A lookback call option gives the holder the right to buy at the lowest price observed over the option's life; a lookback put gives the right to sell at the highest price. The combination — the lookback straddle — pays out the maximum possible trend-following profit ex post.

**Implications**:
- Trend following is mechanically **long volatility**. When large moves occur, the strategy profits. When markets are quiet and range-bound, it loses (the "premium" paid for being long vol).
- Trend following provides a natural hedge for a portfolio of equities and bonds precisely because crises involve sustained directional moves — exactly when the strategy thrives.
- The return distribution exhibits **positive skewness** — many small losses, occasional very large gains. This is the mirror image of selling options.

#### Hurst, Ooi, and Pedersen (2013) — "Demystifying Managed Futures"

Published in the *Journal of Investment Management* (Volume 11, Issue 3, 2013). Shows that the returns of managed futures funds and CTAs are well-explained by time-series momentum strategies.

**Key Finding**: Time-series momentum strategies produce large R-squared values (0.36–0.64) with managed futures indices and individual CTA returns. After controlling for TSMOM strategies, the alpha of even the largest managed futures managers drops to approximately zero, indicating that TSMOM captures the core of what CTAs do.

#### Additional Supporting Literature

- **Baltas and Kosowski (2012)**: "Momentum Trading in Futures Markets" — demonstrates TSMOM profitability across multiple holding periods and its robustness to transaction costs.
- **Asness, Moskowitz, and Pedersen (2013)**: "Value and Momentum Everywhere" — documents momentum across 8 diverse markets and shows momentum and value are negatively correlated, creating a powerful diversification opportunity.
- **Baltas (2019)**: "The Impact of Crowding in Alternative Risk Premia Investing" — introduces the divergence versus convergence premium framework, showing that crowding in trend-following strategies causes underperformance via positive feedback loop dynamics.
- **Lempérière et al. (2014)**: "Two Centuries of Trend Following" — extends evidence back to 1800 using commodity, bond, currency, and stock data, reinforcing the extreme durability of the anomaly.

---

## 3. Signal Construction

### 3.1 Signal Taxonomy

Three families of trend signal are used in institutional practice. They differ in how they define "trend" and how quickly they react to price changes:

| Family | Mechanism | Speed | Pros | Cons |
|---|---|---|---|---|
| Breakout (Donchian) | Price vs. N-day high/low | Fast–Medium | Simple, robust, no look-ahead | Binary, noisy |
| Moving Average Crossover (EWMA/MACD) | Difference of two smoothed prices | Medium | Smooth, parametric | Lag in signal reversal |
| Time-Series Momentum (TSMOM) | Past N-month return sign and magnitude | Variable | Academic foundation, clean | Blunt, monthly granularity |

A fully specified strategy combines all three as sub-signals, or runs them independently as sub-strategies with vol-weighted combination.

---

### 3.2 Breakout Signal (Donchian Channels)

#### Definition

The N-day Donchian Channel is defined by:

```
Upper_N(t) = max(P_{t-N}, P_{t-N+1}, ..., P_{t-1}, P_t)
Lower_N(t) = min(P_{t-N}, P_{t-N+1}, ..., P_{t-1}, P_t)
```

where P_t is the close price (or adjusted settlement price for futures) on day t.

#### Entry Signal

The raw breakout signal at day t for instrument i is:

```
Breakout_Signal_i(t) = 
    +1   if P_i(t) > Upper_N_i(t-1)   [new N-day high: long]
    -1   if P_i(t) < Lower_N_i(t-1)   [new N-day low: short]
     0   otherwise                      [no new signal]
```

In the pure Turtle/Dennis system, the signal is sticky — once you go long on a 55-day breakout, you stay long until a 20-day low exit triggers. The signal does not flip to -1 until a short breakout occurs (and vice versa).

#### Position State (Sticky Signal)

```
Position_i(t) = 
    +1   if last breakout was a new N_entry-day high and no N_exit-day low hit
    -1   if last breakout was a new N_entry-day low and no N_exit-day high hit
```

The exit channel (N_exit) is shorter than the entry channel (N_entry). Standard parameterizations:

| System | Entry | Exit |
|---|---|---|
| Turtle S1 (fast) | 20-day high/low | 10-day opposite |
| Turtle S2 (slow) | 55-day high/low | 20-day opposite |
| Academic benchmark | 252-day high/low | 126-day opposite |

#### Continuous Breakout Score

For blending with other signals, a continuous version of the breakout signal is more useful:

```
Breakout_Score_i(t) = (P_i(t) - Midpoint_N(t)) / (Upper_N(t) - Lower_N(t))
```

where:
```
Midpoint_N(t) = (Upper_N(t) + Lower_N(t)) / 2
```

This scores price position within the channel on [-1, +1]. A score of +1 means price is at the top of its N-day range; -1 means price is at the bottom.

---

### 3.3 Moving Average Crossover (EWMA-Based)

#### Exponentially Weighted Moving Average

The EWMA with decay parameter λ (or equivalently, half-life τ in days) is:

```
EWMA_λ(t) = λ · EWMA_λ(t-1) + (1 - λ) · P(t)
```

The relationship between λ and half-life τ:

```
λ = exp(-ln(2) / τ)     or equivalently     τ = ln(2) / (-ln(λ))
```

For implementation convenience, practitioners often specify the "span" S (equivalent to a simple moving average of length approximately S):

```
λ = (S - 1) / (S + 1)
```

Common half-life to span approximations:

| Half-Life (days) | Approximate Span | λ |
|---|---|---|
| 8 days | ~16 days | 0.882 |
| 16 days | ~32 days | 0.957 |
| 32 days | ~64 days | 0.979 |
| 64 days | ~128 days | 0.989 |
| 126 days | ~252 days | 0.995 |

#### EWMA Crossover Signal

The signal is the difference between a fast EWMA and a slow EWMA, normalized to be comparable across instruments:

```
MACD_raw_i(t) = EWMA(τ_fast, P_i, t) - EWMA(τ_slow, P_i, t)
```

This raw difference has units of price and must be normalized. The standard approach scales by the exponentially weighted standard deviation of the price series:

```
σ_price_i(t) = EWMA_stddev(τ_vol, P_i, t)

MACD_signal_i(t) = MACD_raw_i(t) / σ_price_i(t)
```

This produces a dimensionless score with typical range roughly [-3, +3], centered at zero.

#### Multi-Timeframe MACD Sub-Signals

Rather than a single (fast, slow) pair, the strategy runs multiple pairs simultaneously:

| Label | τ_fast | τ_slow | Effective Lookback |
|---|---|---|---|
| Fast (S) | 8 days | 24 days | ~1 month |
| Medium-Fast (M1) | 16 days | 48 days | ~2 months |
| Medium (M2) | 32 days | 96 days | ~4 months |
| Medium-Slow (M3) | 64 days | 192 days | ~8 months |
| Slow (L) | 126 days | 252 days | ~12 months |

Each pair produces an independent signal for each instrument. These are later blended (Section 4).

#### Volatility Normalization of the Signal

The normalized MACD signal requires further processing before it can be used for position sizing. The goal is to produce a "forecast" that maps into position size. AHL's published approach (as described in their educational materials) applies a "forecast scalar" — a constant that scales the average absolute signal value to a target level (commonly 10):

```
Forecast_i,s(t) = MACD_signal_i,s(t) × ForecastScalar_s
```

where ForecastScalar_s is calibrated so that the average absolute value of Forecast_i,s(t) equals 10, capped at ±20.

---

### 3.4 Time-Series Momentum (Raw Return Signal)

#### Definition (Moskowitz et al. 2012)

The TSMOM signal for instrument i with lookback period L months is:

```
r_i(t, L) = (P_i(t) / P_i(t - L)) - 1
```

This is the total return over the past L months (1-month lag is typically *not* skipped for futures, unlike equities where a 1-month reversal effect exists at the individual stock level; for diversified futures indices the lag skip is optional).

#### Sign Signal

The simple binary TSMOM signal is just the sign:

```
Sign_i(t, L) = sign(r_i(t, L))   = +1, 0, or -1
```

This is the Moskowitz et al. benchmark construction: long all instruments with positive 12-month past returns, short all instruments with negative 12-month past returns, each sized equally by inverse volatility.

#### Continuous Signal

A more refined version uses the return magnitude, bounded and normalized:

```
ContSignal_i(t, L) = r_i(t, L) / σ_i(t, L)
```

where σ_i(t, L) is the realized annualized volatility over the same lookback window L. This produces a t-statistic-like quantity — how many annualized standard deviations of return has the instrument moved over the lookback?

Applying a normalization function (e.g., tanh or simple clipping at ±3) prevents extreme signals from dominating:

```
Signal_i(t, L) = tanh(k · r_i(t, L) / σ_i(t, L))
```

where k is a scaling constant (often chosen so that a 1-sigma past return maps to a signal of approximately 0.5).

#### Multi-Lookback TSMOM

Running TSMOM at multiple lookback horizons L ∈ {1, 3, 6, 12} months and averaging:

```
TSMOM_Composite_i(t) = (1/4) · Σ_L  Signal_i(t, L)
```

This blending averages over fast and slow time scales, reducing the drawdown associated with any single lookback period while preserving the core momentum signal.

---

### 3.5 Volatility Estimation for Signal Normalization

All three signal families require an estimate of instrument volatility. The standard approach uses an exponentially weighted realized volatility (daily returns):

```
Daily_Return_i(t) = ln(P_i(t) / P_i(t-1))

σ²_EWMA_i(t) = λ · σ²_EWMA_i(t-1) + (1 - λ) · Daily_Return_i(t)²

σ_daily_i(t) = sqrt(σ²_EWMA_i(t))

σ_annual_i(t) = σ_daily_i(t) × sqrt(252)
```

The decay parameter λ for volatility estimation is typically set to correspond to a half-life of 20–60 trading days. JP Morgan's RiskMetrics standard uses λ = 0.94, corresponding to a half-life of approximately 11 days — fast-reacting but smooth. Many CTAs use a longer half-life of 30–60 days to reduce position turnover from volatility spikes.

**Practical note**: For commodities and agricultural futures, using a longer half-life (60 days, λ ≈ 0.989) is advisable because these markets exhibit periodic volatility spikes tied to weather or supply shocks. A short half-life would cause dramatic position reduction immediately after a spike, right when the trend might be strongest.

---

## 4. Multi-Timeframe Signal Blending

### 4.1 Rationale

No single lookback period dominates across all market conditions:

- **Fast signals** (1-month lookback) react quickly to trend reversals and provide excellent crisis alpha — they pivot fast when equity markets begin to fall. But in quiet, range-bound markets, fast signals generate excessive whipsaw losses.
- **Slow signals** (12-month lookback) ride large macro trends with minimal transaction costs, but are slow to respond to trend reversals. They carried large losses in 2009 when the equity bottom reversed sharply after CTA programs had built up large equity shorts.
- **Medium signals** (3–6 months) represent the empirical sweet spot — sufficient lookback to avoid noise-driven whipsaw but fast enough to participate in most trend moves.

The solution, documented in AHL's research and widely adopted in the managed futures industry, is to run all speeds simultaneously and blend them into a composite signal.

### 4.2 Blending Methodology

#### Step 1: Compute Sub-Signals

For each instrument i and each speed s ∈ {fast, medium-fast, medium, medium-slow, slow}:

```
SubSignal_i,s(t) = normalize(raw_signal_i,s(t))
```

where normalize() scales the signal to have a common scale (e.g., target mean absolute value of 1.0, or maps to [-1, +1] via tanh).

#### Step 2: Equal-Weight Blend

The simplest blending assigns equal weight to each speed:

```
CompositeSignal_i(t) = (1/S) · Σ_s  SubSignal_i,s(t)
```

where S is the number of speed variants.

#### Step 3: Volatility-Weighted Blend

A more sophisticated approach weights each speed by the inverse of its historical signal volatility, so that noisier (faster) signals contribute less weight:

```
w_s = 1 / σ(SubSignal_s)     (normalized so that Σ w_s = 1)

CompositeSignal_i(t) = Σ_s  w_s · SubSignal_i,s(t)
```

#### Step 4: Sharpe-Weighted Blend

The academically rigorous approach weights sub-signals by their ex-ante expected Sharpe ratio (estimated from historical data with appropriate lookback to avoid look-ahead bias):

```
w_s = SR_s / Σ_s' SR_s'

CompositeSignal_i(t) = Σ_s  w_s · SubSignal_i,s(t)
```

This is difficult to estimate robustly out-of-sample due to parameter instability.

### 4.3 Recommended Blending Scheme

The practical recommendation is a **three-tier equal-weight blend** with the following lookback pairs:

| Tier | EWMA Pair (fast/slow half-life, days) | Approx. Signal Horizon | Weight |
|---|---|---|---|
| Fast | 8 / 24 | 1 month | 1/3 |
| Medium | 32 / 96 | 3–4 months | 1/3 |
| Slow | 126 / 252 | 12 months | 1/3 |

The three-tier blend has been empirically shown to deliver a Sharpe ratio within 5–10% of the theoretically optimal multi-speed combination, at a fraction of the complexity.

### 4.4 Signal Correlation Across Speeds

Importantly, fast and slow signals are positively but imperfectly correlated. Correlations between adjacent speed pairs are typically 0.5–0.7. Correlations between fast and slow (1-month vs. 12-month) are approximately 0.2–0.4. This low correlation means the blend genuinely diversifies signal risk — the combined signal has a higher information ratio than any single component.

### 4.5 Crisis Alpha by Speed

Research from Man AHL's published educational materials shows that **faster speeds provide better crisis alpha**. During the worst quintile of S&P 500 monthly returns, fast trend systems deliver larger positive returns than slow systems. This is because fast systems pivot to short equities more quickly after the trend reversal begins.

The tradeoff: faster systems have higher transaction costs and more frequent whipsaw losses in benign, choppy markets. The optimal speed is therefore a function of the investor's mandate:

- **Pure crisis alpha / tail hedge**: Overweight fast signals (1–2 month speeds)
- **Risk-adjusted return maximization**: Equal-weight fast, medium, slow
- **Cost-sensitive / lower-turnover**: Overweight slow signals (6–12 month speeds)

---

## 5. Universe Selection

### 5.1 Design Principles

The single most important insight from both the academic literature and practitioner experience is that **diversification is the engine of trend following**. Running 50+ uncorrelated instruments is not optional — it is the mechanism by which the strategy generates consistent positive returns despite any individual instrument having a low hit rate (typically 40–45% winning trades, with profits coming from the magnitude of winners vs. losers).

The diversification benefit operates at two levels:

1. **Cross-asset correlation**: Equities, bonds, FX, and commodities have low or negative correlations, especially during crises. Losses in one asset class are offset by gains in others.
2. **Within-asset-class diversification**: Individual commodities (crude oil, natural gas, gold, copper, soybeans) exhibit low inter-correlation. Running all of them expands the opportunity set.

The Moskowitz et al. (2012) paper documents the diversification across 58 instruments. Winton Group famously traded 100+ markets. The SG Trend Index constituents typically trade 150–300+ markets across all asset classes.

### 5.2 Asset Class Coverage

#### Equity Index Futures

These are the most liquid instruments globally. They track broad stock market indices and are used to express directional macro views on economic growth.

**Primary futures markets**:
- S&P 500 E-mini (ES): US large-cap equities
- NASDAQ-100 (NQ): US technology-heavy
- Russell 2000 (RTY): US small-cap
- Euro Stoxx 50 (FESX): European large-cap
- DAX (FDAX): German equities
- FTSE 100 (Z): UK equities
- Nikkei 225 (NK): Japanese equities
- Hang Seng (HSI): Hong Kong equities
- ASX SPI 200 (AP): Australian equities
- Kospi 200 (KM): Korean equities
- MSCI Emerging Markets (EEM futures or proxies)

**ETF proxies** (for ETF-based implementations):
- SPY / IVV / VOO — US large-cap
- QQQ — US technology
- EFA — Developed international ex-US
- EEM — Emerging markets
- VGK — European equities
- EWJ — Japanese equities

#### Fixed Income (Government Bond Futures)

Government bond futures are essential for two reasons: (1) they trend for long periods tied to monetary policy cycles; (2) they often provide the best crisis alpha because safe-haven bond rallies coincide with equity crises.

**Primary futures markets**:
- US 10-Year Treasury Note (ZN)
- US 30-Year Treasury Bond (ZB)
- US 5-Year Treasury Note (ZF)
- US 2-Year Treasury Note (ZT)
- German Bund 10-Year (FGBL)
- German Schatz 2-Year (FGBS)
- UK Gilt 10-Year (R)
- Japanese Government Bond 10-Year (JGB)
- Australian Government Bond 10-Year (YM)
- Canadian Government Bond 10-Year (CGB)

**ETF proxies**:
- TLT — US 20+ year Treasury
- IEF — US 7–10 year Treasury
- SHY — US 1–3 year Treasury
- TIP — US inflation-linked (TIPS)
- BWX — Developed market foreign government bonds
- VGLT — Vanguard long-term Treasury

**Note on bond correlation**: In the current (post-2022) environment, bonds and equities have shown positive correlation during inflationary regimes. This alters the portfolio construction calculus significantly — the traditional "crisis alpha" from bonds may be weaker in prolonged inflation shocks.

#### Foreign Exchange (FX)

Currencies trend persistently, especially around diverging monetary policy cycles. FX is also the most liquid asset class globally (>$7 trillion daily turnover).

**Primary futures/forward markets**:
- EUR/USD (6E)
- GBP/USD (6B)
- JPY/USD (6J)
- AUD/USD (6A)
- CAD/USD (6C)
- CHF/USD (6S)
- NZD/USD (6N)
- USD/CNH (offshore Chinese yuan)
- MXN/USD (6M) — emerging FX

**ETF proxies** (note: ETF proxies for FX are imperfect and introduce basis risk):
- UUP — US Dollar Index bullish
- FXE — Euro
- FXY — Japanese yen
- FXA — Australian dollar
- FXB — British pound

**Note on FX diversification**: FX exposure within the trend portfolio must be netted carefully. Going long EUR/USD on a trend signal while also holding European equity futures creates compounded FX risk. Most institutional implementations use separate FX hedging overlays.

#### Commodities

Commodities provide the richest opportunity for trend following because supply and demand imbalances play out over very long cycles (oil supply takes years to build, agricultural crops have seasonal patterns, metals face mining lead times of 5–10 years).

**Energy**:
- WTI Crude Oil (CL)
- Brent Crude Oil (CO)
- RBOB Gasoline (RB)
- Natural Gas (NG)
- Heating Oil (HO)

**Metals**:
- Gold (GC)
- Silver (SI)
- Copper (HG)
- Platinum (PL)
- Palladium (PA)

**Agriculture**:
- Corn (ZC)
- Wheat (ZW)
- Soybeans (ZS)
- Soybean Oil (ZL)
- Soybean Meal (ZM)
- Sugar #11 (SB)
- Coffee (KC)
- Cotton (CT)
- Cocoa (CC)
- Live Cattle (LE)
- Lean Hogs (HE)

**ETF proxies**:
- GLD / IAU — Gold
- SLV — Silver
- PDBC — Diversified commodities (Invesco Optimum Yield)
- DJP — iPath Bloomberg Commodity Index
- USO — Crude oil (note: severe roll cost issues; not recommended for trend following implementations)
- BCI — iShares Bloomberg Roll Select Commodity

### 5.3 Minimum Universe Requirements

Based on the academic evidence on diversification:

| Portfolio Size | Expected Sharpe Improvement | Notes |
|---|---|---|
| 10 instruments | Baseline | Severely underdiversified |
| 20 instruments | +30–40% | Minimum viable |
| 50 instruments | +60–70% | Typical academic standard |
| 100+ instruments | +75–85% | Institutional-grade diversification |

**Recommended minimum**: 30 instruments across all four asset classes with roughly equal risk allocation to each class.

### 5.4 Instrument Selection Criteria

1. **Liquidity**: Average daily volume must support intended position sizes without excessive market impact. For retail/small-fund implementations, E-mini futures are preferred over full-size contracts.
2. **Continuity**: Avoid instruments with structural breaks (currency pegs, circuit breakers, market closures) that generate false trend signals.
3. **Roll mechanics**: Futures must have liquid front-month and second-month contracts to enable rolling without undue slippage. Roll costs can be the dominant drag on commodity futures performance.
4. **Margin requirements**: Position sizes must remain within margin capacity. ETF implementations avoid this constraint but sacrifice short-selling on the downside.

### 5.5 Correlation Structure

The diversification advantage is quantified by the correlation structure:

| Asset Class Pair | Typical Correlation |
|---|---|
| Equities ↔ Fixed Income | -0.3 to +0.3 (regime-dependent) |
| Equities ↔ Commodities | +0.1 to +0.3 |
| Equities ↔ FX (USD index) | -0.2 to +0.2 |
| Fixed Income ↔ FX | -0.1 to +0.2 |
| Fixed Income ↔ Commodities | -0.1 to +0.2 |
| Commodities ↔ FX | +0.0 to +0.3 |

Within-asset-class correlations are higher (0.3–0.8 for equities, 0.1–0.5 for commodities). The cross-asset-class correlations spike during crises, but importantly they spike in ways that are beneficial for trend followers — equities fall while bonds rise and the USD rallies.

---

## 6. Position Sizing and Volatility Targeting

### 6.1 The Fundamental Principle

Every instrument's position size is set such that its expected daily P&L volatility contributes equally to the total portfolio's risk. This is **volatility targeting** — the single most important technical element of systematic trend following.

The motivation:
- Without volatility targeting, positions in high-volatility instruments would dominate portfolio risk. A full single contract in natural gas has wildly different risk from a full contract in a 10-year Treasury note.
- Volatility targeting ensures that every instrument has an equal shot at contributing to returns regardless of its nominal volatility.
- It creates a natural mechanical response: when volatility spikes (as in a crisis), positions are automatically reduced. When volatility is low, positions are expanded. This is a form of built-in risk management.

### 6.2 Volatility Estimation

The ex-ante daily volatility estimate for instrument i at time t:

```
Step 1: Daily log return
  ret_i(t) = ln(P_i(t) / P_i(t-1))

Step 2: EWMA variance (half-life τ_vol trading days)
  λ_vol = exp(-ln(2) / τ_vol)
  σ²_i(t) = λ_vol · σ²_i(t-1) + (1 - λ_vol) · ret_i(t)²

Step 3: Daily volatility
  σ_daily_i(t) = sqrt(σ²_i(t))

Step 4: Annualized volatility
  σ_annual_i(t) = σ_daily_i(t) × sqrt(252)
```

**Recommended half-life**: τ_vol = 30 trading days (approximately 6 weeks). This is a reasonable balance between responsiveness to regime changes and stability of position sizes.

**Alternative**: Some managers use a hybrid estimator — the average of a 20-day EWMA (fast, reactive) and a 252-day EWMA (slow, stable). This prevents both excessive position cuts after short-lived vol spikes and failure to reduce positions in sustained high-vol regimes.

### 6.3 Instrument Dollar Volatility

The daily dollar volatility (DV01-like quantity) of holding one unit (one contract or one dollar of notional) in instrument i:

For futures (where one contract controls `Multiplier_i` units of the underlying):

```
DollarVol_i(t) = σ_daily_i(t) × Multiplier_i × FuturesPrice_i(t)
```

For ETFs or equity-like instruments:

```
DollarVol_i(t) = σ_daily_i(t) × Price_i(t)
```

This is the expected dollar loss on a 1-sigma adverse move, per unit held.

### 6.4 Target Volatility per Instrument

Given:
- Portfolio NAV: `Portfolio_Value`
- Target annualized portfolio volatility: `σ_target` (e.g., 15% or 20%)
- Number of instruments: N
- Assuming equal vol contribution per instrument (independent risk, though we'll adjust for correlation in Section 7):

```
Target daily vol per instrument = (σ_target / sqrt(252)) × Portfolio_Value / N
                                = σ_target_daily × Portfolio_Value / N
```

**Note**: This naive calculation ignores correlations. With N = 50 instruments, if all were perfectly uncorrelated, individual instrument target vol = 1/50 of total. If correlations are positive, you'd use the actual portfolio variance formula (see Section 7).

### 6.5 Position Size Formula

Combining the signal and the volatility target:

```
RawPosition_i(t) = Signal_i(t) × TargetDollarVol / DollarVol_i(t)
```

where:
- `Signal_i(t)` is the composite signal (Section 4), typically ranging from -1 to +1 (clipped)
- `TargetDollarVol` is the target daily dollar volatility per instrument
- `DollarVol_i(t)` is the per-unit dollar volatility of instrument i

The result `RawPosition_i(t)` is the dollar notional to hold long (positive) or short (negative).

For futures, convert to number of contracts:

```
Contracts_i(t) = round(RawPosition_i(t) / (Multiplier_i × FuturesPrice_i(t)))
```

The rounding step introduces discretization error, which is why small portfolios (under $1 million) struggle with accurate position sizing in full-size futures contracts. E-mini and micro contracts mitigate this.

### 6.6 Full Formula — End to End

Pulling together all components:

```
Signal_i(t) = CompositeSignal_i(t)               [from Section 4, range ~[-1, +1]]

σ_daily_i(t) = EWMA_vol(ret_i, τ_vol=30)          [daily realized vol]
σ_annual_i(t) = σ_daily_i(t) × sqrt(252)

DollarVol_per_unit_i(t) = σ_daily_i(t) × Multiplier_i × Price_i(t)

InstrumentTargetVol_daily = (σ_portfolio_target / sqrt(252)) × NAV × InstrVolWeight_i

RawPosition_i(t) = Signal_i(t) × InstrumentTargetVol_daily / DollarVol_per_unit_i(t)

Contracts_i(t) = round(RawPosition_i(t) / (Multiplier_i × Price_i(t)))
```

where `InstrVolWeight_i` is the fraction of total portfolio volatility budget allocated to instrument i (equal-weight naive case: 1/N; correlation-adjusted: from Section 7).

### 6.7 Portfolio-Level Volatility Target

The aggregate portfolio volatility target is typically set at **10–20% annualized** for institutional managed futures programs. This is calibrated to deliver:
- Sufficient return to justify management and performance fees
- Drawdowns of roughly 1–2× the annual vol target (e.g., 10% vol → 10–20% max drawdown historically)
- Leverage levels of 3–8× notional for a fully diversified multi-asset futures portfolio

A commonly used target for a standalone trend-following program is **15% annualized vol**.

For an overlay/satellite allocation (e.g., 10–20% of a traditional 60/40 portfolio), the vol target might be scaled down to match the desired contribution to overall portfolio volatility.

### 6.8 Kelly Criterion Context

The Kelly Criterion provides the theoretically optimal fraction of wealth to risk per bet:

```
f* = (Win Rate × Win Size - Loss Rate × Loss Size) / Win Size
   = (p × b - q) / b
```

where p = win rate, b = win/loss ratio, q = 1 - p.

For trend following, typical parameters are: p = 0.42 (42% winning trades), b = 2.5 (winners are 2.5× the size of losers, reflecting the right-skewed payoff distribution). This gives:

```
f* = (0.42 × 2.5 - 0.58) / 2.5 = (1.05 - 0.58) / 2.5 = 0.188 ≈ 19%
```

Full Kelly at 19% of NAV per "bet" would be extremely aggressive for a multi-instrument portfolio. Standard practice is to use **half-Kelly or quarter-Kelly** at the portfolio level, which aligns with the 10–20% vol target that practical implementations use. The drawdown under full Kelly is typically 2× that under half-Kelly, making full Kelly psychologically and operationally unacceptable for most investment mandates.

---

## 7. Portfolio Construction

### 7.1 Risk Budgeting Framework

The naive equal-vol-weight approach (give each instrument the same target volatility contribution) is the starting point but ignores inter-instrument correlations. In a correlated portfolio, instruments that move together compound risk rather than diversify it.

**Equal Contribution Risk (ECR) / Risk Parity** per instrument:

The marginal contribution to portfolio variance from instrument i is:

```
MRC_i = (Cov(r_i, r_portfolio)) / σ_portfolio
       = (Σ_j  w_j × ρ_{ij} × σ_i × σ_j) / σ_portfolio
```

True risk parity sets:

```
w_i × MRC_i = c    for all i    (each instrument contributes equally to portfolio variance)
```

Solving for the risk-parity weights `w_i` requires an iterative optimization or a closed-form approximation. In the equal-vol-contribution limit (all correlations equal), the solution reduces to w_i ∝ 1/σ_i.

### 7.2 Asset Class Level Risk Budgeting

Before instrument-level sizing, a top-level risk budget is assigned to each asset class. A common equal-weight allocation across four asset classes:

| Asset Class | Risk Budget |
|---|---|
| Equities (index futures) | 25% |
| Fixed Income (govt bonds) | 25% |
| FX (major pairs) | 25% |
| Commodities | 25% |

Within each asset class, the risk budget is further allocated among instruments based on equal vol contribution (adjusted for within-class correlations).

**Rationale for equal-class allocation**: Over long horizons (decades), each asset class has contributed roughly equal Sharpe ratios to trend following. There is no strong theoretical basis for overweighting any single class ex ante. The equal allocation is also the most robust to estimation error in expected returns.

**Alternative**: Some managers overweight fixed income and FX (2:1 relative to equities and commodities) because these asset classes have shown slightly higher trend Sharpe ratios historically and have lower correlations to equity market crises.

### 7.3 Correlation-Adjusted Instrument Weights

Given the within-asset-class correlation matrix Σ_class, the optimal equal-risk-contribution weights within the class solve:

```
w_i × (Σ_class × w)_i = c_class    for all i within the class
```

For practical implementation with small numbers of instruments (5–10 per class), the correlation-adjusted weights can be approximated as:

```
w_i ≈ (1/σ_i) / Σ_j (1/σ_j)    [equal vol weight, ignoring correlation]
```

then adjusted by a "diversification multiplier" that accounts for the average pairwise correlation:

```
DiversificationMultiplier = 1 / sqrt(1 + (N-1) × ρ_avg)
```

where ρ_avg is the average pairwise correlation within the class.

The portfolio volatility at the asset-class level is:

```
σ_class = sqrt(w' × Σ_class × w) × DiversificationMultiplier
```

### 7.4 Correlation Estimation

Correlation estimates for portfolio construction must be:
- Based on a reasonably long history (3–5 years minimum, 10 years preferred) to capture the regime-dependence of correlations
- Updated regularly (monthly or quarterly) to adapt to structural changes
- Shrunk toward a prior (e.g., the identity matrix or an equal-correlation prior) to reduce estimation error, particularly with small samples

The Ledoit-Wolf shrinkage estimator is a standard approach:

```
Σ_shrunk = (1 - α) × Σ_sample + α × Σ_prior
```

where α is the shrinkage coefficient (often 0.2–0.5 for typical time-series lengths).

**Important caveat**: Correlations tend to increase dramatically during crises ("contagion"), reducing the diversification benefit precisely when it is most needed. This is partially offset by the fact that in crises, trends become very strong — the signal quality improves even as correlations rise. The net result is that the portfolio still performs well in crisis, but with slightly less diversification than the calm-market correlation structure would predict.

### 7.5 Leverage and Portfolio Scaling

Trend following portfolios run on leveraged notional exposure because:
- Short positions require no capital outlay (futures are margin-based)
- The signal may call for 100% gross notional in a single direction across many instruments
- Typical gross notional to NAV ratios: 3–10× depending on the number of instruments and vol target

The portfolio volatility constraint (Section 6.7) is the primary leverage limiter. The total gross exposure is a byproduct of the vol target, not a primary input.

---

## 8. Risk Management

### 8.1 Portfolio-Level Volatility Cap

The primary risk control is the portfolio volatility target itself. When realized portfolio volatility exceeds the target, all position sizes are scaled down proportionally:

```
Scaling_Factor = min(1.0, σ_target / σ_realized_portfolio)

ScaledPosition_i(t) = RawPosition_i(t) × Scaling_Factor
```

This is a dynamic, automatic deleveraging mechanism. When markets become turbulent (vol spikes to 2× target), positions are cut by half. When markets calm down, positions are restored.

### 8.2 Instrument-Level Stops

Individual instrument positions are subject to volatility-based stops:

```
Stop_i(t) = EntryPrice_i ± K × σ_daily_i(t)
```

where K is the stop distance multiplier (typically K = 2 for a medium-term system, K = 1 for a fast system).

The Turtle system used a 2N stop, where N was the 20-day Average True Range (equivalent to K = 2 using daily volatility). Positions that move K standard deviations against the trend signal are exited regardless of the signal state.

**Critical design note**: Stop-loss exits for trend following should be the primary exit mechanism, not explicit stop orders sitting in the market (which are visible to market makers). Instead, stops are implemented as end-of-day rules: if the closing price is K × σ_daily against the entry, exit at the open the following day.

### 8.3 Maximum Position Limits

To prevent concentration risk from an extreme signal in a single instrument:

```
MaxPositionSize_i = MaxPctNAV × Portfolio_Value / Price_i
```

Typical maximum: no single instrument position exceeds 5–8% of NAV in notional terms, or 3–4% of NAV in risk contribution.

### 8.4 Sector Concentration Limits

Within each asset class, no more than a specified fraction of the class risk budget can be concentrated in highly correlated sub-sectors:

```
EnergyRiskBudget ≤ 60% of total commodities budget
```

This prevents the entire commodity allocation from being dominated by crude oil and gas (which are highly correlated to each other) while agricultural commodities are ignored.

### 8.5 Portfolio Drawdown Trigger

A portfolio-level drawdown trigger acts as an emergency brake:

- **Level 1 (10% drawdown from peak)**: Reduce overall position sizes by 25%. Review all open positions.
- **Level 2 (15% drawdown from peak)**: Reduce overall position sizes by 50%. Alert risk committee.
- **Level 3 (20% drawdown from peak)**: Reduce to 25% of target positions. Initiate formal review of strategy parameters.

These triggers are calibrated to the 15% annual vol target — a 15–20% drawdown corresponds to roughly 1–1.5 annual standard deviations of loss, which is within the historical loss distribution for trend following but warrants investigation for regime change.

**Warning**: Automated drawdown triggers can create a "stop and reverse" trap — the strategy cuts positions at the worst time (near the bottom of a drawdown), then the trend reasserts and the strategy misses the recovery while sizing is reduced. Drawdown triggers should have a reinstatement protocol (e.g., restore positions gradually over 20 trading days once drawdown has recovered by 5 percentage points).

### 8.6 Correlation Monitoring

Monthly correlation reviews should check:
- Whether realized correlations remain consistent with historical norms
- Whether any instrument pairs have experienced correlation regime shifts (e.g., post-2022, bond-equity correlation turned positive)
- Whether the portfolio's realized Sharpe and vol are consistent with model expectations

### 8.7 Fat Tail / Stress Testing

The distribution of trend following returns is not normal. It exhibits:
- **Positive skewness**: Occasional very large gains
- **Mild excess kurtosis**: Fat tails relative to normal (both large gains and occasional outsized losses)
- **Near-zero autocorrelation** of monthly returns

Monthly VaR at 99% confidence understates the true tail risk. Preferred risk measures:
- **Expected Shortfall (CVaR) at 95%**: Expected loss in the worst 5% of scenarios
- **Historical stress test**: P&L in 2009, 2012, 2014, and 2022 for the specific instrument universe
- **Monte Carlo simulation**: Generate 10,000 simulated return paths using historical return distributions (block bootstrap preserving autocorrelation structure)

---

## 9. Execution Considerations

### 9.1 Rebalancing Frequency

Trend following signals evolve slowly (days to weeks). Daily rebalancing is standard for the signal calculation, but actual position rebalancing may occur:
- **Daily**: For fast signals (1-month lookback) where position changes are frequent
- **Weekly**: For medium signals (3–6 month lookback)
- **Monthly**: For slow signals (12-month lookback) where weekly changes are minimal

A hybrid approach rebalances daily for signals and for volatility-driven resizing, but only executes trades when position size changes by more than a threshold (e.g., 10% of current position) to reduce transaction costs.

### 9.2 Futures Roll Management

Futures contracts expire. Rolling from the expiring front-month contract to the next-month contract is a critical execution function:

- **Roll schedule**: Determined by open interest migration. Typically, roll begins when the next-month contract's open interest exceeds the front-month's.
- **Roll window**: 3–5 trading days straddling the typical roll date for each contract. Rolling over multiple days reduces market impact.
- **Roll timing**: Execute rolls at the mid-market when bid-ask spreads are tightest (typically the liquid session: 8am–4pm local market time).
- **Roll yield**: The cost or benefit of rolling — the difference between the front and back contract price, annualized. For commodities in contango (back > front), rolling costs money. For markets in backwardation (front > back), rolling earns a positive roll yield.

Roll yield can be a significant component of total return. For trend following specifically, Koijen et al. (2018) document that nearly 50% of cumulative trend following performance in commodity futures historically was attributable to roll yield. In environments of persistent contango (e.g., oil post-2014), roll costs can substantially erode the momentum signal's gross return.

**Roll cost modeling**:

```
Annual_Roll_Cost_i = (BackMonthPrice_i - FrontMonthPrice_i) / FrontMonthPrice_i × (12 / MonthsToExpiry_i)
```

This should be estimated for each instrument and included in the net expected return calculation.

### 9.3 Transaction Cost Budget

Transaction costs include:
- **Bid-ask spread**: For liquid equity index futures (ES, NQ), spreads are typically $12.50–$25 per contract (one tick). For commodities, spreads vary from $10 (gold) to $50+ (agricultural futures).
- **Exchange commissions**: $0.50–$3.00 per contract for major futures.
- **Clearing fees**: $0.10–$0.50 per contract.
- **Market impact**: For large orders, price impact must be estimated. Rule of thumb: impact ≈ (Order Size / ADV) × σ_daily × √(Order Size / ADV).

**Annual transaction cost budget** (as % of NAV): Typically 0.5–2.0% per year for a diversified trend following program. The faster the signal, the higher the costs. This is a key parameter that determines the minimum lookback period for a viable strategy — very fast signals (daily lookback) generate too much turnover to be net profitable after costs.

### 9.4 Slippage and Execution Timing

For daily rebalancing, the standard execution approach is:
- Calculate positions at the close using closing prices
- Execute on the open of the following trading day using market-on-open orders
- Or: execute in the last 15 minutes of the trading session for liquid futures

For large programs managing billions of AUM, execution must be spread over multiple sessions and potentially multiple exchanges (e.g., executing S&P 500 futures in CME Globex overnight session to avoid U.S. market-hours crowding).

### 9.5 Avoiding Signal Crowding at Execution

When a large, clear trend is underway (e.g., crude oil in 2021–2022 uptrend), many trend followers will be executing similar orders. This creates crowding at the execution level — everyone tries to buy/sell the same futures at the same time after the same signal fires. Mitigants:
- Stagger execution times relative to natural roll and rebalancing dates
- Use TWAP or VWAP execution algorithms for large orders
- Allow signals to fire with slight random timing jitter (within a 1-day window) for size above a threshold

---

## 10. Regime Sensitivity

### 10.1 Regime Framework

Trend following performance is highly regime-dependent. The two critical dimensions:

1. **Trend persistence**: Does the market make sustained directional moves (favorable) or oscillate without direction (unfavorable)?
2. **Volatility level**: High-volatility regimes generate larger trends but also larger whipsaw losses; low-volatility regimes have quieter trends with smaller signals.

| Regime | Trend | Vol | Trend Following P&L | Examples |
|---|---|---|---|---|
| Crisis trending | Strong | High | Very high | 2008, 1973, 2002, 2022 (bonds) |
| Bull trending | Moderate | Low–Medium | Good | 2014 bonds, 2017 equities, 2023 equities |
| Choppy high-vol | Weak | High | Very bad | 2011, Q4 2018 |
| Choppy low-vol | Weak | Low | Mildly bad | 2004, 2012–2013 |

### 10.2 Favorable Conditions

The strategy thrives when:
- Central banks are in sustained tightening or easing cycles (multi-year bond trends)
- Commodity supercycles are underway (sustained energy or metals trends)
- Major macro regime shifts occur (dollar bear/bull cycles, emerging market booms)
- Equity market crises create strong downtrends that persist for months

The 2008 financial crisis is the canonical example. From June 2008 to March 2009, the SG CTA Index was up approximately 18%, while global equities lost 45%. The trends were:
- Short equity index futures (S&P 500 lost 56% peak to trough)
- Long US Treasury futures (flight to safety — 30-year bond rose 24%)
- Short energy (crude oil fell from $147 to $35)
- Long USD (dollar rally as global deleveraging)

All four asset classes trended strongly in coordinated directions — the perfect environment.

Similarly, 2022 was an excellent year for trend followers: the Fed's aggressive tightening campaign created strong trends in:
- Short bond futures (rates rose sharply — TLT fell 33%)
- Long USD (dollar rallied 15%)
- Short equity futures (equities fell 20–25%)
- Long energy (crude oil rose)

### 10.3 Unfavorable Conditions

The strategy suffers in:
- Range-bound markets with repeated reversals
- Central bank intervention that suppresses price discovery (QE eras)
- Short-term momentum crashes

**The "CTA Winter" (2010–2014)**: The period following the 2008 crisis was perhaps the worst extended period for trend following in the modern era. From late 2010 to early 2014, the SG Trend Index returned approximately -1.8% cumulatively. The causes:
- Equity markets oscillated with dramatic reversals driven by European debt crisis headlines
- Bond markets traded in a narrow range as central banks pinned rates near zero
- Commodities were volatile but without sustained directionality
- FX markets were subdued with central banks intervening aggressively to prevent large currency moves

**2009**: The year immediately after the strategy's best performance. Equity markets bottomed in March 2009 and reversed sharply. Trend followers, who had built large short equity positions, were caught short as markets rallied 60%+ from the lows. Combined with reversals in energy and commodity shorts, 2009 was a painful year.

**2014 (partial)**: Crude oil fell from $100 to $50 over six months — a trend. But many other markets were choppy. The volatility of volatility was high, meaning the strategy experienced whipsaw conditions in FX and equities while only capturing the energy trend partially (signals were slow to build for such a sudden drop).

### 10.4 Regime Detection for Position Scaling

Regime-awareness can be incorporated as an overlay on the pure trend signal. Common approaches:

**ADX filter**: The Average Directional Index measures trend strength (not direction). ADX > 25 indicates a trend; ADX < 20 indicates a ranging market. Applying an ADX filter reduces position sizes in ranging markets:

```
RegimeMultiplier(t) = min(1.0, max(0.0, (ADX(t) - 20) / 10))
AdjustedPosition_i(t) = RawPosition_i(t) × RegimeMultiplier_i(t)
```

**Hurst exponent**: The Hurst exponent H measures the persistence of a time series. H > 0.5 indicates trending behavior; H = 0.5 is random walk; H < 0.5 indicates mean reversion. Computing H over a rolling window and using it as a signal confidence weight is more complex but more statistically rigorous.

**Warning**: Regime filters introduce significant look-ahead bias risk in backtesting and overfitting risk in optimization. The base strategy (no regime filter) is more robust and easier to validate.

---

## 11. Key Risks and Failure Modes

### 11.1 The Momentum Crash

The single largest risk is the momentum crash — a sharp reversal of all trends simultaneously. The most dangerous scenario:
1. Trend followers build large short positions in an asset that has been falling
2. The asset bottoms and reverses sharply
3. All trend followers are simultaneously on the wrong side and must cover quickly
4. The covering generates further buying pressure, accelerating the reversal

March 2009 was the clearest modern example. March 2020 (COVID crash followed by immediate recovery) produced another momentum crash. These events are the primary source of negative skewness in realized returns.

**Mitigation**: Fast signals reduce exposure to this risk because they reverse quicker. Drawdown triggers (Section 8.5) force position reduction before the full loss materializes. Diversification across uncorrelated assets ensures not all positions reverse simultaneously.

### 11.2 Structural Breakdown Risk

Trend following's academic edge is documented across 136 years of data. But structural changes could diminish or eliminate the premium:

- **High-frequency trading and market efficiency**: As markets become more efficient at incorporating information, the gradual price adjustment process that creates trends may speed up, reducing persistence and making signals too noisy.
- **Overcrowding and capacity constraints**: If too much capital chases the same trend signals, crowding depletes the premium. Baltas (2019) shows that periods of high AUM in trend-following strategies predict lower subsequent returns. The managed futures industry manages approximately $300–400 billion (as of recent estimates), which some researchers believe is approaching capacity for the liquid futures markets.
- **Central bank intervention**: Post-2008, central bank asset purchase programs (QE, yield curve control, FX intervention) explicitly suppress the price discovery that trend following relies on. While the strategy adapted (bonds trends still occurred), the magnitude of intervention creates a constant headwind.
- **Structural correlation shifts**: The positive bond-equity correlation post-2022 reduces the diversification benefit that was a key pillar of the strategy's historical Sharpe ratio.

### 11.3 Execution-Related Failure Modes

- **Roll cost drag**: In persistent contango commodity markets, annual roll costs of 5–10% can wipe out trend profits. Careful instrument selection (using optimized roll strategies or longer-dated contracts) partially mitigates this.
- **Crowded rolls**: When many trend followers roll contracts on the same day, market impact can be significant. Staggered roll windows help.
- **Gap risk**: Overnight gaps (particularly in individual commodity futures after major news events) can trigger execution at prices far from the intended stop level.
- **Currency risk**: A global futures portfolio generates P&L in multiple currencies. FX hedging of portfolio currency exposure is essential but adds its own basis risk.

### 11.4 Model Risk

- **Parameter overfitting**: Optimizing signal parameters (lookback windows, entry/exit thresholds) on historical data creates overfitted models that fail out-of-sample. The robustness test: parameters should work across all decades, all asset classes, without cherry-picking.
- **Look-ahead bias**: Any use of future data in backtesting (including survivorship bias in the instrument universe) will produce overly optimistic backtest results.
- **Market impact underestimation**: Academic papers use daily closing prices; real execution faces bid-ask spreads and market impact. For large programs, transaction costs can halve the theoretical Sharpe ratio.

### 11.5 Behavioral and Operational Risks

- **Style drift**: Pressure to perform in choppy markets may push managers toward discretionary overrides of signals. This is the death of systematic trend following — if signals are overridden, the long-run positive expectation is compromised.
- **Drawdown abandonment**: Many allocators exit CTA programs after 15–20% drawdowns, precisely when mean-reversion probability to the strategy's historical performance is highest. The CTA winter (2010–2014) saw significant AUM outflows; investors who remained were rewarded with strong 2014 and 2022 performance.
- **Leverage constraints**: In crisis environments, margin requirements rise and broker credit lines may be reduced. The worst-case scenario is forced liquidation at crisis trough prices — the exact opposite of the strategy's intended behavior. Maintaining substantial cash buffers (30–50% of NAV) as margin is critical.

### 11.6 The "Crowding" Problem in Detail

Crowding in trend following is a self-referential risk. The mechanism:

1. Trend following is published in academic papers (2012 and after), attracting more capital to the strategy.
2. More capital chasing the same signals means that the early part of a trend is captured by everyone — reducing expected return on entry.
3. At trend reversals, all trend followers simultaneously exit or reverse positions — amplifying the reversal and increasing losses for the entire industry.
4. Over time, this crowding reduces the Sharpe ratio of the strategy.

Evidence: Baltas (2019) shows that divergence premia (trend, momentum) become crowded and underperform following periods of high AUM, while convergence premia (value, carry) show the opposite pattern. The managed futures industry's 15% annual AUM growth rate since 2000 raises serious questions about future capacity.

**Counterargument**: The trend premium may be self-sustaining because it is linked to behavioral biases (under-reaction, herding) that are inherent to human nature and therefore persist despite arbitrage capital. Furthermore, many of the largest trend following programs trade illiquid or less-followed futures markets (smaller commodity contracts, EM currencies) where crowding is less severe.

---

## 12. Parameters and Tunable Knobs

### 12.1 Signal Parameters

| Parameter | Description | Default | Range | Notes |
|---|---|---|---|---|
| `lookback_fast` | Fast EWMA half-life (days) | 8 | 4–16 | Short: more responsive, more whipsaw |
| `lookback_medium` | Medium EWMA half-life (days) | 32 | 16–64 | Core signal for most markets |
| `lookback_slow` | Slow EWMA half-life (days) | 126 | 64–252 | Captures macro trends |
| `fast_span_ratio` | Ratio of slow to fast EWMA span | 3.0 | 2.0–4.0 | Crossover gap; controls sensitivity |
| `tsmom_lookback` | TSMOM past-return window (months) | 12 | 1–12 | Moskowitz et al. standard is 12 |
| `signal_cap` | Maximum absolute signal value | 2.0 | 1.5–3.0 | Prevents position concentration |
| `signal_function` | How raw signal maps to position | tanh | tanh, clip, linear | tanh gives smooth scaling |

### 12.2 Blending Weights

| Parameter | Description | Default | Range |
|---|---|---|---|
| `fast_weight` | Weight of fast signal in blend | 0.33 | 0.10–0.50 |
| `medium_weight` | Weight of medium signal in blend | 0.34 | 0.25–0.50 |
| `slow_weight` | Weight of slow signal in blend | 0.33 | 0.25–0.60 |

Weights must sum to 1.0.

### 12.3 Volatility Estimation Parameters

| Parameter | Description | Default | Range | Notes |
|---|---|---|---|---|
| `vol_halflife_days` | EWMA half-life for vol estimation | 30 | 20–63 | Shorter = more reactive to vol spikes |
| `vol_annualization` | Days to annualize vol | 252 | 252 | Standard trading-day convention |
| `vol_floor` | Minimum annualized vol (prevents infinite sizing) | 0.05 | 0.02–0.10 | 5% minimum annual vol per instrument |
| `vol_cap` | Maximum annualized vol (prevents zero sizing) | 1.00 | 0.50–2.00 | Exclude crisis vol spikes from sizing |

### 12.4 Position Sizing Parameters

| Parameter | Description | Default | Range |
|---|---|---|---|
| `portfolio_vol_target` | Target annualized portfolio volatility | 0.15 | 0.08–0.25 |
| `max_position_pct_nav` | Maximum single instrument notional / NAV | 0.10 | 0.05–0.15 |
| `max_risk_pct_nav` | Maximum single instrument daily vol / NAV | 0.005 | 0.003–0.010 |
| `leverage_cap` | Maximum gross notional / NAV | 8.0 | 4.0–12.0 |

### 12.5 Universe Parameters

| Parameter | Description | Default | Range |
|---|---|---|---|
| `n_instruments` | Total number of instruments | 40 | 20–200 |
| `eq_class_weight` | Equity class risk budget | 0.25 | 0.15–0.40 |
| `fi_class_weight` | Fixed income class risk budget | 0.25 | 0.20–0.40 |
| `fx_class_weight` | FX class risk budget | 0.25 | 0.15–0.35 |
| `cm_class_weight` | Commodity class risk budget | 0.25 | 0.15–0.35 |

### 12.6 Risk Management Parameters

| Parameter | Description | Default | Range |
|---|---|---|---|
| `stop_distance_n` | Instrument stop in units of daily vol | 2.0 | 1.5–3.0 |
| `dd_trigger_l1` | Level 1 drawdown trigger | 0.10 | 0.08–0.15 |
| `dd_trigger_l2` | Level 2 drawdown trigger | 0.15 | 0.12–0.20 |
| `dd_trigger_l3` | Level 3 drawdown trigger | 0.20 | 0.18–0.30 |
| `dd_reduction_l1` | Position scale at L1 trigger | 0.75 | 0.60–0.90 |
| `dd_reduction_l2` | Position scale at L2 trigger | 0.50 | 0.35–0.65 |
| `dd_reduction_l3` | Position scale at L3 trigger | 0.25 | 0.15–0.40 |
| `dd_restore_days` | Days to restore positions post-recovery | 20 | 10–40 |

### 12.7 Execution Parameters

| Parameter | Description | Default | Range |
|---|---|---|---|
| `rebalance_threshold` | Minimum position change to trigger trade (fraction) | 0.10 | 0.05–0.20 |
| `roll_days_before_expiry` | Days before expiry to begin rolling | 10 | 5–15 |
| `roll_window_days` | Number of days to spread roll execution | 5 | 3–7 |
| `execution_time` | When to execute: open, close, TWAP | open | open / close / TWAP |
| `transaction_cost_bps` | Assumed round-trip cost per trade (bps) | 5 | 2–15 |

### 12.8 Correlation Parameters

| Parameter | Description | Default | Range |
|---|---|---|---|
| `corr_lookback_days` | Historical days for correlation estimation | 756 | 252–1260 |
| `corr_shrinkage` | Ledoit-Wolf shrinkage coefficient | 0.30 | 0.10–0.60 |
| `corr_update_freq` | How often to update correlation matrix | monthly | weekly / monthly / quarterly |

### 12.9 Expected Performance Profile

Under the default parameters, the strategy's expected characteristics (based on historical evidence from the academic literature):

| Metric | Expected Value | Range |
|---|---|---|
| Annualized Return (gross) | 8–12% | 5–18% |
| Annualized Volatility | 15% | 12–18% |
| Sharpe Ratio (net) | 0.5–0.8 | 0.3–1.2 |
| Max Drawdown | 20–35% | 15–50% |
| Hit Rate (% winning trades) | 40–45% | 35–50% |
| Win/Loss Ratio | 2.0–3.0 | 1.5–4.0 |
| Skewness | +0.3 to +0.8 | 0 to +1.5 |
| Beta to S&P 500 | -0.1 to +0.1 | -0.2 to +0.2 |
| Correlation to 60/40 portfolio | 0.0 to +0.2 | -0.2 to +0.3 |

Note: Net Sharpe of 0.5–0.8 is the realistic after-costs expectation for an ETF-based retail implementation. Institutional managed futures programs, with access to actual futures, lower costs, and deeper diversification across 100+ markets, historically achieved net Sharpe ratios of 0.8–1.2 before the 2010s crowding effect.

---

## Appendix: Key Mathematical Summary

### Signal Construction at a Glance

```
# Step 1: Volatility estimate (EWMA, half-life = 30 days)
λ_vol = exp(-ln(2) / 30)  ≈  0.977
σ²_i(t) = λ_vol × σ²_i(t-1) + (1 - λ_vol) × [ln(P_i(t)/P_i(t-1))]²
σ_daily_i(t) = sqrt(σ²_i(t))

# Step 2: EWMA prices for crossover (3 speeds)
Fast EWMA:   E_fast_i(t)   = EWMA(P_i, half-life=8)
Medium EWMA: E_med_i(t)    = EWMA(P_i, half-life=32)
Slow EWMA:   E_slow_i(t)   = EWMA(P_i, half-life=126)

# Step 3: Raw MACD signals (crossover of fast/slow pairs within each tier)
S_fast_i(t)   = [EWMA(P_i,8)  - EWMA(P_i,24)]  / (σ_daily_i × Price_i)
S_medium_i(t) = [EWMA(P_i,32) - EWMA(P_i,96)]  / (σ_daily_i × Price_i)
S_slow_i(t)   = [EWMA(P_i,126)- EWMA(P_i,252)] / (σ_daily_i × Price_i)

# Step 4: Normalize and cap
Signal_s_i(t) = tanh(S_s_i(t) × 0.5)    for each speed s
                [maps ±2 sigma to ±tanh(1) ≈ ±0.76]

# Step 5: Equal-weight blend
CompositeSignal_i(t) = (1/3) × [Signal_fast_i(t) + Signal_medium_i(t) + Signal_slow_i(t)]

# Step 6: Position sizing
TargetDailyDollarVol = (σ_target / sqrt(252)) × NAV / N_instruments
DollarVolPerUnit_i(t) = σ_daily_i(t) × Multiplier_i × Price_i(t)
RawPosition_i(t) = CompositeSignal_i(t) × TargetDailyDollarVol / DollarVolPerUnit_i(t)

# Step 7: Apply limits and round
ScaledPosition_i(t) = clip(RawPosition_i(t), -MaxPosition_i, +MaxPosition_i)
Contracts_i(t) = round(ScaledPosition_i(t) / (Multiplier_i × Price_i(t)))
```

---

*This specification is a research and design document. It does not constitute financial advice or a guarantee of future performance. All historical performance data referenced herein comes from academic literature and public index data and does not represent the performance of any actual investment program.*
