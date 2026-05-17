# Post-Earnings Announcement Drift (PEAD) + NLP Strategy Specification

**Version**: 1.0  
**Status**: Draft  
**Domain**: Event-Driven Equity  

---

## Table of Contents

1. [Strategy Overview and Thesis](#1-strategy-overview-and-thesis)
2. [Academic Foundations](#2-academic-foundations)
3. [Earnings Surprise Measurement](#3-earnings-surprise-measurement)
4. [NLP Signal Construction](#4-nlp-signal-construction)
5. [Combined Signal Architecture](#5-combined-signal-architecture)
6. [Universe and Event Detection](#6-universe-and-event-detection)
7. [Entry and Exit Logic](#7-entry-and-exit-logic)
8. [Portfolio Construction](#8-portfolio-construction)
9. [Risk Management](#9-risk-management)
10. [Execution Considerations](#10-execution-considerations)
11. [Regime Sensitivity](#11-regime-sensitivity)
12. [Key Risks and Failure Modes](#12-key-risks-and-failure-modes)
13. [Parameters and Tunable Knobs](#13-parameters-and-tunable-knobs)

---

## 1. Strategy Overview and Thesis

### 1.1 Core Idea

Post-Earnings Announcement Drift (PEAD) is the empirically documented tendency for stock prices to continue moving in the direction of an earnings surprise for weeks to months following the announcement. The effect is directionally persistent: firms with large positive earnings surprises (high SUE decile) drift upward, and firms with large negative surprises (low SUE decile) drift downward, generating a long-short spread that has been observed across six decades of market data.

This strategy combines the classical quantitative PEAD signal — standardized unexpected earnings (SUE) — with modern natural language processing applied to earnings call transcripts, press release text, and forward guidance language. The central thesis is that the market underreacts not only to the *number* in the earnings report but also to the *information* conveyed in how management describes results, characterizes future prospects, and responds to analyst questions. NLP allows us to extract and quantify this additional layer of soft information, which is orthogonal to the raw EPS surprise and improves signal precision.

### 1.2 Behavioral Thesis: Why Underreaction Occurs

PEAD is grounded in behavioral finance. The foundational explanation is that investors fail to fully incorporate the information content of an earnings announcement at the moment of release. Several mechanisms drive this:

**Limited attention**: Investors, including professional ones, cannot simultaneously process every earnings announcement in a given quarter. Low-coverage, low-analyst-following, and small-cap names receive proportionally less attention, and their information is processed more slowly. Drift is therefore strongest among neglected stocks.

**Anchoring and conservatism**: Investors anchor to prior expectations and update their beliefs only partially when confronted with new information. Rather than updating to the rational Bayesian posterior, they take a weighted average between their prior and the new signal, producing a systematic underreaction that dissipates gradually.

**Earnings fixation**: The market tends to fixate on the headline EPS number and under-processes the qualitative signals embedded in management's language — tone, uncertainty, guidance specificity, and analyst Q&A dynamics. These signals are predictively valuable and slow to be priced.

**Naive extrapolation of earnings**: Bernard and Thomas (1990) showed that investors behave as though they believe quarterly earnings follow a seasonal random walk, failing to account for the well-documented positive autocorrelation in seasonal earnings changes across adjacent quarters. This causes systematic underreaction to the persistence of high or low earnings.

**Limits to arbitrage**: Even sophisticated investors who recognize the drift cannot fully exploit it due to transaction costs, short-selling constraints, idiosyncratic risk, and capital constraints. This prevents the anomaly from being arbitraged away instantly.

### 1.3 Alpha Sources

The strategy draws alpha from three distinct sources:

| Source | Description | Horizon |
|--------|-------------|---------|
| Quantitative surprise (SUE) | EPS and revenue surprises vs. analyst consensus and internal time-series models | Day 1 through Day 60 |
| Soft information (NLP) | Tone, uncertainty, guidance specificity, Q&A dynamics from transcripts | Day 1 through Day 40 |
| Guidance revision signal | Forward EPS/revenue guidance beats vs. prior guidance, language around upward revision | Day 1 through Day 30 |

The combined signal is more powerful than any individual component and creates a higher-conviction ranking of expected drift magnitude.

---

## 2. Academic Foundations

### 2.1 Discovery: Ball and Brown (1968)

Ray Ball and Philip Brown published "An Empirical Evaluation of Accounting Income Numbers" in the *Journal of Accounting Research* in 1968 — the first systematic demonstration of PEAD. They examined whether information in annual accounting earnings was useful to market participants by studying cumulative abnormal returns (CARs) around earnings announcements. Their finding: even after the public announcement of earnings, abnormal returns continued to drift for firms with unexpected good news (positive drift) and firms with unexpected bad news (negative drift), indicating the market incorporated earnings information only slowly and partially. This was among the first empirical challenges to the strong form of the Efficient Market Hypothesis.

### 2.2 Replication and Quantification: Foster, Olsen, and Shevlin (1984)

George Foster, Chris Olsen, and Terry Shevlin significantly extended Ball and Brown's work in their 1984 paper "Earnings Releases, Anomalies, and the Behavior of Security Returns." They moved beyond annual earnings to quarterly earnings and introduced the standardized unexpected earnings (SUE) measure as a way to rank earnings surprises cross-sectionally. Their central quantitative finding: a long position in stocks in the highest SUE decile combined with a short position in stocks in the lowest decile generated an annualized abnormal return of approximately 25% over the 60 trading days following announcement, before transaction costs. This established PEAD as one of the most precisely measured anomalies in the financial literature.

### 2.3 Risk Premium vs. Delayed Price Response: Bernard and Thomas (1989, 1990)

Victor Bernard and Jacob Thomas produced the most influential theoretical dissection of PEAD in two landmark papers.

**Bernard and Thomas (1989)** — "Post-Earnings-Announcement Drift: Delayed Price Response or Risk Premium?" (*Journal of Accounting Research*, 27, 1-36): They systematically tested whether the drift could be explained by a risk premium consistent with market efficiency. They found no evidence that PEAD was compensation for systematic risk exposure. The drift was not explained by beta, size, or book-to-market factors available at the time. Their conclusion was that PEAD reflected genuine delayed price response — a market inefficiency.

**Bernard and Thomas (1990)** — "Evidence That Stock Prices Do Not Fully Reflect the Implications of Current Earnings for Future Earnings": They documented the precise nature of investor naivety. Investors appeared to behave as though earnings followed a seasonal random walk, when in fact adjacent quarterly earnings are positively autocorrelated (Q1 of year t correlates with Q1 of year t-1) and lag-4 earnings are negatively correlated. This creates a predictable pattern: approximately 25-30% of the total post-announcement drift occurs within the three-day windows surrounding the next four quarterly earnings announcements, despite those windows constituting only about 5% of total trading days — strong evidence of predictable, systematic underreaction.

The specific autocorrelation pattern Bernard and Thomas identified:

| Quarterly Lag | Autocorrelation of Seasonal Earnings Changes |
|--------------|----------------------------------------------|
| Lag 1 (one quarter) | Positive (~+0.34) |
| Lag 2 (two quarters) | Positive (~+0.19) |
| Lag 3 (three quarters) | Positive (~+0.06) |
| Lag 4 (four quarters) | Negative (~-0.24) |

Market prices behave as if the lag-1, lag-2, and lag-3 correlations are zero and the lag-4 correlation is also zero, when in fact all four are non-trivial. This is the mechanistic underpinning of why the drift re-accelerates around subsequent earnings dates.

### 2.4 Limits to Arbitrage

PEAD persists despite being well-known because of structural limits to arbitrage. These are not incidental frictions but systematic barriers that prevent rational, well-capitalized investors from driving the anomaly to zero.

**Transaction costs**: Extreme SUE deciles tend to concentrate in smaller, less liquid stocks with wider bid-ask spreads. The transaction cost per round-trip trade can consume a meaningful fraction of the available alpha, especially at high turnover.

**Short-selling constraints**: The short leg of PEAD — stocks with large negative surprises — is disproportionately concentrated in stocks that are expensive or difficult to borrow. High short interest is associated with lower borrow availability and higher borrow cost, limiting the ability to exploit the full long-short spread. This effect is asymmetric: the long leg is easier to implement than the short leg.

**Idiosyncratic risk**: PEAD positions are inherently underdiversified in the short run because they are event-driven, concentrated in a small number of names with recent announcements. The idiosyncratic volatility of individual post-earnings stocks is elevated, making it difficult for arbitrageurs to hold positions without substantial variance. Small hedge funds face binding risk limits.

**Capital constraints and leverage**: PEAD arbitrage requires holding positions for 20-60 days. During this horizon, marked-to-market losses can trigger margin calls or force liquidations before the drift realizes. Leverage constraints studied by Shleifer and Vishny (1997) explain why well-informed investors cannot exploit mispricing of arbitrary size.

**Information processing costs**: Extracting and processing earnings call transcripts, analyst revisions, and guidance updates across hundreds of companies per quarter requires significant infrastructure. Small investors lack this capacity; large institutions face coordination costs.

**Crowding**: As PEAD became more widely known from the late 1990s onward, quantitative funds began targeting it explicitly. Academic research by Martineau (2022) argued that PEAD largely disappeared from non-microcap stocks after decimalization in 2001, when electronic arbitrage became more precise and profitable. However, subsequent 2024-2025 research disputes this, finding that PEAD remains statistically significant, especially when text-based signals are incorporated.

### 2.5 The Decline and Revival of PEAD

**The case for decline**: Martineau (2022) documented that PEAD in non-microcap stocks essentially disappeared after 2006, attributing the decline to improved market microstructure following decimalization, increased algorithmic trading, and better arbitrageur infrastructure. The mechanism: as spreads tightened, high-frequency traders could more efficiently exploit post-earnings mispricings.

**The case for persistence**: Columbia Business School research (2023) argues that the decline in PEAD magnitude is primarily explained by declining earnings persistence — the drift has shrunk because surprises themselves have become less predictive of future earnings, not because the market has become more efficient at incorporating them. Two 2024-2025 papers in peer-reviewed journals contradict Martineau's finding directly, showing PEAD remains alive for carefully constructed strategies.

**Revival via text**: Meursault, Liang, Routledge, and Scanlon (2021) at Carnegie Mellon and the Philadelphia Fed demonstrated that text-based PEAD (PEAD.txt) using earnings call transcripts is *larger* than classical PEAD and has not declined with numerical PEAD. Their text-only model produced a drift of 8.01% over the calendar year following earnings calls vs. 1-3% for transcript-based alternatives, suggesting that the information in language is still only partially priced.

### 2.6 Machine Learning Approaches (2018-2025)

Recent research has moved from linear sorting on SUE to richer predictive models:

**PEAD.txt (Meursault et al., 2021, JFQA 2022)**: Constructed SUE.txt — a standardized unexpected earnings measure derived entirely from earnings call text rather than reported EPS. A text-only random forest model trained on bag-of-words features from transcripts produced an 8.01% annual drift. The text-based signal is orthogonal to numerical surprise and generates incremental alpha.

**XGBoost with genetic algorithm optimization (Kim et al., 2021)**: Applied gradient boosting with genetic algorithm feature selection to capture PEAD dynamics. The model identified that earnings surprise magnitude, prior-quarter surprise, analyst revision velocity, and institutional ownership change were the most predictive features. Sharpe ratios in the range of 1.4-3.1 were reported depending on universe and transaction cost assumptions.

**Historical earnings ML (2025)**: Research published in 2025 found that using longer SUE histories (8+ quarters of prior surprises rather than just the most recent) in an ML framework approximately doubled Sharpe ratios compared to traditional 1-quarter SUE. This finding implies that the pattern of past surprises — not just the current one — contains substantial predictive information about drift.

**LLM-enhanced PEAD (2024-2025)**: Studies using GPT-4o and FinBERT for abstractive summarization and contextual embedding extraction from earnings calls found that contextual semantic features outperformed bag-of-words approaches, providing information unexplained by earnings, fundamental, and technical features alone. FinBERT achieves classification accuracy of 57.6% for positive PEAD and 58.3% for negative PEAD — modest but statistically meaningful and orthogonal to numerical signals.

---

## 3. Earnings Surprise Measurement

### 3.1 Standardized Unexpected Earnings (SUE): The Core Measure

The foundational quantitative signal is SUE, first formalized by Livnat and Mendenhall (2006). The measure standardizes the raw earnings surprise by a measure of surprise volatility, enabling cross-sectional comparison across firms of different sizes and industries.

**Analyst consensus-based SUE**:

```
SUE_analyst = (EPS_actual - EPS_consensus) / sigma_forecast_errors
```

Where:
- `EPS_actual` is the reported diluted EPS
- `EPS_consensus` is the median (preferred) or mean of analyst EPS estimates from the most recent period before the announcement
- `sigma_forecast_errors` is the standard deviation of recent analyst forecast errors for that stock (typically trailing 4-8 quarters)

**Time-series based SUE** (Foster, Olsen, Shevlin formulation):

```
SUE_ts = (E_t - E_{t-4}) / sigma_{historical}
```

Where:
- `E_t` is earnings in the current quarter
- `E_{t-4}` is earnings in the same quarter one year prior (seasonal random walk expectation)
- `sigma_{historical}` is the standard deviation of `(E_t - E_{t-4})` over the trailing 8 quarters

The time-series formulation is particularly useful for firms with sparse or no analyst coverage. For covered firms, analyst-based SUE tends to be a better predictor because analysts incorporate forward-looking information.

**Hybrid SUE**: A weighted combination that favors analyst consensus when coverage is sufficient (>= 3 analysts) and falls back to the time-series model for thinly covered stocks:

```
SUE_hybrid = w_analyst * SUE_analyst + (1 - w_analyst) * SUE_ts

w_analyst = min(1.0, n_analysts / 5)
```

### 3.2 SUE Decile Construction

Following the Foster, Olsen, Shevlin tradition, stocks are ranked into deciles (or quintiles) by SUE within each earnings announcement quarter. The long leg consists of stocks in the top decile (SUE decile 10); the short leg consists of stocks in the bottom decile (SUE decile 1).

Historical average abnormal returns by SUE decile over a 60-day post-announcement window (approximate, from Bernard and Thomas 1989):

| SUE Decile | Avg 60-Day Cumulative Abnormal Return |
|------------|--------------------------------------|
| 1 (most negative) | -2.0% to -3.5% |
| 2 | -1.5% to -2.0% |
| 3 | -0.8% to -1.2% |
| 4-5 | -0.2% to +0.2% |
| 6-7 | +0.3% to +0.8% |
| 8 | +1.0% to +1.5% |
| 9 | +1.5% to +2.0% |
| 10 (most positive) | +2.0% to +4.0% |

Long-short spread (D10 minus D1): approximately 4-6% over 60 days in original studies, before transaction costs; approximately 25% annualized in Foster et al.'s formulation.

### 3.3 Revenue Surprise vs. EPS Surprise

Research on revenue surprises provides an important refinement. A positive EPS surprise can be driven by either:
1. **Revenue outperformance** — sales exceeded expectations. This reflects genuine demand upside.
2. **Cost cutting or accrual management** — costs were lower than expected or accruals were managed favorably. This may not persist.

Revenue-driven EPS beats are associated with stronger and more persistent post-announcement drift than cost-driven beats. The intuition: revenue surprise signals persistent future growth, whereas margin expansion from cost cutting is mean-reverting and less informative about future earnings power.

**Revenue SUE**:

```
SUE_rev = (Revenue_actual - Revenue_consensus) / sigma_revenue_forecast_errors
```

**Signal decomposition**: Classify each EPS surprise by its source:

```
EPS_surprise = Revenue_surprise_effect + Margin_surprise_effect + Below-the-line_effect
```

Where:
- `Revenue_surprise_effect = (Revenue_actual - Revenue_consensus) * consensus_operating_margin`
- `Margin_surprise_effect = Revenue_actual * (actual_margin - consensus_margin)`
- `Below-the-line_effect` captures tax, interest, and one-time items

Surprises dominated by revenue are assigned a quality multiplier > 1; surprises dominated by below-the-line items receive a quality discount.

### 3.4 Whisper Number vs. Published Consensus

A critical refinement to SUE construction involves the distinction between the published consensus (what financial media cites) and the true market expectation (the "whisper number"):

**Published consensus**: The mean or median of sell-side analyst EPS estimates aggregated by FactSet, Bloomberg, Refinitiv, or IBES. These are formal, audited estimates that are widely distributed and benchmarked against.

**Whisper number**: The informal buy-side expectation that incorporates management guidance, channel checks, supply chain data, and insider information signals. Research shows EarningsWhispers.com's whisper numbers have been more accurate than published consensus 70% of the time since 1998.

**The whisper effect**: A stock that beats published consensus but misses the whisper number tends to decline on the announcement day despite the apparent "beat." Research shows:
- Beat consensus + beat whisper: +1.8% average first-day return, 60% up frequency
- Beat consensus + miss whisper: -0.3% average first-day return, 45% up frequency

For PEAD construction, the whisper-adjusted surprise may be more informative:

```
SUE_whisper = (EPS_actual - EPS_whisper) / sigma_whisper_errors
```

Whisper data is available from EarningsWhispers.com (free for large caps) and premium providers. The orthogonal surprise relative to whisper tends to be a cleaner signal of true information content.

### 3.5 Earnings Quality Adjustment

Not all SUE observations are equally informative. Low earnings quality — high accruals, income-increasing accounting choices, channel stuffing — contaminates the SUE signal. High accrual firms with positive earnings surprises may eventually experience drift reversal as accruals unwind. The Sloan (1996) accrual anomaly and PEAD are partially independent but interact in important ways.

**Accrual ratio** (Sloan ratio):

```
Accrual_ratio = (Net_income - Operating_cash_flow) / Total_assets
```

High accrual ratio (earnings exceeds cash flow) implies lower earnings quality. Modify the long signal:

```
if SUE_decile >= 9 and Accrual_ratio > 75th_percentile:
    Discount long signal by 30%  # Earnings quality concern
if SUE_decile >= 9 and Accrual_ratio < 25th_percentile:
    Boost long signal by 15%     # High-quality cash-backed beat
```

Similarly, firms with extreme negative surprises (low SUE) and high accruals are high-risk shorts because accrual reversal may reverse the earnings disappointment.

### 3.6 Analyst Estimate Sources

| Provider | Coverage | Lag | Notes |
|----------|----------|-----|-------|
| FactSet Consensus | Broad, professionally curated | Near real-time | Gold standard for institutional use, most cited by media |
| Bloomberg BEst | Broad | Near real-time | Strong for derivatives desks |
| Refinitiv IBES | Broad, long history | T+1 for most estimates | Standard academic dataset; 40+ year history |
| Visible Alpha | Granular line-item estimates | Near real-time | Unique line-item granularity, useful for revenue decomposition |
| EarningsWhispers | Large-cap, informal | Near real-time | Best source for whisper numbers |
| Estimize | Crowdsourced | Near real-time | Aggregates buy-side and retail estimates |
| SEC EDGAR XBRL | Direct from filing | T=0 at filing | Actual reported values; use for SUE_actual computation |

For backtesting, point-in-time consensus data from Refinitiv IBES or FactSet is essential to avoid look-ahead bias. Many academic studies using IBES data are subject to survivorship bias if they do not use the "Stopped" file containing deleted estimates.

### 3.7 Normalization and Cross-Sectional Ranking

Raw SUE values are not directly comparable across firms because the standard deviation of forecast errors varies enormously. Proper normalization is critical:

**Cross-sectional standardization** (preferred for ranking):

```
SUE_normalized = (SUE_i - mean(SUE_cross_section)) / std(SUE_cross_section)
```

This is computed separately within each announcement cohort (same-quarter announcements), allowing fair comparison of surprises across firms that announce in the same window.

**Winsorization**: Cap SUE at the 1st and 99th percentiles to prevent extreme observations from dominating the ranking. Events driven by restatements, discontinued operations, or non-recurring items should be excluded.

**Excluded events**:
- EPS loss to profit transitions (SUE is distorted)
- Spin-offs, mergers, or major corporate actions in the prior year
- Restatements or SEC comment letter periods
- Firms with fewer than 1 analyst estimate (unless using SUE_ts)

---

## 4. NLP Signal Construction

### 4.1 Information Sources for NLP

PEAD NLP extracts signals from three complementary text sources, each providing different information:

| Source | Availability | Information Content | Processing Priority |
|--------|-------------|---------------------|---------------------|
| Earnings call transcript | Immediately post-call | Management tone, guidance language, Q&A dynamics, confidence signals | Highest |
| Earnings press release | Simultaneously with 8-K filing | Headline metrics, management quotes, guidance table | High |
| Conference call audio features | Post-call | Vocal tone, speech rate, pauses, vocal stress | Medium |
| 10-Q/10-K text changes | T+2 to T+40 | Risk factor changes, MD&A language shifts | Lower priority |
| Analyst report revisions | T+1 to T+5 | Consensus revision direction and speed | Medium |

### 4.2 Transcript Structure and Segmentation

Earnings call transcripts have a predictable structure that should be exploited for fine-grained analysis rather than treating the transcript as a monolithic text blob:

**Prepared remarks section** (CEO/CFO scripted):
- Opening business commentary
- Financial results discussion
- Guidance disclosure
- Closing remarks

**Q&A section** (unscripted, analyst-driven):
- Each analyst question
- Management response to each question
- Tone and completeness of answers

The Q&A section is systematically more informative than prepared remarks because management cannot script analyst questions in advance. Evasive or incomplete answers to specific questions are a bearish signal. Direct, data-rich answers are bullish. Research by Bushee, Gow, and Taylor documents that analyst Q&A tones are predictive of future returns incrementally to prepared remark tone.

**Practical segmentation rules**:
- Parse speaker labels to separate CEO/CFO prepared sections from Q&A
- Treat each question-answer pair as an independent unit
- Weight Q&A sections more heavily in the aggregate sentiment score
- Flag instances where management declines to answer or deflects

### 4.3 Financial NLP Models

**FinBERT (Yang et al., 2020)**:
The most widely validated model for financial text sentiment. FinBERT is initialized from BERT-BASE and further pre-trained on 2.5 billion tokens of annual and quarterly reports, 1.3 billion tokens of earnings call transcripts, and 1.1 billion tokens of analyst reports. Fine-tuned on Financial PhraseBank for three-class sentiment: positive, negative, neutral.

- **Accuracy**: 89% on financial sentiment classification vs. 76% for generic BERT
- **PEAD classification accuracy**: 57.6% (positive group), 58.3% (negative group)
- **Practical advantage**: Strong domain adaptation; understands financial jargon, hedging language, and reporting conventions that confuse general-purpose models

**SEC-BERT**:
A BERT-family model trained specifically on SEC filings (10-K, 10-Q, 8-K, proxy statements). SEC-BERT-BASE uses the same architecture as BERT-BASE but captures regulatory and accounting language patterns that are distinct from earnings call conversational language. Best suited for processing press releases and formal filing text.

**Financial-BERT / FinancialBERT**:
An alternative domain-adapted model pre-trained on a financial corpus assembled from Bloomberg, financial news, and corporate filings. Comparable to FinBERT for many tasks; may have edge cases in analyst report interpretation.

**Sentence-BERT for contextual embeddings**:
For semantic similarity and contextual embedding extraction, sentence-transformers (S-BERT) variants are preferred over token-level FinBERT because they produce fixed-size sentence representations suitable for downstream ML models. These can be used to:
- Compute semantic similarity between current call language and prior calls
- Embed guidance statements and compare to historical guidance vectors
- Cluster linguistic patterns associated with post-announcement drift

**GPT-4o / Large Language Models**:
Recent research shows GPT-4o achieves superior abstractive summarization of earnings call content, generating condensed representations that capture the key signals for downstream classification. However, LLM-based approaches introduce latency (1-5 seconds per transcript), token cost, and potential jailbreak/hallucination risks in a production environment. A hybrid approach — LLM summarization feeding a faster FinBERT classifier — balances quality with operational constraints.

**Dictionary-based baseline (Loughran-McDonald)**:
The Loughran-McDonald (2011) financial sentiment dictionary provides a benchmark against which transformer models are compared. LM categorizes words into sentiment buckets: positive, negative, uncertain, litigious, constraining, and modal words. For PEAD applications, the "uncertain" and "negative" word counts are particularly predictive. LM consistently underperforms FinBERT on financial sentiment tasks but is fast, deterministic, and interpretable.

### 4.4 Sentiment Scoring

The sentiment pipeline produces multiple dimensions rather than a single score:

**Tone score**: Aggregate positive vs. negative sentiment across the full transcript, weighted by section:

```
tone_score = 0.3 * prepared_tone + 0.5 * QA_tone + 0.2 * guidance_tone

where each component is:
component_tone = (positive_sentiment_probability - negative_sentiment_probability)
                 scaled to [-1, +1]
```

**Uncertainty score**: Counts of hedging language — "approximately," "could be," "may," "if conditions," "subject to," "we cannot predict," "difficult to estimate." High uncertainty scores are associated with weaker guidance credibility and negative drift.

```
uncertainty_score = count_uncertain_words / total_words
```

**Guidance specificity**: Management that provides narrow guidance ranges ("$8.2-$8.4 billion revenue") signals confidence vs. wide or directional-only guidance ("we expect continued growth"). Quantify:

```
guidance_specificity = 1 - (guidance_range_width / midpoint_value)
# A range of $0.10 on $2.00 guidance = specificity of 0.95 (high)
# A range of $0.50 on $2.00 guidance = specificity of 0.75 (moderate)
# Directional-only guidance = specificity of 0.0
```

**Upward revision language**: Explicit linguistic indicators of positive guidance revision — "raising our outlook," "increasing our guidance," "better than previously expected," "outperform our earlier forecast." These phrases, extracted via keyword matching and validated with FinBERT context-aware classification, are among the strongest drift predictors.

**Deflection index**: The proportion of analyst questions that received non-specific, evasive, or redirection responses. Computed as the fraction of Q&A pairs where the semantic similarity between question and answer (in embedding space) is below a threshold:

```
deflection_index = count(QA_pairs where cos_sim(question_embedding, answer_embedding) < tau) 
                   / total_QA_pairs
```

High deflection index is bearish (management is avoiding uncomfortable topics). Low deflection is bullish.

### 4.5 Semantic Surprise: Beyond the Number

A critical insight from PEAD.txt research is that the *way* the surprise is discussed matters as much as the number itself. Consider two scenarios with identical +10% EPS beats:

**Scenario A** (bullish semantic)**: "We exceeded expectations in every major business line. Revenue growth was broad-based, and we are raising full-year guidance. Demand signals remain strong across all geographies."

**Scenario B** (bearish semantic)**: "The quarter came in ahead of estimates, though we did benefit from some timing of deals and favorable tax items. We are maintaining guidance but want to flag some headwinds in the back half."

The semantic content of Scenario B contains a beat-quality warning (timing, tax), guidance maintenance vs. a raise, and headwind language — all bearish signals despite identical headline EPS. NLP captures this distinction.

**Semantic surprise construction**:

```
semantic_surprise = NLP_implied_sentiment - market_prior_sentiment

where:
market_prior_sentiment = weighted average analyst sentiment from prior 30 days
NLP_implied_sentiment = FinBERT(full_transcript)
```

A positive semantic surprise occurs when the call is more bullish than the pre-announcement consensus expectation implied. This is analogous to SUE for text.

**Cross-reference signal**: Compare current call sentiment to prior quarter's call sentiment for the same firm:

```
tone_change = current_call_tone - prior_call_tone
```

Upward tone change relative to the prior quarter is bullish; downward is bearish.

### 4.6 Guidance Analysis

**Forward guidance types**:
- **Point estimate**: "EPS of $2.45 in Q2" — most specific, highest signal quality
- **Range estimate**: "EPS of $2.40-$2.50 in Q2" — high quality, width measures confidence
- **Directional only**: "We expect growth to continue" — low quality, little information
- **No guidance withdrawn**: Management stops giving guidance, which itself is an event

**Guidance beat/miss signal**:

```
guidance_surprise = (New_guidance_midpoint - Prior_guidance_midpoint) / Prior_guidance_midpoint
```

When a company raises guidance, even slightly, it is a strong forward-looking positive signal that compounds the backward-looking EPS surprise. A beat + guidance raise is the highest-conviction long setup. A beat + guidance in-line is moderate. A beat + guidance cut is a trap — these often reverse the initial pop.

**Management credibility scoring**:

Firms with a history of consistent guidance beats develop credibility capital that amplifies the market's response to new guidance raises. Firms that systematically lowball guidance (the "sandbagging" practice) lose credibility over time as analysts discount the guidance.

```
credibility_score = (beats_last_8Q / 8) * (avg_guidance_accuracy_last_8Q)
```

Where `avg_guidance_accuracy_last_8Q` measures how close actual results came to the initial guidance midpoint. Firms in the top credibility quartile receive a signal boost; firms known as chronic sandbaggers receive a discount because their "guidance raise" is expected and already priced.

**Research finding (Chu, Dechow, Hui, Wang 2018)**: Firms with long strings of guidance beats (8+ consecutive quarters) face analytical skepticism. Analysts dampen their responses to bad-news forecasts from these firms because they expect the sandbagging game to continue. This creates a non-linear credibility effect: 1-4 consecutive beats increase credibility; 8+ consecutive beats face haircut because the game is identified.

### 4.7 Audio Features (Optional Enhancement)

Beyond text, the audio channel of earnings calls contains additional signals:

- **Speech rate (words per minute)**: Faster speech is associated with higher confidence; slower speech with uncertainty
- **Vocal stress and pitch variation**: Elevated stress markers in voice correlate with negative future outcomes
- **Pause frequency**: Unusual pauses on specific questions may indicate reluctance or uncertainty
- **Response latency**: Time between analyst question and management response; longer latency on financial questions is bearish

These features require audio processing infrastructure (speech-to-text + prosody analysis) and add meaningful complexity. They are documented in academic research (Ozer and Erdem) but are an optional enhancement rather than a core feature. Audio processing typically adds 200-500 milliseconds of additional information over text alone.

---

## 5. Combined Signal Architecture

### 5.1 Signal Overview

The strategy uses three independent signal families that are combined into a composite score:

| Signal | Type | Data Source | Update Frequency |
|--------|------|-------------|-----------------|
| SUE_hybrid | Quantitative | IBES/FactSet + EDGAR XBRL | At announcement |
| Revenue_surprise | Quantitative | FactSet + EDGAR | At announcement |
| Earnings quality (accrual ratio) | Quantitative | Financial statements | At announcement |
| Transcript sentiment (tone_score) | NLP | Call transcript | Within 4 hours of call |
| Semantic surprise | NLP | Call transcript + prior quarter | Within 4 hours of call |
| Guidance raise/cut signal | NLP + quantitative | Guidance tables + transcript | Within 4 hours of call |
| Management credibility | Fundamental | Historical guidance database | Pre-computed weekly |
| Short interest ratio | Market data | FINRA/Bloomberg | Semi-monthly update |
| Options market signal (IV crush) | Market data | CBOE/OptionMetrics | Pre-announcement daily |

### 5.2 Signal Normalization

All signals are standardized to a common scale before combination to prevent any single signal from dominating the composite:

```
z_i = (signal_i - mean_i) / std_i
```

Where mean and std are computed in-sample over a trailing 2-year rolling window, with Winsorization at the 1st and 99th percentiles.

### 5.3 Composite Score Construction

**Baseline composite** (linear combination):

```
composite_score = w1 * z_SUE + w2 * z_revenue_surprise + w3 * z_tone + 
                  w4 * z_semantic_surprise + w5 * z_guidance + w6 * z_credibility
```

Default weights (to be optimized):

| Signal | Default Weight |
|--------|----------------|
| z_SUE_hybrid | 0.30 |
| z_revenue_surprise | 0.15 |
| z_tone (transcript) | 0.20 |
| z_semantic_surprise | 0.15 |
| z_guidance | 0.15 |
| z_credibility | 0.05 |

**Quality gating**: Before a position is included in the portfolio, it must pass a minimum composite score threshold. Positions in the middle of the distribution (|composite_score| < 0.5) are excluded — the strategy focuses only on the highest-conviction opportunities.

**Interaction terms**: Research shows the numerical and NLP signals are not fully additive. The combination effect is superadditive when both signals align:

```
if z_SUE > 1.5 AND z_tone > 1.0:
    composite_score *= 1.2  # Super-additive boost for aligned signals
if z_SUE > 1.5 AND z_tone < -0.5:
    composite_score *= 0.7  # Discount: strong beat but bearish tone (trap)
```

### 5.4 Machine Learning Enhancement

As an extension beyond the linear composite, a gradient boosting model (XGBoost) is trained on historical events to predict 20-day forward cumulative abnormal returns:

**Feature set for ML model**:
- All 6 signals above (raw and standardized)
- Interaction features between numerical and NLP signals
- Historical surprise pattern (trailing 8 quarters of SUE)
- Analyst revision velocity (first 24 hours post-announcement)
- Institutional ownership percentile
- Market cap quintile
- Sector / GICS industry classification
- Pre-announcement implied volatility level (as a proxy for uncertainty)
- Short interest ratio at announcement

**Training protocol**:
- Rolling walk-forward: train on years 0-5, test on year 6, advance by 1 year
- Target variable: market-adjusted 20-day return, winsorized at 5th/95th percentile
- Prevent look-ahead bias: no features that require information past announcement day
- Cross-validate within training set using time-series aware CV (no shuffling)

**Signal output**: The ML model outputs a predicted 20-day return rank, which replaces or supplements the linear composite for portfolio construction.

### 5.5 Options Market Pre-Signal

Options market data in the days before announcement provides a forward-looking signal about the magnitude of expected surprise:

**Implied volatility spread**: The spread between call IV and put IV for at-the-money options widens monotonically in the days leading up to announcement. Research documents that the pre-announcement IV spread predicts the direction of announcement returns: a positive call-put spread means the options market is pricing in a more bullish outcome than the historical average.

**Put-call ratio (OTM)**: The ratio of out-of-the-money put to call open interest, or the ratio of put to call volume in the week before announcement. Unusually high put-call ratio is a bearish signal; unusually low (more calls) is bullish.

**Expected move**: The options market's implied expected move (typically computed as the straddle price divided by the stock price) sets the benchmark for whether the actual announcement outcome is surprising relative to options market expectations. A move larger than the expected move in the positive direction reinforces the PEAD long signal.

These options signals feed into the composite as pre-filters rather than direct weighting components:
- If options-implied direction agrees with SUE/NLP direction: proceed normally
- If options-implied direction conflicts: reduce position size by 40%
- If options-implied expected move > 15% (extremely high uncertainty): reduce position size by 50% or skip

---

## 6. Universe and Event Detection

### 6.1 Eligible Universe

**Base universe**: All US-listed common equities (NYSE, NASDAQ, NYSE American). Excludes:
- ADRs and foreign private issuers (different reporting standards, timing asymmetries)
- Closed-end funds, REITs with simplified earnings structures
- SPACs pre-merger completion
- Stocks below $5.00 price (penny stock instability)
- Stocks with market cap below $100M (liquidity constraints)
- Stocks with average daily volume below $1M (execution risk)
- Stocks with fewer than 30 trading days of history post-IPO (insufficient historical data)

**Recommended universe segmentation**:

| Segment | Market Cap Range | Characteristics | Expected PEAD Magnitude |
|---------|-----------------|-----------------|------------------------|
| Small-cap | $100M - $2B | Less coverage, slower price discovery, wider spreads | Highest (3-6% drift) |
| Mid-cap | $2B - $20B | Moderate coverage, reasonable liquidity | Moderate (1.5-3% drift) |
| Large-cap | $20B - $200B | High coverage, tight spreads, faster adjustment | Low (0.5-1.5% drift) |
| Mega-cap | >$200B | Hundreds of analysts, near-instant price discovery | Negligible (<0.5%) |

**Practical focus**: Small-cap and mid-cap names offer the best risk-adjusted PEAD opportunity. Mega-cap PEAD is essentially zero due to wall-to-wall analyst coverage and institutional attention. However, small-cap PEAD is expensive to access due to wider spreads and limited borrow for shorts.

**Recommended starting universe**: S&P 1500 (S&P 500 + S&P 400 + S&P 600), covering $500M to $100B+ market caps. This provides reasonable PEAD magnitude with sufficient liquidity for a $10-50M strategy. Russell 2000 names below $500M should be approached selectively given execution costs.

### 6.2 Earnings Calendar and Event Detection

**Primary sources for earnings dates**:
- **SEC EDGAR XBRL API** (data.sec.gov): The authoritative real-time source for all public company filings. 8-K filings are submitted at or immediately after the earnings release; the filing timestamp is the official disclosure time.
- **Finnhub Earnings Calendar API**: Real-time and forward-looking calendar; free tier available.
- **Wall Street Horizon**: Premium earnings date data with confirmed timing (AMC vs. BMO) and conference call timing.
- **EarningsWhispers.com API**: Provides both the calendar and whisper number data.
- **FactSet Earnings Dates**: Institutional-grade, includes historical confirmed dates.

**Critical timing distinction**:

| Timing | Acronym | Definition |
|--------|---------|------------|
| Before market open | BMO | Announced before 9:30 AM ET; tradeable at open |
| After market close | AMC | Announced after 4:00 PM ET; tradeable next day open |
| During market hours | DMH | Unusual; immediate reaction in current session |

AMC announcements are the most common and cleanest for PEAD because the market has a full overnight period to partially process information, and the drift begins at the next-day open. BMO announcements may create a rush-to-cover dynamic at the open that can initially overshoot before the drift continues.

**Conference call timing**: The conference call typically occurs 30-60 minutes after the press release. The transcript NLP signal is therefore available 1-3 hours after the press release, meaning the NLP signal is actionable at the start of the next trading session for AMC announcements, or during the same session (with some delay) for BMO announcements.

**Event validation rules**:
- Confirm the event is a primary quarterly earnings release (not a pre-announcement, revised guidance, or preliminary filing)
- Ensure the release covers a complete fiscal quarter (exclude partial-quarter guidance updates)
- Verify the 8-K or earnings press release includes actual EPS figures (not just guidance)
- Exclude events where the prior-quarter earnings were restated (distorts SUE baseline)

### 6.3 Data Pipeline Timing

The end-to-end data pipeline from announcement to tradeable signal must complete within the following windows:

**AMC announcement** (most common):
- T+0: Press release published (4:00-5:30 PM ET)
- T+30min to T+90min: Conference call completes
- T+120min: Transcript available from third-party providers (Motley Fool, Seeking Alpha, Market Intelligence)
- T+180min to T+240min: NLP pipeline completes (sentiment scoring, guidance extraction, composite)
- T+next open: Trade executed at market open or limit order during first 30 minutes

**BMO announcement**:
- T+0: Press release published (7:00-8:30 AM ET)
- T+30min to T+60min: Conference call completes
- T+90min: Transcript may not be available before open
- Strategy option 1: Trade on numerical SUE only at open, layer in NLP when transcript arrives
- Strategy option 2: Delay trade entry until mid-morning when full composite is ready (accept missing some of the opening gap)

---

## 7. Entry and Exit Logic

### 7.1 Entry Timing: Debate and Evidence

The timing of entry is one of the most debated operational questions in PEAD implementation. There are three schools of thought:

**Immediate entry** (at the post-announcement open or intraday): Captures the full drift window including the first-day move. Risk: exposed to the initial gap-fill if the market overshoots. Research suggests that some of the apparent first-day drift is actually a partial correction of an initial overreaction.

**Next-day open entry** (for AMC announcements): Waits for the overnight gap to establish and enters at the next open. Avoids intraday noise but sacrifices the first-day move. Evidence suggests this loses approximately 30% of the total drift return.

**Day 2 entry after confirmation** (most conservative): Waits for the gap to hold for one trading session before entering. This reduces the probability of gap-fill reversal significantly. Sacrifices approximately 40-50% of total drift but improves risk-adjusted return by reducing stop-out frequency.

**Recommendation**: For the long leg, enter at the next-day open after AMC announcement. For the short leg, because large negative surprises can have sharper immediate moves with higher gap-fill risk, enter on Day 2 confirmation. This asymmetric approach trades off some short-leg alpha for significantly improved execution quality.

### 7.2 Entry Execution Rules

**Order types**:
- Preferred: Limit orders during the first 30 minutes of the session (7:00-8:30 AM ET on NASDAQ open or 9:30-10:00 AM ET NYSE open)
- Acceptable: VWAP orders for larger positions ($500K+) executed over the first 2 hours
- Avoid: Market orders at the precise open (bid-ask spreads are widest in the first 5 minutes)

**Confirmation filter**: Only enter if the first-day return (announcement day for AMC) is in the same direction as the SUE signal and composite score. If a stock with positive composite score opens down >3% the next morning, treat as a signal failure and do not enter. Empirical research shows this filter improves Sharpe by approximately 15%.

**Composite score threshold for entry**:
- Minimum |composite_score| > 0.75 (1-sigma from mean)
- Preferred: |composite_score| > 1.0 for full position
- Reduce size by 50% for positions in the 0.75-1.0 range

### 7.3 Exit Logic

**Primary exit: Time-based**

The academic literature documents drift lasting 20-60 trading days, with the bulk of cumulative abnormal returns concentrated in the first 30 days. Based on the evidence:

| Exit Rule | Description | Justification |
|-----------|-------------|---------------|
| Day 20 exit | Capture the most concentrated portion of drift | Maximum Sharpe ratio per unit time |
| Day 40 exit | Extended hold for high-conviction positions | Balance of return vs. exposure time |
| Day 60 exit | Full academic drift window | Maximum total return but lowest IR |
| Pre-earnings exit | Exit before the next quarterly earnings announcement | Avoid binary event risk |

**Recommended primary exit**: Day 25 (5 weeks), which captures approximately 75% of the total 60-day drift return while minimizing time in market and the next-quarter earnings surprise risk.

**Secondary exits: Signal-based**

- **Stop-loss**: If position loses more than 2.5 * ATR (average true range at entry), exit. This is a macro stop, not a fixed percentage.
- **Trend reversal**: If the composite score (updated daily with any new analyst revisions, options signals) reverses below zero, reduce position by 50% and exit fully if it crosses -0.5.
- **Earnings announcement approach**: If the next quarterly earnings date is within 10 trading days, begin scaling out 20% per day to avoid holding through the next binary event.
- **Guidance warning**: If management issues a mid-quarter warning or pre-announcement, treat as an immediate exit trigger regardless of position age.

### 7.4 Partial Scaling

Rather than binary entry and exit, consider a scaling framework:

**Entry scale-in**:
- Day 1 (next open after announcement): 50% of target position
- Day 3 (if trend holds): additional 30%
- Day 5 (if trend holds): remaining 20%

**Exit scale-out**:
- Day 15: Exit 25% of position
- Day 20: Exit additional 25%
- Day 25: Exit remaining 50% (full exit)
- Override: Exit 100% immediately if stop-loss triggered

---

## 8. Portfolio Construction

### 8.1 Long-Short vs. Long-Only

The strategy can be implemented in two modes:

**Long-short mode** (academically validated):
- Long basket: top composite decile
- Short basket: bottom composite decile
- Market beta-neutral: short leg offsets market exposure of long leg
- Higher alpha potential; requires securities lending infrastructure

**Long-only mode** (operationally simpler):
- Long basket: top composite quintile
- Market exposure not hedged
- Lower complexity, lower cost, applicable in most fund structures
- Alpha is diminished (loses short-leg contribution) but implementation cost is lower

For most practical implementations below $100M AUM, long-only mode with an index hedge (short SPY or sector ETF) to neutralize beta is a reasonable compromise.

### 8.2 Position Sizing

**Equal weighting**: Assign equal capital to each position in the basket. Simple, robust, avoids over-concentration in high-signal positions that may be noisy.

**Signal-weighted**: Allocate capital proportional to composite score magnitude:

```
weight_i = abs(composite_score_i) / sum(abs(composite_score_j) for all j in basket)
```

Signal-weighted tends to outperform equal-weighted in-sample but is more sensitive to signal estimation error. Recommend equal-weighting for live trading until the signal model has been validated.

**Volatility-weighted** (risk parity within basket):

```
weight_i = (1 / sigma_i) / sum(1 / sigma_j for all j in basket)
```

Where sigma_i is the trailing 20-day realized volatility. This prevents high-volatility stocks from dominating portfolio risk despite equal capital allocation. Recommended for live trading.

### 8.3 Basket Size and Concentration

**Minimum basket size**: 15-20 positions per leg to achieve adequate idiosyncratic risk diversification. With fewer than 10 positions, single-name risk dominates and the strategy becomes more event-driven than systematic.

**Maximum concentration per position**: 
- Single position: 8% of total portfolio capital (prevents single-name catastrophe)
- Single sector: 30% of total portfolio (prevents sector event risk)
- Single earnings cohort (same week): 25% of portfolio (prevents earnings-week cluster risk)

**Basket refresh timing**: Refresh the basket at each new earnings season (quarterly). Within a quarter, as new positions close their holding periods and new announcements occur, roll into new positions continuously. Target 20-30 active positions at any given time.

### 8.4 Long-Short Beta Management

**Market beta**:
- Target net portfolio beta: 0.0 to +0.2 (slight long tilt acceptable)
- Measure daily and rebalance if net beta exceeds 0.3
- Hedge residual beta using S&P 500 futures or SPY/IVV/VOO

**Sector beta**:
- Monitor sector weights in long vs. short baskets
- If any sector is net long > 15% relative to benchmark, apply sector-specific hedge via sector ETF

**Factor exposures**:
- Monitor size factor (SMB) exposure — PEAD tends to generate positive small-cap tilt
- Monitor momentum factor exposure — PEAD and momentum are correlated; avoid double-loading
- Consider neutralizing factor exposures if the strategy is being combined with other factor strategies

---

## 9. Risk Management

### 9.1 Earnings Announcement Gap Risk

The largest single risk in PEAD is gap risk: the stock opens substantially against the anticipated drift direction. This can occur for several reasons:

- **Secondary information release**: A concurrent news item (M&A announcement, FDA result, legal settlement) overrides the earnings signal
- **Market-wide shock**: Macro event overnight (geopolitical, Fed announcement) creates gap downs across the market
- **Earnings manipulation revealed**: Accounting issue surfaces after initial release (restatement risk)
- **Guidance dramatically cuts**: Company beats on the quarter but slashes forward guidance so severely that the initial beat is irrelevant

**Gap risk quantification**:
- Typical average first-day move for high-SUE stocks: +3% to +8%
- Probability of gap reversal (stock gaps up then closes down) for high-SUE stocks: ~20%
- Maximum observed adverse first-day move in a positive SUE stock: -25% (infrequent, usually driven by secondary news)

**Mitigation**:
- Entry at open rather than pre-market: avoids holding through the most illiquid period
- Confirmation filter (Day 2 entry): eliminates the worst gap-fill scenarios at the cost of some alpha
- Position size limits (8% max): contains damage from any single adverse gap

### 9.2 Earnings Announcement Risk (Holding Risk)

If a position is held into the next quarterly earnings announcement (which occurs approximately 65 trading days after the initial entry), the position faces a new binary event. This is not PEAD risk — it is fresh earnings announcement risk.

**Rule**: Never hold a PEAD position through the next quarterly announcement. Begin exiting at Day 45 (3 weeks before typical next announcement) for all positions. This is non-negotiable for the short leg, where a negative-SUE stock may announce a recovery quarter.

### 9.3 Stop-Loss Framework

**Intraday stop**: Not applied. PEAD is a medium-term strategy; intraday noise should not trigger exits. Positions should not be monitored for intraday stop-loss purposes.

**Daily stop** (position-level):
- If a position loses more than 2.0 standard deviations of the stock's daily return distribution in a single session, flag for review
- Exit at next open if the composite signal has also deteriorated
- Do not auto-stop on price alone without signal corroboration

**Portfolio-level drawdown stop**:
- If the portfolio exceeds -10% drawdown from peak NAV, reduce all positions by 50%
- If the portfolio exceeds -15% drawdown from peak NAV, exit all positions and halt new entries until drawdown recovers to -8%
- Drawdown stops prevent catastrophic loss but introduce whipsaw risk in volatile markets

**Thesis-check rule**: Before applying any stop, verify whether the fundamental thesis is intact. A stock that drops 5% because of market-wide selling (macro factor) does not represent a PEAD thesis failure. A stock that drops 5% because of a new company-specific negative announcement represents a thesis failure and warrants exit.

### 9.4 Bid-Ask Spread and Liquidity Risk

**Spread impact on alpha**:

Transaction costs from bid-ask spreads can consume a substantial portion of PEAD alpha, particularly for small-cap positions. A round-trip spread of 0.3% applied to a 3% expected drift leaves only 2.7% of expected alpha — a 10% haircut. For positions with 20 basis point round-trip costs, the impact is modest.

**Liquidity screening**:
- Require minimum $1M average daily volume for inclusion
- Require that the target position size represents no more than 10% of average daily volume (ADV) per day
- For positions requiring >10% ADV to execute, spread execution over 2-3 days

**Bid-ask widening at announcement**: Spreads widen dramatically in the first 30-60 minutes after earnings. Opening cross spreads can be 3-10x the normal spread. Avoid market orders in this window; use limit orders or TWAP algorithms starting 30 minutes after the open.

### 9.5 Short Selling Constraints (Short Leg)

The short leg of PEAD faces structural constraints:

**Borrow availability**: Stocks with high short interest (>10% of float) may be difficult to borrow. Negative-SUE stocks often already have elevated short interest pre-announcement, making the short available but expensive.

**Borrow cost (stock borrow fee)**:
- General collateral (easy to borrow): 0.25-0.75% annualized
- Specials (hard to borrow): 1-10%+ annualized
- At these rates, a 3% expected short-side drift may be entirely consumed by borrow cost for hard-to-borrow names

**Short squeeze risk**: Negative-SUE stocks may have high short interest pre-announcement. If the company beats expectations despite the negative prior-quarter surprise, the short squeeze can create violent upward moves against the short position. This is asymmetric risk.

**Practical recommendation**: For strategies below $50M, implementing the full long-short strategy is possible but requires a prime brokerage relationship with robust securities lending infrastructure. Long-only PEAD with a broad index short hedge is more practically viable for smaller capital bases.

### 9.6 Model Risk

**Look-ahead bias**: The most common backtesting error in PEAD research. Ensure that:
- Analyst consensus used is the last estimate before announcement, not any post-announcement revision
- Transcript NLP signals use only information available at the time of trade entry (no future transcript content)
- Price data used for normalization is point-in-time (no price adjustments using future split information)
- Financial statement data used point-in-time (Compustat's Point-in-Time database or equivalent)

**Overfitting risk**: NLP models trained on in-sample data may overfit to specific earnings cycle patterns that are period-specific. Walk-forward validation and out-of-sample testing on held-out data are mandatory before deploying any ML enhancement.

---

## 10. Execution Considerations

### 10.1 Slippage and Market Impact

**Estimated slippage by market cap tier**:

| Tier | Market Cap | Typical Round-Trip Cost | ADV Limit per Position |
|------|------------|------------------------|----------------------|
| Small-cap | $100M-$2B | 30-80 bps | 5% of ADV per day |
| Mid-cap | $2B-$20B | 10-25 bps | 10% of ADV per day |
| Large-cap | $20B+ | 5-12 bps | 20% of ADV per day |

**Spread-adjusted alpha**: For any position, compute the spread-adjusted expected alpha before entering:

```
spread_adjusted_alpha = expected_drift - round_trip_spread - borrow_cost(if short)
```

Skip positions where spread-adjusted alpha < 1% (insufficient margin over costs).

### 10.2 Order Routing Strategy

**Opening auction participation**: For AMC announcements, participating in the NASDAQ or NYSE opening auction at the next open provides price improvement over chasing the opening print. The auction guarantees execution at the official opening price (lowest possible spread at open).

**VWAP participation**: For larger positions (>5% ADV), use VWAP algorithms executing over the first 1-2 hours of the session to minimize market impact.

**Dark pool routing**: ATS/dark pool routing for large-cap names can reduce market impact for positions above $500K notional but may introduce partial fill risk.

### 10.3 Short Availability Pre-Check

Before finalizing the short leg basket, query securities lending inventory:
- Obtain a locate from the prime broker (for Reg SHO compliance)
- Confirm the borrow rate
- Adjust the expected alpha calculation for borrow cost
- If no locate is available, skip that position and replace with the next-highest-signal stock

### 10.4 Options as Alternative to Stock Shorts

For the short leg, when borrow is expensive or unavailable, long puts or put spreads can replicate the economic short exposure:

**Long put structure**:
- Strike: ATM or 5% OTM
- Expiry: 30-45 day DTE (covers the core drift window)
- Cost: Implicitly paid as theta decay; must be weighed against borrow cost on stock short
- Advantage: Defined downside, no borrow risk, no squeeze risk

**Comparison**:

```
Short stock alpha = expected_drift - borrow_cost - slippage
Long put alpha = expected_drift - option_premium_paid - slippage

Break-even: option is preferred when borrow_cost > implied volatility premium for puts
```

In practice, after a large negative surprise, put IV is elevated (the options market is already pricing in the drift), making put options expensive. The preferred window for buying puts on low-SUE stocks is the next day after announcement, when IV has partially compressed from its pre-announcement peak.

### 10.5 Announcement Timing Risk (AMC vs. BMO)

**AMC announcements**: Most common. Press release released after market close, call completed by 6:00-7:00 PM ET, transcript available by 8:00-9:00 PM ET, full NLP pipeline completes overnight, trade placed at next open. Cleanest execution path.

**BMO announcements**: Press release released 7:00-8:30 AM ET, call may finish 10-20 minutes before open, transcript typically not available until 10:00-11:00 AM ET. Options:
- Trade on numerical SUE only at the open (fast signal)
- Wait for transcript and trade mid-morning (slower but more complete signal)
- Use pre-market price movement as an additional filter

**Weekend/holiday announcements**: Some companies announce on Friday AMC or over weekends. The drift is similar but execution occurs at Monday's open, which may have wider spreads due to weekend information accumulation.

---

## 11. Regime Sensitivity

### 11.1 Market Volatility Regime

PEAD is a slow-moving anomaly and is sensitive to the ambient volatility environment. Evidence and reasoning:

**Low volatility regime (VIX < 15)**:
- Tight bid-ask spreads reduce transaction cost drag
- Slow, steady drift is cleanest in low-noise environments
- Highest Sharpe ratios for PEAD
- Recommended: Full position size, full universe

**Moderate volatility regime (VIX 15-25)**:
- Normal operating environment; PEAD performs well
- Some increase in stop-out frequency due to larger daily moves
- Recommended: Full position size; slightly tighter stop-loss (1.5x ATR vs. 2x)

**Elevated volatility regime (VIX 25-35)**:
- Macro factors overwhelm stock-specific drift signals
- Sector rotation and de-risking trades dominate
- Bid-ask spreads widen significantly
- Recommended: Reduce position sizes by 30-40%, tighten concentration limits

**Crisis volatility regime (VIX > 35)**:
- Factor reversal risk is very high (value/momentum factors reverse, dragging correlated PEAD positions)
- Short-selling bans may be enacted in some jurisdictions
- Spreads are prohibitively wide for small-cap positions
- Recommended: Halt new entries; hold existing positions only if thesis intact; reduce portfolio to maximum 50% of normal capital deployment

**Implementation**: Compute trailing 20-day VIX average at market close. Apply regime multiplier:

```
position_size_multiplier = 1.0 - max(0, (avg_VIX - 20) / 60)
# VIX 20 -> multiplier 1.0 (full size)
# VIX 35 -> multiplier 0.75
# VIX 50 -> multiplier 0.50
# VIX 60 -> multiplier 0.33
```

### 11.2 Earnings Season Concentration Risk

Earnings are reported in concentrated waves — approximately 70% of S&P 500 companies report within a 4-week window each quarter. This creates:

- **Portfolio bunching**: Most new positions enter simultaneously, reducing diversification
- **Correlated information releases**: Bellwether earnings (Apple, Google, Amazon) affect multiple sectors simultaneously
- **Liquidity strain**: Execution is harder when many stocks are simultaneously experiencing post-earnings volatility

**Mitigation**:
- Limit total new entries per week to 25% of total portfolio capital during peak earnings weeks
- Use earlier reporters as predictors for later reporters in the same sector (inter-earnings transmission)
- Maintain a cash buffer of 20% throughout earnings season for tactical deployment

### 11.3 Factor Crowding and Momentum Interaction

PEAD is positively correlated with the momentum factor (WML: winners minus losers). Both strategies tend to go long stocks that have recently performed well and short stocks that have recently underperformed. This creates:

- **Factor correlation**: PEAD and momentum may both be harmed during momentum reversals (crowded factor unwinds)
- **Capacity constraint**: The combined demand of PEAD and momentum strategies for the same stocks can push prices up, reducing future expected drift

**Monitoring**: Track rolling correlation between PEAD strategy returns and a momentum factor ETF (e.g., MTUM) or custom momentum factor. If correlation exceeds 0.6, reduce position sizes by 20% to account for embedded momentum risk.

### 11.4 Interest Rate Regime

Rising interest rate environments affect PEAD indirectly:
- Higher rates increase discount rates, putting pressure on growth stocks (many high-SUE stocks are growth names)
- Short selling becomes relatively more attractive (higher borrow cash returns on short proceeds)
- Cost of carry for long positions increases, modestly reducing net alpha

Historical evidence suggests PEAD is relatively insensitive to interest rate levels, as it is a near-term momentum phenomenon rather than a valuation-sensitive strategy. However, the interaction with the long-duration growth stock tilt should be monitored.

---

## 12. Key Risks and Failure Modes

### 12.1 Data Latency and Technology Risk

**Risk**: NLP pipeline fails to complete before market open, forcing entry on numerical signal only (or missing the trade entirely).

**Failure modes**:
- Transcript provider API downtime (Seeking Alpha, Market Intelligence, Refinitiv)
- NLP inference infrastructure failure (GPU cluster, cloud API rate limits)
- Consensus data refresh delays (FactSet API, Bloomberg DL)

**Mitigation**: Maintain redundant transcript sources. Have a fallback mode where positions are entered on numerical SUE alone with a conservative position size (50% of normal), with NLP enhancement applied intraday when the transcript becomes available.

### 12.2 Look-Ahead Contamination

**Risk**: Backtested performance significantly overstates live performance because the backtest inadvertently uses information not available at trade entry time.

**Common sources**:
- Using quarterly earnings figures before the 10-Q filing date (earnings are released in press releases; 10-Q may be filed 1-6 weeks later)
- Using analyst revisions from after the earnings announcement in the pre-announcement consensus calculation
- Accessing CRSP/Compustat data that has been restated to reflect subsequent corrections
- Using corporate action adjustment factors not available at the time of the event

**Mitigation**: Use Compustat's point-in-time (PIT) database. Use Refinitiv IBES historical stopped-estimate files. Audit each backtest signal by verifying that every data point used was available 24 hours before trade entry.

### 12.3 Gap Risk on Announcement Day

**Risk**: Holding a position through the next announcement causes a violent adverse move that overwhelms the preceding drift returns.

**Failure mode**: A high-SUE stock from last quarter announces a severe miss in the current quarter. The stock gaps down 20-30% on the new announcement.

**Mitigation**: Strict time-based exit rules ensure positions are never held through the next announcement. The 25-day default holding period is almost always shorter than the 65-day inter-announcement period.

### 12.4 Crowding and Alpha Decay

**Risk**: As more capital flows into PEAD strategies (systematic funds, quant hedge funds), the anomaly becomes more efficiently priced and the drift magnitude shrinks.

**Evidence**: Martineau (2022) documented near-complete disappearance of PEAD in non-microcap stocks after 2006, attributed partly to increased algorithmic arbitrage. The recovery of PEAD via text-based signals (PEAD.txt) suggests that crowding has not yet fully eliminated the NLP-enhanced version.

**Monitoring metrics**:
- Track the rolling 12-month alpha of the strategy. Alert if Sharpe ratio drops below 0.5 for two consecutive quarters.
- Monitor the 1-day post-announcement return as a fraction of the total 60-day return. If the 1-day return is consuming >70% of the total drift, the market is increasingly pricing in PEAD immediately at the announcement.
- If both signals trigger simultaneously, scale back deployment by 50% and extend holding periods.

### 12.5 NLP Model Degradation

**Risk**: The NLP models trained on historical language patterns fail to generalize to new linguistic styles, new corporate communication norms, or new disclosure regulations.

**Examples of drift in language**:
- Post-COVID communications introduced entirely new vocabulary ("supply chain headwinds," "pandemic uncertainty," "remote work transition") that models trained on pre-2020 data may misclassify
- SEC rule changes affecting what management can say on calls
- Increasing use of scripted non-answers to reduce legal liability

**Mitigation**: Retrain NLP models at minimum annually on rolling data including recent transcripts. Monitor precision and recall of sentiment classification on a labeled validation set quarterly. Use model ensembles that include both dictionary-based (stable) and transformer-based (adaptive) components.

### 12.6 Short Squeeze (Short Leg)

**Risk**: A stock in the short basket receives positive news (M&A bid, FDA approval, secondary analyst upgrade) causing a violent short squeeze that overwhelms the PEAD short thesis.

**Failure mode**: A low-SUE stock with high short interest receives a buyout bid at a 40% premium three days after entry. The loss is limited by the time stop (would exit anyway within 25 days) but the position loss could be 40%+.

**Mitigation**: 
- Size limits (8% max per position) contain catastrophic single-position loss
- Screen out stocks with >20% short interest in the short basket (high squeeze risk)
- Consider protective call options on the highest-risk short positions

---

## 13. Parameters and Tunable Knobs

The following parameters define the strategy's behavior and should be subject to rigorous walk-forward optimization rather than curve fitting:

### 13.1 Signal Construction Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `sue_lookback_quarters` | 8 | 4-12 | Number of prior quarters for SUE standard deviation estimation |
| `min_analyst_count` | 3 | 1-5 | Minimum analysts required for analyst-based SUE |
| `analyst_weight_saturation` | 5 | 3-10 | Number of analysts at which analyst weight reaches 1.0 |
| `sue_winsorize_pct` | 1/99 | 0.5/99.5 to 2/98 | Winsorization bounds for SUE |
| `revenue_surprise_weight` | 0.15 | 0.05-0.30 | Weight of revenue surprise in composite |
| `nlp_section_weights` | [0.3, 0.5, 0.2] | Tunable | Prepared / Q&A / Guidance weighting in tone score |
| `uncertainty_word_threshold` | 0.03 | 0.01-0.08 | Uncertainty score level that triggers a signal discount |
| `guidance_specificity_min` | 0.7 | 0.5-0.9 | Minimum guidance specificity for guidance signal activation |
| `credibility_lookback_quarters` | 8 | 4-12 | Quarters of guidance history for credibility scoring |
| `deflection_similarity_threshold` | 0.4 | 0.3-0.6 | Cosine similarity cutoff for Q&A deflection detection |

### 13.2 Signal Combination Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `composite_weights` | [0.30, 0.15, 0.20, 0.15, 0.15, 0.05] | Optimization target | Weights for [SUE, RevSurprise, Tone, SemSurprise, Guidance, Credibility] |
| `composite_threshold_entry` | 0.75 | 0.5-1.5 | Minimum |composite_score| for entry |
| `composite_threshold_full_size` | 1.0 | 0.75-2.0 | Composite score above which full position size is used |
| `aligned_signal_boost` | 1.2 | 1.0-1.5 | Multiplier when SUE and tone agree strongly |
| `conflicting_signal_discount` | 0.7 | 0.5-0.9 | Multiplier when SUE and tone conflict |
| `options_conflict_size_reduction` | 0.60 | 0.40-0.80 | Position size multiplier when options signal conflicts |

### 13.3 Universe Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `min_price` | $5.00 | $3-$10 | Minimum stock price for universe inclusion |
| `min_market_cap_mm` | 100 | 50-500 | Minimum market cap in millions |
| `min_adv_mm` | 1.0 | 0.5-5.0 | Minimum average daily volume in millions |
| `max_adv_pct` | 0.10 | 0.05-0.20 | Maximum position as fraction of ADV per day |
| `min_analysts` | 1 | 1-3 | Minimum analyst coverage for universe inclusion |
| `max_short_interest_pct` | 20 | 15-30 | Maximum short interest (as % of float) for short leg inclusion |

### 13.4 Entry and Exit Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `entry_day` | 1 | 0-2 | Days after announcement for long entry (0=same day AMC open) |
| `short_entry_day` | 2 | 1-3 | Days after announcement for short entry |
| `primary_exit_day` | 25 | 15-45 | Primary time-based exit in trading days |
| `confirmation_return_min` | 0.0% | -2% to +2% | Minimum first-day return required to confirm long signal |
| `stop_loss_atr_multiple` | 2.0 | 1.5-3.0 | ATR multiple for position-level stop |
| `scale_in_days` | [1, 3, 5] | Configurable | Days for entry scaling (50%, 30%, 20%) |
| `scale_out_days` | [15, 20, 25] | Configurable | Days for exit scaling (25%, 25%, 50%) |
| `pre_next_earnings_exit_days` | 10 | 5-15 | Trading days before next announcement to begin scaling out |

### 13.5 Portfolio Construction Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `max_positions` | 30 | 15-50 | Maximum total positions (long + short) |
| `max_position_weight` | 0.08 | 0.05-0.12 | Maximum single position as fraction of portfolio |
| `max_sector_weight` | 0.30 | 0.20-0.40 | Maximum single GICS sector weight (net) |
| `max_earnings_cohort_weight` | 0.25 | 0.15-0.35 | Maximum fraction entering in the same earnings week |
| `target_net_beta` | 0.10 | 0.0-0.3 | Target portfolio market beta |
| `max_net_beta` | 0.30 | 0.2-0.5 | Maximum allowed net beta before rebalancing hedge |

### 13.6 Risk Management Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `portfolio_drawdown_reduce_pct` | 10% | 7-15% | Portfolio NAV drawdown triggering 50% size reduction |
| `portfolio_drawdown_halt_pct` | 15% | 10-20% | Portfolio NAV drawdown triggering full halt |
| `vix_regime_threshold` | 20 | 15-25 | VIX level above which regime multiplier begins applying |
| `vix_regime_min_multiplier` | 0.33 | 0.25-0.50 | Minimum position size multiplier at peak VIX |
| `min_spread_adjusted_alpha` | 1.0% | 0.5-2.0% | Minimum net alpha after costs for position inclusion |
| `max_borrow_cost_bps` | 100 | 50-200 | Maximum acceptable borrow cost for short positions |

### 13.7 NLP Model Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `nlp_model` | FinBERT | FinBERT, SEC-BERT, LM-dictionary | NLP model selection |
| `max_transcript_age_hours` | 6 | 2-12 | Maximum hours since call end for transcript to be used |
| `min_transcript_length_words` | 3000 | 1000-5000 | Minimum transcript length (shorter may be truncated/incomplete) |
| `semantic_embedding_model` | all-mpnet-base-v2 | Sentence-BERT variants | Sentence embedding model for semantic similarity |
| `nlp_retrain_frequency_months` | 12 | 6-18 | How often to retrain NLP model on new transcript data |
| `ensemble_nlp_weight` | 0.7 | 0.5-1.0 | Weight of transformer vs. dictionary model in NLP ensemble |

---

## Appendix A: Key Academic References

- Ball, R. and Brown, P. (1968). An Empirical Evaluation of Accounting Income Numbers. *Journal of Accounting Research*, 6(2), 159-178.
- Foster, G., Olsen, C., and Shevlin, T. (1984). Earnings Releases, Anomalies, and the Behavior of Security Returns. *The Accounting Review*, 59(4), 574-603.
- Bernard, V.L. and Thomas, J.K. (1989). Post-Earnings-Announcement Drift: Delayed Price Response or Risk Premium? *Journal of Accounting Research*, 27 (Supplement), 1-36.
- Bernard, V.L. and Thomas, J.K. (1990). Evidence That Stock Prices Do Not Fully Reflect the Implications of Current Earnings for Future Earnings. *Journal of Accounting and Economics*, 13(4), 305-340.
- Sloan, R.G. (1996). Do Stock Prices Fully Reflect Information in Accruals and Cash Flows About Future Earnings? *The Accounting Review*, 71(3), 289-315.
- Livnat, J. and Mendenhall, R.R. (2006). Comparing the Post-Earnings Announcement Drift for Surprises Calculated from Analyst and Time Series Forecasts. *Journal of Accounting Research*, 44(1), 177-205.
- Loughran, T. and McDonald, B. (2011). When Is a Liability Not a Liability? Textual Analysis, Dictionaries, and 10-Ks. *Journal of Finance*, 66(1), 35-65.
- Yang, Y. et al. (2020). FinBERT: A Pre-trained Financial Language Representation Model for Financial Text Mining. *IJCAI 2020*.
- Meursault, V., Liang, P.J., Routledge, B., and Scanlon, M. (2022). PEAD.txt: Post-Earnings-Announcement Drift Using Text. *Journal of Financial and Quantitative Analysis*.
- Martineau, C. (2022). Rest in Peace Post-Earnings Announcement Drift. *Critical Finance Review*.
- Kim, J. et al. (2021). Capturing Dynamics of Post-Earnings-Announcement Drift Using a Genetic Algorithm-Optimized XGBoost. *Expert Systems with Applications*.
- Chu, J., Dechow, P., Hui, K.W., and Wang, A. (2019). Maintaining a Reputation for Consistently Beating Earnings Expectations and the Slippery Slope to Earnings Manipulation. *Contemporary Accounting Research*.

---

## Appendix B: Data Vendor Summary

| Data Type | Vendor | Notes |
|-----------|--------|-------|
| Analyst consensus (EPS, revenue) | FactSet, Refinitiv IBES | IBES for backtesting (PIT file); FactSet for live |
| Whisper numbers | EarningsWhispers.com | Free for large caps; API available |
| Earnings calendar (confirmed timing) | Wall Street Horizon, Finnhub | WSH has highest accuracy for AMC/BMO timing |
| Earnings transcripts | S&P Market Intelligence, Motley Fool | Market Intelligence has fastest delivery |
| EDGAR XBRL filings | SEC data.sec.gov | Free, real-time, authoritative |
| Options data (IV, greeks) | CBOE LiveVol, OptionMetrics | OptionMetrics for backtesting |
| Short interest | FINRA, S3 Partners | FINRA updates semi-monthly; S3 provides daily estimates |
| Price, volume, fundamentals | Compustat PIT, Bloomberg | PIT critical for avoiding look-ahead bias |
| Crowdsourced estimates | Estimize | Useful supplement for whisper-like signals |

---

*This document is a research and design specification. All return estimates are drawn from published academic literature and should be interpreted as historical observations, not guarantees of future performance. Live strategy performance depends critically on execution quality, data infrastructure, and capital deployment scale.*
