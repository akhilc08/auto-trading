# Deep Learning Forecasting Systems for Trading — Design Specification

**Status:** Research Spec  
**Domain:** Systematic Equity / Multi-Asset  
**Last Updated:** 2026-05-17  
**Classification:** Internal Research

---

## Table of Contents

1. [Strategy Overview and Thesis](#1-strategy-overview-and-thesis)
2. [Academic Foundations](#2-academic-foundations)
3. [Where Deep Learning Genuinely Adds Value](#3-where-deep-learning-genuinely-adds-value)
4. [Model Architecture Options](#4-model-architecture-options)
5. [Feature Engineering](#5-feature-engineering)
6. [Training Methodology](#6-training-methodology)
7. [Overfitting Mitigation](#7-overfitting-mitigation)
8. [Signal Generation and Confidence Scoring](#8-signal-generation-and-confidence-scoring)
9. [Portfolio Construction](#9-portfolio-construction)
10. [Model Lifecycle Management](#10-model-lifecycle-management)
11. [Risk Management](#11-risk-management)
12. [Execution Considerations](#12-execution-considerations)
13. [Key Risks and Failure Modes](#13-key-risks-and-failure-modes)
14. [Honest Assessment of Probability of Success](#14-honest-assessment-of-probability-of-success)
15. [Parameters and Tunable Knobs](#15-parameters-and-tunable-knobs)

---

## 1. Strategy Overview and Thesis

### The Honest Starting Point

Deep learning in finance is not a magic alpha engine. It is a set of powerful function approximators that, when carefully applied within strict constraints, can improve specific narrowly-scoped tasks within a larger investment process. The naive framing — "train a neural network on price history, predict tomorrow's return" — does not work reliably and is responsible for a large body of spurious academic results and failed trading systems.

The correct framing is more limited and more honest:

- Deep learning is best suited to **representation learning from high-dimensional, unstructured inputs** (text, satellite imagery, earnings audio) where hand-crafted features are insufficient and the mapping from input to signal is genuinely complex.
- For structured tabular time series (OHLCV, technical indicators), deep learning has only marginal advantages over well-regularized gradient boosted trees (GBT) and traditional factor models, but at substantially higher model complexity and operational cost.
- Predicting **direction** (up/down) is tractable as a narrow classification problem; predicting **magnitude** of returns is much harder and typically unreliable.
- Predicting **volatility** is materially easier than predicting returns because volatility exhibits well-documented persistence (GARCH clustering), leverage effects, and cross-asset commonality. DL models can exploit these regularities more effectively than they can find return signals.

### What This Strategy Is

A systematic, multi-asset strategy that uses deep learning models as **one input** into a signal ensemble, rather than as a standalone trading oracle. The DL layer serves three specific roles:

1. **NLP Feature Extraction:** Extract sentiment, tone, linguistic signals, and event flags from earnings call transcripts, SEC filings (10-K, 10-Q, 8-K), and news feeds using fine-tuned transformer models. This is where DL has its clearest edge.
2. **Non-Linear Factor Interaction:** Capture conditional relationships between known factors (momentum, value, quality, volatility) that are missed by linear models. This is marginal but real (Gu, Kelly, Xiu 2020).
3. **Volatility Regime Forecasting:** Use DL models to forecast near-term realized volatility, feeding risk scaling and position sizing.

### What This Strategy Is Not

- A price prediction engine. Raw price level forecasting is near-random in expectation.
- A replacement for risk management. All DL signals are downstream of hard position limits and stop-loss rules.
- A high-frequency strategy. DL models for structural alpha are best suited to holding periods of days to weeks. Sub-daily prediction degrades sharply as microstructure noise dominates.
- A fully autonomous system. Model outputs require human oversight for regime change detection and retraining authorization.

### The Adaptive Markets Problem

Financial markets are non-stationary adversarial environments. Unlike computer vision (where cats remain cats regardless of who is looking) or protein folding (where physics is invariant), financial markets adapt to the models that trade them. As soon as a pattern is widely discovered and exploited, it diminishes or disappears. This is the Adaptive Markets Hypothesis (Lo, 2004): market efficiency is a dynamic equilibrium, not a fixed state.

The practical consequence is that the expected lifespan of any ML-based alpha signal is finite. Strategies need continuous monitoring for signal decay and systematic retraining schedules. A model trained and left static will deteriorate with near-certainty.

---

## 2. Academic Foundations

### Core Empirical Papers

**Gu, Kelly, and Xiu (2020) — "Empirical Asset Pricing via Machine Learning"**  
Published in *Review of Financial Studies*, Vol. 33. This is the most cited empirical paper on ML for equity returns. Key findings:
- Neural networks and gradient boosted trees outperform linear models for predicting monthly US equity returns across 94 factors.
- The out-of-sample R² is economically meaningful (roughly 0.4-0.6% on monthly returns) but extremely small in absolute terms.
- The dominant predictors are variations of **momentum, liquidity, and volatility** — not exotic features. DL captures nonlinear interactions between these factors.
- Economic gains to a hypothetical investor are significant, but transaction cost assumptions are generous. Real-world friction erodes much of the stated advantage.
- This is the gold standard for what DL can deliver: a real but modest improvement over linear factor models in the return prediction task.

**Chen, Pelger, and Zhu (2024) — "Deep Learning in Asset Pricing"**  
Published in *Management Science*. Uses a deep neural network to price the SDF (stochastic discount factor). Shows DL identifies pricing kernels that traditional factor models miss, especially in regime transitions. Important for understanding DL as a risk model, not just a return predictor.

**Oord et al. (WaveNet/temporal convolutions applied to finance)**  
Temporal convolutions (TCNs) often match or exceed LSTM performance on financial series with lower training time. Relevant baseline for comparing architectures.

**Lim, Arik, Loeff, Pfister (2021) — "Temporal Fusion Transformers for Interpretable Multi-Horizon Time Series Forecasting"**  
Google Research. The canonical TFT paper. Shows TFT outperforms LSTM, DeepAR, and ARIMA on 9 real-world time series benchmarks with multi-step forecasting. Architecture designed for mixed input types (static metadata, known future covariates, unknown historical inputs) — directly applicable to equity forecasting.

**Feng, He, and Polson (2018) — "Deep Learning for Predicting Asset Returns"**  
Shows that deep feedforward networks applied to factor data deliver higher Sharpe ratios than linear factor models, but with careful regularization and feature normalization as prerequisites.

**López de Prado (2018) — "Advances in Financial Machine Learning"**  
Practitioner-focused. Essential on: combinatorial purged cross-validation (CPCV), embargo periods to prevent leakage, the backtest overfitting problem, and feature importance in finance. Required reading before implementation.

**Bailey, Borwein, López de Prado, Zhu (2014) — "The Probability of Backtest Overfitting"**  
Formalizes the relationship between the number of trials run during strategy optimization and the probability that the best backtest result is due to chance. Quantifies how severely ML strategy selection overfits.

### On NLP in Finance

**Loughran and McDonald (2011) — "When is a Liability Not a Liability?"**  
Establishes the financial domain-specific sentiment lexicon. Baseline for all text-based finance research.

**Yang et al. (2020) — "FinBERT: A Pretrained Language Model for Financial Communications"**  
Fine-tuned BERT on financial corpora. Outperforms general sentiment models for financial text classification. Directly usable for earnings transcript analysis.

**ExtractAlpha Transcripts Model (2024)**  
Commercial research showing that factor- and industry-neutralized NLP signals from earnings transcripts generated 13.7% annual return and 2.57 Sharpe ratio over 2006-2024. This is among the strongest documented NLP alpha signals and validates the NLP-as-feature-extraction thesis.

### Key Empirical Benchmarks

- Monthly equity return R² from DL: 0.4-0.6% (Gu et al. 2020) — tiny but real.
- Sharpe ratio in walk-forward backtests of microstructure DL signals: ~0.33 annualized in recent US equity data (2015-2024 study with strict validation).
- Walk-forward validation studies with 9 sequential time splits on S&P 500 data show significant shrinkage from in-sample to out-of-sample performance.
- Real-time investor gains from ML stock return forecasts are "much more modest" than in-sample hedge portfolio results suggest (Li, 2024).

---

## 3. Where Deep Learning Genuinely Adds Value

### High-Confidence Applications

**NLP on Unstructured Financial Text**  
This is the clearest case. Human analysts can read an earnings call transcript; they cannot read 5,000 transcripts per quarter and extract systematic signals. Fine-tuned transformer models (FinBERT, domain-adapted RoBERTa) can:
- Score tone and sentiment of management language across thousands of documents.
- Detect hedging language, uncertainty markers, and deviation from prior quarter tone.
- Flag new risk disclosures in 10-K filings.
- Extract guidance revision signals (management saying "challenging environment" vs. "accelerating momentum").
- Capture prosodic signals in audio/text mismatches (management voice tone vs. prepared remarks).

The key insight: the signal is not price movement; it is information extraction at scale from a domain where DL genuinely outperforms alternatives. The extracted feature then feeds a factor model or composite signal, not a standalone trading rule.

**Volatility Forecasting**  
DL models (dilated convolutions, LSTM variants) demonstrate consistent gains over GARCH-class models for near-term realized volatility forecasting (1-5 day horizon). The reason: volatility has real persistence and cross-asset commonality that nonlinear models capture better than linear ones. This feeds risk scaling in portfolio construction, not directional bets.

**Non-Linear Factor Interaction Detection**  
The Gu, Kelly, Xiu result: neural networks find nonlinear conditional relationships between momentum, volatility, and liquidity factors that a linear model misses. Concretely: momentum may only be predictive among low-volatility stocks, and this interaction is non-obvious. A deep network trained on a properly constructed factor input matrix can detect these conditionalities. This is a genuine incremental advantage over linear factor models.

**Regime Classification**  
Unsupervised and semi-supervised DL can cluster market environments (trending/mean-reverting, high/low volatility, risk-on/risk-off) from price, volatility, credit spread, and macro features. This regime label can then be used to activate or weight different underlying alpha signals, not to trade directly.

**Cross-Asset Relationship Modeling with GNNs**  
Graph Neural Networks can model supply chain relationships, sector hierarchies, and dynamic correlation structures between assets in ways that static correlation matrices cannot. Early research (2023-2024) shows improvement in equity prediction when incorporating GNN embeddings that propagate information across related companies (same sector, supplier/customer relationships, shared macro exposure). This is promising but still in early stages for production use.

### Lower-Confidence Applications

**Direct Daily Return Prediction**  
The signal-to-noise ratio of daily equity returns is extremely low. Sharpe-equivalent R² of 0.4-0.6% monthly (Gu et al.) translates to roughly 0.05% daily — barely above noise. DL can extract some of this, but small model errors or data quality issues wipe out the entire edge. Viable only in large, diversified portfolios with tight risk management and strict look-ahead-bias control.

**High-Frequency (Sub-daily) Prediction**  
Microstructure noise dominates at high frequencies. DL models struggle to separate signal from noise. Limit order book DL models (DeepLOB) show promise but require co-location, specialized hardware, and extremely careful data handling. Out of scope for this system.

---

## 4. Model Architecture Options

### 4.1 LSTM and GRU (Recurrent Neural Networks)

**Mechanism:** Long Short-Term Memory networks use gating mechanisms (input gate, forget gate, output gate) to selectively retain or discard information across timesteps. Gated Recurrent Units (GRU) are a streamlined variant with two gates (update, reset), fewer parameters, and comparable performance.

**What They Capture:**
- Sequential temporal dependencies in time series.
- Long-range patterns that vanish in simpler models.
- Non-linear transformations of input sequences.

**Strengths for Finance:**
- Well-understood, widely validated, large body of financial literature.
- Handles variable-length lookback windows naturally.
- Moderate training cost relative to transformers.
- GRU often matches LSTM performance with faster training (~20-30% fewer parameters).

**Failure Modes:**
- Gradient vanishing even with gating — struggles with dependencies beyond ~100-200 timesteps in practice.
- Not parallelizable during training (sequential computation) — slow for large datasets.
- Sensitive to hyperparameter choices (hidden units, layers, dropout rate).
- Prone to overfitting on small financial datasets.
- Does not natively handle multiple input types (static metadata, known future inputs) without architectural hacks.
- "94% accuracy on Apple stock" results in academic papers are heavily overfitted and do not generalize. High in-sample accuracy is not a reliable indicator of out-of-sample performance.

**Appropriate Use Cases:** Rolling volatility forecasting, short sequence feature encoding as part of a larger ensemble, initial baseline for comparison.

**Verdict:** Solid baseline; better than nothing; not the top performer. Use as one member of an ensemble or as a feature encoder, not as the primary model.

### 4.2 Temporal Convolutional Networks (TCN)

**Mechanism:** Dilated causal convolutions applied hierarchically. Dilation allows the receptive field to grow exponentially with depth while maintaining causal (no future leakage) operations. WaveNet is the canonical architecture; financial adaptations (DeepVol for volatility) show strong results.

**Strengths:**
- Fully parallelizable training — significantly faster than RNNs.
- Stable gradients (no vanishing/exploding gradient problem).
- Flexible receptive field control via dilation factor.
- Strong results for volatility forecasting tasks.

**Weaknesses:**
- Fixed maximum receptive field determined by architecture (not adaptive).
- Less expressive for complex multivariate cross-asset dependencies.
- Less interpretable than TFT.

**Verdict:** Underrated. Often matches LSTM/GRU on financial benchmarks with faster training. Should be included in any architecture comparison. Strong choice for volatility forecasting.

### 4.3 Transformer Architectures for Finance

**Mechanism:** Self-attention mechanisms compute relationships between all pairs of input timesteps, allowing the model to selectively focus on the most relevant historical moments without the sequential bottleneck of RNNs.

**Vanilla Transformer Limitations in Finance:**
- Self-attention is O(n²) in sequence length — expensive for long sequences.
- Standard transformers lack the native ability to distinguish between time steps (positional encoding is approximate in irregular financial data).
- Without modification, quadratic attention is prohibitive for daily data over multi-year lookbacks.
- Vanilla transformers do not differentiate between observed historical inputs and known future inputs (like macro schedules), nor do they handle static metadata naturally.
- Empirically, standard transformers are often outperformed by simpler models on financial tabular time series (benchmark results from N-BEATS, N-HiTS show this).

**Modified Transformers with Promise:**
- Informer (2021): Sparse attention to reduce complexity to O(n log n). Better for long sequences.
- Autoformer (2022): Decomposition-based approach that separates trend and seasonality. Useful for non-stationary data.
- PatchTST (2023): Treats time series as patches (like image patches in ViT), showing strong results on multivariate series benchmarks.
- TimesFM (Google, 2024) and Moirai (Salesforce, 2024): Foundation model approaches pre-trained on massive time series corpora. Early evidence suggests pre-trained time series transformers transfer better to finance than training from scratch.

**Verdict for Finance:** Stock vanilla transformers are not recommended without modification. The TFT (below) is the gold standard for tabular financial time series. Foundation model approaches (TimesFM, Moirai) warrant experimentation as zero-shot or fine-tuned baselines.

### 4.4 Temporal Fusion Transformer (TFT) — Recommended Primary Architecture

**Origin:** Google Research. Lim et al. (2021). Designed explicitly for multi-horizon time series forecasting with mixed input types.

**Architecture Components:**

1. **Variable Selection Networks (VSN):** Instance-level gating that selects which input features are relevant for each prediction. This is critical for finance where feature relevance varies by market regime. The VSN outputs variable importance scores directly — a built-in interpretability mechanism.

2. **Gated Residual Networks (GRN):** Non-linear transformation blocks with skip connections that suppress irrelevant inputs. Allows the model to be selective without requiring all features to be informative.

3. **Static Covariate Encoders:** Separate processing pathway for time-invariant metadata (sector, market cap bucket, country, exchange). Static context is projected to condition the temporal layers.

4. **Sequence-to-Sequence Layer (LSTM encoder-decoder):** Local temporal processing of observed inputs. Captures short-range dependencies before attention is applied.

5. **Multi-Head Attention (Temporal Self-Attention):** Attends across the full historical sequence to capture long-range dependencies. Generates interpretable attention weights showing which past timesteps matter most for each prediction.

6. **Quantile Output Head:** Outputs multiple quantiles (e.g., 10th, 50th, 90th percentile) rather than a point estimate. Directly provides uncertainty bounds for position sizing.

**Why TFT Is Suited to Financial Data:**

- Handles three input categories simultaneously: static metadata (ticker-level), known future inputs (earnings dates, Fed meeting calendar, index rebalance dates), and unknown historical inputs (returns, volume, sentiment scores).
- Interpretable by design: VSN variable importance and attention weights are native outputs, not post-hoc approximations.
- Probabilistic forecasting via quantile regression matches the uncertainty-aware position sizing requirement.
- Outperforms LSTM, DeepAR, ETS, and ARIMA on multi-step forecasting benchmarks.

**Limitations of TFT:**
- Computationally expensive relative to LSTM or TCN. Training time can be 3-5x longer.
- Requires careful preprocessing: input normalization, handling of missing data, and feature construction must be rigorous.
- More hyperparameters than simpler models.
- Large dataset requirements: rule of thumb is 3-5 years of daily data minimum per asset for fine-tuning; cross-sectional pooling across many assets (universal model) is necessary for data efficiency.

**Verdict:** TFT is the recommended primary architecture for the structured factor forecasting component. It is not magic — on noisy financial data with low SNR, even TFT produces modest R² — but it is the best single architecture for handling the heterogeneity of financial inputs with built-in interpretability.

### Architecture Comparison Summary

| Property | LSTM/GRU | TCN | Vanilla Transformer | TFT |
|---|---|---|---|---|
| Training speed | Slow (sequential) | Fast (parallel) | Fast (parallel) | Moderate |
| Long-range dependency | Moderate | Good (with dilation) | Excellent | Excellent |
| Interpretability | Poor | Poor | Poor | Good (native) |
| Mixed input types | Poor (requires hacks) | Poor | Poor | Excellent (native) |
| Probabilistic output | Requires modification | Requires modification | Requires modification | Native (quantile) |
| Financial benchmark performance | Moderate | Moderate-Good | Moderate | Best in class |
| Overfitting risk | High | Moderate | High | Moderate |
| Data requirement | High | Moderate | Very high | High |
| Recommended role | Baseline/ensemble | Volatility forecasting | Foundation models only | Primary model |

---

## 5. Feature Engineering

Feature engineering for DL in finance is not optional. Raw price inputs to a neural network will overfit. The quality of features is the primary determinant of model quality. The following categories have empirical support for surviving nonstationarity.

### 5.1 Return-Based Features

**Why returns, not prices:** Raw price series are non-stationary (unit root processes). Returns are stationary in the sense that their distributional properties are more stable over time. All price-derived inputs must be expressed in returns or normalized differences, never in raw price levels.

- Log returns at multiple horizons: 1-day, 5-day, 10-day, 21-day, 63-day.
- Risk-adjusted returns: each horizon divided by rolling realized volatility over the same window.
- Momentum signals: cumulative return over 12 months excluding the most recent month (the standard 12-1 momentum factor), plus shorter-horizon variants.
- Mean-reversion signals at short horizons (1-5 day reversal, particularly in liquid large-cap equities).
- Return skewness and kurtosis over rolling windows (tail risk features).

### 5.2 Volatility Features

**Why volatility inputs work:** Volatility is far more persistent and predictable than returns. Volatility-derived features contain real signal for both volatility forecasting (direct use) and return forecasting (conditional: low-volatility stocks have different momentum dynamics than high-volatility stocks).

- Realized volatility: rolling standard deviation of returns at 5, 10, 21, 63-day windows.
- EWMA volatility (exponentially weighted — more weight to recent data).
- Garman-Klass volatility estimator using OHLC data (more efficient than close-to-close).
- Volatility-of-volatility: rolling standard deviation of the 21-day realized vol series.
- VIX and sector VIX levels, changes, and term structure slope.
- Implied vs. realized volatility spread (volatility risk premium).

### 5.3 Volume and Liquidity Features

- Volume normalized by trailing 21-day average (removes size effect).
- Dollar volume (volume × price) — absolute measure of market participation.
- Amihud illiquidity ratio: |return| / dollar volume, rolling average.
- Bid-ask spread (if available) — proxy for transaction costs and information content.
- Volume-return correlation (unusual volume accompanying a move is more informative than quiet moves).
- On-balance volume and volume-weighted price deviation.

### 5.4 Cross-Asset and Macro Features

**The rationale:** Individual stock returns do not happen in a vacuum. The factor structure (market beta, sector beta, rate sensitivity) creates systematic cross-asset dependencies. Including these inputs gives the model context about the current macro environment that is absent from single-ticker inputs.

- Market return (S&P 500 index) at 1, 5, 21-day horizons.
- Sector ETF returns (XLK, XLF, XLE, etc.) — 11 GICS sectors.
- Treasury yield curve features: 2-year, 10-year yields, 2s10s spread, changes in each.
- Credit spread: Investment grade and high yield OAS (option-adjusted spread) levels and changes.
- Dollar Index (DXY) changes.
- Commodity index changes (CRB, WTI crude as specific inputs).
- VIX level and VIX term structure slope (front vs. back month futures ratio).
- Factor return streams: value (HML), momentum (UMD), size (SMB) from standard factor models.

### 5.5 NLP-Derived Features

These are generated by the NLP sub-system (FinBERT / fine-tuned transformer):
- Earnings call sentiment score: aggregate tone (positive/negative/neutral).
- Delta sentiment: change in tone vs. prior quarter's call.
- Uncertainty score: density of hedging language and modal verbs.
- Guidance tone: language used specifically in the guidance section.
- Q&A sentiment divergence: management prepared remarks vs. analyst Q&A responses.
- 10-K language novelty: cosine distance of this year's filing vs. prior year (freshness signal).
- 8-K event flag: type of event (guidance update, executive change, earnings warning, etc.).

### 5.6 Normalization and Preprocessing

**The nonstationarity problem:** Even using returns rather than prices does not fully solve nonstationarity. The distributional properties of returns change across regimes (2008 vs. 2013 vs. 2020 are different distributions). Models trained on pre-2008 data systematically underperform post-crisis.

Normalization strategies that partially address this:

- **Cross-sectional Z-scoring:** At each time step, normalize each feature to zero mean and unit variance across the cross-section of all assets in the universe. This removes the time-series-level regime drift by anchoring to the contemporaneous cross-section. Critical for pooled multi-asset models.
- **Rolling Z-scoring with expanding or rolling windows:** Normalize each feature for each asset using the trailing N-day mean and standard deviation. Window length trades off between stability (longer) and adaptability to regime changes (shorter). Recommended: 252 trading days (one year) rolling window.
- **Rank transformation:** Replace each feature with its cross-sectional rank, normalized to [0, 1]. Eliminates outlier sensitivity. Standard practice in factor investing.
- **Winsorization:** Cap extreme values at the 1st and 99th percentiles before any other transformation. Prevents individual outlier events from dominating gradient updates.
- **Instance normalization within the model:** Some architectures (including TFT) support internal normalization layers. Adding adaptive input normalization layers (RevIN — Reversible Instance Normalization) has been shown to help on non-stationary financial series.

**What not to do:**
- Do not normalize using statistics computed over the full historical dataset (including the test period). This is look-ahead bias in normalization.
- Do not use raw prices or price levels as inputs to the network.
- Do not mix training and test set statistics for any preprocessing step.

### 5.7 Feature Stability and Survival Criteria

Before including any feature, it should pass:
1. **Economic rationale:** Is there a plausible mechanism? Features without a story are more likely to be spurious.
2. **Out-of-sample stability:** The feature should have positive predictive value in multiple independent holdout periods and across different asset universes.
3. **Orthogonality check:** Highly correlated features add noise, not signal. Measure pairwise correlations and remove redundant features.
4. **Nonstationarity survival test:** Does the feature's predictive validity degrade systematically over time? Apply rolling tests of predictive validity.

---

## 6. Training Methodology

### 6.1 The Look-Ahead Bias Problem

Look-ahead bias is the cardinal sin of financial backtesting. Any information that would not have been available to the model at prediction time, if incorporated, produces an artificially inflated backtest. With deep learning, look-ahead can be introduced subtly:

- Normalizing with future statistics (as noted above).
- Using a target variable computed with data from within the feature lookback window.
- Training on overlapping windows without embargo periods.
- Using adjusted close prices (retroactively adjusted for splits and dividends) in ways that encode future events.

Every preprocessing step, every normalization, every feature construction must be simulated as it would have occurred in real time.

### 6.2 Walk-Forward Validation

Standard k-fold cross-validation is inappropriate for time series data because it violates temporal ordering — it allows the model to train on future data and validate on past data. The correct approach is walk-forward (also called rolling-window or time-series cross-validation).

**Walk-Forward Protocol:**

```
Total data: 2010-01-01 to 2024-12-31

Fold 1: Train [2010-01-01 to 2015-12-31], Embargo [2016-01-01 to 2016-01-21], Test [2016-01-22 to 2016-12-31]
Fold 2: Train [2010-01-01 to 2016-12-31], Embargo [2017-01-01 to 2017-01-21], Test [2017-01-22 to 2017-12-31]
Fold 3: Train [2010-01-01 to 2017-12-31], Embargo [2018-01-01 to 2018-01-21], Test [2018-01-22 to 2018-12-31]
...continuing through 2023, hold out 2024 as final out-of-sample
```

**Embargo Period:** A gap between the training period end and validation period start, set to the length of the prediction horizon plus any feature lookback that could leak future information. If predicting 5-day returns with features that use up to 21-day windows, the embargo should be at least 21 business days. This prevents training data from overlapping with validation targets.

**Expanding vs. Rolling Window Training:**
- Expanding window: all data from the beginning to the current training cutoff is used. Maximizes data but may overweight distant past that is less relevant to current market conditions.
- Rolling window: only the most recent N years of data is used for training. More responsive to regime changes but discards older observations.
- Recommended: start with expanding window, then test rolling window with 3-5 year fixed training periods. Compare out-of-sample Sharpe ratios across both.

### 6.3 Purged Cross-Validation

For overlapping samples (e.g., when labels are computed as returns over a 5-day forward window, consecutive daily observations will have 4 days of overlap in their label), purging is required. Purged k-fold cross-validation (López de Prado, 2018) removes training observations whose labels overlap with validation period labels. This is computationally more expensive but eliminates a significant source of overfitting.

For combinatorial purged cross-validation (CPCV), the set of valid training-validation splits is restricted to those with no temporal overlap in labels, providing a better estimate of the strategy's true expected performance distribution.

### 6.4 Target Variable Construction

**Recommendation for primary target:** Risk-adjusted return over a fixed forward window.

- Compute raw forward log return over H days (e.g., H = 5 trading days).
- Divide by trailing realized volatility (same-length window) to produce a risk-adjusted score.
- Cross-sectionally rank and normalize to remove common market factor.
- For regression: use this continuous score as the training target.
- For classification: bin into quantiles (e.g., top 20% = "buy signal", bottom 20% = "sell signal", middle 60% = no action). This reduces sensitivity to outlier return days.

**Binary vs. regression targets:** Classification (direction) is more robust to outliers and produces well-calibrated probability outputs when paired with sigmoid activation and binary cross-entropy loss. Regression with MSE loss is sensitive to large return events. Consider ranking loss functions (pairwise or listwise) that directly optimize the ordinal ranking of predicted returns across assets, which is what matters for portfolio construction.

### 6.5 Training Infrastructure Requirements

- Minimum training data: 5 years of daily data across at least 200 assets for a pooled model.
- Cross-sectional pooling: train a single model across all assets rather than one model per asset. This dramatically improves data efficiency and forces the model to learn generalizable patterns.
- Batch construction: sample mini-batches such that each batch contains diverse assets across diverse dates, not consecutive windows from the same asset (which would cause the model to memorize asset-specific patterns).
- Gradient clipping: apply norm-based gradient clipping (typical value: 1.0) to prevent exploding gradients, which are common with financial data due to high-kurtosis events.
- Learning rate scheduling: cosine annealing or reduce-on-plateau schedulers. Financial time series models are sensitive to learning rate; too high leads to instability, too low causes underfitting.

---

## 7. Overfitting Mitigation

Overfitting is the dominant failure mode of DL in finance. The statistical properties of financial data make it uniquely susceptible:

- Low signal-to-noise ratio: the true predictive signal may explain only 0.1-0.5% of variance, while noise explains the remaining 99.5-99.9%.
- Small effective sample size: while a 10-year dataset has 2,500 trading days, each independent market regime (2008-crisis, 2009-2013 recovery, 2020-COVID, 2022-rate-shock) may have only a few hundred independent observations.
- Distribution shift: the data-generating process changes over time, invalidating statistical stationarity assumptions.
- Publication bias: academic papers report models that worked; the unreported models that failed are invisible.

### 7.1 Regularization Techniques

**Dropout:** Randomly set activations to zero during training with probability p. Prevents co-adaptation of neurons. Standard values for financial DL: 0.1-0.4 on hidden layers. Higher dropout is more aggressive regularization and better for small datasets.

**Weight Decay (L2 Regularization):** Adds λ||W||² to the loss function, penalizing large weights. Standard value: λ = 1e-4 to 1e-3. Forces the model toward simpler weight configurations.

**Early Stopping:** Monitor validation loss (on a temporally-separated validation set) and stop training when it ceases to improve. Patience parameter of 5-20 epochs is typical. Prevents the model from memorizing training data in later epochs.

**Gradient Norm Clipping:** Prevents individual large-gradient steps from destabilizing training. Norm threshold of 1.0 is standard.

**Label Smoothing:** For classification targets, rather than hard 0/1 labels, use soft labels (e.g., 0.1 and 0.9 instead of 0 and 1). Reduces overconfidence and improves calibration.

**Data Augmentation (Finance-Specific):**
- Window jittering: train on overlapping windows with random offsets.
- Noise injection: add small random perturbations to input features (Gaussian noise with σ proportional to feature standard deviation) — analogous to dropout at the input level.
- Synthetic minority oversampling for regime events: rare events (flash crashes, volatility spikes) are underrepresented; augment these if possible.

### 7.2 Ensemble Methods

Ensembles are the most reliable tool for reducing overfitting in financial DL. A single model's idiosyncratic errors are partially averaged out across an ensemble.

**Ensemble strategies:**

- **Architecture ensemble:** Train LSTM, TCN, and TFT with the same features and average predictions. Architectures fail differently, so averaging reduces model-specific failure.
- **Random seed ensemble:** Train the same architecture 5-10 times with different random weight initialization. Variance across predictions serves as an implicit uncertainty estimate.
- **Hyperparameter ensemble:** Train models with slightly different hyperparameter configurations within a plausible range. Averaging across configurations reduces sensitivity to any specific setting.
- **Temporal ensemble:** Combine models trained on different training window lengths (e.g., 2-year, 3-year, 5-year rolling windows). This provides implicit robustness to regime change — models trained on different history disagree, and their average is more conservative.
- **Feature subset ensemble (random subspace):** Train each model on a random subset of features. Reduces correlation between ensemble members.

**Ensemble weighting:** Simple averaging (equal weights) is robust. Performance-weighted averaging (weight by recent out-of-sample accuracy) can adapt to regime changes but introduces its own overfitting risk. Recommended: begin with equal weights, introduce performance weighting only after sufficient out-of-sample data is available (at least 6 months of live signals).

**Ensemble uncertainty:** The variance of ensemble member predictions provides a natural uncertainty signal. High disagreement among ensemble members signals lower confidence; such predictions should receive smaller position sizing.

### 7.3 Model Selection

The central paradox of model selection: the process of searching for the best model across hyperparameter configurations is itself a source of overfitting. If you run 100 hyperparameter configurations and select the best, the expected out-of-sample performance of the winner is substantially lower than its in-sample validation performance.

Mitigations:
- Limit hyperparameter search to a pre-specified budget (e.g., 20 configurations).
- Use Bayesian optimization for hyperparameter search rather than random or grid search — more efficient use of the configuration budget.
- Apply the Bailey-López de Prado probability of backtest overfitting formula to quantify expected performance shrinkage given the number of trials.
- Maintain a strict holdout set (the final test set) that is not examined until a single model configuration has been selected. Examining the test set multiple times and reselecting based on it is a form of test set overfitting.

---

## 8. Signal Generation and Confidence Scoring

### 8.1 Model Output Interpretation

**For TFT with quantile output head:**
The model produces quantile forecasts: Q10, Q50, Q90 (10th, 50th, 90th percentile of the predicted return distribution). The Q50 is the point estimate; the Q10-Q90 spread is the uncertainty band.

Interpreting these outputs:
- If Q50 is strongly positive and the Q10-Q90 band is narrow, this is a high-confidence bullish signal.
- If Q50 is positive but Q10 is negative, the distribution spans both sides — low conviction.
- The Q10-Q90 spread normalized by the absolute value of Q50 provides a signal-to-uncertainty ratio.

**For ensemble outputs:**
- Compute the mean of all ensemble member predictions — this is the signal estimate.
- Compute the standard deviation across ensemble member predictions — this is the uncertainty estimate.
- The signal-to-uncertainty ratio (mean / std across members) is the confidence score.

### 8.2 Signal Construction

Raw model output is not directly usable as a trading signal. Several transformations are required:

1. **Cross-sectional ranking:** For each date, rank all assets in the universe by model output (Q50 or ensemble mean). Normalize ranks to [0, 1]. This ensures the signal is comparable across assets and immune to absolute level changes.

2. **Winsorization:** Cap extreme predictions at the 1st and 99th percentile to prevent outlier predictions from dominating position sizing.

3. **Sector neutralization:** Remove sector-level return component from the signal by demeaning within each GICS sector. This prevents the strategy from being a disguised sector bet.

4. **Market beta neutralization:** Regress the cross-sectional signal on estimated market beta and remove the component explained by beta. This isolates idiosyncratic alpha from factor exposure.

5. **Decay weighting:** If predictions are produced daily but positions are rebalanced less frequently, apply an exponential decay to yesterday's signal to account for information aging.

### 8.3 Confidence Scoring Framework

| Score Component | Source | Weight |
|---|---|---|
| Ensemble signal agreement | Std dev across members (inverted) | 40% |
| TFT quantile spread | (Q90 - Q10) / |Q50| (inverted) | 30% |
| Feature data quality | Missing value rate, staleness | 15% |
| Regime alignment | Does current regime match training distribution? | 15% |

**Confidence score = weighted average of above components, normalized to [0, 1].**

A confidence score below 0.3 suppresses the signal entirely (no trade). A confidence score between 0.3 and 0.7 scales position to 50% of the full-size allocation. A confidence score above 0.7 permits full-size allocation.

This three-tier gating — off, half, full — is preferable to continuous scaling in practice because it limits the number of positions opened on weak signals, reducing transaction costs and preventing the portfolio from becoming crowded with low-conviction bets.

### 8.4 NLP Signal Construction

The NLP pipeline produces a separate set of signals from unstructured text:

- Event-driven signals: generated at the time of an earnings call or 8-K filing, with a decay function (e.g., half-life of 5 trading days) applied to model the information absorption by the market.
- Tone drift signals: computed as the delta of the current call's sentiment score vs. the rolling average of the prior 4 quarters. Negative drift is a bearish signal; positive drift is bullish. This is a more robust signal than absolute tone because it controls for base rates of positivity in corporate language.
- Analyst surprise signals: when earnings beat/miss is accompanied by a tone signal in the same direction, the composite signal is stronger (confirming information). When they diverge, the tone signal may be leading (soft guidance deterioration not yet reflected in numbers).

---

## 9. Portfolio Construction

### 9.1 Signal-to-Weight Mapping

The composite signal (combining DL factor signal and NLP signal) maps to portfolio weights through a construction process that enforces diversification and risk limits. A raw signal ranking should never be directly used as a weight without constraints.

**Recommended approach: Signal-weighted long-short with hard constraints.**

- Compute composite score for each asset: weighted combination of DL return forecast signal, DL volatility forecast, and NLP event signal.
- Rank all assets by composite score.
- Target long positions in the top N assets (by score) and short positions in the bottom N assets.
- Weight each position proportionally to: (confidence score) × (1 / estimated volatility) — inverse volatility weighting within the long and short books.
- Apply hard gross and net exposure limits (see Section 11).

### 9.2 Confidence-Weighted Sizing

Position size for asset i:

```
w_i = (confidence_i × signal_strength_i) / vol_i × (budget / sum_of_all_weights)
```

where:
- confidence_i = confidence score [0, 1]
- signal_strength_i = absolute value of normalized cross-sectional signal
- vol_i = estimated 21-day realized volatility of asset i
- budget = total gross exposure budget (e.g., 2.0x for 200% gross)

This formulation simultaneously rewards high-confidence signals, penalizes high-volatility assets (risk-adjusted sizing), and normalizes the portfolio to the target gross exposure.

### 9.3 Concentration Limits

- Maximum weight per single asset: 5% of portfolio NAV (long or short). Prevents idiosyncratic blowup from single-name exposure.
- Maximum sector concentration: 25% of gross long or short in any single GICS sector. Controls against hidden sector bets.
- Maximum factor exposure: beta to standard risk factors (market, size, value, momentum) should be within ±0.2 of target. Prevent the DL signal from becoming a disguised factor bet.
- Minimum number of positions: at least 20 longs and 20 shorts. Diversification floor to prevent concentration.
- Maximum single-country exposure: 40% of gross exposure in any country for multi-asset strategies.

### 9.4 Turnover Control

DL models, especially those retrained frequently, can generate high turnover that erodes returns through transaction costs. Controls:

- Signal smoothing: apply an exponential moving average to each asset's daily signal with a 2-5 day half-life before converting to a weight. This reduces turnover without sacrificing much signal quality.
- Minimum holding period: do not close a position opened on day T unless a) the signal reverses with high confidence on day T+3 or later, or b) a stop-loss is triggered.
- Rebalancing threshold: only rebalance positions if the target weight deviates from current weight by more than a threshold (e.g., 0.5% of NAV). Prevents excessive trading on small signal updates.

---

## 10. Model Lifecycle Management

### 10.1 Retraining Schedule

DL models trained on historical financial data have finite shelf lives. The primary driver is distribution shift — the statistical relationships between features and targets evolve as the market adapts, new participants enter, and macro regimes change.

**Recommended retraining cadence:**

- **Quarterly (primary):** Full model retraining on all available data using the walk-forward validation protocol. Select hyperparameters, rebuild the ensemble, validate on the most recent holdout year.
- **Monthly (incremental):** Fine-tuning of existing model weights using the most recent month's data, with a very small learning rate (1e-5) to update model parameters without catastrophic forgetting of earlier patterns. This is analogous to online learning with regularization toward the prior state.
- **Event-driven (reactive):** Immediate model re-evaluation (not necessarily retraining) when a structural break is detected. If recent out-of-sample prediction accuracy drops by more than 2 standard deviations from its historical mean, escalate to emergency assessment.

### 10.2 Performance Monitoring and Decay Detection

Monitoring should track the following metrics on a rolling basis:

**Signal quality metrics (computed weekly on out-of-sample predictions):**
- IC (Information Coefficient): Spearman rank correlation between predicted score and realized return. Benchmark: IC > 0.03 on a weekly basis is meaningful; IC < 0.01 consistently signals decay.
- ICIR (IC Information Ratio): IC divided by its standard deviation over a rolling 12-week window. This measures signal reliability. Target ICIR > 0.5.
- Hit rate: fraction of assets where the predicted direction matches realized direction. Meaningful only as a relative metric (vs. historical baseline), not in absolute terms.
- Long-short return attribution: the model generates a notional long-short portfolio each period. Track cumulative return, Sharpe ratio, and drawdown of this paper portfolio.

**Model calibration metrics:**
- Expected calibration error (ECE): does the model's quantile output match empirical frequencies? If the model predicts a 10% probability of being below Q10, do 10% of realized outcomes fall below that threshold?
- Feature importance stability: SHAP values should be computed on the most recent 60-day out-of-sample period. Compare top-10 features to the historical benchmark. Large shifts in feature importance can signal either regime change or data quality issues.

**Data quality metrics:**
- Staleness rate: percentage of feature inputs that are older than expected. High staleness signals data pipeline failure.
- Coverage: percentage of universe assets with complete features. Coverage drops signal data provider issues.
- Distribution drift: KL divergence or maximum mean discrepancy between recent feature distributions and training feature distributions. Large drift signals regime change.

### 10.3 Alpha Decay Recognition

Alpha decay manifests as a gradual reduction in IC, ICIR, and signal-weighted long-short returns. The key question is whether the decay is:

- **Statistical noise:** Normal fluctuation in a strategy with inherently noisy returns. Requires patience and does not warrant intervention.
- **Crowding:** The signal has been discovered by enough competing firms that its profitability is competed away. Manifests as declining IC without declining data quality, often in liquid large-cap names first.
- **Regime change:** The underlying statistical relationship has broken down due to a structural market change (e.g., zero interest rate environment vs. high rate environment). Manifests as model performance diverging from historical norms during identifiable macro shifts.
- **Data/code issue:** A data provider change, corporate action handling error, or preprocessing bug has corrupted inputs. Manifests suddenly rather than gradually.

Detection protocol: apply a CUSUM (cumulative sum) control chart to the weekly IC series. When the CUSUM statistic exceeds 3 standard deviations from zero, trigger a decay investigation. Distinguish causes before deciding on remediation.

### 10.4 Model Versioning

- Every trained model is tagged with: training cutoff date, feature set version, hyperparameter configuration, and walk-forward validation results.
- A champion-challenger framework: the production model is the "champion." New model versions are the "challenger," which runs in shadow mode (predictions generated but not traded) for at least 30 business days before promotion.
- Promotion criterion: challenger must show ICIR > champion ICIR and no increase in maximum drawdown over the shadow period.
- Rollback procedure: if a newly promoted model shows materially worse performance than the prior champion within 30 trading days, automatic rollback to the prior version.

---

## 11. Risk Management

### 11.1 Model-Specific Failure Modes

**Overfit model trading on noise:** The model produces signals based on spurious historical correlations. Symptoms: high in-sample IC, rapidly deteriorating out-of-sample IC, signals that are not economically interpretable. Mitigation: strict walk-forward validation, ensemble variance monitoring, human review of top feature importance.

**Regime mismatch (covariate shift):** The model was trained on one market regime (e.g., 2012-2020 low-volatility bull market) and is operating in a different one (e.g., 2022 high-inflation, rising-rate bear market). Mitigation: monitor feature distribution drift, include diverse regime data in training, use rolling training windows, and apply regime classifiers to down-weight model output during identified distribution shifts.

**Data leakage after deployment:** A data provider changes a data point retroactively (e.g., restates earnings), or a timing assumption is violated (e.g., assuming earnings are released after market close when some are released pre-market). Mitigation: point-in-time database for all fundamental data, explicit timestamp validation for all data ingestion, regular data quality audits.

**Model failure under stress:** DL models trained on normal market conditions may produce extreme or erratic predictions during market dislocations (March 2020 COVID crash, October 1987 analog, 2008 Lehman period). The model has never seen anything similar and its predictions are unreliable. Mitigation: automatic risk reduction rules that trigger when VIX exceeds a threshold (e.g., > 35), reducing gross exposure by 50% and applying tighter stop-losses.

**NLP pipeline failure:** The text preprocessing pipeline produces incorrect sentiment scores due to domain shift in language (new CEO, new terminology) or data provider interruptions. Mitigation: anomaly detection on daily NLP output distributions, fallback to prior quarter's NLP signal when current data quality is flagged.

### 11.2 Hard Position Limits

| Limit Type | Threshold | Action |
|---|---|---|
| Maximum single position | 5% of NAV | Hard limit; orders blocked above this |
| Maximum gross exposure | 200% of NAV | Hard limit |
| Maximum net exposure | ±20% of NAV | Hard limit |
| Maximum sector gross | 25% of NAV per sector | Hard limit |
| Maximum factor beta | ±0.20 (any factor) | Soft limit; alert at breach |
| Daily loss limit | -2% of NAV | Reduce gross exposure by 50% |
| Weekly loss limit | -5% of NAV | Halt new positions, wind down |
| Monthly loss limit | -8% of NAV | Full strategy suspension, senior review |

### 11.3 Stop-Loss Rules

**Position-level stop-loss:** Any individual position that loses more than 2× its expected 1-day volatility (approximately 2 standard deviations) in a single session is closed immediately, regardless of model signal. This prevents "holding while the model is wrong" scenarios.

**Correlation-based stop:** If multiple positions in the same sector or correlated cluster all move against the portfolio simultaneously, exit positions in that cluster regardless of individual stop status. Correlation spikes during stress events mean individual position risk estimates understate actual portfolio risk.

**Model signal-stop:** If the model's predicted direction for a position reverses (signal crosses zero with confidence > 0.5), reduce the position by 50% immediately and close fully within 2 trading days.

### 11.4 Concentration Risk Under Stress

When market-wide correlation rises above 0.7 (a standard stress indicator), individual asset risk models break down because diversification is temporarily lost. Under such conditions:
- Gross exposure automatically scales by (1 - (current_correlation - 0.5) × 2) where current_correlation is the average pairwise correlation in the portfolio.
- This mechanically reduces gross exposure from 100% at correlation = 0.5 to 0% at correlation = 1.0 — a scaled de-risking as correlation spikes.

---

## 12. Execution Considerations

### 12.1 Prediction Horizon and Holding Period

The prediction horizon must match the holding period. A model trained to predict 5-day forward returns should generate signals that the strategy expects to hold for approximately 5 days.

**Recommended initial configuration:** 5-day forward return target, 3-5 day holding period. This is short enough that information half-life is relevant but long enough to keep turnover manageable.

**Trade-offs:**
- Shorter prediction horizon (1 day): Higher alpha potential but high turnover, transaction cost sensitive, and more susceptible to microstructure noise.
- Medium horizon (5-21 days): Balances alpha decay rate with transaction cost burden. Best fit for DL factor models.
- Longer horizon (21-63 days): Lower signal strength per unit time but very low turnover. NLP signals (earnings-based) are better suited to this horizon.

### 12.2 Market Impact Considerations

DL factor strategies run across diversified universes (100+ stocks) with typical daily turnover of 20-40% of portfolio. For a hypothetical $50M portfolio:

- Daily turnover at 30%: $15M/day in gross trading.
- For large-cap US equities with average daily volume of $500M+, this is under 0.003% of daily volume — negligible impact.
- For mid-cap stocks with average daily volume of $50M, this is 0.03% of daily volume — still manageable with patient execution (VWAP over the full session).
- For small-cap or illiquid names: market impact becomes significant and must be incorporated into the signal generation as a cost-adjusted expected return.

Minimum ADV (average daily volume) threshold for eligible universe: $10M per day. Preferred threshold: $100M+.

### 12.3 Execution Algorithm Selection

- For planned rebalances (end of day signal update): TWAP or VWAP algorithms spread the order over the session to minimize impact.
- For stop-loss or risk reduction exits: market orders or aggressive VWAP algorithms when speed matters more than price.
- Do not use limit orders for DL-driven trades unless the limit is within a narrow band of the current mid-price. Limit order management creates additional implementation complexity and increases the risk of adverse selection.

### 12.4 Transaction Costs in Signal Evaluation

All signal evaluation, in both backtesting and live monitoring, must incorporate realistic transaction cost estimates:

- Commission: $0.003-$0.005 per share for institutional brokers (or basis points equivalent).
- Bid-ask spread crossing: assume half-spread on entry and exit. Estimate from historical bid-ask data or use the Amihud ratio as a proxy.
- Market impact (Kyle's lambda model): impact proportional to order size relative to daily volume.
- Total round-trip cost estimate for large-cap US equities at 30% daily turnover: approximately 3-7 bps per trade, or 100-250 bps annualized at typical turnover rates.

Any signal with a post-cost expected Sharpe ratio below 0.3 should not be deployed.

---

## 13. Key Risks and Failure Modes

### 13.1 Overfitting — The Primary Risk

The single most likely failure mode. A DL model can achieve impressive backtest results that are entirely an artifact of the model memorizing historical noise. The backtest looks convincing because:

- The model is very expressive (many parameters) relative to the number of independent observations.
- The researcher unconsciously biases hyperparameter selection toward configurations that perform well in-sample.
- The model captures regime-specific patterns that appear consistent in the historical data but are not generalizable.

Evidence of this being widespread: papers using LSTM achieve "94% accuracy" on individual stock prediction, while empirically validated production signals produce IC of 2-5% monthly. The gap is almost entirely overfitting.

Probability of encountering this: extremely high without strict walk-forward methodology, purged cross-validation, and ensemble variance monitoring.

### 13.2 Regime Change and Distribution Shift

Markets undergo structural changes that invalidate model assumptions: zero interest rates (2009-2021) to high rates (2022+); algorithmic market-making dominance (post-2010) vs. dealer-based markets; COVID-era retail trading (2020-2021). A model trained exclusively on one regime will fail in another.

This is not fully solvable — it is an inherent limitation of any historical training approach. Mitigations (rolling training windows, regime detection, exposure reduction under detected distribution shift) reduce but do not eliminate the risk.

### 13.3 Crowding

If the same DL features and architectures are adopted industry-wide, all strategies trade on the same signals simultaneously. The result is correlated drawdowns during periods of forced liquidation or factor reversals. In 2018 and 2020, momentum factor crowding led to rapid, severe reversals that damaged systematic strategies industry-wide. DL crowding risk is harder to detect than traditional factor crowding because signals are less transparent.

### 13.4 Model Rot

Even without regime change, a model deteriorates as: new market participants (other ML funds) learn the same patterns and trade against them; the information in the training data becomes incorporated into prices; and the model's features become stale (e.g., a technical indicator that was predictive pre-HFT may not be post-HFT).

Model rot is slow and insidious. It may take 6-18 months to observe statistically significant decay in IC. By the time the decay is statistically confirmed, substantial losses may have occurred.

### 13.5 Data Quality and Pipeline Failures

Financial data is messy: corporate actions (splits, dividends, mergers) must be handled correctly; point-in-time databases for fundamental data are expensive and imperfect; alternative data providers may change their collection methodology; API failures cause missing data. Any of these, if undetected, produce incorrect feature inputs that the model will attempt to trade on, leading to losses.

### 13.6 Leverage and Liquidity Risk

If the strategy runs with gross exposure materially above 100% NAV (typical for long-short equity) and relies on prime broker leverage, a prime broker margin call during a period of market stress can force liquidation at the worst possible time. This is not unique to DL strategies but is amplified by the possibility that model signals are wrong precisely during stress events.

### 13.7 Regulatory and Operational Risk

- Some jurisdictions impose limits on algorithmic trading frequency or require pre-trade risk checks.
- A model that generates unusually concentrated activity in a single stock may trigger market manipulation scrutiny.
- Explainability requirements: some regulated entities must be able to explain trading decisions. Black-box DL models may conflict with this.

---

## 14. Honest Assessment of Probability of Success vs. Alternatives

### Baseline Performance Expectations

Based on the academic literature and practitioner experience:

- **Best case (NLP + factor DL ensemble, strict methodology):** Annualized Sharpe ratio of 0.8-1.5 on a diversified long-short portfolio before fees, achievable with a mature NLP pipeline and good data infrastructure. This is consistent with documented NLP signal Sharpes of 2.5+ at the standalone signal level (pre-cost, pre-combination with other signals).
- **Base case (DL factor model only, no NLP):** Annualized Sharpe of 0.3-0.7 after walk-forward validation and transaction costs. Modest improvement over a linear factor model.
- **Worst case (typical academic-style model without rigorous methodology):** Sharpe ratio close to zero or negative after transaction costs. This is the most common real-world outcome for teams new to financial ML.

### Comparison to Alternatives

| Strategy | Expected Sharpe (realistic) | Key Advantage | Key Risk |
|---|---|---|---|
| DL Factor + NLP (this spec) | 0.8-1.5 | Novel information extraction | Overfitting, model rot |
| Linear multi-factor model | 0.5-1.2 | Interpretable, robust | Limited feature space |
| Gradient boosted trees | 0.7-1.3 | Best for tabular data, less overfitting | Same nonstationarity risk |
| Statistical arbitrage | 0.8-2.0 | Mean reversion is robust | Cointegration breaks |
| Trend following (CTA) | 0.5-0.8 | Diversified, crisis alpha | Long drawdowns |
| Post-earnings drift | 0.6-1.2 | Behavioral, documented | Decay as crowded |

**Assessment:** The DL approach justified over alternatives only when NLP is included. The NLP component is the clearest source of genuine incremental alpha — large-scale text extraction at frequencies humans cannot match is a real technological advantage. The structured factor DL component (replacing a linear model) adds incrementally but is not transformative.

Without NLP, the recommendation is to use gradient boosted trees (e.g., LightGBM) over deep learning for equity factor prediction. GBTs are more data-efficient, less prone to catastrophic overfitting, faster to train and iterate, and achieve comparable out-of-sample performance to DL on structured financial features. The case for replacing GBTs with DL in the factor component is not conclusively made by the academic literature.

### Resource Requirements vs. Expected Return

| Resource | Requirement |
|---|---|
| Engineering team | 2-3 ML engineers, 1 quant researcher minimum |
| Data infrastructure | Point-in-time database, NLP pipeline, feature store: $50-200K/year |
| Compute | GPU cluster for training + daily inference: $5-20K/month |
| Data feeds | Earnings transcripts, filings parser, news feed: $30-100K/year |
| Timeline to production | 12-24 months (research → live trading) |

**The honest conclusion:** Deep learning adds genuine value in a narrow set of applications within algorithmic trading — primarily NLP-based information extraction and, secondarily, nonlinear factor interaction detection. It is not a generalized alpha engine. The probability of success is high for teams with strong ML infrastructure, a disciplined methodology, and realistic expectations about the incremental improvements achievable. It is low for teams that approach it as "train a neural network on price history and see what happens."

The best real-world models — at firms like Two Sigma, DE Shaw, and Citadel — use DL as one component of a diversified factor and signal ensemble, with heavy investment in data quality, infrastructure, and research process, rather than as a standalone trading oracle.

---

## 15. Parameters and Tunable Knobs

The following parameters define the strategy's behavior and require calibration through walk-forward validation. Default values are listed as starting points; these should be treated as hypotheses to validate, not ground truth.

### 15.1 Model Architecture Parameters

| Parameter | Default | Range | Notes |
|---|---|---|---|
| Model type | TFT | {LSTM, TCN, TFT, Ensemble} | TFT recommended; ensemble if compute permits |
| Hidden state dimension | 64 | 32-256 | Larger = more expressive, more prone to overfit |
| Number of attention heads | 4 | 1-8 | TFT multi-head attention; 4 is default |
| Number of LSTM layers | 2 | 1-4 | For LSTM baseline and TFT internal LSTM |
| Dropout rate | 0.2 | 0.1-0.5 | Higher = more regularization |
| Lookback window (sequence length) | 63 trading days | 21-252 | Longer lookback captures more history but increases overfit risk |
| Prediction horizon | 5 trading days | 1-21 | Must match holding period |
| Quantile outputs | {0.1, 0.5, 0.9} | Flexible | Add 0.25, 0.75 for finer uncertainty |

### 15.2 Training Parameters

| Parameter | Default | Range | Notes |
|---|---|---|---|
| Learning rate | 1e-3 | 1e-4 to 1e-2 | With cosine annealing scheduler |
| Batch size | 256 | 64-1024 | Larger batch → more stable gradients |
| Maximum epochs | 100 | 50-500 | With early stopping (patience=10) |
| Early stopping patience | 10 | 5-30 | Epochs without validation improvement before stopping |
| Weight decay (L2) | 1e-4 | 1e-5 to 1e-3 | L2 regularization coefficient |
| Gradient clip norm | 1.0 | 0.5-5.0 | Norm threshold for gradient clipping |
| Training window length | Expanding from 2015 | Rolling 3-5yr or expanding | Test both; rolling more adaptive, expanding uses more data |
| Walk-forward fold count | 8 folds | 5-10 | More folds = better estimate, more compute |
| Embargo period | 21 business days | 10-42 | Scales with prediction horizon and max feature lookback |

### 15.3 Feature Engineering Parameters

| Parameter | Default | Range | Notes |
|---|---|---|---|
| Return lookback windows | [1, 5, 10, 21, 63] | Subset or expanded | These 5 horizons capture short-to-medium term |
| Volatility estimation window | 21 days | 10-63 | Rolling standard deviation of daily returns |
| Cross-sectional z-score window | 252 days | 126-504 | Window for computing cross-sectional normalization stats |
| Winsorization percentile | [1, 99] | [0.5, 99.5] to [2, 98] | Tighter clips reduce outlier influence more aggressively |
| NLP sentiment decay half-life | 5 trading days | 3-10 | How quickly an earnings signal fades |
| Minimum ADV for universe | $100M | $10M-$500M | Liquidity filter; tighter = more liquid, fewer stocks |

### 15.4 Signal Generation Parameters

| Parameter | Default | Range | Notes |
|---|---|---|---|
| DL signal weight | 50% | 30-70% | Weight vs. NLP signal in composite |
| NLP signal weight | 30% | 10-50% | Depends on coverage of NLP pipeline |
| Volatility regime weight | 20% | 10-30% | Weight of volatility forecast in composite |
| Confidence threshold (suppress) | 0.3 | 0.1-0.5 | Below this confidence, no trade |
| Confidence threshold (half-size) | 0.7 | 0.5-0.8 | Below this confidence, half position |
| Signal smoothing half-life | 3 days | 1-10 | EMA applied to daily signal before weight conversion |

### 15.5 Portfolio Construction Parameters

| Parameter | Default | Range | Notes |
|---|---|---|---|
| Target gross exposure | 150% | 100-200% | Long + short as % of NAV |
| Target net exposure | 0% | -15% to +15% | Net market exposure |
| Maximum single position | 3% of NAV | 1-5% | Hard cap per asset |
| Maximum sector concentration | 20% of NAV | 10-30% | GICS sector cap |
| Minimum number of positions | 20 long + 20 short | 10-50 | Diversification floor |
| Rebalancing frequency | Daily | Daily, Weekly | Daily signal update; weekly full rebalance may reduce costs |
| Rebalancing threshold | 0.5% of NAV | 0.2-1.0% | Minimum deviation to trigger rebalance |

### 15.6 Risk Management Parameters

| Parameter | Default | Range | Notes |
|---|---|---|---|
| Daily loss limit | -2% of NAV | -1% to -3% | Triggers gross reduction to 75% |
| Weekly loss limit | -5% of NAV | -3% to -7% | Halts new positions |
| Monthly loss limit | -8% of NAV | -5% to -12% | Full suspension |
| Position stop-loss | 2× expected daily vol | 1.5× to 3× | Exits position if move exceeds this threshold |
| VIX stress threshold | 35 | 25-45 | Above this VIX, reduce gross by 50% |
| Correlation stress threshold | 0.7 | 0.5-0.8 | Average pairwise correlation triggering de-risking |

### 15.7 Lifecycle Management Parameters

| Parameter | Default | Range | Notes |
|---|---|---|---|
| Primary retraining cadence | Quarterly | Monthly to Semi-annual | More frequent = more adaptive, more operational burden |
| Incremental fine-tuning cadence | Monthly | Weekly to Quarterly | Low-LR update on recent data |
| IC decay alert threshold | 2 std deviations | 1.5-3 | CUSUM threshold for decay detection |
| Shadow model period | 30 business days | 20-60 | Duration challenger runs before promotion |
| Minimum ICIR for production | 0.5 | 0.3-0.8 | Minimum acceptable signal quality for live deployment |
| Model ensemble size | 5 | 3-10 | More members = better uncertainty estimates, more compute |

---

*This specification is a living document. Parameters, architecture choices, and operational procedures should be revisited quarterly as new research emerges and production experience accumulates. The financial ML literature is evolving rapidly — specifically in foundation model approaches (TimesFM, Moirai, Chronos) that may materially change the architecture recommendations within 12-18 months.*
