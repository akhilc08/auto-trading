# Reinforcement Learning for Trading Alpha — Strategy Specification

**Status:** Research & Design  
**Version:** 1.0  
**Domain:** Quantitative Trading / Execution / Portfolio Allocation  
**Classification:** Tier 3 — Complex Research Strategy

---

## Table of Contents

1. [Strategy Overview and Thesis](#1-strategy-overview-and-thesis)
2. [Academic Foundations](#2-academic-foundations)
3. [Where RL Works vs Where It Fails](#3-where-rl-works-vs-where-it-fails)
4. [MDP Formulation](#4-mdp-formulation)
5. [Algorithm Selection](#5-algorithm-selection)
6. [State Space Construction](#6-state-space-construction)
7. [Reward Function Design](#7-reward-function-design)
8. [Training Methodology](#8-training-methodology)
9. [Exploration Strategy](#9-exploration-strategy)
10. [Offline RL Approach](#10-offline-rl-approach)
11. [Portfolio Construction](#11-portfolio-construction)
12. [Risk Management](#12-risk-management)
13. [Model Monitoring and Retraining](#13-model-monitoring-and-retraining)
14. [Recommended Application Focus](#14-recommended-application-focus)
15. [Key Risks and Failure Modes](#15-key-risks-and-failure-modes)
16. [Parameters and Tunable Knobs](#16-parameters-and-tunable-knobs)

---

## 1. Strategy Overview and Thesis

### Honest Assessment

Reinforcement learning is not a general-purpose alpha engine for directional trading. The popular narrative — that an RL agent can learn to "beat the market" by interacting with historical price data — is largely unsupported by rigorous out-of-sample evidence. Most published results showing high Sharpe ratios in RL trading systems are backtests that suffer from lookahead bias, survivorship bias, overfitting to regime-specific data, or environments that model market frictions incorrectly.

The honest thesis is narrower and more defensible:

**RL is genuinely useful in finance for three specific problems where the problem structure maps cleanly onto the MDP framework:**

1. **Execution optimization** — minimizing implementation shortfall when liquidating or acquiring large positions (Almgren-Chriss style problems, TWAP/VWAP improvement)
2. **Portfolio allocation and dynamic rebalancing** — deciding target weights across a universe of assets over time, where the agent can condition on current portfolio state, risk exposure, and market regime
3. **Dynamic hedging** — managing derivatives books and option portfolios in the presence of transaction costs, where Black-Scholes delta is provably suboptimal

For pure directional alpha — predicting whether SPY closes up tomorrow — RL offers no systematic advantage over supervised learning or classical signal research, and introduces substantial additional complexity and failure modes.

### Why the Thesis Is Constrained

Financial markets are fundamentally different from the environments where RL has proven transformative (games, robotics, control systems). The key structural differences:

- **Non-stationarity**: Market regimes shift. A policy trained on 2015–2019 data may not generalize to 2020–2024. Unlike Atari or MuJoCo, the data-generating process changes in ways that are not predictable from the state representation.
- **Adversarial adaptation**: Other market participants observe patterns. A strategy that generates alpha will be arbitraged away — often within months for systematic signals. RL policies do not model this meta-game.
- **Sparse and noisy rewards**: Daily PnL is an extremely noisy reward signal. With low signal-to-noise ratios on financial data, RL agents often learn to exploit spurious correlations in the training period.
- **No safe exploration**: In robotics, a failed exploration step is recoverable. In trading, poor exploration decisions cause real capital losses. This eliminates the standard online RL paradigm for live deployment.
- **Limited data**: A decade of daily data provides roughly 2,500 training points. This is catastrophically insufficient for training deep neural networks without severe overfitting.

### What This Spec Covers

This spec designs a production-grade RL system targeting execution optimization as the primary application, with portfolio allocation as a secondary application. Dynamic hedging is noted as a proven use case but is scoped out of this system's initial implementation. Pure directional alpha generation via RL is explicitly excluded from the recommended scope.

---

## 2. Academic Foundations

### Core RL Theory Applied to Finance

**Merton's Portfolio Problem (1969/1971)** — The earliest formulation of portfolio choice as a continuous-time stochastic control problem, which is the conceptual ancestor of modern RL portfolio optimization. Merton showed analytically that the optimal policy in a GBM world is constant-fraction investment. RL methods are trying to solve the generalization of this where the dynamics are unknown.

**Almgren-Chriss (2000)** — "Optimal Execution of Portfolio Transactions" — established the mean-variance framework for optimal liquidation under linear market impact. This is the benchmark every RL execution optimizer must beat. Key insight: the optimal liquidation schedule is a function of risk aversion, time horizon, and market impact coefficients — parameters RL does not need to assume.

**Bertsimas and Lo (1998)** — Dynamic programming approach to optimal execution, showing that adaptive strategies outperform static schedules when the agent can observe market conditions.

### Key RL-for-Finance Papers

**Moody and Saffell (2001)** — "Learning to Trade via Direct Reinforcement" — early recurrent reinforcement learning for trading using the Sharpe ratio as the reward signal. Conceptually important but results do not generalize out of sample.

**Nevmyvaka, Feng, Kearns (2006)** — "Reinforcement Learning for Optimized Trade Execution" — one of the first serious empirical demonstrations of RL outperforming VWAP and TWAP in execution, using real Level 2 order book data. Results held out of sample. This remains one of the most credible demonstrations of RL in finance.

**Deng et al. (2016)** — "Deep Direct Reinforcement Learning for Financial Signal Representation and Trading" — applied deep RL with recurrent networks to futures trading. Important for establishing the state-space design literature.

**Buehler, Gonon, Teichmann, Wood (2019)** — "Deep Hedging" — demonstrated that deep RL can outperform Black-Scholes delta hedging in the presence of transaction costs. Widely cited; results have been substantially replicated. This is arguably the strongest empirical case for RL in finance.

**FinRL (Liu et al., 2020–2024)** — Open source RL for finance framework from Columbia. Documents comparative performance of DQN, DDPG, PPO, SAC across portfolio tasks. Useful benchmark but results should be treated skeptically due to backtesting methodology concerns.

**Hambly, Xu, Yang (2021)** — "Recent Advances in Reinforcement Learning in Finance" — Oxford survey. Excellent critical overview of where theory meets practice. Identifies execution and hedging as the strongest use cases.

**Conservative Q-Learning (Kumar et al., 2020)** — NeurIPS 2020. Established the offline RL paradigm that enables learning from historical data without live exploration. Critical for finance applications where live exploration destroys capital.

**Dual-Level RL for Optimal Trade Execution (2024)** — Adaptive approach using PPO with Transformer + LSTM architecture capturing intraday volume U-shaped pattern. Demonstrates state-of-the-art execution results on live data.

**Deep Reinforcement Learning for Dynamic Stock Option Hedging (2023)** — MDPI review confirming RL agents (PPO, SAC) outperform Black-Scholes delta in the presence of market frictions, with MCPG and PPO showing best results.

### What the Empirical Record Actually Shows

The table below is an honest synthesis of out-of-sample evidence as of 2025:

| Application | Evidence Quality | RL vs Baseline | Notes |
|---|---|---|---|
| Execution optimization | High | +1–10 bps over TWAP/VWAP | Nevmyvaka (2006), Dual-Level PPO (2024) |
| Dynamic hedging | High | Outperforms BS-delta with costs | Deep Hedging (2019), replicated widely |
| Portfolio allocation | Moderate | Mixed vs. MV/equal-weight | Results regime-dependent |
| Pure directional alpha | Low | No consistent OOS advantage | Nearly all results are backtest artifacts |
| Market making | Moderate | Works in simulation; live evidence thin | Citadel/Virtu proprietary |

---

## 3. Where RL Works vs Where It Fails

### Where RL Works: Structural Fit

#### Execution Optimization

**Why it works:** The problem has clear MDP structure. State = (quantity remaining, time remaining, current spread, recent volume, order book imbalance). Action = how many shares to execute in this interval. Reward = negative implementation shortfall. The reward is dense (you receive feedback every interval), the horizon is short (minutes to hours), and the problem does not require predicting future price direction — only adapting execution pace to observed market conditions.

The adversarial market problem does not apply here. Whether other participants know your execution algorithm is largely irrelevant — a large pension fund liquidating a block will always face market impact, and the RL policy learns to minimize that impact conditional on real-time observations, which is strictly better than a fixed schedule.

Demonstrated results: RL execution agents consistently beat TWAP by 1–10 basis points on block trades. For large institutions executing hundreds of millions in daily volume, this is economically significant.

#### Dynamic Hedging

**Why it works:** Options hedging in discrete time with transaction costs is exactly the kind of problem where the analytical solution (Black-Scholes delta) is provably suboptimal. The MDP is well-defined: state = (option portfolio, underlying price, time to expiry, current hedge position, remaining transaction budget). Action = change in hedge ratio. Reward = P&L of the hedged portfolio.

The deep hedging literature (Buehler et al. 2019) showed that RL agents learn to trade less frequently than delta-neutral dictates, saving transaction costs, and that this generalizes out of sample across different volatility regimes. This is now a recognized industrial application at derivatives dealers.

#### Portfolio Allocation (with caveats)

**Why it partially works:** The portfolio allocation problem — allocating capital across N assets over time — has genuine MDP structure. The agent conditions on portfolio state (current weights, unrealized P&L, drawdown), market features (momentum, vol, correlation), and outputs new target weights.

The advantage over static mean-variance optimization is that the RL policy can be regime-aware and risk-adaptive: it can learn to reduce equity exposure during high-volatility regimes, avoid assets with momentum reversals, and manage rebalancing costs dynamically.

**The caveat:** The performance of RL portfolio agents is highly sensitive to the training regime. Results in academic papers frequently do not survive regime changes from training to test period. The agent is learning a combination of genuine allocation skill and spurious regime-specific patterns.

### Where RL Fails: Structural Mismatch

#### Pure Directional Alpha

**Why it fails:**

**The non-stationarity problem.** Financial returns are non-stationary at multiple frequencies. The cross-sectional correlations, autocorrelation structure, and volatility regime that held during training may reverse during deployment. Unlike a physical system, where dynamics are stable (pendulum physics do not change), market dynamics are endogenous to participant behavior. A signal that worked from 2010–2018 may have been arbitraged by 2020.

**The sparse reward problem.** Daily returns have a typical information coefficient (IC) of 0.02–0.05 for good alpha signals. This means roughly 51–52.5% accuracy on directional bets. An RL agent trying to learn from this signal faces an extremely noisy training environment. The agent will frequently attribute PnL to irrelevant features due to random correlation in any finite training window. Deep Q-Networks, PPO, and SAC all have enough parameters to memorize spurious patterns.

**The adversarial adaptation problem.** In game playing, the environment (Atari game) does not adapt to the policy. In markets, if an RL agent discovers a momentum pattern, other participants will trade against it once it becomes detectable in order flow. The market is an adversarial environment where successful strategies create the conditions for their own failure.

**The data insufficiency problem.** A decade of daily data provides ~2,500 samples. Even with data augmentation and synthetic environments, training a deep neural network on 2,500 examples is a recipe for overfitting. Intraday data helps but introduces regime-specific microstructure features that do not generalize.

**The reality gap.** Most published RL trading results use gym environments that model market frictions as fixed percentage costs, ignore market impact, assume perfect execution, and suffer from look-ahead bias in feature construction. When deployed with realistic frictions (variable bid-ask, partial fills, market impact scaling with order size, latency), results degrade substantially.

**The benchmark problem.** Many RL trading papers compare against buy-and-hold or equal-weight benchmarks. During bull markets (2010–2021), any reasonable model underperformed buy-and-hold with lower volatility. A model that "outperforms" in backtest is often just a different Sharpe frontier point, not genuine alpha.

---

## 4. MDP Formulation

### The Markov Decision Process Framework

An MDP is defined by the 5-tuple (S, A, R, T, γ) where:

- **S** = state space (what the agent observes)
- **A** = action space (what the agent can do)
- **R** = reward function R(s, a, s') (feedback signal)
- **T** = transition function T(s'|s,a) (environment dynamics)
- **γ** = discount factor (weighting of future vs immediate rewards)

### 4.1 Execution Optimization MDP

This is the highest-confidence formulation.

**State Space (execution):**

The state at time step t within an execution window is a vector containing:
- `q_remaining` — normalized quantity remaining to execute (0 to 1)
- `t_remaining` — normalized time remaining in execution window (0 to 1)
- `spread_bps` — current bid-ask spread in basis points, normalized
- `midprice_t` — current midprice relative to arrival price (signed, in bps)
- `vol_short` — realized volatility over last N minutes, normalized
- `vol_long` — realized volatility over last M hours, normalized
- `volume_ratio` — current volume rate vs. VWAP historical volume curve at this time of day
- `book_imbalance` — (bid volume - ask volume) / (bid volume + ask volume) at top K levels
- `price_momentum` — short-term price momentum over last K intervals
- `trade_participation_rate` — recent execution rate vs. market volume

State dimension: ~10–15 scalars. Manageable without dimensionality reduction.

**Action Space (execution):**

Continuous: `a_t ∈ [0, 1]` representing the fraction of remaining quantity to execute in this interval.

This is naturally bounded and interpretable. The agent decides how aggressively to execute right now. A value of 0 means "wait," a value of 1 means "liquidate everything immediately."

**Reward Function (execution):**

`R_t = -(execution_price_t - arrival_price) * shares_executed_t - λ * risk_exposure_t`

Where:
- `execution_price_t` is the average fill price in interval t
- `arrival_price` is the midprice at the start of the execution window
- `shares_executed_t` is the number of shares executed in interval t
- `risk_exposure_t` is the value of inventory still held (penalizes holding risk)
- `λ` is the risk aversion parameter

This formulation exactly mirrors the implementation shortfall framework. The reward is dense (earned every interval), sparse in the sense that it only matters at the end of the day for total IS, and well-defined.

**Transition dynamics:**

The environment is the order book simulation. In live deployment, the environment is the actual market. The key challenge is that the transition function T is not stationary — market conditions change across days, instruments, and regimes.

**Episode structure:**

Each episode is a single execution problem: liquidate Q shares of asset X within T time steps, starting at arrival time with arrival price P_0.

---

### 4.2 Portfolio Allocation MDP

**State Space (portfolio):**

The state at daily (or intraday) rebalancing time t:
- `w_t` — current portfolio weights, N-dimensional vector
- `r_t` — returns over last K periods, N × K matrix (often flattened or encoded)
- `vol_t` — realized volatility estimates per asset, N-dimensional
- `corr_t` — rolling pairwise correlation features (or principal components thereof)
- `momentum_t` — cross-sectional momentum ranks, N-dimensional
- `regime_indicator` — VIX level, credit spreads, or regime probability from HMM
- `drawdown_t` — current portfolio drawdown from peak
- `cash_t` — current cash position (important for rebalancing cost awareness)
- `macro_t` — macro features: yield curve slope, DXY, credit spreads (optional)

For N = 20 assets, K = 60 days lookback: raw dimension is approximately 1,200 + N-dimensional portfolio state. Requires careful feature engineering and dimensionality reduction.

**Action Space (portfolio):**

Continuous: `a_t ∈ R^N` representing target portfolio weights, subject to sum-to-one constraint.

Implementation approaches:
- Softmax output: naturally sums to one, but prevents short selling
- Unconstrained output + projection: allows long/short, more flexible
- Weight change delta: `Δw_t`, applied to current weights (smaller action space, but cumulative drift)

**Reward Function (portfolio):**

See Section 7 for detailed design. The summary formulation:

`R_t = r_{portfolio,t} - λ_risk * σ_{portfolio,t} - λ_tc * TC_t - λ_dd * DD_penalty_t`

**Episode structure:**

Portfolio episodes typically span the full training window. The agent interacts at each rebalancing interval (daily, weekly). Each episode is one trajectory through the training data. Walk-forward evaluation uses separate test windows.

---

### 4.3 Discount Factor Design

The discount factor γ controls how far ahead the agent looks:

- `γ = 0.99` for execution (short horizons, 30-minute windows): agent values near-term IS almost equally to terminal IS
- `γ = 0.95` for portfolio (daily rebalancing, multi-week episodes): agent appropriately discounts distant rewards
- `γ < 0.9` is generally too myopic for multi-step financial problems
- `γ = 1.0` risks numerical instability and is only appropriate with well-defined finite horizons

---

## 5. Algorithm Selection

### Comparison of Core Algorithms

#### DQN (Deep Q-Network)

**How it works:** Approximates the action-value function Q(s,a) with a deep neural network. At each state, evaluates Q for all possible actions and selects the highest-value action. Uses experience replay and a target network for stability.

**Pros:**
- Well-understood, stable training
- Sample efficient via experience replay
- Works well when action space is small and discrete

**Cons for trading:**
- Requires discrete action space. Trading actions (position sizes, execution schedules) are naturally continuous. Discretizing a continuous action (e.g., 10 position sizes) loses granularity and causes suboptimal behavior.
- Q-value estimation is unstable when rewards are non-stationary
- Overestimates Q-values (maximization bias), causing overly aggressive policies

**Verdict:** Appropriate only for simple buy/hold/sell decisions. Not recommended for execution or portfolio allocation where continuous actions matter.

---

#### DDPG (Deep Deterministic Policy Gradient)

**How it works:** Actor-critic architecture where the actor outputs a deterministic continuous action and the critic evaluates Q(s,a) using the actor's output. Uses experience replay. Off-policy learning enables sample efficiency.

**Pros:**
- Handles continuous action spaces natively
- Off-policy learning — can reuse historical data (important for data-scarce finance)
- Theoretically motivated for continuous control

**Cons for trading:**
- Highly sensitive to hyperparameters; unstable training is common
- Deterministic policy provides no natural exploration mechanism (requires added noise)
- Prone to overestimation bias in Q-values
- Brittle across environments; requires careful reward scaling

**Verdict:** Viable for portfolio allocation but largely superseded by SAC, which addresses the exploration and stability problems.

---

#### PPO (Proximal Policy Optimization)

**How it works:** On-policy policy gradient method. Collects trajectories under the current policy, computes policy gradient updates, then clips the update magnitude to prevent destructively large policy changes. The "proximal" constraint is the core innovation — it prevents policy collapse.

**Pros:**
- Stable training; less hyperparameter-sensitive than DDPG
- Works well in continuous action spaces
- Good sample reuse via multiple gradient steps per batch
- Current best practice for continuous control across many domains (robotics, games)
- Dual-level PPO with Transformer+LSTM architecture shows state-of-the-art execution results (2024)

**Cons for trading:**
- On-policy: requires generating fresh trajectories under the current policy. In live trading, this means the policy must interact with the market to learn — which conflicts with the capital preservation requirement.
- Less sample-efficient than off-policy methods; needs more environment interactions
- Performance degrades when trajectory length mismatches episode structure

**Verdict:** Best choice for simulation-based training in execution optimization. The on-policy constraint is manageable when training entirely in historical simulation.

---

#### SAC (Soft Actor-Critic)

**How it works:** Off-policy actor-critic method that adds an entropy bonus to the reward. The policy maximizes expected return plus a temperature-weighted entropy term: `max_π E[R] + α * H(π)`. The entropy term encourages the policy to remain stochastic, maintaining exploration throughout training.

**Pros:**
- Off-policy: learns from a replay buffer, reusing historical data. Sample-efficient and compatible with offline-RL style training.
- Entropy maximization provides natural exploration without explicit noise injection
- More stable than DDPG due to entropy regularization
- Naturally avoids premature convergence to suboptimal deterministic policies
- Automatic temperature tuning (α is learned, not a fixed hyperparameter)
- Works with distributional extensions for portfolio optimization

**Cons for trading:**
- More complex implementation than PPO
- Entropy bonus can cause the policy to remain unnecessarily stochastic even in well-understood situations
- Slightly more hyperparameters to manage
- Stochastic policy makes position sizing less precise (acceptable, but noted)

**Verdict:** Best overall choice for portfolio allocation. The off-policy nature enables training on historical data buffers. Entropy regularization addresses the exploration problem in a principled way.

---

#### Algorithm Selection Summary

| Use Case | Recommended | Rationale |
|---|---|---|
| Execution optimization | PPO (primary), SAC (secondary) | PPO stable in simulation; SAC if replay buffer needed |
| Portfolio allocation | SAC (primary), PPO (secondary) | Off-policy + entropy bonus suits data-scarce finance |
| Dynamic hedging | PPO or DDPG | Short episodes, well-defined MDP |
| Directional alpha (if attempted) | SAC with strong offline RL constraints | Minimize live exploration risk |
| DQN | Prototype / research only | Not recommended for production |

---

## 6. State Space Construction

### Feature Selection Principles

The state space must satisfy the Markov property: the agent's optimal action given the state should not depend on any information not contained in the state. In practice, this is approximated — markets are not fully Markov — and we include features that maximize the information content of the state.

**Selection criteria:**
1. **Predictive relevance** — the feature must have demonstrated predictive relationship with the reward signal
2. **Temporal stability** — the feature's distribution should not shift dramatically across regimes (raw prices fail this; returns pass)
3. **Computational tractability** — the feature must be computable in real-time with low latency
4. **Survivorship** — the feature must not require information that was not available at decision time (no lookahead)

### Feature Categories

#### Price-Derived Features

Use returns, not price levels. Price levels are non-stationary; log returns are approximately stationary.

- Log returns over multiple lookback windows: 1d, 5d, 21d, 63d, 252d
- Realized volatility: rolling 5d, 21d standard deviation of log returns
- Volatility ratio: short-term vol / long-term vol (regime indicator)
- ATR (Average True Range): captures intraday volatility
- For execution: bid-ask spread, midprice deviation from arrival price

#### Volume and Market Microstructure Features

- Volume relative to trailing average (normalized)
- Volume-weighted price trend (VWAP deviation)
- Order book imbalance at top 5 levels
- Trade participation rate (for execution)
- Time of day / day of week encoding (sinusoidal or learned embeddings)

#### Technical / Momentum Features

Use cross-sectional ranks, not raw values, to remove distributional shift:

- Cross-sectional momentum rank: 12-1 month returns ranked across universe
- Mean reversion signal: short-horizon autocorrelation in returns
- Trend strength: time-series momentum over multiple lookbacks

Do not include: raw RSI, MACD, Bollinger Bands (these are transformations of price and do not add information beyond returns and volatility; they also have many free parameters that overfit)

#### Portfolio State Features

These are essential and frequently omitted in academic papers:

- Current portfolio weights (normalized)
- Unrealized P&L per position
- Current portfolio volatility (realized, rolling)
- Current portfolio drawdown from high-water mark
- Days since last rebalancing (to model transaction cost accumulation)
- Leverage ratio

Without portfolio state, the RL agent cannot make sensible risk management decisions. A policy that ignores current drawdown will treat a 10% drawdown the same as a 0% drawdown, leading to excessive risk-taking.

#### Macro Features (optional, use carefully)

- VIX level (normalized, log-transformed)
- Credit spread (IG OAS or HY OAS)
- Yield curve slope (10Y-2Y)
- DXY (dollar index, normalized)

Macro features add regime information but also add non-stationarity risk. Include only if you have long enough history to sample multiple macro regimes.

### Normalization

Every feature must be normalized. Options:

1. **Z-score normalization**: subtract rolling mean, divide by rolling std. Window must be long enough to be stable but short enough to adapt to regime changes. Use 252-day rolling for most features.
2. **Percentile rank normalization**: convert to 0–1 range based on empirical percentile. More robust to outliers.
3. **Clipping**: clip normalized features at [-3, 3] to prevent extreme values from destabilizing training.

Never use global normalization statistics from the test set. All normalization parameters must be computed from the training window only.

### Temporal Encoding

For features with lookback structure, options include:

1. **Flat vector concatenation**: simplest, works for short lookbacks (≤ 21 days)
2. **Recurrent encoding (LSTM/GRU)**: the actor/critic network processes a sequence of observations. More expressive but slower to train.
3. **Transformer encoding**: multi-head self-attention over the lookback window. State-of-the-art for execution tasks (demonstrated in dual-level PPO, 2024).
4. **Fixed lookback window**: use the last K observations as a 2D feature map (assets × time)

Recommendation: Use flat vector for initial prototype (fastest iteration). Migrate to Transformer encoding for execution if computational budget allows.

### Dimensionality

For N = 20 assets, a reasonable state vector is:

- Per-asset features (returns, vol, momentum, rank): 20 assets × 10 features = 200 dimensions
- Portfolio state: 20 (weights) + 5 scalars = 25 dimensions
- Macro features: 4 dimensions
- Time encoding: 2 dimensions (sin/cos of day of year)

Total: ~231 dimensions. Manageable without PCA for a feedforward network.

For N > 50 assets, apply PCA or a learned projection layer to reduce dimensionality before the policy network.

---

## 7. Reward Function Design

### Why Reward Design Is Paramount

The reward function is the single most consequential design decision in RL. A poorly designed reward leads to:

1. **Reward hacking**: the agent finds ways to maximize the reward metric that do not correspond to the desired behavior. Example: maximizing Sharpe by taking very small positions with near-zero volatility, generating negligible returns with negligible risk — technically high Sharpe.
2. **Reward sparsity**: if reward is only given at episode end, the agent cannot learn which intermediate decisions contributed to the final outcome.
3. **Metric misalignment**: optimizing a single metric (cumulative return) ignores others (drawdown, volatility) that investors care about.

### Candidate Reward Components

#### Instantaneous Return

`r_t = w_t · R_t`

Where `w_t` is the portfolio weight vector and `R_t` is the asset return vector.

Simplest formulation. Provides dense reward. Problem: high variance — the agent attributes noise to policy decisions. Learns to be long during training bull markets regardless of skill.

#### Differential Sharpe Ratio

Moody and Saffell (2001) formalized the differential Sharpe ratio:

`DSR_t = (A_{t-1} * ΔR_t - 0.5 * B_{t-1} * ΔA_t) / (B_{t-1} - A^2_{t-1})^{3/2}`

Where `A_t` and `B_t` are exponential moving averages of returns and squared returns. This provides a return that, when summed, approximates the change in Sharpe ratio from adding this step's return.

Advantage: directly optimizes risk-adjusted performance. Disadvantage: complex, can be unstable numerically, harder to tune.

#### Drawdown Penalty

`DD_t = max(0, max_{τ≤t}(W_τ) - W_t) / max_{τ≤t}(W_τ)`

Where `W_t` is portfolio wealth. Penalize the agent whenever the portfolio is in drawdown relative to its high-water mark.

This term prevents the agent from letting losses run. Without it, policies frequently exhibit a pattern of gradual losses followed by desperate risk-taking to recover — classic path to ruin.

#### Transaction Cost Penalty

`TC_t = c * ||w_t - w_{t-1}||_1`

Where `c` is the round-trip transaction cost per unit traded and `||·||_1` is the L1 norm of weight changes (turnover).

This prevents the agent from learning to churn the portfolio — high-frequency rebalancing that generates positive gross returns but negative net returns. Without this term, RL agents consistently discover high-turnover policies.

### Composite Reward Function

The recommended production reward function:

`R_t = α₁ * return_t - α₂ * σ_t - α₃ * DD_t - α₄ * TC_t`

Where:
- `return_t` = portfolio return in period t
- `σ_t` = realized portfolio volatility over trailing window
- `DD_t` = current drawdown from high-water mark
- `TC_t` = transaction costs incurred in period t
- `α₁, α₂, α₃, α₄` = weights controlling the tradeoff

Default starting values: α₁ = 1.0, α₂ = 0.5, α₃ = 1.0, α₄ = 5.0

**Note on α₄:** Transaction costs should be penalized heavily (α₄ >> α₁) relative to return. This is because RL agents are aggressive optimizers that will exploit any gap between gross and net returns by churning the portfolio. A high TC penalty forces the policy toward sensible rebalancing frequency.

### Reward Scaling

Neural network training is sensitive to reward magnitude. Normalize rewards to have mean approximately 0 and standard deviation approximately 1 within each training batch. Use a running statistics tracker to compute the normalization constants; do not normalize across train and test periods.

### Avoiding Common Reward Hacking Patterns

| Hacking Pattern | Symptom | Mitigation |
|---|---|---|
| Zero-risk hacking | High Sharpe, near-zero returns, near-zero positions | Add minimum return or turnover floor |
| Momentum overfitting | High returns in training bull market, severe drawdown in test | Include multiple regime data in training |
| Transaction cost evasion | Agent never rebalances even when optimal to do so | Ensure TC penalty is not so high it prevents all trading |
| Drawdown ignoring | High returns with large drawdowns | Increase α₃; cap drawdown level at which punishment scales |
| Reward hacking on Sharpe | Very low denominator (tiny positions) | Minimum position size constraint in action space |

---

## 8. Training Methodology

### The Core Training Loop

1. Initialize replay buffer B with capacity C (e.g., 1 million transitions)
2. Initialize actor network π_θ and critic network Q_φ with random weights
3. For each training episode sampled from historical data window [t_start, t_end]:
   a. Reset state s_0 to initial portfolio conditions at t_start
   b. For each step t in episode:
      - Sample action a_t = π_θ(s_t) + ε (with noise for exploration)
      - Simulate environment: observe s_{t+1} and r_t
      - Store (s_t, a_t, r_t, s_{t+1}) in replay buffer B
      - If |B| >= batch_size: sample batch from B, compute TD targets, update Q_φ and π_θ
   c. Log episode metrics
4. Evaluate on validation window every K episodes
5. Save checkpoint when validation performance improves

### Walk-Forward Validation

This is the minimum acceptable validation methodology. Simple train/test splits are insufficient because they do not test the model's ability to generalize across regime transitions.

**Walk-Forward Protocol:**

```
Training Windows (non-overlapping folds):

Fold 1: Train [2010-2014] → Val [2015] → Test [2016]
Fold 2: Train [2010-2016] → Val [2017] → Test [2018]
Fold 3: Train [2010-2018] → Val [2019] → Test [2020]
Fold 4: Train [2010-2020] → Val [2021] → Test [2022]
Fold 5: Train [2010-2022] → Val [2023] → Test [2024]
```

Report performance averaged across all test folds. A strategy that shows positive Sharpe on average across 5 distinct test periods — including the 2020 COVID crash, the 2022 rate spike, and the 2023–2024 AI rally — has substantially more credibility than a single backtest.

**Key rules:**
- Never use test-fold data to tune hyperparameters. Only the validation fold is used for early stopping.
- Rebalancing costs must be simulated consistently; do not change cost assumptions between folds.
- Re-train the model from scratch for each fold. Do not warm-start with weights from the previous fold (this is a form of data leakage).

### Historical Simulation Quality

The training environment must accurately model:

1. **Transaction costs**: Use empirical bid-ask spread data, not fixed percentage costs. Model market impact as proportional to order size relative to ADV.
2. **Slippage**: Model partial fills and fill uncertainty, especially for illiquid names.
3. **Corporate actions**: Adjust for dividends, splits, delistings (survivorship bias is a major source of backtest inflation).
4. **Point-in-time data**: Use only data available at each historical timestamp. Fundamental data has reporting delays; economic releases have revision histories.

### Online Learning Risks

Online learning — updating the policy continuously as live data arrives — is the intuitive ideal: the agent learns and adapts in real-time. In practice it is extremely dangerous for trading:

1. **Catastrophic forgetting**: neural networks trained sequentially on new data can rapidly forget what they learned from historical training, potentially adopting completely different policies with no reversion mechanism.
2. **Instability**: if the policy changes significantly on a single bad day, it may take aggressive actions that cause further losses — a feedback loop.
3. **Overfitting to recent regime**: a policy that updates aggressively on live data will converge to the most recent market regime. When the regime changes, the policy will be wrong in a correlated way.
4. **Manipulation vulnerability**: if a counterparty could detect that the policy updates from live data, they could deliberately manipulate market conditions to shift the policy in a direction that benefits them.

**Recommendation:** Do not use online learning in production. Use periodic retraining on an expanding window with a fixed retraining cadence (monthly or quarterly). Treat the live policy as frozen between retraining cycles.

---

## 9. Exploration Strategy

### The Core Tension

Standard RL exploration — epsilon-greedy (DQN), action noise (DDPG), entropy bonus (SAC) — assumes that exploration is costless or that costs are reflected in the reward function. In live trading, exploration costs are asymmetric: a bad exploratory action causes a real capital loss that is not recoverable by subsequent good actions (a dollar lost is a dollar lost, not just a lower reward signal in a simulation).

This makes the standard RL exploration paradigm inapplicable for live trading. Exploration must be handled during training (in simulation), not during deployment.

### Simulation-Based Exploration (Training)

All exploration happens in the simulated historical environment during training. This is the key design principle.

**For SAC:** Entropy maximization encourages the policy to explore during training without any manual noise injection. The temperature parameter α controls exploration intensity. Higher α = more exploration = stochastic policy. During training in simulation, this is appropriate. Before deployment, α can be annealed toward zero to sharpen the policy.

**For PPO:** The stochastic policy head (Gaussian policy with learned variance) provides natural exploration. The variance collapses as training converges. The key is to run sufficient training episodes across diverse historical regimes before freezing the policy.

**For DDPG:** Ornstein-Uhlenbeck (OU) noise is added to the action during training:
- `a_t = π_θ(s_t) + OU_noise_t`
- OU noise is temporally correlated, which is appropriate for financial time series where actions have serial correlation (positions don't change dramatically every step)

### Conservative Action Spaces During Initial Deployment

When deploying a newly trained policy for the first time:

1. **Scale position sizes to 10–20% of intended target** for the first 30 trading days. This limits downside while confirming the policy behaves as expected in live market conditions.
2. **Use paper trading** for the first full regime cycle before committing real capital.
3. **Hard limits override the policy**: the policy never executes an action that violates position limits, concentration limits, or sector limits. These are enforced as post-processing constraints, not learned.

### Constrained Policy Optimization

For applications where some live exploration is unavoidable (e.g., execution optimization where the agent must respond to live market conditions), use constrained policy optimization:

- Define a safety constraint: `E[DD] ≤ max_drawdown_tolerance`
- Enforce the constraint using Lagrangian relaxation or penalized objective
- The agent explores within the feasibility region defined by the constraint

---

## 10. Offline RL Approach

### Why Offline RL Is the Right Paradigm for Finance

Offline RL (also called batch RL) learns a policy entirely from a fixed historical dataset without any online interaction with the environment. This is the natural paradigm for finance:

- The historical dataset is fixed (you cannot re-run 2008 to collect more data)
- Live exploration destroys capital
- You have a large corpus of logged trajectories from existing execution systems, portfolio managers, or rule-based strategies

The key challenge in offline RL is **distributional shift**: the learned policy will take actions that were never observed in the historical data, and the Q-function estimate for those out-of-distribution actions is unreliable (often wildly optimistic).

### Conservative Q-Learning (CQL)

CQL (Kumar et al., NeurIPS 2020) addresses distributional shift by penalizing Q-values for out-of-distribution actions:

`L_CQL(Q) = L_standard_Bellman(Q) + α * E_{s~D}[log Σ_a exp(Q(s,a)) - E_{a~D}[Q(s,a)]]`

The penalty term pushes down Q-values for actions not seen in the dataset while pushing up Q-values for actions that were taken. This makes the Q-function conservative: it underestimates the value of out-of-distribution actions rather than overestimating them. The result is a policy that stays close to the behavior policy (the historical data-generating policy) while improving on it where the data supports improvement.

**CQL in practice for finance:**

1. Collect a dataset of historical trajectories: `D = {(s_t, a_t, r_t, s_{t+1})}`
   - If using execution data: these are real execution records from an existing TWAP or broker algo
   - If using portfolio data: these are the historical weight changes made by an existing strategy or fund
2. Train a CQL agent on this dataset
3. The CQL agent learns to improve on the historical policy without deviating too far from it

This is particularly powerful for execution optimization: you have years of historical execution logs from your broker's algo. The CQL agent learns to do better than the historical algo without making bets that were never tried before.

### Implicit Q-Learning (IQL)

IQL (Kostrikov et al., 2021) is an alternative offline RL algorithm that avoids querying out-of-distribution actions entirely during training, using expectile regression to estimate the value function from the dataset alone.

**Advantage over CQL:** More stable training, no hyperparameter for the conservatism penalty.

**When to use IQL vs CQL:**
- CQL when you want explicit control over the conservatism level
- IQL when training stability is more important than tuning conservatism

### Decision Transformer

Decision Transformer (Chen et al., 2021) reframes RL as a sequence modeling problem. A Transformer is trained to predict actions given a sequence of (return-to-go, state, action) tuples. At inference, you condition on the desired return (e.g., "I want to achieve Sharpe 1.5") and the model generates actions.

**Finance application:** Given a dataset of historical portfolio management decisions with realized outcomes, train a Decision Transformer to generate actions conditioned on target performance levels. This is a particularly natural fit for offline learning from historical fund data.

**Recent work (2024):** LLM-adapted LoRA as Decision Transformer for offline RL in quantitative trading shows competitive results with CQL and IQL on quantitative trading tasks.

### Offline RL Data Requirements

The quality of the behavioral policy matters for CQL and IQL. Poor-quality historical data (e.g., pure random execution) produces poor offline RL policies. You need:

- At minimum: a reasonably good existing policy (TWAP, equal-weight portfolio)
- Diverse action coverage: the historical policy must have taken a range of actions, not always the same action
- Long enough time span: ideally 5+ years of data to cover multiple market regimes

---

## 11. Portfolio Construction

### From RL Policy to Live Portfolio

The RL policy outputs a target weight vector `w^*_t ∈ R^N`. Converting this to an executable portfolio requires several layers of processing.

### Step 1: Policy Output Adjustment

**Clipping**: clip weights to `[w_min, w_max]`. For a long-only strategy, clip at [0, 0.2] (maximum 20% single-position concentration). For long-short, clip at [-0.1, 0.2].

**Renormalization**: after clipping, renormalize weights to sum to 1 (long-only) or to target net exposure.

**Minimum position threshold**: weights below `|threshold|` = 0.01 are set to zero. Small positions below ~1% are not worth the transaction cost to initiate or maintain.

### Step 2: Turnover Filtering

Compare `w^*_t` with current weights `w_{t-1}`. Compute turnover: `T = ||w^*_t - w_{t-1}||_1`.

If T < turnover_threshold (e.g., 5%), do not rebalance. The signal is not strong enough to justify transaction costs.

If T > max_turnover (e.g., 30%), reduce the trade: execute `w_{t-1} + λ(w^*_t - w_{t-1})` with `λ < 1`. This "soft landing" prevents the policy from making drastic one-period allocation changes that may be noise-driven.

### Step 3: Risk Overlay

Before execution, pass the target weights through a risk management layer:

- **Concentration check**: no single position > concentration_limit
- **Sector check**: no single sector > sector_limit
- **Beta check**: ensure portfolio beta vs. benchmark is within tolerance
- **Volatility check**: ensure ex-ante portfolio volatility is within target range
- **Correlation check**: ensure the portfolio is not inadvertently concentrated in a single risk factor

If any check fails, the risk overlay modifies weights toward compliance before execution. The policy's weights are a starting point, not a final instruction.

### Step 4: Execution

Pass the target trades to the execution layer. For large orders (>1% ADV), route through the execution optimization RL policy (Section 4.1) rather than naive market orders.

For small orders (<0.1% ADV), use aggressive limit orders at the near side of the spread.

### Step 5: Portfolio State Update

After execution, record actual fills. Update the portfolio state tracker with actual weights (which will differ from targets due to partial fills and price moves during execution).

### Rebalancing Frequency

| Asset Class | Recommended Frequency | Rationale |
|---|---|---|
| Equities (liquid large cap) | Weekly | Daily is too costly; monthly too slow to react |
| Equities (small/mid cap) | Bi-weekly to monthly | Higher transaction costs, less liquidity |
| Futures / ETFs | Daily to weekly | Lower transaction costs enable more frequent rebalancing |
| Execution optimization | Per-minute to per-5-min | Short execution windows require high-frequency decisions |

---

## 12. Risk Management

### RL Policy Failure Modes

RL policies can fail in several distinct ways that are different from traditional algorithmic trading failures:

**Mode 1: Distributional shift failure**
The policy encounters a market state it has never seen during training (e.g., a black swan event, a regime shift). The policy's output in this region is undefined by training and may be extreme. In practice, this manifests as: the policy suddenly takes maximum positions, or zeros out entirely, with no apparent reason from a human perspective.

Detection: monitor the distance between current state vector and the training data distribution (Mahalanobis distance or autoencoder reconstruction error). If the distance exceeds a threshold, the policy is operating out-of-distribution.

Mitigation: fall back to a safe policy (equal-weight, existing systematic strategy) when OOD detected.

**Mode 2: Reward hacking**
The policy discovers a way to achieve a high reward signal that does not correspond to genuinely good behavior. Example: in the live environment, bid-ask spreads are wider than training simulation, causing the policy to churn the portfolio (which was rewarded in simulation with tight spreads) and lose money on real frictions.

Detection: monitor gross return vs. net return. If the spread is widening, transaction costs are higher than the policy expects.

Mitigation: update the transaction cost model in the simulation and retrain.

**Mode 3: Catastrophic forgetting (if online learning is used)**
The policy rapidly unlearns historical training when exposed to a new market regime, adopting a degenerate policy that maximizes the most recent signal.

Detection: monitor policy behavior diversity — if the policy is taking the same action regardless of state, it has collapsed.

Mitigation: freeze the policy; retrain from scratch on expanded historical data.

**Mode 4: Overfitted policy**
The policy overfits to specific patterns in the historical training data (e.g., the 2017 low-volatility bull market) and fails when those patterns break. The backtest looks excellent; live performance is poor.

Detection: evaluate policy on out-of-time hold-out data that was never touched during development.

Mitigation: increase data diversity in training; reduce model complexity; use ensemble of policies trained on different subsets.

### Hard Risk Limits (Override Conditions)

These limits are enforced regardless of policy output. They are not learned; they are hardcoded constraints:

| Limit | Default Value | Action on Breach |
|---|---|---|
| Maximum single-position concentration | 20% of portfolio | Reduce to limit |
| Maximum sector concentration | 40% of portfolio | Reduce to limit |
| Maximum portfolio gross leverage | 150% | Halt new positions |
| Maximum daily loss (stop-loss) | 2% of AUM | Liquidate to cash |
| Maximum drawdown from HWM | 10% | Reduce to 50% risk; notify |
| Maximum drawdown from HWM | 20% | Full liquidation; suspend policy |
| Maximum turnover in single day | 30% of portfolio | Cap the trade |
| VIX level trigger | VIX > 40 | Reduce position sizes by 50% |
| Illiquidity trigger | Volume < 50% of 30-day avg | Halt execution, reduce position |

### Circuit Breakers

Automated policy suspension triggers:

1. **PnL circuit breaker**: if the strategy loses more than X% in a rolling 5-day window, suspend trading and require human review before resuming.
2. **Behavioral circuit breaker**: if the policy's actions are statistically inconsistent with its historical behavior distribution (as measured by KL divergence from the historical action distribution), suspend and alert.
3. **Market circuit breaker**: if a market-wide circuit breaker triggers (halts, extreme VIX), suspend all RL-driven orders.

---

## 13. Model Monitoring and Retraining

### Performance Metrics to Monitor Continuously

**Primary:**
- Rolling 60-day Sharpe ratio (vs. 252-day training average)
- Rolling 60-day information ratio (for execution: IS improvement vs. TWAP)
- Rolling 60-day maximum drawdown
- Net-of-fees PnL vs. benchmark

**Secondary:**
- Turnover rate (daily %)
- Policy action distribution (mean weight, weight distribution, entropy of actions)
- State distribution OOD score (Mahalanobis distance from training distribution)
- Transaction cost ratio (TC as % of gross PnL)

### Policy Degradation Detection

**Statistical tests:**
- CUSUM (Cumulative Sum Control Chart): detects structural breaks in PnL time series. If the CUSUM statistic exceeds a threshold, the policy may have degraded.
- Rolling t-test: compare rolling 60-day Sharpe to the null hypothesis of zero alpha. If the p-value exceeds 0.15 (weak evidence of positive alpha), trigger a review.
- Kolmogorov-Smirnov test: compare the distribution of live returns to the distribution of walk-forward validation returns. A significant distributional shift indicates policy degradation.

**Behavioral monitoring:**
- If the policy's action distribution shifts significantly from its historical distribution (measured by KL divergence), the policy is in an OOD region of the state space.
- If turnover suddenly increases without a corresponding increase in information (PnL/turn), the policy has entered a churning mode.

### Retraining Cadence

| Trigger | Action |
|---|---|
| Scheduled quarterly review | Retrain on expanded data; compare new vs. old policy in walk-forward |
| Sharpe drops below 0.3 for 60 consecutive days | Trigger early retraining review |
| State OOD score exceeds 2σ for 5 consecutive days | Investigate; potentially suspend and retrain |
| Major market regime change (COVID-scale) | Immediate review; paper trade new regime before live deployment |
| Reward function is updated | Full retrain required |

### Model Versioning

- Every trained policy is versioned with: training data range, hyperparameters, validation Sharpe, validation max drawdown, and training date.
- Live policy version is logged with every executed trade.
- Never deploy an unversioned policy.
- Maintain at least the last 3 production policy versions for rollback capability.

### A/B Testing New Policies

Before replacing the production policy with a newly trained version:

1. Run both policies in paper trading for 30 days
2. Compare performance on live market data (paper fills using actual market prices)
3. Switch to new policy only if performance is meaningfully better (Sharpe improvement > 0.2)
4. Gradual rollout: deploy new policy at 20% of target AUM; scale to full AUM over 3 months if performance holds

---

## 14. Recommended Application Focus

### Primary Focus: Execution Optimization

Execution optimization is the highest-confidence, highest-ROI application of RL for this system. The recommendation is to begin here before attempting portfolio allocation.

**Why execution first:**

1. **Clear MDP structure**: the problem is well-defined with a dense, interpretable reward signal (implementation shortfall)
2. **No directional alpha required**: the policy does not need to predict future prices — only to adapt execution pace to observed market conditions. This removes the hardest element of the trading problem.
3. **Directly measurable ROI**: every basis point of IS improvement multiplied by execution volume is direct P&L. At $100M daily execution volume, a 2bps improvement = $200K per year.
4. **Strong out-of-sample evidence**: Nevmyvaka et al. (2006) demonstrated this over 15 years ago with real data; subsequent work has substantially confirmed the result.
5. **No regime dependency**: the qualitative structure of market impact (trading too fast is costly; trading too slow is risky) is stable across regimes. The policy may need retraining across regimes, but the fundamental problem does not change sign.
6. **Compatible with existing infrastructure**: the execution RL agent is a drop-in replacement for the TWAP/VWAP scheduler. It does not require overhauling the portfolio construction layer.

**Target metric:** Reduce implementation shortfall vs. VWAP by ≥ 2 basis points averaged across all execution events, sustained over 90 days of live trading.

### Secondary Focus: Portfolio Risk Allocation

After execution optimization is in production, apply SAC-based portfolio allocation to the dynamic risk allocation problem:

- Given current portfolio, market conditions, and risk budget, how should capital be allocated across existing strategies or asset classes?
- This is not about picking individual stocks but about tilting exposure across risk factors (value/growth, duration, credit) as a function of regime indicators.

**Why this is more defensible than pure alpha:**
The agent is not predicting returns directly. It is learning a mapping from risk signals (VIX, credit spreads, momentum) to portfolio risk exposure. The signal is predictable at a macro level (reducing risk when VIX is elevated is a well-established result in the risk-premia literature).

### Explicitly Out of Scope: Directional Alpha Generation

Direct application of RL to predict stock returns or take directional market bets based on RL policy output is explicitly out of scope for the initial implementation. The evidence base does not support this application as more effective than well-implemented supervised learning or classical quant signals, and it introduces substantial overfitting and regime-change risk.

If the team wishes to explore this in a research context, it must be:
1. Treated as a research project with zero capital allocation until sustained out-of-sample results over 12+ months are demonstrated
2. Limited to paper trading during the research period
3. Compared against a strong baseline (ensemble of supervised learning models + classical momentum signals)

---

## 15. Key Risks and Failure Modes

### Risk Register

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Policy overfits to training regime | High | High | Walk-forward validation; ensemble of policies |
| Live frictions exceed training assumptions | High | Medium | Validate TC model empirically before live trading |
| Market regime shift invalidates policy | Medium | High | OOD detection; circuit breakers; quarterly retraining |
| Reward hacking in unexpected way | Medium | Medium | Diverse validation metrics; human review of policy behavior |
| Distributional shift in state features | Medium | Medium | Rolling normalization; OOD detection |
| Online learning instability | High (if attempted) | High | Prohibit online learning; frozen deployment policy |
| Simulation-to-reality gap | High | High | Empirical calibration of market impact model; slippage estimation |
| Computational failure during live trading | Low | High | Fallback to TWAP/equal-weight on system failure |
| Adversarial market adaptation | Low (execution) / High (alpha) | High | Limit RL to execution/allocation, not alpha |
| Policy produces extreme positions | Low | High | Hard position limits; action clipping |

### The Simulation-to-Reality Gap

This is the most persistent and underappreciated risk. Every training environment is a simplification of reality. The gap between simulation and reality includes:

- **Transaction cost model**: fixed bps vs. variable (function of spread, volume, size)
- **Market impact**: ignored vs. linear vs. nonlinear; permanent vs. temporary impact
- **Fill model**: instantaneous perfect fills vs. partial fills, missed orders, queuing
- **Latency**: zero latency vs. 50–500ms round-trip; stale data risk
- **Survivorship bias**: historical universe includes delisted stocks; simulation may not
- **Corporate actions**: not modeled in most training environments

**Quantification approach:** Before live deployment, paper trade the trained policy for 60 days using actual market data and actual fill simulations. Measure the difference between simulated and paper-trading IS. If the gap is > 5 bps, the simulation model needs recalibration before live deployment.

### The Non-Stationarity Time Bomb

The most dangerous failure mode for RL trading strategies is silent policy degradation. The policy continues to trade, generating slightly negative alpha, but nothing triggers an obvious alarm. Over 6–12 months, capital is quietly eroded.

This is more dangerous than catastrophic failure because it is harder to detect. A policy that loses 50% in a day triggers circuit breakers. A policy that loses 0.1% per week over 52 weeks loses 5% before the annual review catches it.

**Detection:** Implement rolling performance attribution. Break the policy's return into known components (market beta, factor exposures) and unexplained alpha. If unexplained alpha has been consistently negative for 60 days, something is wrong.

---

## 16. Parameters and Tunable Knobs

### Algorithm Hyperparameters (SAC)

| Parameter | Role | Default | Range | Notes |
|---|---|---|---|---|
| `actor_lr` | Actor learning rate | 3e-4 | [1e-5, 1e-3] | Reduce if training unstable |
| `critic_lr` | Critic learning rate | 3e-4 | [1e-5, 1e-3] | Match actor LR typically |
| `alpha_lr` | Temperature learning rate | 3e-4 | [1e-5, 1e-3] | Automatic tuning |
| `gamma` | Discount factor | 0.99 | [0.95, 0.999] | Lower for short-horizon execution |
| `tau` | Soft update coefficient | 0.005 | [0.001, 0.05] | Higher = faster target network update |
| `replay_buffer_size` | Experience replay capacity | 1e6 | [1e5, 1e7] | Larger = more diverse experience |
| `batch_size` | Training batch size | 256 | [64, 1024] | Larger = more stable gradient |
| `update_frequency` | Steps per gradient update | 1 | [1, 4] | Higher = more sample efficiency |
| `hidden_dim` | Policy network width | 256 | [128, 512] | Balance capacity vs. overfitting |
| `num_hidden_layers` | Policy network depth | 2–3 | [2, 4] | Diminishing returns beyond 3 |
| `target_entropy` | Desired policy entropy | -dim(A) | auto | SAC auto-tunes; set manually if unstable |

### Algorithm Hyperparameters (PPO)

| Parameter | Role | Default | Range | Notes |
|---|---|---|---|---|
| `clip_epsilon` | Policy clip ratio | 0.2 | [0.1, 0.3] | Lower for more conservative updates |
| `entropy_coef` | Entropy bonus weight | 0.01 | [0.001, 0.1] | Higher encourages more exploration |
| `value_coef` | Value loss weight | 0.5 | [0.25, 1.0] | Balance policy vs. value learning |
| `ppo_epochs` | Gradient steps per batch | 10 | [5, 20] | Too high causes policy collapse |
| `gae_lambda` | GAE advantage estimation | 0.95 | [0.9, 0.99] | Higher = less bias, more variance |
| `max_grad_norm` | Gradient clipping | 0.5 | [0.25, 1.0] | Prevents exploding gradients |

### Environment / MDP Parameters

| Parameter | Role | Default | Range | Notes |
|---|---|---|---|---|
| `lookback_window` | State history length | 60 | [21, 252] | Match signal decay rate |
| `rebalancing_frequency` | Portfolio (days) | 5 | [1, 21] | Balance signal freshness vs. TC |
| `execution_interval` | Execution (minutes) | 5 | [1, 30] | Balance granularity vs. noise |
| `episode_length` | Training episode (days) | 252 | [63, 504] | One year default |
| `num_assets` | Portfolio universe size | 20 | [10, 100] | Keep manageable for initial deployment |

### Reward Function Weights

| Parameter | Role | Default | Tuning Notes |
|---|---|---|---|
| `alpha_return` (α₁) | Return weight | 1.0 | Keep fixed as reference |
| `alpha_vol` (α₂) | Volatility penalty | 0.5 | Increase for more risk-averse policy |
| `alpha_drawdown` (α₃) | Drawdown penalty | 1.0 | Increase if max drawdown is too high |
| `alpha_tc` (α₄) | Transaction cost penalty | 5.0 | Increase if turnover too high |
| `risk_aversion` (λ) | Execution risk aversion | 0.1 | Almgren-Chriss equivalent |

### Risk Management Parameters

| Parameter | Default | Notes |
|---|---|---|
| `max_position_size` | 0.20 | Hard clip; reduce for more conservative deployment |
| `min_position_threshold` | 0.01 | Positions below this are set to zero |
| `max_turnover_daily` | 0.30 | Soft cap; hard cap at 0.50 |
| `max_drawdown_suspend` | 0.20 | Full liquidation above this level |
| `max_drawdown_reduce` | 0.10 | Halve risk budget above this level |
| `ood_threshold` | 2.5σ | Mahalanobis distance trigger |
| `pnl_stop_loss_5d` | 0.02 | 5-day rolling loss stop |
| `vix_reduce_trigger` | 40 | VIX level for 50% position reduction |

### Offline RL (CQL) Parameters

| Parameter | Role | Default | Notes |
|---|---|---|---|
| `cql_alpha` | Conservatism penalty weight | 1.0 | Higher = more conservative; reduce if policy too timid |
| `cql_n_actions` | Actions sampled for penalty | 10 | Computational cost vs. penalty accuracy |
| `min_q_weight` | Minimum Q-value weight | 0.5 | Balance conservatism vs. improvement |
| `lagrange_thresh` | Automatic CQL-alpha tuning | 10.0 | Target minimum Q-value level |

---

## Appendix: Key Terminology

**Implementation Shortfall (IS):** The cost of executing a trade, measured as the difference between the midprice at the time the decision was made (arrival price) and the actual average fill price, expressed in basis points.

**TWAP:** Time-Weighted Average Price. A benchmark execution strategy that divides the order evenly across time intervals.

**VWAP:** Volume-Weighted Average Price. An execution benchmark that distributes the order in proportion to historical volume patterns throughout the day.

**MDP:** Markov Decision Process. The mathematical framework for sequential decision making where the future depends only on the current state (Markov property).

**Policy:** The mapping from states to actions that the RL agent learns. In finance, this is the trading rule.

**Q-function:** The action-value function Q(s,a) estimating the expected cumulative reward from taking action a in state s and then following the policy.

**Temporal Difference (TD) Learning:** Learning by bootstrapping estimates of future value from current estimates, without waiting for the episode to end.

**Experience Replay:** Storing past (state, action, reward, next_state) tuples in a buffer and sampling randomly for training. Breaks temporal correlations and improves sample efficiency.

**Walk-Forward Validation:** A time-series cross-validation approach that respects temporal ordering. Train on past data, test on future data, advance the window forward.

**Information Coefficient (IC):** The correlation between predicted and realized returns. An IC of 0.05 is considered good in quantitative equity.

**Distributional Shift:** The change in the statistical distribution of the data between training and deployment. A primary source of model failure in live trading.

**OOD (Out-of-Distribution):** A state or observation that falls outside the range of states seen during training. RL policies are unreliable in OOD regions.

---

*Spec authored for the auto-trading system. Review recommended before implementation. No production capital should be allocated to any RL strategy without completing walk-forward validation across at least 4 non-overlapping test periods spanning different market regimes.*
