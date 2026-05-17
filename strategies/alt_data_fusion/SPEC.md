# Alternative Data Fusion Strategy — Design Specification

**Status**: Draft  
**Domain**: Equity Long/Short, Event-Driven  
**Holding Period**: 1–30 days (signal-dependent)  
**Universe**: US-listed equities, Russell 3000 + S&P 500 focus  
**Last Updated**: 2026-05-17

---

## Table of Contents

1. [Strategy Overview & Thesis](#1-strategy-overview--thesis)
2. [Alternative Data Taxonomy](#2-alternative-data-taxonomy)
3. [Signal Source Deep-Dives](#3-signal-source-deep-dives)
4. [Feature Engineering Pipeline](#4-feature-engineering-pipeline)
5. [Signal Quality Evaluation](#5-signal-quality-evaluation)
6. [Signal Combination Architecture](#6-signal-combination-architecture)
7. [Universe Construction](#7-universe-construction)
8. [Portfolio Construction](#8-portfolio-construction)
9. [Risk Management](#9-risk-management)
10. [Execution Considerations](#10-execution-considerations)
11. [Regime Sensitivity](#11-regime-sensitivity)
12. [Key Risks & Failure Modes](#12-key-risks--failure-modes)
13. [Parameters & Tunable Knobs](#13-parameters--tunable-knobs)

---

## 1. Strategy Overview & Thesis

### 1.1 Core Thesis

Markets are fundamentally information-processing machines. The speed and breadth at which a market incorporates new information determines where inefficiencies persist. Traditional fundamental and technical signals are now deeply crowded — every sophisticated participant uses the same 10-K data, the same price-volume history, and the same factor loadings. The edge from those sources compresses continuously.

Alternative data — data derived from sources outside the standard financial reporting ecosystem — represents the next battleground for information advantage. The thesis of this strategy rests on three compounding observations:

1. **Attention precedes price.** Retail and institutional attention is measurable before it manifests in order flow. Google search spikes, Reddit mention surges, and app download acceleration all precede the capital reallocation that moves prices. The signal is in the attention velocity, not the price level.

2. **Behavior is more honest than reports.** Companies manage their reported financials, but they cannot manage their credit card transaction volumes, their employee headcount growth, their app store ratings, or the number of cars in their parking lots. Behavioral data is structurally harder to falsify.

3. **Information velocity has a half-life.** The edge from a given alternative data signal decays as more participants discover and act on it. A good alt data strategy must continuously evaluate signal freshness, source exclusivity, and crowding dynamics, rotating toward underexploited sources as crowding reduces the margin on established ones.

### 1.2 Market Size & Ecosystem Context

The global alternative data market reached approximately $11.65–14.16 billion in 2024–2025 and is growing at a compound annual rate of 50–63% depending on the measurement methodology. Hedge funds represent over 71% of end-user spending, with adoption among institutional investors approaching 90% as of 2025. Two-thirds of institutional users spend over $1 million annually on alt data budgets.

This market growth itself is a signal about crowding: as more capital chases the same datasets, the marginal alpha per dollar of data spend declines. The practical implication is that differentiation now comes from novel data combination, proprietary normalization methods, and regime-conditional application — not simply from purchasing access to a headline dataset.

### 1.3 Strategic Objectives

- Generate uncorrelated alpha relative to standard equity factors (market, size, value, momentum, quality)
- Maintain average holding periods of 3–21 days, calibrated to the decay rate of each source signal
- Target an annualized gross Information Ratio (IR) above 0.8 before transaction costs
- Keep one-way annual turnover below 600% to manage execution costs
- Maintain strict MNPI compliance firewall between data acquisition and portfolio construction

### 1.4 What This Strategy Is Not

This is not a high-frequency strategy. The signals exploited here operate on daily-to-weekly update frequencies. It is not a pure fundamental strategy — no earnings model or DCF is the primary driver. It is not a pure technical strategy — price and volume are inputs only insofar as they help normalize alt data signals, not as primary predictors. It is a systematic, medium-frequency strategy fusing weak signals from orthogonal data sources.

---

## 2. Alternative Data Taxonomy

Alternative data is best organized by the behavioral mechanism through which it predicts returns, not merely by its collection method. The following taxonomy reflects the signal-generating process:

### 2.1 Category A — Sentiment & Attention Data

Data that measures the degree and direction of human attention toward a security or sector.

| Source Type | Examples | Update Frequency | Primary Mechanism |
|---|---|---|---|
| Social media sentiment | Reddit WSB, StockTwits, Twitter/X | Tick / hourly | Retail attention precedes order flow |
| News sentiment | RavenPack, Bloomberg BEAP, Refinitiv | Tick / minute | Information shock and drift |
| Search trends | Google Trends, Bing Trends | Daily | Retail awareness leading indicator |
| Analyst sentiment | NLP on earnings call transcripts | Quarterly event | Hedged language signals management uncertainty |
| Options sentiment | Put/call ratio, IV skew | Intraday | Informed trader positioning |

### 2.2 Category B — Transactional Data

Data derived from actual economic transactions, representing revealed purchasing behavior.

| Source Type | Examples | Update Frequency | Primary Mechanism |
|---|---|---|---|
| Credit/debit card spend | Earnest Analytics, Bloomberg Second Measure, Yodlee | Weekly/monthly | Real revenue proxy before earnings report |
| Point-of-sale data | YipitData, M Science | Weekly | Consumer spending by merchant |
| E-commerce data | Similarweb checkout flows, ComScore | Weekly | Online revenue proxy |
| Subscription tracking | RecurSpark, Antenna | Monthly | Subscriber cohort dynamics |

### 2.3 Category C — Behavioral & Engagement Data

Data measuring how users interact with companies' digital and physical products.

| Source Type | Examples | Update Frequency | Primary Mechanism |
|---|---|---|---|
| App downloads/DAU | Apptopia, Sensor Tower, data.ai | Daily/weekly | User growth precedes revenue |
| Web traffic | SimilarWeb, Comscore | Weekly | Traffic = top-of-funnel attention |
| App ratings & reviews | App Store, Google Play | Daily | Product quality/user satisfaction |
| Email receipt data | Earnest, Rakuten | Weekly | Purchase confirmation volume |

### 2.4 Category D — Satellite & Geospatial Data

Data derived from remotely sensed imagery or location signals.

| Source Type | Examples | Update Frequency | Primary Mechanism |
|---|---|---|---|
| Parking lot occupancy | RS Metrics, Orbital Insight | Weekly | Foot traffic proxy for retail revenue |
| Shipping & port activity | MarineTraffic, SpaceKnow | Daily | Supply chain throughput |
| Construction progress | SpaceKnow | Bi-weekly | Capex execution tracking |
| Oil storage levels | Orbital Insight, Kayrros | Weekly | Commodity inventory signal |
| Crop yield monitoring | Planet Labs, DigitalGlobe | Seasonal | Agricultural commodity forecasting |

### 2.5 Category E — Workforce & Organizational Data

Data derived from labor market signals and corporate organizational behavior.

| Source Type | Examples | Update Frequency | Primary Mechanism |
|---|---|---|---|
| Job postings | Coresignal, Thinknum, Burning Glass | Daily/weekly | Headcount growth = business expansion |
| LinkedIn headcount | LinkedIn Economic Graph, Aura | Monthly | Workforce size and growth rate |
| Executive departures | Form 8-K, news NLP | Event-driven | Management change risk signal |
| Patent filings | USPTO, PatSnap | Monthly/event | R&D velocity, competitive moat |

### 2.6 Category F — Derived Market Microstructure Data

Data derived from secondary processing of market data that reveals positioning and flow.

| Source Type | Examples | Update Frequency | Primary Mechanism |
|---|---|---|---|
| Short interest | FINRA, S3 Partners, ORTEX | Semi-monthly/daily | Crowd positioning, squeeze risk |
| Options flow (unusual) | Unusual Whales, Market Chameleon | Intraday | Informed money positioning |
| Dark pool prints | Bookmap, InsiderFinance | Intraday | Institutional accumulation/distribution |
| Gamma exposure (GEX) | SpotGamma, OptionStrat | Daily | Market maker hedging constraints |
| Insider transactions | SEC Form 4 (EDGAR) | 2-day lag | Management conviction signal |

---

## 3. Signal Source Deep-Dives

### 3.1 Social Sentiment — Reddit, StockTwits, Twitter/X

#### 3.1.1 Platform Characteristics

**Reddit — r/WallStreetBets and related subreddits:**  
WSB exhibits strong predictive signals for abrupt volatility shifts rather than directional drift. The mechanism is a reflexive one: discussion volume itself attracts more retail participants, creating self-reinforcing order flow. The signal is therefore most predictive for smaller-cap stocks where retail order flow can move the market. For large-cap S&P 500 components, WSB discussion rarely generates durable alpha because institutional liquidity absorbs retail flows without price impact.

The key quantitative construct from WSB data is the **Sentiment Volume Change (SVC)** metric — the product of sentiment score change and comment volume change over a rolling window. Research demonstrates that SVC achieves roughly 70% higher backtested returns in bull market years and 84% higher returns in volatile years, while mitigating losses in declining markets. This suggests the signal has a regime-conditional component (discussed further in Section 11).

**StockTwits:**  
StockTwits provides self-labeled sentiment tags (bullish/bearish) which sidesteps NLP model error. However, the platform skews heavily retail and contains substantial noise. The actionable component is the ratio of bullish-to-bearish labels for a given ticker over time, particularly large discontinuous shifts that signal potential regime changes in retail positioning.

**Twitter/X:**  
Twitter aligns more with gradual market reactions than abrupt shifts, making it complementary to WSB rather than substitutable. The useful construct is **mention velocity** — the rate of change of ticker mentions per hour — normalized against its own trailing distribution. Velocity spikes above the 95th percentile of the trailing 30-day distribution constitute a potential signal trigger.

#### 3.1.2 NLP Signal Extraction

Modern approaches use transformer-based models fine-tuned on financial text:

- **FinBERT**: BERT pre-trained on financial corpora; produces sentiment probability distributions rather than binary labels
- **BERTweet**: Trained on 800M tweets; better handles informal language, abbreviations, and ticker references than general-purpose BERT
- **Dynamic Expert Tracing**: A filtering algorithm that identifies "true experts" — users whose historical sentiment calls have predictive power — and "inverse experts" — users whose calls consistently predict the opposite direction. Weighting by expert quality substantially reduces noise

The raw output from any NLP model should be treated as a noisy weak signal. Its standalone IC (Information Coefficient, correlation with forward returns) is typically in the range of 0.01–0.04 for daily returns, which is below threshold for standalone deployment but meaningful in an ensemble.

#### 3.1.3 Sentiment Aggregation

For a given ticker at time `t`, the aggregated sentiment score `S(t)` is:

```
S(t) = Σ_i [ w_i * sentiment_i(t) ] / Σ_i w_i
```

where `w_i` is the credibility weight of user `i` (derived from their historical accuracy), and `sentiment_i(t)` is their NLP-scored sentiment value in `[-1, +1]`.

The **normalized sentiment momentum** signal then becomes:

```
SentMom(t) = [ S(t) - μ_S(t, L) ] / σ_S(t, L)
```

where `μ_S` and `σ_S` are the rolling mean and standard deviation of `S` over lookback window `L` (typically 20–60 days).

---

### 3.2 Google Trends — Search Velocity as a Leading Indicator

#### 3.2.1 Mechanism

Google Trends reflects the number of searches for a given query term relative to total search volume, indexed to 100 for the peak period in the selected window. The mechanism through which it predicts returns is **attention-driven order flow**: retail investors search for companies they intend to buy, and institutional analysts search for topics driving their investment theses. A spike in searches for a company's ticker or product name precedes retail buying pressure.

The seminal work by Preis, Moat, and Stanley (2013) in *Nature Scientific Reports* ("Quantifying Trading Behavior in Financial Markets Using Google Trends") demonstrated that changes in search volume for finance-related terms Granger-cause stock market movements, with predictive power over horizons of 1–3 weeks. Strategies using these signals outperformed buy-and-hold by approximately 40% in the studied period.

#### 3.2.2 Query Design

Query design is the highest-leverage variable in Google Trends-based signals. Effective queries include:

- **Company name + ticker** (e.g., "NVIDIA stock")
- **Company name alone** (e.g., "Nvidia")
- **Core product name** (e.g., "ChatGPT" for Microsoft/OpenAI-adjacent theses)
- **Industry terms** for sector-level signals (e.g., "electric vehicle tax credit")

Avoid overly specific queries that have too little search volume — Google Trends replaces low-volume values with 0, introducing artificial sparsity.

#### 3.2.3 Normalization

Google Trends data is indexed (0–100) relative to its own history, which solves for secular growth in internet usage but introduces cross-stock incomparability. The normalization pipeline:

1. **Seasonal decomposition**: Remove seasonal patterns (e.g., retail stocks always spike in December)
2. **Z-score normalization**: Compute rolling z-score over a trailing 52-week window:
   ```
   GT_z(t) = [ GT(t) - μ_GT(t, 52w) ] / σ_GT(t, 52w)
   ```
3. **Change-point detection**: Flag when GT_z exceeds +2.0 sigma as a potential signal event
4. **Lag consideration**: The predictive content of search spikes decays rapidly; most predictive power is within the same week and 1–2 weeks forward. Signal weight should decay exponentially with a half-life of approximately 5–7 calendar days.

#### 3.2.4 Limitations

- Google Trends provides weekly data for most queries (daily only available for short windows)
- Data is sampled, not a complete count — low-volume tickers have high sampling variance
- The relationship between search volume and returns is non-monotonic: extreme search spikes can reverse quickly as retail buyers become exhausted
- Higher search volumes empirically predict *lower* future excess returns at very long horizons (6–12 months), suggesting an attention-driven overvaluation effect that reverses

---

### 3.3 Options Flow — Unusual Activity, GEX, and Dark Pool Prints

#### 3.3.1 The Information Content of Options

Options markets are where informed traders express directional and volatility views with leverage. Because option purchases are directional bets with defined risk, large institutional and informed-money option orders leave observable footprints in the market's public data feed. The challenge is separating informed flow from hedging flow and retail speculation.

**Key constructs:**

**Unusual Volume**: Options volume 5x or more above the average daily volume for that specific contract. When volume far exceeds open interest, it indicates new position-taking rather than closing of existing positions.

**Put/Call Ratio (PCR)**: The ratio of put volume to call volume. A PCR below 0.7 signals bullish sentiment; above 1.2 signals elevated bearish hedging. The signal is most informative as a deviation from its own trailing mean, not as an absolute level.

**Open Interest Delta (OI Delta)**: Change in open interest at a specific strike over the prior session. Large OI growth at out-of-money calls suggests accumulation of bullish speculation; large OI growth at puts suggests institutional hedging or directional short bets.

**Delta-Adjusted Open Interest (DAOI)**: Multiplying open interest by the option delta produces a dollar-equivalent equity exposure for each strike. Summing DAOI across all strikes and expirations provides an aggregate measure of the market's option-implied equity positioning.

```
DAOI = Σ_{strikes, expirations} [ OI * Δ * ContractSize * UnderlyingPrice ]
```

#### 3.3.2 Gamma Exposure (GEX) — Market Structure Signal

GEX represents the dollar magnitude of stock that market makers must buy or sell to remain delta-neutral when the underlying moves $1.

```
GEX = Σ_{calls} [ OI * Γ * ContractSize * (S²/100) ]
     - Σ_{puts} [ OI * Γ * ContractSize * (S²/100) ]
```

where `Γ` is the option gamma and `S` is the underlying price.

**Positive GEX** (market makers are net long gamma): Makers sell rallies and buy dips to re-hedge, suppressing realized volatility and creating price resistance at high-strike clusters. Price tends to gravitate toward gamma-heavy strikes ("pin risk").

**Negative GEX** (market makers are net short gamma): Makers must buy as prices rise and sell as prices fall, amplifying moves. This regime produces higher realized volatility and is associated with momentum continuation.

**GEX as a regime indicator**: When aggregate market GEX (typically measured on SPX/SPY) is deeply negative, the structural environment favors momentum and breakout strategies. When GEX is large and positive, mean-reversion and volatility-selling strategies perform better.

#### 3.3.3 Dark Pool Prints

Dark pools are private trading venues where large institutional orders are executed away from the lit exchange to minimize market impact. For heavily traded large-cap stocks, 30–40% of total daily volume may occur in dark pools. The prints become visible in the public tape with a delay (typically end-of-day in FINRA ATS data).

**Interpreting dark pool direction:**
- Dark pool print **below the prevailing bid** at time of execution suggests selling pressure — the institution sold at a discount to move size
- Dark pool print **above the prevailing offer** suggests buying pressure
- Large dark pool volume **below the session's open price** implies accumulation before a bullish move; above implies distribution before a decline

Dark pool signals are most meaningful when combined with GEX context. A large dark pool call purchase in a negative GEX environment creates a gamma squeeze catalyst: the delta-hedging requirement forces market makers to buy the underlying as prices rise, amplifying the move.

#### 3.3.4 Signal Construction

The options signal score `O(t)` for a security combines:

```
O(t) = w1 * NormalizedUnusualCallVolume(t)
     - w2 * NormalizedUnusualPutVolume(t)
     + w3 * DarkPoolDirectionScore(t)
     + w4 * GEXRegimeMultiplier(t)
```

where each component is z-scored against its trailing 60-day distribution.

---

### 3.4 Credit & Debit Card Transaction Data

#### 3.4.1 Data Providers & Coverage

**Earnest Analytics (formerly Earnest Research):** Provides anonymized credit, debit, and bill-pay data from millions of US households. Their flagship Orion dataset covers over 450 publicly traded companies with AI-powered earnings predictions. The data is structured as consumer spending at the merchant level, aggregated weekly and updated before quarterly earnings releases.

**Bloomberg Second Measure:** Acquired by Bloomberg in 2021, tracks anonymized transaction data from millions of US consumers. Coverage spans thousands of companies with a focus on consumer-facing businesses: restaurants, e-commerce, streaming, retail, travel.

**YipitData (Bloomberg Second Measure + proprietary blend):** Combines transaction data, app data, and web data into unified KPI estimates. Particularly strong for digital-native businesses where transaction data and app data can be cross-validated.

#### 3.4.2 Signal Mechanism

The core mechanism is **revenue surprise prediction before the earnings announcement**. Consumer spending data aggregated at the merchant level directly maps to company revenue for consumer-facing businesses. The signal is:

```
TxnRevSurprise(t) = [ TxnImpliedRevenue(t) - ConsensusEstimate(t) ] / ConsensusEstimate(t)
```

Positive values indicate the company is tracking above consensus, making an earnings beat likely; negative values suggest a miss.

This signal has a natural decay: its predictive power concentrates in the 4–6 weeks before an earnings announcement and decays to near-zero after the announcement (when the information becomes public). The **signal half-life** is approximately 3 weeks in the pre-announcement window.

#### 3.4.3 Coverage Constraints

Transaction data covers:
- **High coverage**: Restaurants, retail, e-commerce, streaming, travel, food delivery
- **Medium coverage**: Software (when sold via consumer credit cards), healthcare services
- **Low coverage**: B2B software, financial services, industrials, mining, utilities

Universe construction must restrict this signal to sectors with adequate spending data coverage.

#### 3.4.4 Normalization & Comparability

Raw transaction dollar values are not comparable across companies due to scale differences. The signal must be expressed as:

1. **Year-over-year growth rate**: Removes seasonality
2. **Growth deviation from consensus growth expectation**: Isolates surprise component
3. **Trailing seasonality adjustment**: Some merchants have highly seasonal patterns (e.g., holiday retailers); the seasonal component must be estimated and removed

---

### 3.5 App Usage & Web Traffic Data

#### 3.5.1 Data Providers

**Apptopia:** Tracks over 7 million apps across iOS and Android, measuring daily active users (DAU), monthly active users (MAU), session length, session frequency, retention rates, and app store rankings. Covers 3,500+ public companies. Data is updated daily.

**Sensor Tower:** Similar coverage to Apptopia with additional focus on advertising intelligence and app store optimization metrics. Particularly strong for gaming, social media, and entertainment apps.

**SimilarWeb:** Web traffic intelligence covering 210 categories in 190 countries. Provides monthly unique visitors, session duration, bounce rate, traffic source breakdown (organic, paid, social, referral), and page-level engagement data.

#### 3.5.2 Signal Mechanism

App engagement metrics function as a **leading KPI proxy**. For digital-native businesses, DAU growth and MAU growth directly predict subscription revenue, advertising revenue, and in-app purchase revenue in subsequent quarters. The mapping is:

- **DAU growth acceleration** → ad revenue acceleration (for ad-supported apps)
- **Session length increase** → engagement-driven revenue per user increase
- **New installs surge** → user cohort growth → future revenue potential
- **Rating improvements** → churn reduction → subscriber economics improvement

The signal lead time varies:
- App installs are recognized as revenue over subscription periods — the revenue shows up 1–3 months after the install surge
- DAU directly correlates with same-month advertising revenue but predicts next-quarter revenue on a seasonal-adjusted basis

#### 3.5.3 Cross-Validation

App data and web traffic data should be cross-validated for consistency. If SimilarWeb shows declining web traffic but Apptopia shows rising DAU, the business may be successfully migrating users from web to mobile — a nuanced signal that requires holistic interpretation rather than mechanical combination.

---

### 3.6 Satellite & Geospatial Data

#### 3.6.1 Parking Lot Analysis

RS Metrics pioneered the satellite analysis of retail parking lots in 2011. The methodology counts vehicles in identified parking lots belonging to a company's locations using computer vision applied to satellite imagery, typically captured 1–4 times per week depending on cloud cover.

**Signal construction:**
```
FootTrafficSignal(t) = [ ParkingLotCarCount(t) / ParkingLotCarCount(t-52w) ] - 1
```
This year-over-year growth rate controls for day-of-week effects, seasonal patterns, and permanent changes to lot capacity.

Academic research confirms that YoY parking lot changes predict quarterly same-store sales — a primary performance metric for retailers. A portfolio that long the top quintile (best parking lot growth) and short the bottom quintile of retail stocks ahead of earnings earned approximately 4.95% over the earnings window, after transaction costs.

**Limitations**: Cloud cover creates data gaps; parking lots are not always visible; employee parking may confound customer traffic; the relationship between cars and sales depends on ticket size and basket composition.

#### 3.6.2 Shipping & Port Activity

Port throughput measured from satellite imagery (MarineTraffic, SpaceKnow) provides leading indicators for:
- **Retailer inventory builds** (ships arriving at Los Angeles/Long Beach predict retailer inventory levels 30–60 days later)
- **Commodity exporters** (loading rates at iron ore or coal ports predict earnings for mining companies)
- **Logistics companies** (vessel utilization rates predict freight rate movements)

#### 3.6.3 Oil Storage Monitoring

Orbital Insight and Kayrros use shadow analysis on floating-roof oil storage tanks to estimate fill levels. As a tank fills, the floating roof descends and casts a shorter shadow that is detectable from space. This provides weekly oil inventory estimates that precede the EIA Wednesday release by several days, creating a tradeable signal for energy equities and crude futures.

---

### 3.7 Workforce & Organizational Data

#### 3.7.1 Job Postings as Business Health Signal

Job postings represent one of the most actionable alternative data signals because they reflect **revealed corporate intent**. Companies incur direct costs for each open role and post positions only when they have budget authority and genuine hiring plans. Unlike press releases, job postings are difficult to stage for perception management.

**Signal construction:**
```
HiringVelocity(t) = [ JobPostings(t, 90d) - JobPostings(t-90d, 90d) ] / JobPostings(t-90d, 90d)
```

A 30%+ quarter-over-quarter increase in job postings is associated with 2.4x higher probability of revenue beat in the next quarter. Breakdowns by department provide nuance:

- **Engineering/R&D hiring surge**: Product development acceleration — bullish for future revenue
- **Sales/marketing hiring surge**: Revenue growth investment — leads revenue by 2–3 quarters
- **Support/operations hiring surge**: Reactive to existing growth — contemporaneous signal
- **Finance/legal hiring surge**: Potentially precedes acquisition or regulatory event

#### 3.7.2 LinkedIn Headcount Tracking

LinkedIn company headcount growth measured via the Economic Graph (or third-party providers like Aura, Coresignal) provides a monthly signal of workforce expansion or contraction. Headcount data is particularly valuable for:

- **Verifying job posting signals**: Open postings that don't result in headcount growth indicate hiring difficulty or strategic pivot away from that function
- **Early downsizing detection**: Headcount decline before announced layoffs generates a short-selling signal
- **Competitive intelligence**: Comparing headcount growth rates across competitors within a sector

**Signal construction:**
```
HeadcountGrowthSignal(t) = [ HeadCount(t) - HeadCount(t-3m) ] / HeadCount(t-3m)
```
Annualized and normalized against sector-specific headcount growth benchmarks.

#### 3.7.3 Patent Filing Velocity

Patent filing data (USPTO) provides a signal for R&D pipeline health. Patent velocity — the rate of new patent applications per quarter — predicts future product differentiation and competitive moat durability. This signal operates on multi-year horizons, making it most useful for long-duration fundamental tilts rather than short-term trading signals.

---

### 3.8 Short Interest Data

#### 3.8.1 Data Sources & Frequency

**FINRA** requires member firms to report short positions twice monthly (as of the settlement dates closest to mid-month and end-of-month). This official data is published with a roughly 9-trading-day lag. The official metric is short interest as a percentage of shares outstanding ("short interest ratio") and short interest as days-to-cover relative to average daily volume.

**S3 Partners, ORTEX, IHS Markit, S&P Global:** Provide daily estimated short interest by synthesizing securities lending data, which updates continuously as shares are borrowed and returned. These estimates are more timely than FINRA data but carry estimation error.

#### 3.8.2 Signal Interpretation

**Short interest ratio** (shares short / float) as an absolute level is a contrarian or momentum signal depending on context:

- **Very high short interest (>20% of float)**: Potential short squeeze risk; constrains further shorting; if a positive catalyst emerges, forced covering amplifies the upside move
- **Rising short interest**: Bearish signal from informed sellers; historically predicts underperformance
- **Declining short interest**: Short covering; can be bullish (covers into price decline = bearish resolve fading) or neutral

**Days-to-cover (DTC)** = Short Interest / Average Daily Volume. High DTC stocks are vulnerable to squeeze because covering would take many days even at full daily volume.

**The squeeze signal:** The combination of high short interest + high DTC + rising price + positive catalyst (earnings beat, buyback announcement) creates the conditions for a gamma squeeze when combined with high options open interest. This is the "multi-factor squeeze" construct used by flow traders.

#### 3.8.3 Frequency Caveat

Because official FINRA data is bi-monthly with a 9-day lag, trading strategies cannot react to official short interest changes quickly. Daily estimated data from commercial vendors is necessary for any strategy with sub-monthly holding periods.

---

### 3.9 Insider Transaction Data

#### 3.9.1 SEC Form 4 Mechanics

Section 16 of the Securities Exchange Act requires officers, directors, and beneficial owners of more than 10% of a class of registered equity securities to file a Form 4 within **two business days** of any transaction. The electronic filing is publicly accessible via EDGAR. Transaction types are coded:

- **Code P (Open Market Purchase)**: Most bullish signal — insider voluntarily bought shares with personal capital
- **Code S (Open Market Sale)**: Weakest signal; insiders sell for many non-informational reasons (diversification, taxes, estate planning)
- **Code A (Award/Grant)**: Compensation-related; low information content
- **Code D (Disposition)**: Often relates to tax withholding on vesting events; low information content
- **Code M (Option Exercise)**: Typically followed immediately by Code S; combined net signal is often neutral to negative

#### 3.9.2 Signal Extraction

**Cluster buying** is the highest-quality signal: multiple insiders (different individuals, different roles) buying simultaneously in open market transactions. Academic literature consistently shows cluster buying predicts positive abnormal returns of 2–5% over 6-month horizons.

**Signal construction:**
```
InsiderBuyScore(t) = Σ_{insiders buying in t} [ (DollarAmount / AnnualComp) * RoleWeight ]
```

Where `RoleWeight` assigns higher weights to CEO/CFO purchases (highest information asymmetry) and lower weights to board director purchases. `DollarAmount / AnnualComp` normalizes for conviction — a $5M purchase by a CEO earning $5M per year is a more significant signal than a $5M purchase by a billionaire founder.

**Limitations of insider data:**
- Academic research shows positive abnormal returns exist but are difficult to capture at scale due to small trade sizes and low liquidity of the target stocks
- The 2-business-day reporting window means some price movement occurs before the signal is public
- Returns are negatively correlated with stock liquidity — the signal concentrates in smaller, less liquid stocks

---

### 3.10 News Analytics

#### 3.10.1 RavenPack

RavenPack has been processing structured news since 2000 and provides investment-grade sentiment scores to over 70% of top-performing quantitative hedge funds. Their platform:

- Recognizes over 12 million named entities (companies, executives, products, geographies)
- Covers 45,000+ companies across 143 countries
- Provides real-time news analytics from premium sources including Dow Jones, WSJ, Barron's, MT Newswires
- Produces an **Event Sentiment Score (ESS)** on a 0–100 scale (100 = most positive) and a **Composite Sentiment Score (CSS)** aggregating event-level sentiment over rolling windows

The 79% contemporaneous correlation between the RavenPack Sentiment Index and the S&P 500 from 2000–2011 demonstrates that news sentiment is a significant co-determinant of price movement, though the causal direction is bidirectional (news moves prices, and price moves drive news coverage).

#### 3.10.2 Bloomberg News Sentiment (BEAP)

Bloomberg's Event-Driven Analytics platform (BEAP) provides structured news signals from the Bloomberg news wire and third-party sources. It is particularly strong for macro events, central bank actions, and geopolitical developments — areas where RavenPack's strength in company-level events is less differentiated.

#### 3.10.3 News Velocity & Momentum

The actionable signal is not absolute sentiment level but **sentiment velocity** and **news volume acceleration**:

```
NewsVelocity(t) = dSentiment/dt = Sentiment(t) - Sentiment(t - Δt)
NewsAcceleration(t) = NewsVelocity(t) - NewsVelocity(t - Δt)
```

Positive acceleration in news sentiment (sentiment improving at an increasing rate) predicts short-term price continuation. This signal has a very short half-life — most predictive power is within 1–48 hours of the news event.

**News sparsity problem:** Only approximately 10% of listed companies receive news coverage on any given day. For low-coverage tickers, news analytics signals are extremely sparse and must be treated as event-driven rather than continuous signals.

---

## 4. Feature Engineering Pipeline

### 4.1 Pipeline Overview

The raw alternative data must be transformed through a multi-stage pipeline before it can be combined into a tradeable signal. Each stage reduces noise and improves comparability across securities and time.

```
Raw Data --> Cleaning --> Normalization --> Decay-Weighting --> Cross-Sectional Ranking --> Composite Signal
```

### 4.2 Stage 1 — Data Cleaning & Quality Gating

Before normalization, each data point must pass quality gates:

**Coverage filter:** Does this security have sufficient data history for this source? Require at least 252 trading days (1 year) of history for any signal included in the composite. Securities with fewer than 90 days of history for a given source receive zero weight on that source.

**Outlier detection:** Flag and investigate any observation that is more than 5 standard deviations from the trailing mean. These may represent data errors, vendor issues, or genuine extreme events. Apply Winsorization at the 1st and 99th percentile of the trailing 60-day distribution before normalization.

**Staleness detection:** Time-stamp each data point and flag data that has not been updated within the expected refresh window (e.g., a weekly-updated signal with a gap of more than 14 days). Stale data receives decayed weight.

**Vendor reconciliation:** Where multiple vendors cover the same underlying variable (e.g., both Apptopia and Sensor Tower estimate app DAU), cross-validate the two series. If they diverge by more than 20% on a relative basis, exclude the signal for that security until reconciliation is possible.

### 4.3 Stage 2 — Normalization

Different data types require different normalization approaches:

**Time-series normalization (Z-scoring):**
For signals with stationary dynamics (sentiment scores, Google Trends), compute the rolling z-score:
```
z(t) = [ x(t) - μ(t, L) ] / σ(t, L)
```
where `L` is the lookback window (typically 60–252 trading days depending on signal frequency). This centers the signal at zero and scales it to unit variance, making signals comparable across securities and time.

**Growth rate normalization:**
For level variables (headcount, job postings, app installs), use year-over-year or quarter-over-quarter growth rates to remove secular trends before z-scoring:
```
g(t) = [ x(t) - x(t-N) ] / x(t-N)
z_g(t) = [ g(t) - μ_g(t, L) ] / σ_g(t, L)
```

**Rank normalization:**
For the final cross-sectional combination step, convert all z-scores to percentile ranks within the investable universe to prevent any single signal from dominating due to outlier values:
```
r(t) = percentile_rank(z(t), universe)  ∈ [-0.5, 0.5]
```

### 4.4 Stage 3 — Temporal Decay Weighting

Alternative data signals have finite predictive half-lives. A signal generated 3 weeks ago should contribute less to today's composite than a signal generated yesterday. Apply exponential decay weighting:

```
DecayedSignal(t) = Σ_{τ=0}^{T} [ z(t-τ) * exp(-λ * τ) ]
```

Where `λ = ln(2) / H`, and `H` is the signal half-life in days. Empirically estimated half-lives:

| Signal Source | Estimated Half-Life |
|---|---|
| News sentiment velocity | 0.5–2 days |
| Social media sentiment | 1–5 days |
| Options unusual flow | 1–7 days |
| Google Trends spike | 5–10 days |
| Dark pool accumulation | 5–14 days |
| App download surge | 7–21 days |
| Credit card spend surprise | 14–42 days (before earnings) |
| Short interest change | 14–60 days |
| Insider purchase | 30–180 days |
| Parking lot foot traffic | 21–60 days |
| Job posting acceleration | 30–90 days |
| Headcount growth | 60–180 days |
| Patent filing velocity | 180–730 days |

### 4.5 Stage 4 — Sector Neutralization

Many alternative data signals have sector-specific content. Credit card spend acceleration may be high across all restaurant stocks in a good consumer environment. Sector-neutralizing the signal isolates the idiosyncratic component:

```
z_sector_neutral(i, t) = z(i, t) - μ(sector, t)
```

where `μ(sector, t)` is the cross-sectional mean z-score within the security's GICS sector at time `t`. This step is critical for avoiding inadvertent sector bets disguised as alt-data alpha.

### 4.6 Stage 5 — Orthogonalization to Standard Factors

Alt data signals may contain embedded factor exposures (e.g., momentum companies often have high social sentiment; small-cap companies have more volatile sentiment due to lower liquidity). To isolate the genuinely incremental information in the alt data:

Regress the signal on standard Barra/MSCI factor exposures:
```
z_ortho(i, t) = z(i, t) - β_mkt*MktFactor(i) - β_mom*MomFactor(i) - ... - ε(i, t)
```

The residual `ε(i, t)` represents the component of the alt data signal unexplained by known factors — the genuinely novel information content.

---

## 5. Signal Quality Evaluation

### 5.1 The Information Coefficient (IC)

The primary metric for signal quality is the **Information Coefficient**: the Spearman rank correlation between the signal at time `t` and forward returns over the holding period `H`:

```
IC(t) = ρ_S [ z_ortho(i, t) , r(i, t, t+H) ]
```

Where `ρ_S` denotes Spearman rank correlation computed across the cross-section of stocks `i` at time `t`.

**IC benchmarks for alternative data:**
- IC < 0.02: Noise; not tradeable as a standalone signal
- IC 0.02–0.05: Weak; useful only in ensemble context
- IC 0.05–0.10: Moderate; deployable standalone with risk control
- IC 0.10–0.15: Strong; high confidence in signal validity
- IC > 0.15: Exceptional; warrants investigation for overfitting

**IC Stability (ICIR):** IC values are highly volatile. The **Information Ratio of the IC (ICIR)** is more actionable:
```
ICIR = μ_IC / σ_IC
```
An ICIR above 0.5 indicates a consistently predictive signal. Below 0.3 suggests regime-dependent or noisy signal quality.

### 5.2 The Four Dimensions of Alt Data Signal Quality

Any alternative data signal should be evaluated across four dimensions before inclusion in the composite:

#### 5.2.1 Predictiveness

Beyond IC, evaluate:
- **Hit rate**: Percentage of periods where the signal correctly predicts the direction of return (should exceed 52% for a useful directional signal)
- **Profit factor**: Average gain in positive signal periods / average loss in negative signal periods (target > 1.2)
- **Return persistence**: Does the IC remain positive across multiple forward periods (1d, 5d, 21d)? Decay patterns reveal optimal holding periods
- **Turnover-adjusted IC**: IC net of expected transaction costs; a signal with IC 0.04 but 500% annual turnover may generate less net alpha than one with IC 0.02 and 150% turnover

#### 5.2.2 Coverage

Coverage is the fraction of the target universe for which a signal has valid data in any given period:
```
Coverage(t) = |{i : z(i,t) is non-missing}| / |Universe|
```

A signal with 40% coverage can only inform portfolio decisions for 40% of the book. Low-coverage signals require careful position sizing to avoid concentration of alt-data bets in the covered subset, which may bias the portfolio toward specific sectors or market caps.

#### 5.2.3 Uniqueness

**Correlation with other signals in the ensemble** determines the marginal diversification value:
```
DiversificationValue(new signal) = 1 - max_i[ ρ(new signal, existing signal i) ]
```

A signal that is 85% correlated with existing signals in the composite adds little incremental information regardless of its standalone IC. The marginal IC contribution to the ensemble, net of correlation, is what matters for ensemble construction.

#### 5.2.4 Latency & Freshness

Latency is the time between when a real-world event occurs and when the signal reaches the portfolio manager's model. Sources of latency:

- **Data collection latency**: Time for the vendor to collect and clean the raw data
- **Processing latency**: Time for the vendor to compute derived metrics from raw data
- **Delivery latency**: Time for the signal to reach the model via API or file delivery

For event-driven signals (news, insider filings, unusual options flow), latency measured in minutes matters — a 2-hour delay in processing an insider Form 4 filing means competing with other systematic strategies that have faster pipelines.

### 5.3 Evaluating Data Vendor Quality

Before purchasing or integrating a dataset:

1. **Request a data sample and independently backtest** against the vendor's performance claims
2. **Check for look-ahead bias** in the vendor's historical data — some vendors "backfill" historical observations with data that would not have been available at that point in time
3. **Evaluate survivorship bias** — does the dataset include companies that were later acquired, went private, or went bankrupt?
4. **Audit the cleaning methodology** — how does the vendor handle missing data, outliers, and corporate events like mergers and splits?
5. **Reference checks with other users** of the dataset who are not competitors

---

## 6. Signal Combination Architecture

### 6.1 The Weak Signal Problem

No individual alternative data signal is strong enough to trade alone at scale. IC values of 0.02–0.05 from individual sources, combined with high noise and incomplete universe coverage, preclude standalone deployment. The core statistical challenge is combining many weak, partially correlated signals into a composite with meaningful predictive power.

The Fundamental Law of Active Management provides the theoretical foundation:

```
IR ≈ IC * √(N * (1-ρ))
```

Where `N` is the number of independent signals and `ρ` is the average pairwise correlation between signals. With IC = 0.03 for each of 8 signals that are 30% correlated, this yields:

```
IR ≈ 0.03 * √(8 * 0.7) ≈ 0.03 * 2.37 ≈ 0.071
```

This is before diversification benefits at the portfolio level. The implication is that breadth (more independent signals) is as important as depth (higher IC per signal) in alt data fusion.

### 6.2 Combination Methods

#### 6.2.1 Equal-Weighted Composite (Baseline)

The simplest approach: average the rank-normalized signals with equal weights.

```
Composite(i, t) = (1/N) * Σ_j z_ortho_j(i, t)
```

This approach is robust to parameter estimation error and performs surprisingly well in practice when signals are roughly equally predictive. It is the recommended starting point before more sophisticated methods are applied.

#### 6.2.2 IC-Weighted Combination

Weight signals by their historical IC:

```
Composite(i, t) = Σ_j [ IC_j(t, L) * z_ortho_j(i, t) ] / Σ_j |IC_j(t, L)|
```

Where `IC_j(t, L)` is the rolling IC of signal `j` computed over the trailing `L` periods. This approach adapts weights to signal performance but risks overfitting to recent signal performance and may increase turnover as weights shift.

#### 6.2.3 Maximum Information Ratio Weighting

Solve the optimization problem:
```
max_{w} w^T * μ_IC / √(w^T * Σ_IC * w)
subject to: Σ w_j = 1, w_j ≥ 0
```

Where `μ_IC` is the vector of trailing mean ICs and `Σ_IC` is the covariance matrix of IC time series across signals. This is formally equivalent to maximum Sharpe ratio portfolio optimization applied to the signal IC vectors. It accounts for correlations between signals and upweights uncorrelated signal pairs.

**Practical caveat**: The IC covariance matrix must be estimated from limited history and is therefore noisy. Apply shrinkage toward the equal-weighted solution to prevent extreme weights.

#### 6.2.4 Stacked Generalization (Ensemble Learning)

Train a second-layer model to optimally combine signal outputs:

```
r_i(t+1) ≈ f( z_1(i,t), z_2(i,t), ..., z_N(i,t) )
```

where `f` is a machine learning model (gradient boosted trees, ridge regression, neural network) trained on the cross-sectional panel.

Gu, Kelly, and Xiu (2020) showed that ensemble machine learning models outperform traditional linear factor models in predicting stock returns across 30,000 US equities. The key implementation constraint is preventing data leakage: the training set must use only data available at the time of prediction, with strict out-of-sample validation.

Gradient boosted trees (XGBoost, LightGBM) are preferred over deep learning for this use case due to:
- Better performance on tabular data with mixed feature types
- Built-in feature importance for signal auditing
- More robust to limited sample sizes
- Faster inference for daily rebalancing

#### 6.2.5 Integrated vs. Mixed Signal Combination

Two architectures exist for combining signals into portfolio weights:

**Integrated approach**: Combine signals at the alpha model level, then solve a single portfolio optimization using the composite score. Advantages: consistent risk treatment; disadvantages: cannot separately validate individual signal contributions.

**Mixed approach**: Construct separate portfolios for each signal, then combine portfolio weights using an overlay weighting scheme. Advantages: cleaner attribution; disadvantages: higher transaction costs from multiple separate turnover streams.

The recommended architecture is **integrated** for signals with similar holding periods (e.g., all 5–15 day signals) and **mixed** for signals with very different time horizons (e.g., combining a 2-day news signal with a 90-day hiring velocity signal).

### 6.3 Time-Scale Separation

Different alt data signals operate on different time scales and should be separated before combination:

**Fast signals (1–7 day holding period):**
- News sentiment velocity
- Social media attention spikes
- Unusual options flow
- Dark pool prints

**Medium signals (7–30 day holding period):**
- Google Trends momentum
- App download acceleration
- Short interest changes
- Insider purchases

**Slow signals (30–180 day holding period):**
- Credit card spend trends
- Job posting velocity
- Headcount growth
- Parking lot foot traffic

The overall composite is then:
```
Composite(i, t) = α_fast * FastComposite(i, t)
               + α_medium * MediumComposite(i, t)
               + α_slow * SlowComposite(i, t)
```

Where `α_fast`, `α_medium`, `α_slow` are calibrated to the risk budget allocated to each time scale. This separation reduces spurious interactions between signals with incompatible horizons.

---

## 7. Universe Construction

### 7.1 Base Universe

**Primary universe**: Russell 3000 + ADRs of major international companies listed in the US.

**Rationale**: The Russell 3000 covers roughly 98% of US market capitalization and provides sufficient breadth for diversification. S&P 500 components provide the best data coverage across most alt data categories; smaller Russell 2000 components are included selectively where data coverage is sufficient.

### 7.2 Coverage-Driven Universe Filtering

The universe must be dynamically filtered based on which securities have sufficient data coverage to generate a meaningful composite signal:

**Minimum coverage requirement**: A security must have valid data from at least 3 of the 8 signal sources in the composite at any given time to be included in the active universe. Securities with coverage from 1–2 sources receive exposure only in those specialized signals, not in the full composite.

**Consumer-facing bias**: Transaction data, app usage, and satellite data have the best coverage for consumer-facing businesses (retail, restaurants, e-commerce, streaming, gaming, travel). The effective alt data universe naturally skews toward the consumer discretionary, consumer staples, communication services, and technology sectors.

**Minimum market cap**: $500 million. Below this threshold, alt data coverage is sparse, liquidity is insufficient for meaningful position sizes, and small-cap-specific risks dominate any alt data signal.

**Minimum ADV filter**: $10 million average daily volume (60-day trailing). Ensures positions can be entered and exited without excessive market impact.

### 7.3 Special Sub-Universes

**High-options-activity universe**: Stocks with average daily options volume > $5 million notional. Required for the options flow signal. Approximately 500–700 stocks.

**High-social-attention universe**: Stocks appearing in Reddit WSB or StockTwits at least 10 times per week on average. Approximately 200–400 stocks. Heavily biased toward technology, consumer, and meme-adjacent names.

**Earnings-proximity sub-universe**: Within 45 days of a quarterly earnings announcement. Transaction data signals are concentrated here. Requires a real-time earnings date calendar.

---

## 8. Portfolio Construction

### 8.1 Signal to Weights

The composite signal score is converted to portfolio weights using a mean-variance optimization framework, with the alternative data composite entering as the alpha (expected return) input.

**Expected return estimate:**
```
α(i, t) = κ * Composite(i, t) / σ_idio(i)
```

Where `κ` is a scaling constant calibrated to the empirical relationship between signal scores and forward returns, and `σ_idio(i)` is the idiosyncratic volatility of security `i` estimated from the Barra risk model. Dividing by idiosyncratic volatility applies a bet-sizing adjustment that favors higher-confidence, lower-noise positions.

### 8.2 Portfolio Optimization

Solve the standard long-short portfolio optimization:
```
max_{w} w^T * α - (γ/2) * w^T * Σ * w
subject to:
  |w_net| ≤ δ_net   (net exposure constraint)
  |Σ w| ≤ δ_gross   (gross exposure constraint)
  |β_market(w)| ≤ β_max   (market beta constraint)
  Σ |w_i| * FactorExposure_f(i) ≤ F_max, for each factor f   (factor constraints)
  |w_i| ≤ w_max   (position size constraint)
```

**Risk aversion parameter `γ`**: Controls the tradeoff between return maximization and variance minimization. Calibrated such that the resulting portfolio has a target ex-ante volatility of 10–15% annualized.

**Barra risk model**: Use MSCI Barra or Axioma multi-factor risk model for the covariance matrix `Σ`. This captures both systematic factor risks and stock-specific residual risk. Crucial for preventing the composite alt data signal from generating unintended concentrated factor bets.

### 8.3 Single-Name Bets vs. Basket Construction

**Single-name bets**: High-conviction positions (composite signal > 1.5 sigma) where multiple signal sources converge. Position size: 2–5% of portfolio gross exposure per name. These are the highest-risk, highest-return positions in the book.

**Thematic baskets**: When a sector-level alt data signal is strong (e.g., restaurant transaction data shows broad-based spending acceleration), construct a market-neutral basket: long the top-quintile names and short the bottom-quintile names within the sector. Individual position sizes: 0.5–1.5% per name. Baskets provide more stable exposure but dilute stock-specific alpha with sector-average noise.

**Earnings event sub-portfolios**: A separate allocation for earnings-proximity positions where the transaction data signal is strongest. These positions are opened 4–6 weeks before earnings and closed within 2 days of the announcement. Sizing: up to 20% of total gross exposure during peak earnings season.

### 8.4 Long/Short Allocation

The strategy is designed as equity market-neutral at the market-beta level:
```
Σ_i w_i * β_i ≈ 0
```

However, strict dollar-neutrality (Σ w_i = 0) is not required. A small net-long bias (5–15% of gross) is acceptable to avoid the cost of fully hedging the long book. The target is low beta (|β_portfolio| < 0.15) rather than zero beta.

---

## 9. Risk Management

### 9.1 Data Quality Risk

The largest and most underappreciated risk in alt data strategies is **data quality failure** — receiving bad data that generates false signals leading to incorrect positions.

**Risk types:**
- **Vendor outages**: The data provider fails to deliver the daily data file. Position: implement dead-man switches that decay signal weights to zero as data ages past the expected refresh window
- **Data corruption**: Vendor delivers data with encoding errors, bad values, or incorrect ticker mappings. Position: implement cross-validation rules (e.g., signal z-score exceeding 6 sigma triggers human review before execution)
- **Methodology changes**: Vendor changes how they compute a metric without adequate notice, creating a structural break in the time series. Position: maintain z-score lookbacks long enough to re-anchor quickly, and require vendor notification of methodology changes as a contract term
- **Sample composition shifts**: Vendor's panel of credit cards or app tracking panels changes, introducing a new source of systematic bias. Position: monitor the ratio of actual observed panel size to expected panel size

### 9.2 Latency Risk

For time-sensitive signals (news, options flow, Form 4 filings), the value of the signal decays rapidly and may be zero by the time a slower system processes it.

**Latency budget by signal type:**
- News sentiment: Target <5 minutes from publication to model input
- Form 4 filings: Target <30 minutes from EDGAR filing time to model input
- Options unusual flow: Target <15 minutes from tape time to model input
- Credit card weekly update: No latency constraint — weekly frequency gives 7 days to process

### 9.3 Legal & Compliance Risk

This is an existential risk. Trading on Material Non-Public Information (MNPI) subjects the firm to SEC enforcement, criminal prosecution, and civil liability.

**The MNPI boundary for alt data:**
The SEC's Division of Examinations 2022 Risk Alert specifically addressed alternative data. The legal framework is:

- **Permissible**: Satellite images of publicly visible areas, aggregated anonymized consumer spending data, social media posts by retail investors, SEC public filings
- **Potentially impermissible**: Data derived from an expert network call with a company employee who reveals confidential operational metrics, credit card data from a bank that has a banking relationship with the issuer (potential breach of duty)
- **Impermissible**: Data purchased from a data vendor who obtained it from company insiders (the App Annie enforcement action: $10M+ settlement)

**Compliance requirements:**
- **Vendor due diligence protocol**: Every data vendor must certify that their data collection does not involve MNPI, does not breach any duty of confidentiality, and complies with GDPR/CCPA privacy regulations
- **MNPI policy**: Written policies under Section 204A of the Investment Advisers Act governing alt data sourcing and use
- **Legal review**: All new data sources must be reviewed by outside counsel before live trading
- **Information barrier**: The alt data research team must be information-barrier-separated from any business relationship with covered issuers

### 9.4 Signal Crowding Risk

As alt data becomes mainstream, crowded signals lose their edge. The crowding process is self-defeating: the first movers earn the alpha, and as more participants act on the same signal simultaneously, the price impact of the initial signal is absorbed before later participants can profit.

**Monitoring for crowding:**
- Track the correlation of the strategy's returns with known alt data indices and peer funds
- Monitor how quickly unusual signals are absorbed into price (post-signal return windows shortening is evidence of crowding)
- Track the alpha decay rate: if a signal that historically had a 10-day predictive window has compressed to 3 days, crowding is occurring

**Response to crowding:**
- Shift weight toward less-crowded signal sources (typically newer, more expensive, or harder-to-process data)
- Increase holding period to look past crowded short-term signal exploitation
- Explore proprietary combinations of multiple public signals that are more unique than any individual source

### 9.5 Position-Level Risk Limits

| Limit Type | Limit Value |
|---|---|
| Maximum single-name gross exposure | 5% of gross NAV |
| Maximum sector net exposure | ±10% of gross NAV |
| Maximum factor beta (any Barra factor) | ±0.2 |
| Maximum market beta | ±0.15 |
| Maximum gross leverage | 300% |
| Maximum net leverage | ±30% |
| Stop-loss per position | -15% from entry |
| Portfolio-level drawdown stop | -8% NAV from peak |

---

## 10. Execution Considerations

### 10.1 Holding Period and Turnover

Alt data signals operate on varying time scales, which creates a structural tension in execution: longer holding periods reduce transaction costs but reduce signal freshness, while shorter holding periods capture the freshest signal but incur higher costs.

**Target holding periods by signal layer:**

| Layer | Signal Sources | Target Holding | One-Way Turnover (annual) |
|---|---|---|---|
| Fast | News, Options Flow, Social Momentum | 1–7 days | ~2000–5000% |
| Medium | Trends, App Data, Insider | 5–21 days | ~500–1500% |
| Slow | Transaction Data, Headcount, Satellite | 14–60 days | ~100–400% |
| Composite | Weighted blend | 7–21 days (target) | ~300–600% |

Annual one-way turnover of 300–600% is aggressive but manageable for a liquid-equity-focused strategy. Transaction cost targets should assume 5–10 bps all-in per side for S&P 500 components and 10–25 bps for smaller-cap names.

### 10.2 Transaction Cost Modeling

A realistic transaction cost model must be incorporated into the signal and portfolio optimization to avoid overfitting to pre-cost performance:

**Half-spread cost**: For stocks with $20M+ ADV, bid-ask spreads are typically 2–5 bps. For $2–20M ADV, assume 5–15 bps.

**Market impact model**: The Almgren-Chriss market impact model estimates temporary and permanent impact:
```
TemporaryImpact ≈ σ * (TradeSize / ADV)^0.5
PermanentImpact ≈ γ_perm * (TradeSize / ADV)
```

For a fund with $500M AUM and 300% turnover, average position sizes of 0.5–2% of ADV will produce minimal market impact in the S&P 500 but material impact in smaller names.

**Total transaction cost target**: 40–80 bps annualized (approximately 5–10 bps per side at the target turnover rate). This is the cost that must be subtracted from gross alpha to arrive at net alpha.

### 10.3 Execution Algorithm Selection

Given the medium-frequency nature of signals (daily rebalancing at most):

- **VWAP/TWAP algorithms**: Appropriate for most positions; spreads execution over the day to minimize information leakage and market impact
- **Arrival price algorithms**: For signals with very short decay windows (news-driven, options-flow-driven); accept higher impact to ensure signal is captured before it's absorbed by the market
- **Dark pool routing**: Appropriate for large institutional-sized positions; request dark pool access from prime broker to minimize lit exchange impact

### 10.4 Portfolio Rebalancing Frequency

The portfolio should not be rebalanced daily for all signals — only for signals in the fast layer. A multi-frequency rebalancing schedule reduces unnecessary turnover:

- **Intraday** (fast signals only): Execute within 2 hours of a strong news/options signal
- **Daily** (fast + medium signals): Review and rebalance positions in the fast and medium layers based on signal updates
- **Weekly**: Rebalance the slow signal layer; review sector and factor exposures
- **Monthly**: Recalibrate signal weights, update universe, review coverage statistics

---

## 11. Regime Sensitivity

### 11.1 Why Regime Matters for Alt Data

Alternative data signals do not have uniform predictive power across market regimes. The signal-to-noise ratio of each source changes as a function of the macro and market environment. A strategy that ignores regime sensitivity will appear to work in backtests because it averages across regimes, but will underperform or generate losses during specific regime states.

### 11.2 Regime Taxonomy

Define four primary market regimes based on VIX level and realized volatility:

| Regime | VIX Level | Market Character | Alt Data Behavior |
|---|---|---|---|
| R1: Low-vol Trending | VIX < 15 | Slow grind higher, momentum works | Sentiment and attention signals are strongest; social momentum valid |
| R2: Low-vol Choppy | VIX 15–20 | Range-bound, mean reversion works | Transaction data and job posting signals dominate; sentiment noisy |
| R3: Elevated Vol | VIX 20–30 | Risk-off episodes, correlation spikes | Insider buys and dark pool accumulation most predictive; social sentiment becomes contrarian |
| R4: Crisis | VIX > 30 | Forced selling, correlation near 1 | Most alt data signals lose predictive power; reduce exposure; options GEX critical for structural positioning |

### 11.3 Regime-Conditional Signal Weighting

The weight of each signal source in the composite should be modulated by the current regime estimate:

```
Composite(i, t) = Σ_j [ w_j * RegimeModifier(j, R(t)) * z_ortho_j(i, t) ]
```

Where `RegimeModifier(j, R)` is a lookback-calibrated adjustment factor:

| Signal | R1 (Low-vol Trend) | R2 (Choppy) | R3 (Elevated) | R4 (Crisis) |
|---|---|---|---|---|
| Social sentiment | 1.5x | 0.8x | 0.3x | 0.0x |
| Options flow | 1.2x | 1.0x | 1.5x | 0.5x |
| News sentiment | 1.0x | 1.0x | 1.2x | 0.8x |
| Transaction data | 1.0x | 1.3x | 1.1x | 0.6x |
| Insider buys | 0.8x | 1.0x | 1.5x | 1.8x |
| Short interest | 1.0x | 1.2x | 1.3x | 0.5x |
| GEX | 0.8x | 1.0x | 1.5x | 2.0x |

### 11.4 When Sentiment Matters Most

Social sentiment signals (Reddit, Twitter, StockTwits) are most predictive under specific conditions:
- **Retail participation is elevated**: High retail order flow as a fraction of total volume (estimated from odd-lot statistics, retail broker reports)
- **Meme/attention economy is active**: Periods when social media narrative is driving significant price action in multiple names simultaneously
- **VIX < 20**: In high-volatility regimes, institutional forced-selling and macro factors dominate retail attention signals

Conversely, social sentiment signals are least reliable when:
- Macro events dominate (FOMC, NFP, earnings seasons in aggregate)
- A given stock is experiencing an idiosyncratic crisis (credit event, fraud allegation, regulatory action)
- Institutional positioning is extremely concentrated in the opposite direction of social sentiment

### 11.5 When Fundamental Alt Data Dominates

Transaction data, job postings, and satellite signals are more robust to regime changes because they reflect actual business fundamentals rather than market psychology. During R2 (choppy) and R3 (elevated volatility) regimes, overweight these fundamental-behavior signals and underweight attention/sentiment signals. This regime shift reduces drawdown during volatility spikes because business behavior changes more slowly than sentiment.

---

## 12. Key Risks & Failure Modes

### 12.1 MNPI Risk — Existential Threat

The SEC has demonstrated willingness to pursue enforcement actions against alt data practitioners whose data collection methods breach the duty of confidentiality or constitute insider trading. The App Annie settlement ($10M+) established that providing investment managers with access to app usage data derived from third-party apps whose developers shared data in confidence constitutes securities fraud.

**Failure scenario**: The firm purchases a web scraping dataset that a vendor compiled by logging into retailer back-end dashboards using credentials obtained without authorization. The SEC traces the investment performance to a pattern of trades preceding retail earnings announcements and subpoenas the vendor's client list. The firm is named as a relief defendant and the dataset is deemed MNPI.

**Mitigation**: Legal review for every new data source, comprehensive vendor certification requirements, and ongoing compliance monitoring of dataset provenance.

### 12.2 Data Vendor Concentration Risk

If a disproportionate share of the strategy's edge comes from a single data vendor, the firm is exposed to:
- **Vendor bankruptcy or discontinuation** of the dataset
- **Vendor methodology changes** that invalidate historical calibration
- **Competitive disclosure** of the vendor's client list by the vendor themselves
- **Data exclusivity loss**: Vendor begins selling to more competitors, rapidly crowding the signal

**Mitigation**: Diversify across at least 6–8 distinct data vendors; require contract terms guaranteeing notification of methodology changes; track signal degradation on an ongoing basis.

### 12.3 Crowding & Alpha Decay

As documented in academic research, alt data alpha decays at approximately 5.6% annually in US markets as more participants discover and exploit the same signals. Strategies that were highly profitable in 2018–2020 using credit card data or Google Trends may now require faster execution, shorter holding periods, or combination with more proprietary data sources.

The hyperbolic decay model: `α(t) = K / (1 + λt)` fits empirical alpha decay patterns better than exponential decay, implying that the initial period of a signal's discovery is disproportionately profitable. **First-mover advantage is substantial, and late adoption is expensive.**

**Failure scenario**: The strategy relies on a publicly known alt data combination that a 2023 Quantpedia paper documented in detail. Within 12 months of publication, hundreds of systematic funds have implemented the same combination, crowding the trade and compressing the IC from 0.05 to 0.01.

**Mitigation**: Monitor IC decay on a rolling basis; establish threshold IC floor (IC < 0.02) below which a signal is removed from the composite; continuously develop and backtest new proprietary signal combinations.

### 12.4 Noise Masquerading as Signal

Most alt data is noise. An IC of 0.03 means the signal explains less than 0.1% of the cross-sectional variance of returns (IC² = R² in cross-sectional regression context). Distinguishing a true IC of 0.03 from a spurious backtested IC of 0.03 requires:

- **Out-of-sample validation**: Never use the last 3 years of data for development; reserve it for final validation
- **Multiple testing correction**: After evaluating 100 signal variations, expect 5 to appear significant at the 5% level purely by chance. Apply Bonferroni or Benjamini-Hochberg corrections
- **Economic rationale first**: Only test signals with a prior economic mechanism. "Data mining" signals that lack a causal story are almost never real

### 12.5 Latency Arbitrage by HFT

High-frequency traders systematically pick off slow participants by detecting their intent from order flow and adjusting quotes ahead of their trades. For alt data strategies that execute immediately upon signal receipt (e.g., news-driven trades), HFT may detect the surge of systematic orders and front-run the execution.

**Mitigation**: Use dark pool execution, VWAP algorithms, and randomized execution schedules to mask systematic patterns. Accept slightly worse fills in exchange for reduced adverse selection.

### 12.6 Model Overfitting

Given the high dimensionality of alt data features and the relatively short history of most datasets (typically 5–10 years), overfitting is an acute risk. Ensemble methods and regularized models (ridge regression, Lasso, gradient boosted trees with depth constraints) are preferred over unconstrained neural networks for this reason.

**The "beautiful backtest" trap**: A model that achieves 2.5 Sharpe in backtest but 0.3 Sharpe in live trading has likely overfitted. Common overfitting symptoms in alt data backtests:
- Sharpe ratio is stable or improving across all sub-periods
- The model performs well in the last 12 months of history (which were often used for calibration without explicit holdout)
- No plausible economic mechanism explains why this specific combination of features predicts returns
- Transaction costs were not realistically modeled

---

## 13. Parameters & Tunable Knobs

### 13.1 Signal Layer Parameters

| Parameter | Default | Range | Sensitivity |
|---|---|---|---|
| Fast signal lookback (z-score window) | 60 days | 30–120 days | Medium |
| Medium signal lookback | 126 days | 60–252 days | Low |
| Slow signal lookback | 252 days | 180–504 days | Low |
| News sentiment half-life | 1 day | 0.5–3 days | High |
| Social sentiment half-life | 3 days | 1–7 days | High |
| Options flow half-life | 4 days | 2–10 days | Medium |
| Google Trends half-life | 7 days | 5–14 days | Medium |
| Transaction data half-life | 21 days | 14–42 days | Medium |
| Insider purchase half-life | 90 days | 60–180 days | Low |
| Headcount growth half-life | 120 days | 90–180 days | Low |

### 13.2 Signal Combination Parameters

| Parameter | Default | Range | Sensitivity |
|---|---|---|---|
| Fast layer allocation (α_fast) | 20% | 10–40% | High |
| Medium layer allocation (α_medium) | 40% | 30–60% | Medium |
| Slow layer allocation (α_slow) | 40% | 20–60% | Medium |
| IC lookback for weighting | 63 days | 42–126 days | Medium |
| IC shrinkage factor (toward equal weight) | 0.3 | 0.1–0.7 | High |
| Minimum IC threshold for inclusion | 0.015 | 0.010–0.030 | High |
| Signal orthogonalization: include which factors | Mkt, Mom, Val, Size, Low-vol | All Barra factors | Medium |

### 13.3 Universe & Portfolio Parameters

| Parameter | Default | Range | Sensitivity |
|---|---|---|---|
| Minimum market cap | $500M | $200M–$2B | Medium |
| Minimum ADV | $10M | $5M–$50M | Medium |
| Minimum signal coverage (sources) | 3 of 8 | 2–5 | High |
| Maximum single-name weight | 5% | 3–8% | Medium |
| Maximum sector net exposure | ±10% | ±5–±20% | Medium |
| Target market beta | 0.0 | −0.1–+0.1 | Low |
| Target portfolio volatility (annualized) | 12% | 8–18% | Medium |
| Risk aversion parameter (γ) | 2.5 | 1.0–5.0 | High |

### 13.4 Execution Parameters

| Parameter | Default | Range | Sensitivity |
|---|---|---|---|
| Rebalance frequency (medium layer) | Daily | Daily–Weekly | High |
| Max daily turnover (% of gross) | 15% | 5–30% | Medium |
| Transaction cost assumption (bps per side) | 8 bps | 5–20 bps | High |
| Market impact model: temporary impact coefficient | 0.10 | 0.05–0.20 | Medium |
| VWAP execution participation rate | 10% | 5–20% | Low |
| Stop-loss per position | -15% | -10% to -20% | Medium |

### 13.5 Regime Parameters

| Parameter | Default | Range | Sensitivity |
|---|---|---|---|
| Regime detection window (VIX rolling window) | 21 days | 10–63 days | Medium |
| R1/R2 VIX threshold | 15 | 12–18 | Medium |
| R2/R3 VIX threshold | 20 | 18–25 | Medium |
| R3/R4 VIX threshold | 30 | 25–35 | Medium |
| Regime modifier recalibration frequency | Quarterly | Monthly–Annually | Low |
| Max social sentiment weight (R1) | 1.5x | 1.2–2.0x | Medium |
| Min social sentiment weight (R4) | 0.0x | 0.0–0.3x | High |

---

## Appendix A — Vendor Reference Map

| Signal Category | Tier-1 Vendors | Tier-2 / Open-Source |
|---|---|---|
| News NLP | RavenPack, Bloomberg BEAP, Refinitiv | GDELT Project, NewsAPI |
| Social Sentiment | Quiver Quantitative, Accern, StockGeist | Reddit PRAW API, Pushshift |
| Google Trends | Glimpse (premium), Ticker Trends | pytrends (Google Trends API) |
| Options Flow | Unusual Whales, Market Chameleon, SpotGamma | CBOE public data, SEC options data |
| Transaction Data | Earnest Analytics, Bloomberg Second Measure | FRED consumer spending data |
| App Data | Apptopia, Sensor Tower, data.ai | App Store Connect (self-reported) |
| Web Traffic | SimilarWeb, Comscore | Cloudflare Radar (partial) |
| Satellite | RS Metrics, Orbital Insight, Kayrros | Planet Labs, USGS Landsat |
| Job Postings | Coresignal, Thinknum, Burning Glass | JOLTS, Indeed API |
| LinkedIn/Headcount | Aura, Revelio Labs | LinkedIn Economic Graph (partnership) |
| Short Interest | S3 Partners, ORTEX, IHS Markit | FINRA bi-monthly data (free) |
| Insider Transactions | InsiderFinance, OpenInsider | SEC EDGAR Form 4 (free) |
| Patent Data | PatSnap, Derwent Innovation | USPTO public patent database (free) |

---

## Appendix B — Signal IC Summary Table (Representative Empirical Estimates)

| Signal | Standalone IC (daily) | ICIR | Optimal Holding | Coverage (S&P 500) |
|---|---|---|---|---|
| News sentiment velocity | 0.03–0.05 | 0.4–0.7 | 1–3 days | ~60% daily |
| Social sentiment (WSB) | 0.01–0.03 | 0.2–0.4 | 2–5 days | ~20–30% |
| Google Trends spike | 0.02–0.04 | 0.3–0.5 | 5–10 days | ~70% |
| Options unusual flow | 0.03–0.06 | 0.5–0.8 | 2–7 days | ~60% |
| GEX regime | 0.02–0.04 | 0.4–0.6 | 1–5 days | 100% (index) |
| Dark pool accumulation | 0.02–0.04 | 0.3–0.5 | 3–10 days | ~40% |
| Insider cluster buy | 0.03–0.06 | 0.4–0.7 | 30–120 days | Event-driven |
| Short interest change | 0.02–0.04 | 0.3–0.5 | 14–45 days | ~90% |
| Transaction data surprise | 0.04–0.08 | 0.6–1.0 | 14–42 days pre-EPS | ~40–50% |
| App DAU growth | 0.03–0.05 | 0.5–0.8 | 7–21 days | ~30% |
| Job posting velocity | 0.02–0.04 | 0.3–0.5 | 30–90 days | ~60% |
| Parking lot foot traffic | 0.03–0.06 | 0.5–0.8 | 21–60 days | ~20% retail names |
| Headcount growth | 0.01–0.03 | 0.2–0.4 | 60–180 days | ~70% |

*All IC estimates are approximate, drawn from academic literature and practitioner research. Live performance will differ and must be validated with proprietary backtests on the specific datasets purchased.*

---

*End of Specification*
