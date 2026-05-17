# Statistical Arbitrage: Medium-Frequency Pairs & Residual Mean Reversion

**Strategy Class:** Market-neutral equity long/short  
**Frequency:** Medium-frequency (holding period: 1–20 trading days)  
**Universe:** Liquid equities, ETFs, futures pairs  
**Risk Profile:** Low-beta, long-vol-of-vol, short-crowding

---

## Table of Contents

1. [Strategy Overview and Thesis](#1-strategy-overview-and-thesis)
2. [Academic Foundations](#2-academic-foundations)
3. [Pair and Group Selection Methodology](#3-pair-and-group-selection-methodology)
4. [Spread Construction](#4-spread-construction)
5. [Signal Generation](#5-signal-generation)
6. [Portfolio Construction](#6-portfolio-construction)
7. [Risk Management](#7-risk-management)
8. [Execution Considerations](#8-execution-considerations)
9. [Regime Sensitivity](#9-regime-sensitivity)
10. [Key Risks and Failure Modes](#10-key-risks-and-failure-modes)
11. [Parameters and Tunable Knobs](#11-parameters-and-tunable-knobs)

---

## 1. Strategy Overview and Thesis

### 1.1 Origins

Statistical arbitrage was invented at Morgan Stanley in 1982–83. The originator was Gerry Bamberger, a computer scientist, who noticed that stocks in related industries tended to move together and that temporary divergences from their historical ratio were exploitable. His program was primitive by modern standards—it searched for stock pairs with high historical correlation and bet on convergence when prices drifted apart—but the risk-adjusted returns were extraordinary.

Bamberger's work was formalized and scaled by Nunzio Tartaglia, a former Jesuit priest with a PhD in physics, who assembled a secretive group of mathematicians, physicists, and computer scientists at Morgan Stanley around 1985. Tartaglia's "Black Box" was genuinely automated: it identified pairs, executed trades, and managed positions without human discretion. In 1987 the group reportedly generated $50 million in profit for Morgan Stanley. The group disbanded in 1989 when returns declined, but its alumni—including David Shaw, who would found D.E. Shaw & Co.—spread the methodology across Wall Street. Peter Muller later ran an analogous effort at Morgan Stanley under the name PDT (Process Driven Trading), which operated until 2012 when it spun out as PDT Partners.

By the 2000s hundreds of quantitative funds were running variants of the strategy. This concentration created the conditions for the August 2007 quant crisis, which is examined in detail in Section 10.

### 1.2 Core Thesis

The fundamental premise is that assets sharing genuine economic linkages—common products, common customers, common risk factors—tend to be priced in a stable long-run relationship. Short-run pricing deviations arise from:

- Idiosyncratic order flow (a large passive fund rebalancing one name)
- Temporary liquidity differences between two otherwise fungible instruments
- Information that has been incorporated in one security but not yet in the other (lead-lag)
- Mechanical flows from index rebalancing, ETF creation/redemption, or corporate actions

These deviations are mean-reverting: the spread between two cointegrated assets is stationary and returns to its long-run equilibrium. The strategy profits by shorting the expensive side and buying the cheap side whenever the spread is sufficiently dislocated, then closing when convergence has occurred.

### 1.3 What Distinguishes Medium Frequency

Medium-frequency stat arb operates on holding periods from one to twenty trading days. This distinguishes it from:

- **High-frequency stat arb**: Holding periods measured in milliseconds to minutes, focused on microstructure, order-book imbalances, and latency. Requires co-location infrastructure.
- **Low-frequency stat arb / fundamental relative value**: Holding periods of months to years, driven by valuation differentials. Less dependent on short-term cointegration stability.

The medium-frequency domain is where the original Morgan Stanley approach operated and where the bulk of the academic and practitioner literature is concentrated. It is accessible to practitioners with standard execution infrastructure (direct market access, but not co-location) and generates enough turnover to be economically meaningful without requiring microsecond-level technology.

### 1.4 Strategy Variants

Three main sub-strategies fall under this umbrella:

1. **Classical pairs trading**: A single pair of cointegrated stocks. Simple and transparent. Sensitive to pair breaks.
2. **Basket / portfolio stat arb**: A portfolio of K pairs or an N-asset cointegrating basket. More diversified, less exposed to any single relationship breaking.
3. **Residual mean reversion (PCA / factor model approach)**: Returns are decomposed via a factor model (market model, sector model, PCA). The idiosyncratic residuals are modeled as mean-reverting. This is the dominant institutional approach.

---

## 2. Academic Foundations

### 2.1 Cointegration Theory

**Cointegration** is the central theoretical concept. Two price series P_t^A and P_t^B are said to be cointegrated if:

- Both series are integrated of order 1, denoted I(1): the series themselves are non-stationary (they have unit roots), but their first differences (returns) are stationary.
- There exists a linear combination z_t = P_t^A - β · P_t^B that is I(0), meaning the combined spread is stationary.

The parameter β is the **cointegrating coefficient** or **hedge ratio**. The spread z_t fluctuates around a constant mean μ and has finite, bounded variance—it cannot drift to infinity. This is what makes it tradeable.

Cointegration is a stronger concept than correlation. Two series can be highly correlated in returns yet not cointegrated. Correlation measures linear association of stationary increments; cointegration measures whether the levels share a long-run equilibrium. For trading, cointegration is the correct framework because we are betting on convergence in price levels, not in returns.

### 2.2 Engle-Granger Two-Step Test

Robert Engle and Clive Granger received the 2003 Nobel Prize in Economics for developing cointegration theory. The Engle-Granger test (1987) is the canonical two-step procedure:

**Step 1 — Estimate the cointegrating regression:**

```
log(P_t^A) = α + β · log(P_t^B) + ε_t
```

Run OLS on the log-price levels. The slope β is the estimated hedge ratio and the intercept α is the long-run mean of the spread. The residuals ε_t are the estimated spread.

**Step 2 — Test residuals for stationarity:**

Apply the Augmented Dickey-Fuller (ADF) test to ε_t. The null hypothesis is a unit root (non-stationarity; no cointegration). If the test statistic is sufficiently negative (p-value below 0.05 or 0.01 depending on desired confidence), reject the null and conclude the pair is cointegrated.

The ADF regression is:

```
Δε_t = δ · ε_{t-1} + Σ_{j=1}^{p} φ_j · Δε_{t-j} + η_t
```

The test statistic is t(δ̂). Critical values for the residual-based ADF test differ from standard ADF critical values (Engle-Granger critical values are more stringent because the residuals are estimated, not observed).

**Limitation:** The test requires designating one asset as the dependent variable. OLS is asymmetric: regressing A on B yields a different hedge ratio than regressing B on A (they are not reciprocals). In practice, run both directions and select the specification with stronger ADF evidence. More importantly, the test assumes a static, constant hedge ratio—an assumption that often fails over multi-year periods.

### 2.3 Johansen Test

The Johansen test (1988, 1991) is the multivariate generalization. It estimates a Vector Error Correction Model (VECM):

```
ΔX_t = Π · X_{t-1} + Σ_{j=1}^{p-1} Γ_j · ΔX_{t-j} + μ + ε_t
```

where X_t is an N-dimensional vector of log prices. The rank of the matrix Π determines the number of cointegrating relationships:

- **Rank 0**: No cointegration. ΔX_t is the correct model (VAR in differences).
- **Rank r (0 < r < N)**: r cointegrating vectors exist. The matrix decomposes as Π = α · β', where β contains the r cointegrating vectors and α contains the adjustment speeds (error correction coefficients).
- **Rank N**: All series are stationary (unlikely for prices).

Two test statistics are available:

1. **Trace statistic**: Tests H₀ that there are at most r cointegrating vectors. Compares the trace of the matrix of eigenvalues.
2. **Maximum eigenvalue statistic**: Tests H₀ that there are exactly r cointegrating vectors vs. H₁ of r+1.

**Advantages over Engle-Granger:**
- Symmetric: treats all assets equally, no arbitrary choice of dependent variable.
- Handles N > 2 assets simultaneously, identifying multiple cointegrating relationships.
- Provides the full set of cointegrating vectors, enabling basket construction.
- More powerful when multiple cointegrating relationships exist.

### 2.4 Ornstein-Uhlenbeck Process

Once a cointegrated spread z_t is identified, its dynamics are typically modeled as an **Ornstein-Uhlenbeck (OU) process**—the continuous-time version of a mean-reverting AR(1). The stochastic differential equation is:

```
dz_t = θ(μ - z_t) dt + σ dW_t
```

where:
- **θ > 0** is the **speed of mean reversion** (also called the drift rate). Higher θ means faster reversion.
- **μ** is the **long-run mean** (equilibrium level).
- **σ** is the **diffusion coefficient** (volatility of the spread).
- **W_t** is a standard Brownian motion.

The stationary distribution of z_t is Gaussian: z_t ~ N(μ, σ²/(2θ)).

**Half-life of mean reversion:** The expected time for the spread to cover half the distance from its current level back to μ is:

```
H = ln(2) / θ
```

This is the single most practically important quantity for medium-frequency stat arb. If H = 5 days, the strategy needs holding periods of approximately 5–15 days to capture the reversion; if H = 60 days, the strategy operates more slowly and faces more turnover and opportunity cost.

**Discrete-time estimation:** In discrete time (daily data), the OU process corresponds to an AR(1):

```
z_t = α + φ · z_{t-1} + ε_t,   ε_t ~ N(0, σ_ε²)
```

The parameter mapping is:
- φ̂ corresponds to e^{-θΔt}, so θ̂ = -ln(φ̂) / Δt (with Δt = 1 for daily)
- μ̂ = α̂ / (1 - φ̂)
- σ̂ = σ_ε / √(1 - φ̂²) (unconditional std of the spread)
- Half-life: H = ln(2) / (-ln(φ̂))

**Important calibration caveats:**

1. The estimator for θ has substantial upward bias and high variance. Even with 10,000 observations, the estimate can be unreliable. This is not a bug—it reflects the genuine difficulty of measuring mean reversion speed from finite samples.
2. When the true θ is small (slow reversion), estimates become unstable and can even be negative. Treat very long estimated half-lives with skepticism; they may indicate a non-cointegrated pair rather than slow cointegration.
3. At least 20 mean-reversion cycles (spread crossings of the mean) or at least one year of daily data are needed for reliable estimation.
4. The Doob exact simulation formula provides more accurate parameter estimates than the naive Euler discretization.

### 2.5 The Gatev-Goetzmann-Rouwenhorst (2006) Study

The seminal academic validation of pairs trading is Gatev, Goetzmann, and Rouwenhorst (2006), published in The Review of Financial Studies. Their study:

- Used daily data from 1962 to 2002 on US equities.
- Employed the **distance method**: pairs selected by minimum sum-of-squared-differences on normalized cumulative return paths over a 12-month formation period.
- Traded pairs during a 6-month trading period when the spread exceeded 2 historical standard deviations.
- Found average annualized excess returns of up to 12% for top-20 pair portfolios.
- Showed profitability survived conservative transaction cost estimates of ~83 basis points per roundtrip.
- Identified that returns were highest in periods of high dispersion and when pairs diverged due to idiosyncratic rather than systematic shocks.

This study established pairs trading as a genuine and long-lived anomaly. Subsequent research found returns decayed significantly post-2002, suggesting arbitrage capital had eroded the opportunity—a crowding dynamic consistent with the 2007 events.

---

## 3. Pair and Group Selection Methodology

### 3.1 The Selection Hierarchy

Good pair selection proceeds through three successive filters:

1. **Economic rationale filter**: Only consider pairs with genuine fundamental linkages.
2. **Statistical cointegration test**: Among economically linked pairs, select those with statistically significant long-run equilibria.
3. **Trading quality filter**: Among cointegrated pairs, select those with favorable OU parameters (short half-life, high signal-to-noise).

Skipping step 1 and running pure statistical tests over large universes produces spurious pairs—relationships that appear cointegrated by chance over a lookback window but have no economic basis for persistence.

### 3.2 Economic Rationale

Strong economic rationale exists in several categories:

**Same product, different wrapper:**
- Two ETFs tracking the same index (e.g., SPY vs. IVV, both tracking the S&P 500)
- A futures contract and its corresponding ETF (ES futures vs. SPY)
- ADRs vs. local shares for the same underlying company

**Sector peers with shared cost structure:**
- Airlines sharing the same fuel cost exposure (e.g., DAL/UAL)
- Integrated oil majors with similar production mixes (e.g., XOM/CVX)
- Regional banks with similar loan books and deposit franchises
- Semiconductor equipment companies with overlapping customer bases

**Upstream-downstream supply chain:**
- A steel producer and an auto manufacturer with significant steel input costs
- A commodity producer and a processor (e.g., CORN futures and an ethanol producer)

**Sister funds or asset classes:**
- Investment-grade corporate bond ETF vs. Treasury ETF at similar duration
- Gold futures vs. a gold mining equity ETF

The requirement is that the co-movement is mechanistic and ongoing—not historical coincidence.

### 3.3 Statistical Tests

**Formation window:** Use 12–24 months of daily data for the formation (training) period. This is long enough to observe several mean-reversion cycles but not so long that distant history dominates over recent structural changes.

**Engle-Granger procedure:**
1. Run OLS of log(P^A) on log(P^B) to get residuals.
2. Run OLS of log(P^B) on log(P^A) to get residuals in the other direction.
3. Apply ADF test to both sets of residuals using Engle-Granger critical values.
4. Select the direction with the stronger ADF statistic.
5. Require p-value below 0.05 as a minimum threshold; 0.01 is preferable for live trading.

**Johansen test (for baskets of 3+ assets):**
1. Determine lag order p via information criteria (AIC, BIC) on a VAR in differences.
2. Run Johansen trace and max-eigenvalue tests.
3. Require at least one cointegrating vector significant at the 5% level.
4. Use the cointegrating vector β as the basket weights.

**Half-life filter:**
After passing cointegration tests, fit the AR(1) to the spread residuals and compute the half-life H. Apply the following filters:
- H_min < H < H_max (see Section 11 for defaults)
- Pairs with H < H_min revert too fast to trade at medium frequency (HFT territory)
- Pairs with H > H_max are too slow—cost of carry and opportunity cost overwhelm the edge

**OU signal-to-noise ratio:**
The ratio σ_eq / σ (equilibrium std of the spread divided by its unconditional std) should be high, meaning the spread is volatile relative to its equilibrium std. A useful derived metric is the **expected profit per trade** which scales with the spread displacement relative to the half-life.

### 3.4 Correlation vs. Cointegration

Many practitioners mistakenly use rolling return correlation as a selection criterion. This is inadequate:

- **Correlation** measures co-movement of stationary increments (returns). Two I(1) series can have near-perfect return correlation yet be non-cointegrated because their price levels drift apart without bound.
- **Cointegration** requires a stable, bounded long-run price relationship.

For trading purposes, cointegration is the necessary condition. High correlation is often present in cointegrated pairs, but it is a consequence, not the cause, of the mean-reversion opportunity.

However, correlation remains useful as a rough first screen to reduce the pair universe before running computationally expensive cointegration tests: discard pairs with formation-period return correlation below a threshold (e.g., 0.7) as a pre-filter.

### 3.5 Pair Rotation and Formation/Trading Periods

The strategy operates on a rolling schedule:

- **Formation period**: The lookback window during which cointegration is estimated and pair quality is assessed. Typically 12 months of daily data.
- **Trading period**: The live trading window for selected pairs. Typically 3–6 months.
- **Re-evaluation frequency**: Monthly or quarterly, a fresh cointegration screen is run. Pairs that fail the re-test are graduated out and replaced with new candidates.

**Churn considerations:** Replacing too many pairs each period implies overfitting to the formation data. A well-specified strategy should have modest quarter-to-quarter turnover in the pair universe (20–30% replacement is acceptable; 70%+ suggests the selection criteria are too sensitive to recent noise).

---

## 4. Spread Construction

### 4.1 Log-Price vs. Raw-Price Spreads

The spread can be constructed using either raw prices or log prices:

**Raw price spread:**
```
z_t = P_t^A - β · P_t^B
```

**Log-price spread:**
```
z_t = log(P_t^A) - β · log(P_t^B)
```

Log prices are preferred for several reasons:

1. **Returns are additive in log space**: A 10% move in a $100 stock and a 10% move in a $10 stock represent the same economic event. The raw price spread conflates absolute dollar moves.
2. **Stationarity properties are better**: The log-price spread relates to the ratio P_t^A / (P_t^B)^β, which is dimensionless and more naturally stationary.
3. **Theoretical consistency**: If prices follow geometric Brownian motion, log prices are the appropriate domain for mean reversion analysis.
4. **Econometric equivalence**: If two price series are cointegrated, their log-prices are also cointegrated (with the same cointegrating vector), so nothing is lost by using logs.

The one exception is very short-maturity instruments or pairs where one component has a strict floor (e.g., a near-zero-yield bond ETF in a low-rate environment). In these cases the log-price may behave oddly and raw prices may be more appropriate.

### 4.2 Hedge Ratio Estimation: OLS

The simplest hedge ratio estimation is static OLS on the formation period:

```
log(P_t^A) = α + β · log(P_t^B) + ε_t
```

The OLS estimate β̂ minimizes the sum of squared residuals over the formation period. The spread is then:

```
z_t = log(P_t^A) - β̂ · log(P_t^B) - α̂
```

**Properties of OLS:**
- Simple, interpretable, and fast.
- Assumes the cointegrating vector is constant over time.
- The estimated β̂ depends on which variable is the dependent. Running A on B gives a different β than running B on A.
- Appropriate for pairs where the relationship is genuinely stable over the formation period.

**When OLS fails:**
- If the pair undergoes a gradual structural change in the ratio (e.g., due to changing capital structures, industry dynamics), the static hedge ratio will lag, producing a poorly conditioned spread that does not revert cleanly.
- In periods of high volatility, OLS estimates become noisy.

### 4.3 Hedge Ratio Estimation: Rolling OLS

Rolling regression applies OLS over a sliding window of fixed length W (e.g., 60 days):

```
β̂_t = OLS(log(P_{t-W}^A ... P_t^A), log(P_{t-W}^B ... P_t^B))
```

The hedge ratio updates daily or weekly, allowing it to track slow structural changes. The spread at time t uses today's estimated hedge ratio:

```
z_t = log(P_t^A) - β̂_t · log(P_t^B) - α̂_t
```

**Trade-off:** Shorter windows make β̂_t more responsive to recent data but also more noisy, producing a chaotic spread. Longer windows are smoother but slower to adapt. A typical range is 30–90 days. Rolling regression can create spurious trading signals if the window is too short, as the hedge ratio itself becomes a source of noise that dominates the mean-reversion signal.

### 4.4 Hedge Ratio Estimation: Kalman Filter

The Kalman filter is the theoretically optimal approach when the hedge ratio is a latent (unobserved) variable that evolves over time. It treats the problem as a state space model:

**Observation equation (measurement model):**
```
y_t = F_t · θ_t + v_t,   v_t ~ N(0, V_t)
```

where y_t = log(P_t^A), F_t = [log(P_t^B), 1], θ_t = [β_t, α_t]', and V_t is the observation noise variance (calibrated to recent price-level volatility).

**State transition equation (process model):**
```
θ_t = θ_{t-1} + w_t,   w_t ~ N(0, W_t)
```

The hedge ratio is assumed to follow a random walk: today's ratio is yesterday's ratio plus small random perturbation. The process noise covariance W_t = δ/(1-δ) · I controls how quickly the ratio is allowed to change. Small δ (e.g., 10^{-4}) means the ratio changes slowly; large δ means faster adaptation.

**Kalman recursion (prediction step):**
```
θ_{t|t-1} = θ_{t-1|t-1}
R_{t|t-1} = R_{t-1|t-1} + W_t
```

**Kalman recursion (update step):**
```
e_t = y_t - F_t · θ_{t|t-1}            (innovation / forecast error)
Q_t = F_t · R_{t|t-1} · F_t' + V_t     (innovation variance)
K_t = R_{t|t-1} · F_t' / Q_t            (Kalman gain)
θ_{t|t} = θ_{t|t-1} + K_t · e_t
R_{t|t} = (I - K_t · F_t) · R_{t|t-1}
```

The **trading signal** at each time step is the normalized innovation:

```
s_t = e_t / √Q_t
```

This is equivalent to a z-score but with a self-updating variance that reflects the current predictive uncertainty. It is inherently "parameterless" in the sense that no fixed rolling window is required; the model continuously estimates its own uncertainty.

**Advantages over rolling OLS:**
- Handles non-stationary hedge ratios without introducing lookback window noise.
- Spreads constructed from Kalman-estimated hedge ratios are empirically more stationary and mean-reverting than rolling-OLS spreads.
- Provides a natural measure of uncertainty (√Q_t) that can scale position sizes.
- Does not require a burn-in period of fixed length; the posterior covariance converges automatically.

**Disadvantages:**
- Requires careful tuning of δ and V_t. Poor calibration can make the filter under-react (too static) or over-react (too noisy).
- Computationally slightly more complex, though still O(1) per time step.

### 4.5 Dollar Neutrality and Beta Neutrality

The spread constructed above is **share-neutral** (β shares of B for every 1 share of A), but it is not necessarily **dollar-neutral** or **market-beta-neutral**.

**Dollar neutrality:** Ensure the dollar value of the long leg equals the dollar value of the short leg. This eliminates the PnL impact of overall market moves on the dollar notional of the trade.

**Beta neutrality:** Residual market beta in the pair can survive even after dollar-neutral construction. If stock A has β_A = 1.3 and stock B has β_B = 0.9, a dollar-neutral long/short still has net market exposure. To achieve beta neutrality, weight the legs so that:

```
w_A · β_A = w_B · β_B
```

This requires knowing β_A and β_B (typically from the most recent 60-day rolling regression against the market), and may produce a hedge ratio different from the cointegration hedge ratio. In practice, use the cointegration ratio for spread construction and the beta-neutrality constraint for position sizing.

---

## 5. Signal Generation

### 5.1 Z-Score Construction

The z-score is the primary entry and exit signal. It standardizes the spread by its recent mean and standard deviation:

```
z-score_t = (z_t - μ_t) / σ_t
```

where:
- z_t is the current spread value (log(P_t^A) - β̂ · log(P_t^B))
- μ_t is the rolling mean of the spread over a lookback window L (typically 20–60 days)
- σ_t is the rolling standard deviation of the spread over the same window L

For the Kalman filter approach, the z-score is replaced by the normalized innovation s_t = e_t / √Q_t, which automatically adapts to changing spread volatility.

The z-score has the attractive property of being stationary even if the underlying spread has a slow drift, provided the rolling window is short enough to track the drift but long enough to produce a stable estimate.

### 5.2 Half-Life and Its Role in Parameter Selection

The estimated half-life H fundamentally governs all timing parameters:

| Parameter | Relationship to H |
|-----------|-------------------|
| Rolling mean window (L) | 1–2× H |
| Rolling std window | 1–2× H |
| Expected holding period | 1–2× H |
| Maximum holding period (stop on time) | 3–5× H |

If H is 5 days, use a 5–10 day rolling window and expect to hold for 5–10 days. If H is 20 days, use a 20–40 day rolling window and expect to hold for 20–40 days.

**Practical filtering:** Pairs whose estimated H is less than 2 days or greater than 30 days are generally excluded for medium-frequency stat arb. Below 2 days, the opportunity is in HFT territory; above 30 days, the carry cost and opportunity cost erode the edge.

### 5.3 Entry Logic

**Standard z-score thresholds:**

Enter a long-spread position (long A, short B) when the z-score falls below **-z_entry** (spread is abnormally cheap).
Enter a short-spread position (short A, long B) when the z-score rises above **+z_entry** (spread is abnormally expensive).

Common values for z_entry: 1.5 to 2.5, with 2.0 as the most common default. Research by Gatev et al. used 2.0 standard deviations. Some researchers have found optimal entry thresholds as low as 1.42 depending on the OU parameters.

**Theoretical basis for threshold selection:**

For a given OU process with known parameters (θ, μ, σ), the optimal entry and exit thresholds can be derived analytically from an optimal stopping problem. The optimal threshold balances the probability of convergence (higher when spread is more extreme) against the expected time to convergence (longer when spread is more extreme, which increases carry cost and time value). In practice, OU parameters are estimated with error, so theoretical optima are used as guides rather than precise prescriptions.

**Conditional entry filters:**

Beyond the z-score threshold, additional conditions can filter false positives:
- Require the z-score to be moving in the convergence direction (momentum confirmation)
- Require cointegration p-value to remain below 0.05 in real-time rolling tests (pair health check)
- Require pair to be in a "mean-reverting regime" as classified by an HMM regime detector
- Reject entries if aggregate market VIX is above a crisis threshold (in stress regimes, relationships break more frequently)
- Reject entries if the spread has been widening continuously for more than T days without reversal (suggests structural break rather than temporary dislocation)

### 5.4 Exit Logic

**Mean reversion exit:** Close both legs when the z-score crosses back through **z_exit** toward zero. Common values: z_exit = 0.0 to 0.5. Exiting exactly at zero captures the full mean reversion but risks giving back gains if the spread overshoots. Exiting at 0.5 takes partial profit while leaving some upside.

**Stop-loss exit:** Close both legs if the z-score continues to move against the position and reaches **z_stop**. Common values: z_stop = 3.0 to 4.0. Stop-losses are critical because a pair undergoing a structural break will produce an ever-widening z-score with no convergence. Without a stop, losses can be severe.

**Time stop:** If a position has been open for longer than max_holding_days without triggering either the profit exit or the stop-loss, close the position. This prevents capital lockup in slow-reverting pairs that may be experiencing a quiet structural change.

**Re-entry after stop:** After a stop-loss, impose a cooling-off period before allowing new entries in the same pair. This prevents compounding losses on a broken relationship.

### 5.5 Signal Scaling

Rather than binary on/off signals, positions can be scaled continuously with the z-score:

```
position_size_t ∝ |z-score_t| × volatility_scaling
```

where volatility_scaling = target_dollar_vol / current_spread_vol. This means larger positions when the z-score is more extreme and when volatility is low, both of which increase expected return. This approach is similar to the signal scaling used in multi-factor risk premia strategies.

---

## 6. Portfolio Construction

### 6.1 Universe and Number of Pairs

A medium-frequency stat arb book typically holds 20–100 active pairs simultaneously. Fewer than 20 creates idiosyncratic concentration (the failure of one pair hurts significantly). More than 100 pairs dilutes the selection quality—the marginal pair is likely weak—and creates execution complexity.

For a U.S. equity book, the eligible universe is the Russell 1000 or S&P 500 (large-cap, liquid). The cointegration screen narrows this to a manageable candidate set, from which the top pairs by statistical quality are selected.

### 6.2 Pair Allocation

**Equal dollar allocation** per pair is the simplest approach: divide the gross capital budget equally across all active pairs. This is the standard in the academic literature and provides a transparent baseline.

**Volatility-scaled allocation:** Allocate capital inversely proportional to the pair's spread volatility, so that each pair contributes approximately equal risk (in terms of spread PnL volatility). This is analogous to risk parity at the pair level:

```
allocation_i ∝ 1 / σ_{spread,i}
```

**Kelly-based allocation:** In theory, the Kelly criterion maximizes long-run geometric return by sizing each bet proportional to edge divided by variance. For a portfolio of correlated bets (pairs), the full Kelly solution requires the inverse of the correlation matrix of pair PnL returns, which is sensitive to estimation error. In practice, fractional Kelly (50% Kelly or less) is used to dampen the impact of estimation error on sizing.

**Practical constraint:** Dollar-neutral at the pair level does not guarantee dollar-neutral at the portfolio level if pairs overlap (if stock X appears in both pair 1 as the long leg and pair 3 as the short leg, the net exposure to X is non-zero). Track gross and net exposure to individual names and impose single-name concentration limits (e.g., no more than 5% of gross capital in any single stock across all pairs).

### 6.3 Correlation Between Pairs

The diversification benefit of holding K pairs depends critically on the cross-pair PnL correlation. If all pairs are highly correlated (because they all share exposure to the same risk factor, or because they hold overlapping names), a single adverse market event will simultaneously open all spreads without convergence—the 2007 quant crisis in miniature.

**Sources of cross-pair correlation:**
- Sector concentration: if 70% of pairs are in financials, a sector-specific event creates correlated losses
- Factor overlap: multiple pairs with the same directional factor exposure (e.g., all pairs are long low-beta, short high-beta)
- Name overlap: individual stocks appearing in multiple pairs
- Common liquidity source: all pairs sourcing borrow from the same intermediary

**Diversification targets:**
- Spread pairs across at least 5 distinct sectors (GICS Level 1 or Level 2)
- Average pairwise PnL correlation below 0.3
- Single stock name in no more than 3 active pairs; net exposure per name below 2% of gross

**Monitoring:** Compute the rolling pairwise correlation of daily pair PnL across all active pairs. A sudden spike in average pairwise correlation (from 0.1 to 0.5 in a week) is a warning signal of factor crowding or a common adversarial event. This should trigger position reduction.

### 6.4 Gross Leverage

Pairs trading books typically run at 2× to 6× gross leverage (gross long + gross short divided by equity). Lower leverage reduces return but also reduces drawdown in adverse regimes. Higher leverage amplifies both. The sweet spot depends on the Sharpe ratio of the strategy before leverage: if the unlevered Sharpe is 1.5, modest leverage is rational; if the unlevered Sharpe is 0.5, leverage is dangerous.

---

## 7. Risk Management

### 7.1 Single-Pair Stop-Loss

The stop-loss on an individual pair is the primary risk control. As described in Section 5.4, it triggers when the z-score reaches z_stop (typically 3–4 standard deviations). The logic is:

- A z-score of 3–4 is a rare event under the null hypothesis that the pair is genuinely cointegrated and well-estimated.
- If the z-score has reached this extreme level, either (a) we are experiencing an exceptional but temporary dislocation (in which case the position will reverse profit after the stop), or (b) the relationship has broken structurally (in which case the stop prevents further loss).
- The cost of incorrectly stopping out a good position is limited: the position can be re-entered after the cooling-off period if the z-score subsequently reverts.
- The benefit of correctly stopping out a broken pair is survival of the book.

**Stop calibration:** The stop should be set wide enough that normal spread volatility does not trigger it spuriously (otherwise Sharpe degrades from stop-out churn), but tight enough that a structural break is caught before losses compound. Backtesting on the formation data (with out-of-sample validation) should show that stops trigger less than 5–10% of trades but save significant capital when triggered.

### 7.2 Time-Based Position Limits

Each pair position should have a maximum holding period defined as max_holding_days (typically 3–5× the estimated half-life). If a position has not closed by this deadline, it is liquidated regardless of z-score. This prevents:
- Capital lockup in slow-reverting pairs
- Compounding carrying costs on large positions
- Hidden structural breaks that manifest as very slow spread widening

### 7.3 Correlation Monitoring

Monitor the rolling cross-pair correlation of pair PnL at the portfolio level. If average pairwise correlation spikes above 0.5 (from a normal level around 0.1–0.2), the book has become a covert factor bet. Responses:
- Reduce gross exposure on all pairs proportionally.
- Identify and eliminate pairs responsible for the correlation spike.
- Avoid entering new pairs until correlation normalizes.

### 7.4 Cointegration Health Monitoring

During live trading, continuously re-test cointegration on active pairs using a rolling window. If the ADF p-value deteriorates above 0.10 on a pair that has an open position:
- Do not enter new positions in this pair.
- Consider exiting existing positions if the health continues to deteriorate.
- Formally drop the pair from the universe if the p-value rises above 0.20.

A structural break test (Chow test, CUSUM, or QLR test) can detect parameter instability in the cointegrating relationship. The QLR (Quandt likelihood ratio) test is particularly useful—it tests for structural breaks at unknown dates over the estimation sample, producing a supremum statistic that indicates the probability of regime change.

### 7.5 Portfolio-Level Risk Limits

| Risk Metric | Limit |
|-------------|-------|
| Max gross leverage | 6× NAV |
| Max net market exposure | ±10% of NAV |
| Max single-name net exposure | 2% of NAV |
| Max single-sector net exposure | 15% of NAV |
| Max daily portfolio-level drawdown | 2% of NAV (triggers 50% de-gross) |
| Max peak-to-trough drawdown | 8% of NAV (triggers full book liquidation review) |
| Max open pairs in same sector | 20% of total pairs |

### 7.6 Crowding Monitoring

Track the following signals for crowding risk on a daily basis:

1. **Cross-pair PnL correlation**: As described above, spike above 0.5 is a warning.
2. **Aggregate short interest**: If short interest in the pairs' short legs rises significantly (>20% increase in one month), the trade is becoming crowded on the short side.
3. **13F overlap**: Quarterly, assess how many other known stat arb funds hold the same pair components (using public 13F filings). High overlap does not require immediate action but raises the risk estimate for a correlated unwind.
4. **Market impact on entry**: If slippage on pair entries is increasing without a corresponding increase in individual stock volatility, it suggests more capital is trying to enter the same positions.

---

## 8. Execution Considerations

### 8.1 Holding Period and Turnover

Medium-frequency stat arb has holding periods of 1–20 days and typical round-trip turnover of 300–500% of gross notional per year. This turnover structure means transaction costs are a primary determinant of live versus theoretical performance.

A pair entering at z = ±2.0 and exiting at z = 0 generates one round-trip trade. If the half-life is 5 days and the average holding period is 7 days, and the book turns over all pairs approximately 4 times per year per pair, the annual number of round trips per pair is approximately 4. With 50 pairs, that is 200 round trips per year at the book level.

### 8.2 Bid-Ask Spread Impact

Each round-trip trade involves crossing the bid-ask spread on both legs (long leg entry, short leg entry, long leg exit, short leg exit). For a pair involving two large-cap stocks with typical spreads of 1–2 basis points each leg:

```
Round-trip cost ≈ 4 × (average bid-ask spread / 2) ≈ 4 × 1 bps = 4 bps (best case)
```

For mid-cap stocks with 5–10 bp spreads, the round-trip cost rises to 20–40 bps per pair. Academic research (Gatev et al.) estimated effective round-trip costs of ~83 basis points including market impact. Given typical pairs trade PnL of 50–200 bps per round trip (depending on entry z-score and spread volatility), transaction costs at this level consume a substantial fraction of gross alpha.

**Break-even spread:** For a strategy to be profitable after costs, the expected gross profit per trade must exceed the round-trip cost. If gross alpha per trade is 80 bps and costs are 83 bps, the strategy loses money. This calculation makes clear that pair selection (focusing on large-cap liquid stocks with tight spreads) and entry threshold (higher z-scores generate larger expected profit) are critical profit drivers.

### 8.3 Market Impact

For large positions, market impact—the price movement caused by the trader's own activity—is an additional cost beyond the bid-ask spread. Empirically, market impact scales approximately with the square root of participation:

```
impact ≈ σ_daily × (Q / ADV)^{0.5}
```

where Q is the order size and ADV is the average daily volume. For a pair trade that represents 2% of ADV in each stock, impact is approximately 14% of the daily standard deviation per leg.

To mitigate market impact:
- Execute via limit orders rather than market orders where possible.
- Spread execution over 30–60 minutes rather than trading at the open print.
- Use VWAP or TWAP algorithms for larger positions.
- Size positions so that the larger leg is at most 5–10% of ADV.

### 8.4 Short-Selling Costs

The short leg of each pair incurs a short-selling cost: the securities lending fee (the rebate relative to the fed funds rate that must be paid to borrow shares). For common large-cap stocks (general collateral), this fee is typically 10–50 basis points per year. For hard-to-borrow names, it can be 5–30% per year, making the short leg economically impractical.

**Borrow availability:** Pairs should be screened for borrow availability. If either leg is on the restricted list or has an extreme lending fee, the pair should be excluded from the live book regardless of its statistical quality.

**Short-sale restrictions:** In periods of extreme market stress, regulators sometimes impose temporary restrictions on short selling. This is a tail risk for stat arb books with large short positions. In 2008, the SEC banned short selling in financial stocks for three weeks, causing severe losses for books with financial pairs.

### 8.5 Capacity Constraints

Statistical arbitrage is capacity-constrained by construction. The edge comes from exploiting small, temporary mispricing opportunities in the limit order book. As AUM grows:

1. **Position sizes grow** relative to the float of individual stocks. Market impact per unit of alpha rises.
2. **The trade itself moves the price**. As the book enters a pair, the act of buying A and selling B pushes A's price up and B's price down, partially eliminating the spread before convergence occurs naturally.
3. **Competitors observe similar signals**. Other stat arb funds seeing the same z-score signal enter simultaneously, amplifying market impact and reducing available profit.

The practical capacity of a single pairs book is typically in the range of $500 million to $2 billion of gross notional, depending on the specific universe and liquidity profile. Beyond this range, returns per dollar of capital decline steeply. Renaissance Technologies and similar large-scale stat arb operators address this through extreme strategy diversification, superior execution technology, and proprietary signals unavailable to competitors.

---

## 9. Regime Sensitivity

### 9.1 Trending Markets Kill Mean Reversion

Statistical arbitrage relies on mean reversion. In strongly trending markets—where broad market indices are moving decisively in one direction with low cross-sectional dispersion—individual stock returns are driven primarily by systematic factors rather than idiosyncratic value. The spread between even genuinely cointegrated pairs can widen persistently during such regimes because:

- Both stocks are predominantly tracking the same market factor.
- Idiosyncratic noise is overwhelmed by systematic moves.
- Other stat arb funds see widening spreads and de-risk, creating further market impact in the adverse direction.

A sustained bull or bear trend (e.g., 2017 or 2022 in US equities) is particularly challenging for pairs books. The cross-sectional correlation across stocks rises, pairs spreads widen together, and the book faces correlated drawdowns across many positions simultaneously.

**Regime detection approaches:**
- **Realized dispersion**: Measure the cross-sectional standard deviation of stock returns over a rolling window. High dispersion favors stat arb (stocks are moving independently); low dispersion warns of trending regime.
- **Hurst exponent**: A Hurst exponent H < 0.5 indicates mean reversion; H > 0.5 indicates trending. Computed on the spread or on an aggregate index.
- **Hidden Markov Models (HMM)**: A two-state HMM on aggregate market returns and volatility can classify regimes as "mean-reverting/ranging" vs. "trending." In the trending state, reduce exposure by 50–75%.
- **VIX level and term structure**: High absolute VIX (>30) combined with contango suggests stress regime. Inverted VIX term structure (backwardation, front > back) signals acute crisis.

### 9.2 Liquidity Crises

Liquidity crises—2008 GFC, March 2020 COVID crash—are the worst environment for stat arb because:

1. Bid-ask spreads widen dramatically, raising execution costs.
2. Borrow availability collapses for many names, creating forced unwinds of short legs.
3. Forced selling by levered funds creates correlated, non-mean-reverting spread moves.
4. Historical cointegration relationships break because the liquidity shock affects names differently based on their investor base, not their fundamentals.

In such environments, the correct response is aggressive position reduction and avoidance of new entries. A tail-risk hedge (e.g., long VIX calls or long puts on the index) can partially offset the market-impact losses from forced liquidation by competitors.

### 9.3 Index Rebalancing and Forced Flows

Index reconstitution events create predictable but transient dislocations:

- When a stock is added to the S&P 500, passive funds must buy it simultaneously, often on or around the effective date. The stock's price typically rises 3–5% in anticipation and then partially reverts.
- When a stock is deleted, passive funds must sell it, creating a temporary discount.
- Russell index reconstitution (annual, typically at end of June) involves hundreds of stocks, creating broad-based forced flows for a week.

These flows create short-term stat arb opportunities, particularly in pairs where one component is being added/deleted and the other is not. The pair spread widens due to forced buying/selling and then mean-reverts once the rebalancing is complete. The risk is that the forced flow is larger and more persistent than expected, or that other arbitrageurs preempt the trade.

### 9.4 ETF Premium/Discount Arbitrage

ETFs can trade at a premium or discount to their Net Asset Value (NAV). The creation/redemption mechanism is designed to eliminate these dislocations:

- **At a premium**: Authorized Participants (APs) buy the basket of underlying securities, deliver them to the ETF issuer in exchange for newly created ETF shares, then sell those shares in the open market. This reduces the premium.
- **At a discount**: APs buy ETF shares on the open market, redeem them from the issuer for the underlying basket, then sell the basket. This reduces the discount.

This mechanism works continuously in normal markets, keeping premiums/discounts below 10 basis points for liquid ETFs. However, in stressed markets, the arbitrage can break down:

- During the March 2020 COVID crash, some bond ETFs (e.g., LQD, HYG) traded at discounts of 3–5% for several days because APs were unwilling to hold the underlying bonds while markets were dislocated.
- For international ETFs, there is a time-zone mismatch between the ETF's trading hours and the local market hours of the underlying. This creates predictable intraday premiums/discounts.

**Stat arb on ETF premium/discount:** The cleanest trade is long the discount ETF / short the constituent basket (or a proxy with high correlation). This requires the ability to construct the basket trade, which is operationally complex for large-universe ETFs but tractable for sector ETFs with 20–50 constituents.

---

## 10. Key Risks and Failure Modes

### 10.1 Pair Break (Structural Change)

The most common failure mode is the **pair break**: the cointegrating relationship that existed during the formation period ceases to hold in the trading period.

**Causes:**
- **Mergers and acquisitions**: If one stock is acquired, the pair relationship changes permanently.
- **Business model shift**: One company divests a major division or enters a new industry, changing its fundamental exposure.
- **Balance sheet restructuring**: A leveraged recapitalization changes a company's risk profile significantly.
- **Regulatory change**: New regulation disproportionately affects one side of the pair.
- **Macroeconomic regime shift**: An interest rate regime change can alter the relative pricing of sectors that had a stable relationship under the previous regime.

**Detection:** Monitor rolling ADF p-values, rolling hedge ratio stability, and apply the QLR structural break test. A widening spread that fails to revert within 2× the estimated half-life is a strong warning signal.

**Response:** Stop losses (Section 7.1) are the primary defense. A secondary defense is the time stop (Section 5.4). The cooling-off period after a stop prevents re-entry into a broken pair.

### 10.2 Crowding and the August 2007 Quant Crisis

The August 2007 event is the defining historical failure mode for statistical arbitrage. It occurred over the trading week of August 7–9, 2007, before the mainstream awareness of the subprime crisis.

**Mechanism:**

A large multi-strategy quant fund (widely attributed to Goldman Sachs's Global Alpha fund, though the identity was never confirmed) needed liquidity. To raise cash, it began unwinding its most liquid equity market-neutral positions—its statistical arbitrage book. This selling moved prices against positions held by every other stat arb fund that had independently constructed similar portfolios. The losses at those funds triggered their own stop-losses and risk limits, causing further forced selling. The self-reinforcing spiral (loss → forced liquidation → further loss) spread across the quant fund community.

**Scale of impact:** Simulated factor strategies lost 4–7% in three trading days (August 7–9) while the S&P 500 was essentially flat. Cross-fund PnL correlation spiked to approximately 0.85 from a normal level of 0.35. Goldman Sachs's Global Equity Opportunities fund lost more than 30% of its value. Goldman Sachs Asset Management eventually closed both Global Alpha and Global Equity Opportunities.

**Recovery:** By September, most quant funds had partially recovered their August losses as the forced selling subsided and spreads reverted. The initial losses contained no fundamental information—they were purely a liquidity-driven crowding event. Funds with sufficient capitalization and no forced redemptions survived; funds that faced redemptions during the crisis were forced to crystallize losses.

**Lessons:**
1. Crowding risk is invisible to standard risk models because standard models estimate covariance from historical data where crowding was not active.
2. Low-correlation strategies (0.1 historical cross-pair correlation) can experience 0.85 correlation during unwinds.
3. Liquidity reserves and moderate leverage are survival tools. Funds with 2× gross leverage survived; funds at 8–10× were forced to liquidate at the worst time.
4. Diversification across factor implementations reduces overlap with competitors.
5. Position limits based on ADV are essential—if your position is a meaningful fraction of daily volume, you cannot exit without moving the market against yourself.

### 10.3 Regime Change

A statistical relationship that was cointegrated for 10 years can cease to be cointegrated permanently if the underlying economic structure changes. This is distinct from a temporary pair break—it is a regime change in the fundamental pricing of the assets.

Examples:
- Post-2008, the cointegration between bank stocks broke down because the regulatory and balance-sheet differences between institutions became more important than their common business exposure.
- The oil price crash of 2014–2016 permanently altered the cointegration structure within energy sector pairs, as many pairs' relative economics depended on a crude price above $60.
- The shift to near-zero interest rates from 2009–2021 altered rate-sensitive pairs (utilities, REITs) in ways not anticipated by pre-financial-crisis models.

**Defense:** Formation periods should not be too long (max 24 months). Regular re-testing and pair rotation provides an organic defense against using stale relationships. Macro regime indicators can trigger blanket exclusion of sector pairs most exposed to specific macro variables.

### 10.4 Model Overfitting

The statistical tests used in pair selection have well-known finite-sample biases. Running ADF tests across 500,000 potential pairs in the Russell 1000 will produce many pairs that appear cointegrated by chance (false positives at the 5% level). With 500,000 pairs and a 5% false positive rate, 25,000 pairs will appear cointegrated even if no true cointegration exists.

**Defenses:**
- Apply stricter significance levels (1% rather than 5%).
- Require economic rationale as a prerequisite for statistical testing.
- Use out-of-sample testing: train on years 1–5, test on years 6–7. Discard pairs that do not show statistically significant performance in the out-of-sample period.
- Limit the pair universe to a small number (20–100) to reduce multiple comparison problems.

### 10.5 Short-Squeeze Risk

The short legs of pairs positions are exposed to short squeezes: a rapid price increase driven by short-covering rather than fundamental news. A short squeeze can occur when short interest is very high, borrow becomes scarce or recalled, and a positive catalyst (even small) forces short-sellers to cover simultaneously.

Short squeezes create extremely adverse mark-to-market on the short leg without any corresponding fundamental improvement. The z-score widens dramatically, potentially triggering stop-losses at the worst time.

**Mitigation:** Screen short legs for borrow availability and cost weekly. Avoid shorting names with short interest above 20% of float. Monitor stock-specific borrow cost; a spike from 50 bps to 500 bps per year is a warning that a squeeze is building.

---

## 11. Parameters and Tunable Knobs

### 11.1 Pair Selection Parameters

| Parameter | Description | Default | Reasonable Range | Notes |
|-----------|-------------|---------|-----------------|-------|
| `formation_window_days` | Length of historical data used for cointegration testing | 252 (1 year) | 126–504 | Shorter = more adaptive, more false positives. Longer = more stable, slower to detect breaks. |
| `coint_pvalue_threshold` | Maximum ADF p-value to include a pair | 0.05 | 0.01–0.10 | Use 0.01 for conservative books. |
| `min_correlation` | Minimum return correlation as pre-filter | 0.70 | 0.50–0.85 | Pre-screen before running costly coint tests. |
| `hlife_min_days` | Minimum half-life to trade | 2 | 1–5 | Below this, HFT territory. |
| `hlife_max_days` | Maximum half-life to trade | 30 | 10–60 | Above this, carry cost erodes edge. |
| `max_pairs` | Maximum number of simultaneously active pairs | 50 | 10–150 | Balance diversification vs. selection quality. |
| `economic_filter_required` | Require pair to be in same sector/supply chain | True | Boolean | Reduces spurious pairs significantly. |

### 11.2 Spread and Hedge Ratio Parameters

| Parameter | Description | Default | Reasonable Range | Notes |
|-----------|-------------|---------|-----------------|-------|
| `hedge_ratio_method` | OLS / rolling_OLS / Kalman | `kalman` | Enum | Kalman preferred for non-stationary relationships. |
| `rolling_ols_window` | Window for rolling OLS in days | 60 | 30–120 | Shorter = more responsive but noisy. |
| `kalman_delta` | Kalman process noise parameter (δ) | 1e-4 | 1e-5 to 1e-2 | Higher = faster adaptation of β. |
| `kalman_obs_noise` | Kalman observation noise variance (V_t) | 1e-3 | 1e-4 to 1e-2 | Tune to log-price volatility. |
| `use_log_prices` | Compute spread in log-price space | True | Boolean | Strongly preferred; only disable for instruments with floor prices. |

### 11.3 Signal Generation Parameters

| Parameter | Description | Default | Reasonable Range | Notes |
|-----------|-------------|---------|-----------------|-------|
| `zscore_lookback` | Rolling window for z-score mean/std | 30 | 10–60 | Rule of thumb: 1–2× estimated half-life. |
| `entry_zscore` | Z-score threshold to open a position | 2.0 | 1.5–3.0 | Higher = fewer trades, higher per-trade profit. |
| `exit_zscore` | Z-score threshold to close a profit | 0.0 | -0.5 to 0.75 | 0 captures full mean reversion; 0.5 takes partial profit. |
| `stoploss_zscore` | Z-score threshold to cut loss | 3.5 | 3.0–5.0 | Must be wide enough to avoid false triggers but tight enough to catch breaks early. |
| `max_holding_days` | Time-based position stop in days | 90 | 30–180 | Rule of thumb: 3–5× estimated half-life. |
| `entry_momentum_confirm` | Require z-score moving toward 0 before entry | False | Boolean | Reduces early entries on still-widening spreads at cost of higher z-score on average entry. |
| `reentry_cooldown_days` | Days after stop-loss before new entries allowed | 10 | 5–30 | Prevents repeated losses on broken pairs. |

### 11.4 Portfolio Construction Parameters

| Parameter | Description | Default | Reasonable Range | Notes |
|-----------|-------------|---------|-----------------|-------|
| `target_pair_vol_bps_daily` | Target daily volatility per pair in bps | 30 | 15–60 | Determines per-pair allocation from spread volatility. |
| `max_gross_leverage` | Maximum gross leverage (gross / NAV) | 4.0 | 2.0–8.0 | Above 6× creates severe crowding and margin risk. |
| `max_net_market_exposure_pct` | Maximum net beta exposure as % of NAV | 10 | 5–20 | Keep market-neutral. |
| `max_single_name_exposure_pct` | Max exposure to any single stock as % of NAV | 3 | 1–5 | Prevents name concentration. |
| `max_sector_concentration_pct` | Max fraction of pairs in any one GICS sector | 25 | 15–40 | Prevents sector crowding. |
| `max_pairs_per_name` | Max number of pairs any single stock can appear in | 3 | 1–5 | Limits name-level hidden concentration. |

### 11.5 Risk Management Parameters

| Parameter | Description | Default | Reasonable Range | Notes |
|-----------|-------------|---------|-----------------|-------|
| `portfolio_drawdown_trigger_pct` | Daily portfolio loss that triggers 50% de-gross | 2.0 | 1.0–3.0 | Daily-level trip wire. |
| `peak_to_trough_limit_pct` | Cumulative drawdown that triggers review/full de-gross | 8.0 | 5.0–15.0 | Strategy-level circuit breaker. |
| `cross_pair_correlation_warning` | Average pairwise PnL correlation threshold for warning | 0.4 | 0.3–0.6 | Trigger position review and reduction. |
| `coint_health_retest_days` | Frequency of rolling coint retest on active pairs | 5 | 1–20 | More frequent = earlier warning of breaks. |
| `coint_exit_pvalue` | ADF p-value above which active pair positions are exited | 0.20 | 0.10–0.30 | Wider band avoids excessive pair churn. |
| `vix_blackout_level` | VIX level above which no new entries permitted | 35 | 25–50 | During crises, avoid entering into potentially broken regimes. |

### 11.6 Execution Parameters

| Parameter | Description | Default | Reasonable Range | Notes |
|-----------|-------------|---------|-----------------|-------|
| `max_adv_participation` | Max position size as fraction of ADV | 5% | 1%–10% | Limits market impact. |
| `execution_window_minutes` | Time window over which to spread execution | 30 | 5–60 | Reduce impact vs. execution risk trade-off. |
| `max_borrow_cost_bps_annual` | Maximum acceptable annual borrow cost for short leg | 200 | 50–500 | Above this, pair is excluded. |
| `min_adv_millions` | Minimum ADV of each component in millions | 5 | 1–50 | Ensures basic liquidity for entry/exit. |
| `rebalance_frequency` | How often pair universe is reconstituted | Monthly | Weekly–Quarterly | More frequent allows faster dropping of broken pairs; more expensive in rebalancing costs. |

---

## Appendix: Key Academic References

1. **Engle, R.F. and Granger, C.W.J. (1987)**: "Co-integration and Error Correction: Representation, Estimation, and Testing." *Econometrica*, 55(2), 251-276. — The foundational paper establishing cointegration theory and the two-step test.

2. **Johansen, S. (1991)**: "Estimation and Hypothesis Testing of Cointegration Vectors in Gaussian Vector Autoregressive Models." *Econometrica*, 59(6), 1551-1580. — The multivariate cointegration test used for basket construction.

3. **Gatev, E., Goetzmann, W.N., and Rouwenhorst, K.G. (2006)**: "Pairs Trading: Performance of a Relative-Value Arbitrage Rule." *Review of Financial Studies*, 19(3), 797-827. — The landmark empirical study documenting pairs trading returns from 1962–2002.

4. **Lo, A. and Khandani, A. (2007/2011)**: "What Happened To The Quants In August 2007? Evidence from Factors and Transactions Data." *Journal of Financial Markets*, 14(1), 1-46. — Definitive academic analysis of the August 2007 quant crisis, the unwind hypothesis, and crowding dynamics.

5. **Avellaneda, M. and Lee, J-H. (2010)**: "Statistical Arbitrage in the U.S. Equities Market." *Quantitative Finance*, 10(7), 761-782. — The PCA-based residual mean reversion framework; establishes the s-score signal and empirically validates the approach across the U.S. equity market.

6. **Pole, A. (2007)**: *Statistical Arbitrage: Algorithmic Trading Insights and Techniques*. Wiley Finance. — Practitioner textbook covering the Morgan Stanley origins, spread construction, Kalman filter approaches, and operational considerations in depth.
