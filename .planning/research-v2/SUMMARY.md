# Prediction Model Research Summary (v2 Milestone)

**Project:** VCT Match Prediction Model for Polymarket Edge
**Domain:** Esports ML prediction from CV-extracted event data
**Researched:** 2026-02-13
**Confidence:** MEDIUM-HIGH

## Executive Summary

The v2 milestone extends the existing event detection foundation with machine learning models to predict map and match winners from Valoscribe's 71 Champions 2025 event logs. The recommended approach treats this as a **small-data tabular classification problem** requiring discipline: gradient boosting (XGBoost) with 5-10 carefully engineered features, walk-forward temporal validation, and probability calibration optimized for betting-grade predictions. The architecture adds new modules (`src/data/`, `src/features/`, `src/models/`, `src/evaluation/`) while preserving all Phase 1 code.

The dominant risk is **overfitting on 71 maps masquerading as predictive skill**. With only ~35 series from one tournament, models easily memorize team-specific patterns rather than learning generalizable game mechanics. This is compounded by temporal data leakage from random train/test splits and calibration issues from accuracy-focused optimization. The mitigation strategy is disciplined: start with logistic regression baseline (3-5 features), use leave-one-series-out cross-validation with chronological ordering, optimize for log loss instead of accuracy, and apply post-hoc calibration (Platt scaling). Dataset expansion to 200+ maps across multiple tournaments is the real solution — 71 maps is a prototype dataset, not a production foundation.

Academic research on Valorant prediction confirms that **economy (team loadout value) is the single strongest predictor** of round outcomes, far outweighing agent compositions or ability usage. Starting with score differential + economy tier + team Elo as the baseline feature set leverages this finding. The model pipeline architecture follows standard ML patterns: data ingestion (read JSONL), feature engineering (pure functions producing round/map/match features), model training (sklearn Pipeline with XGBoost), and walk-forward backtesting (temporal splits, never random). For betting deployment, calibration matters more than accuracy — a miscalibrated model loses money even at 65% accuracy.

## Key Findings

### Recommended Stack

The stack extends existing Python ML tools (scikit-learn, pandas, numpy) with gradient boosting for modeling, SHAP for interpretability, matplotlib for calibration visualization, and Optuna for hyperparameter tuning. No infrastructure overhead — this is pure data science on top of Valoscribe's processed event logs.

**Core technologies (add to requirements.txt):**
- **XGBoost 3.2.0**: Primary prediction model — gradient boosted trees outperform simpler models on tabular data at this scale (71-200 samples), with strong regularization defaults critical for small datasets. Native categorical support and stable JSON serialization. Preferred over LightGBM (speed advantage irrelevant at n=71) and CatBoost (low-cardinality categoricals don't need advanced encoding).
- **SHAP 0.50.0**: Model interpretability — with only 71 maps, understanding which features drive predictions is more important than raw accuracy. TreeExplainer validates whether the model learns game mechanics (economy, round momentum) or just memorizes team strength. Required, not optional.
- **matplotlib 3.10.8**: Calibration curves, SHAP plots, evaluation reports — required dependency for SHAP visualization and sklearn's CalibrationDisplay. Sufficient without seaborn.
- **Optuna 4.7.0**: Bayesian hyperparameter optimization — more efficient than grid/random search in 7-dimension hyperparameter space (XGBoost parameters). Add during tuning phase (Phase 3), not blocking for initial model.

**Existing stack (no changes needed):**
- scikit-learn 1.8.0 (already installed): CalibratedClassifierCV for probability calibration, cross-validation, metrics (brier_score_loss, log_loss, calibration_curve)
- pandas (already installed): Primary data wrangling for JSONL ingestion and feature engineering
- numpy (already installed): Numerical operations

**Explicitly NOT adding:** Deep learning frameworks (71 maps far too small for neural networks), automated feature engineering (featuretools/tsfresh add complexity without value at this scale), MLflow/W&B (overkill for single developer + 71-200 experiments), Polars (pandas adequate for ~60K total events).

### Expected Features

Research on Valorant prediction and the specific characteristics of Valoscribe's event data dictate a minimal, high-signal feature set. With 71 map-level observations, the budget is **5-7 features maximum for pre-match prediction** (map winner before match starts) and **10-15 features for in-game prediction** (updating round-by-round).

**Must have (table stakes for any prediction model):**
- **Team Elo ratings** (from VCT historical results): The single most important pre-match feature. Without it, the model is just guessing. Riot's GPR system achieves 65% accuracy using 80/20 team/league Elo weighting.
- **Map-specific win rates**: VCT Champions 2025 shows huge map variance (Abyss 57.9% attack-sided, Sunset 60.4% defense-sided). Teams have dramatically different map pools.
- **Current score differential** (in-game): Most obvious in-game predictor. Non-linear — 12-0 is not proportionally worse than 6-0 due to side swap at round 13.
- **Economy tier estimation**: Derived from round outcomes using Valorant's deterministic economy rules (win: 3000/player, loss: escalating 1900/2400/2900, spike plant: 300/player). Academic research consistently finds economy is the strongest round-outcome predictor. Classify as pistol/eco/half-buy/full-buy rather than exact credits (reduces noise).
- **Pistol round outcomes** (rounds 1 and 13): Teams winning both pistols have 74% map win rate (2025 VCT data). Cascades into 2-3 bonus rounds via economy advantage.

**Should have (competitive differentiators):**
- **Starting side + map interaction**: Attack/defense side advantage varies dramatically by map. Starting defense on Sunset vs starting defense on Abyss is completely different.
- **First blood rate** (per-team): Team getting first kill wins the round 65-70% of the time. Track which team gets first blood more consistently.
- **Win streak / loss streak**: Consecutive round wins reflect momentum and economy snowballing. 4-round win streak almost always means full economy vs eco.
- **First half score** (score at round 12): Highly predictive because it encodes side advantage + score differential before the swap.
- **Head-to-head record**: Direct matchup history. Limited value if teams have few prior meetings, decays with roster changes.

**Defer (v2+ or skip entirely):**
- **Individual player statistics**: With 71 maps, player-level features massively overfit. Player skill is captured by team Elo.
- **Per-agent win rates**: Agent meta shifts between patches. Historical win rates from 3 months ago may be inverted.
- **Ability usage counts**: Noise, not signal. Ability usage correlates with round length and engagement style, not directly with winning.
- **Exact economy values**: More noise than signal. Difference between $4200 and $4400 is meaningless. Economy tier classification captures the signal.
- **Map positioning / minimap data**: Not available in Valoscribe's event logs. Requires video analysis (TimeSformer research achieved 81% with positional features but different data modality).

**Feature engineering strategy for 71 maps:**
1. Start with 3-5 uncorrelated features (one economy, one score, one team strength, one side/map)
2. Add features one at a time with grouped cross-validation to validate improvement
3. Use L2 regularization (logistic regression) or max_depth/min_samples constraints (XGBoost)
4. Prefer categorical over continuous (economy tier better than exact credits)
5. Every feature must have theoretical justification from Valorant game mechanics

### Architecture Approach

The pipeline follows standard ML architecture: data ingestion → feature engineering → model training → temporal backtesting. The critical design is **two prediction scopes sharing one feature engineering layer** — round-level features aggregate into map-level features, which aggregate into match-level features. This avoids duplicated logic and ensures consistency between pre-match and in-game models.

**Major components (all new, no modifications to Phase 1 code):**

1. **Data Layer (`src/data/`)**: Read Valoscribe JSONL/CSV/JSON, parse into Pydantic models matching Valoscribe's output format (NOT Phase 1 event schemas), index available matches with metadata. Configuration-based path to Valoscribe repo (no data duplication).

2. **Feature Engineering (`src/features/`)**: Pure functions extract round features from events, aggregate to map features, aggregate to match features. Three-tier hierarchy with sklearn-compatible transformers for pipeline integration. Feature registry defines feature sets by name (experiments reference names, not code).

3. **Model Layer (`src/models/`)**: Configuration-driven training (ModelConfig dataclass specifies model type, hyperparameters, feature set). Support logistic regression baseline, gradient boosting, XGBoost via registry pattern. XGBoost native JSON serialization (NOT joblib/pickle which breaks across versions). Calibration wrapper (CalibratedClassifierCV) applied post-training.

4. **Evaluation Layer (`src/evaluation/`)**: Walk-forward temporal validation (expanding window, never random splits), grouped by series to prevent leakage. Metrics specific to prediction markets: log loss (primary), Brier score (calibration), calibration curves (reliability diagrams), accuracy (secondary). ROI-at-threshold analysis for deployment validation.

5. **Pipeline Orchestrator (`src/pipeline/`)**: End-to-end experiment runner wires components together. Local JSON experiment tracking (no MLflow until 500+ maps). Separate notebooks for exploration (not production code).

**Data flow:**
```
Valoscribe JSONL → data/loader.py → features/round_features.py →
features/map_features.py → models/trainer.py → evaluation/backtester.py →
reports (JSON + plots)
```

**Integration with existing codebase:**
- All Phase 1 code (`src/state/`, `src/events/`, `src/quality/`) preserved untouched
- `requirements.txt` extended with new dependencies
- `dashboard.py` eventually updated to load trained model (Phase 5+, not blocking)
- Existing 65 tests continue to pass

**Build order (dependency-driven):**
1. Data ingestion layer (must load/parse Valoscribe before anything else)
2. Feature engineering (must have features before training)
3. Model training + baseline (logistic regression baseline validates end-to-end)
4. Evaluation + backtesting (measure quality before iterating)
5. Iteration + advanced models (gradient boosting, feature selection)
6. Match/series prediction (optional for v2, extends map model)

### Critical Pitfalls

These are mistakes that produce a model that looks good in development but loses money in production, or require fundamental rework to fix.

1. **Overfitting on 71 maps masquerading as predictive skill** — Model memorizes "Team X beats Team Y" rather than learning generalizable patterns. Gradient boosting with 20+ features achieves 80%+ CV accuracy but performs at coin-flip on new tournaments. **Mitigation:** Start with logistic regression + 3-5 features, leave-one-series-out CV, strong regularization (L1 Lasso), establish naive baseline ("always pick higher-ranked team"). Consider Bayesian Elo instead of ML. Plan for dataset expansion to 200+ maps.

2. **Random train/test splits causing temporal data leakage** — Default sklearn shuffle puts Day 4 maps in training and Day 2 maps in test. Model learns from "future" information (form shifts, meta evolution). Test accuracy inflated 5-15 percentage points. **Mitigation:** Always chronological splits, grouped by series (GroupKFold with series_id), expanding window validation simulates real deployment. Never look forward in time.

3. **Optimizing for accuracy instead of calibration, then losing money** — Model achieves 65% accuracy but predicts "70% probability" when true rate is 55%. Kelly criterion sizes for 20% edge that doesn't exist. Walsh & Joshi (2024) showed calibration-optimized models generate 69.86% higher returns than accuracy-optimized. **Mitigation:** Log loss as primary metric (not accuracy), build reliability diagrams from day one, Platt scaling for post-hoc calibration, Brier score as secondary metric. Never use full Kelly (use 0.10x-0.25x with 71-map calibration).

4. **Treating noisy CV-extracted data as ground truth** — Valoscribe has 87% validation rate (9/71 maps failed), but even "passing" maps have noise: phantom kills from undetected replays, killfeed agent attribution bugs, round count mismatches. Features built on noise. **Mitigation:** Build data quality scoring per map, audit 9 failed maps manually, spot-check 5-10 passing maps against VOD, use robust features that degrade gracefully (final score more reliable than kill timing), weight maps by quality score during training.

5. **Single-tournament bias (Champions 2025 is not all of Valorant)** — Entire dataset is one tournament, one meta, one patch, one set of teams. Model learns "Champions 2025 patterns" and fails on 2026 Kickoff (meta shift, roster changes, map pool rotation). **Mitigation:** Prioritize meta-stable features (economy, first blood, side advantage transcend patches), expand dataset across tournaments ASAP (30 more maps from different event dramatically improves generalization), implement time decay on training data (exponential decay, 3-month half-life), use Elo ratings that update continuously rather than static ML features.

## Implications for Roadmap

Based on research, suggested phase structure emphasizes **validation and discipline over complexity**. The 71-map constraint forces a bottom-up approach: data quality first, baseline model second, only then consider sophistication.

### Phase 0: Data Pipeline + Validation
**Rationale:** Cannot build features without trustworthy data. Valoscribe's 87% validation rate and documented bugs (no replay detection, killfeed attribution issues) mean data quality is the foundation risk. Must establish before feature engineering.

**Delivers:**
- Data ingestion layer (`src/data/`) reads JSONL/CSV/JSON from Valoscribe
- Data quality scoring per map (kill counts vs expected, round progression consistency)
- Audit report: which of the 71 maps are usable, which need exclusion
- Spot-check validation: 5-10 passing maps verified against VOD footage

**Addresses:** Critical pitfall #4 (treating noisy data as ground truth). Establishes confidence in the 62-71 usable maps.

**Avoids:** Building feature engineering on top of phantom kills, replay-corrupted rounds, or misaligned round counts.

**Time estimate:** 3-5 days. This is unglamorous but non-negotiable.

### Phase 1: Baseline Model (Logistic Regression)
**Rationale:** With 71 maps, overfitting is the dominant risk. Must establish that the pipeline works end-to-end with the simplest possible model before considering complexity. Logistic regression with 3-5 features is not a limitation — it is discipline.

**Delivers:**
- Feature engineering layer (`src/features/`) with round/map aggregation
- Initial feature set: team Elo differential, map-specific win rates, starting side, current score differential, economy tier (5 features)
- Logistic regression baseline with L2 regularization
- Model training pipeline (`src/models/`) with configuration-driven experiments
- Walk-forward evaluation (`src/evaluation/`) with leave-one-series-out CV
- Baseline metrics: log loss, Brier score, calibration curve, accuracy

**Uses:** scikit-learn (LogisticRegression, CalibratedClassifierCV), pandas (feature engineering), matplotlib (calibration plots)

**Implements:** End-to-end pipeline from Valoscribe data → features → model → evaluation

**Addresses:** Critical pitfalls #1 (overfitting), #2 (temporal leakage via chronological splits), #3 (log loss over accuracy)

**Avoids:** Jumping to complex models before validating that simple models work. Establishing whether there is ANY predictive signal in the 71 maps.

**Success criteria:** Baseline log loss < 0.68 (better than uninformed prior), calibration curve within ±10% of diagonal, accuracy > 55%.

**Time estimate:** 5-7 days (feature engineering is the bulk).

### Phase 2: Calibration + Interpretability
**Rationale:** For betting deployment, probability quality matters more than accuracy. Must understand what the model learned (via SHAP) and fix calibration issues (via Platt scaling) before trusting it for Kelly sizing.

**Delivers:**
- SHAP integration for feature importance analysis
- Platt scaling / isotonic regression for post-hoc calibration
- Reliability diagrams with confidence intervals
- Feature importance reports: is the model learning game mechanics or team identity?
- Validation that probabilities mean what they say (60% → 60% actual win rate)

**Uses:** SHAP (TreeExplainer for baseline, upgrading to XGBoost in Phase 3), sklearn.calibration

**Implements:** Calibration as a hard gate — model cannot proceed to deployment without passing calibration validation

**Addresses:** Critical pitfall #3 (calibration over accuracy). Validates that the model's learned patterns are theoretically sound (economy matters, not just "Team A wins").

**Research flag:** If SHAP reveals the model is dominated by team identity features rather than gameplay features, this is a red flag for overfitting. May require revisiting feature set or moving to Bayesian Elo approach.

**Time estimate:** 3-4 days.

### Phase 3: Gradient Boosting + Feature Iteration
**Rationale:** Baseline established, calibration validated. Now safe to add model complexity (XGBoost) and iterate on feature engineering. Regularization discipline remains — max_depth=4, min_samples constraints.

**Delivers:**
- XGBoost integration with native categorical support
- Hyperparameter tuning via Optuna (Bayesian optimization)
- Expanded feature set: pistol round outcomes, win streaks, first blood rate, first half score (10-12 features)
- Feature selection via cross-validated performance (add one at a time, keep only if improves log loss)
- Performance comparison: does XGBoost beat logistic regression baseline?

**Uses:** XGBoost 3.2.0, Optuna 4.7.0, SHAP (TreeExplainer for XGBoost)

**Implements:** Incremental feature addition with validation (not all features at once)

**Addresses:** Extracting signal from the 71 maps without overfitting. Discipline: if a feature does not improve grouped CV log loss, remove it.

**Avoids:** Adding all 20 possible features and overfitting the noise (pitfall #1, #8 multicollinearity).

**Research flag:** If XGBoost does not beat logistic regression baseline by >5% log loss improvement, the added complexity is not justified. Stick with simpler model.

**Time estimate:** 5-7 days (hyperparameter tuning is iterative).

### Phase 4: Dataset Expansion (Cross-Tournament Validation)
**Rationale:** Single-tournament model (Champions 2025) does not generalize to new metas, patches, or rosters. Must expand to 200+ maps from multiple tournaments before trusting model for real money. This is not optional.

**Delivers:**
- Process 30-50 additional maps via Valoscribe from VCT Kickoff 2025 or Masters 2025
- Cross-tournament validation: train on Champions 2025, test on Kickoff 2025
- Distribution shift analysis: compare feature distributions across tournaments
- Time-decay weighting: exponential decay with 3-month half-life
- Model performance on unseen tournament data (real generalization test)

**Addresses:** Critical pitfall #5 (single-tournament bias). Validates whether model learned Valorant or just Champions 2025.

**Avoids:** Deploying a model trained on one patch/meta onto a different patch/meta without validation.

**Research flag:** If cross-tournament performance drops >10 percentage points, meta-stable features need rethinking or Bayesian Elo approach needed.

**Time estimate:** 2-3 weeks (depends on VOD availability and Valoscribe processing time).

### Phase 5 (Optional for v2): Match/Series Prediction
**Rationale:** Map-level prediction is the core product. Series prediction (BO3/BO5 winner) is an extension. Can be analytical (combine map probabilities) or learned (train series-level model).

**Delivers:**
- Analytical series probability calculator: given P(win each map), compute P(win BO3/BO5)
- Map veto integration from VLR.gg (which team picked which map)
- Correlation term for map outcomes within series (map 1 winner gets +X% on map 2)
- Series-level calibration validation (separate from map-level)

**Implements:** Match-level features (`src/features/match_features.py`), series probability math

**Addresses:** Moderate pitfall #9 (ignoring series dynamics). Map outcomes are not independent — momentum, adaptation, fatigue matter.

**Defer rationale:** Map prediction must work before series prediction. If map model is not calibrated, series model compounds the errors.

**Time estimate:** 3-5 days (mostly probability math and validation).

### Phase Ordering Rationale

**Why this order:**
1. **Data quality gates feature engineering** — cannot engineer features from untrustworthy data (9/71 failed maps, phantom kills, replay corruption). Phase 0 must come first.
2. **Baseline gates complexity** — with 71 maps, must prove simple models work before adding complexity. Logistic regression baseline (Phase 1) establishes whether there is ANY signal. XGBoost (Phase 3) is only justified if baseline succeeds.
3. **Calibration gates deployment** — betting requires probability quality, not just accuracy. Phase 2 (calibration) is a hard gate before any discussion of real money.
4. **Cross-tournament validation gates production use** — single-tournament models overfit the meta. Phase 4 (dataset expansion) is required before deploying with real money.
5. **Series prediction is optional** — map prediction is the core product. Series (BO3/BO5) is an extension. Phase 5 deferred if timeline constrained.

**Dependency structure:**
- Phase 1 depends on Phase 0 (need clean data)
- Phase 2 depends on Phase 1 (need baseline model to calibrate)
- Phase 3 depends on Phase 2 (need calibration framework to validate XGBoost)
- Phase 4 depends on Phase 3 (need tuned model to validate cross-tournament)
- Phase 5 depends on Phase 3 (series prediction uses map model outputs)

**How this avoids pitfalls:**
- Chronological ordering + grouped CV (Phase 1) → prevents temporal leakage (pitfall #2)
- Data quality scoring (Phase 0) → prevents noise amplification (pitfall #4)
- Baseline before complexity (Phases 1→3) → prevents premature overfitting (pitfall #1)
- Calibration as hard gate (Phase 2) → prevents accuracy optimization trap (pitfall #3)
- Cross-tournament validation (Phase 4) → prevents meta overfitting (pitfall #5)

### Research Flags

**Phases needing deeper research during execution:**
- **Phase 4 (dataset expansion):** VOD availability for other tournaments unknown. May need Kaggle datasets or VLR.gg scraping for historical match results (Elo calculation). Research flag for alternative data sources if Valoscribe VOD processing is blocked.
- **Phase 0 (data quality):** If audit reveals >20% of 71 maps are unusable (not just 9/71), may need to pivot to Bayesian Elo approach entirely (skip ML) or delay v2 until more VODs processed.

**Phases with standard patterns (no additional research needed):**
- **Phase 1 (baseline):** Logistic regression + pandas feature engineering is well-documented. sklearn Pipeline patterns are standard.
- **Phase 2 (calibration):** Platt scaling and reliability diagrams are standard sklearn methods. SHAP documentation is comprehensive.
- **Phase 3 (XGBoost):** XGBoost documentation for tabular data is mature. Optuna integration is well-documented.

**Open questions requiring phase-specific research:**
1. **Optimal CV strategy for 71 maps:** Leave-one-out vs repeated stratified k-fold. LOO is unbiased but high variance. Test both in Phase 1.
2. **Feature count budget:** With 71 samples, how many features before overfitting dominates? Start with 5, test up to 10-15. Empirical validation needed.
3. **Valoscribe data quality filtering:** Which of the 9 failed maps are salvageable? Requires manual VOD audit in Phase 0.
4. **Match-level aggregation:** How to combine map predictions into BO3/BO5 predictions? Analytical formula vs learned model. Phase 5 research.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | XGBoost, SHAP, sklearn well-documented for tabular ML at this scale. Versions verified via PyPI Feb 2026. Dependency tree understood. |
| Features | MEDIUM-HIGH | Economy + Elo + score differential are theoretically grounded and supported by academic research (TechRxiv, CSU thesis). Feature count discipline (5-7 pre-match, 10-15 in-game) is standard ML for small datasets. Specific win probability estimates (e.g., "74% map win when winning both pistols") need validation on our 71 maps. |
| Architecture | HIGH | Pipeline structure (data → features → model → evaluation) is standard ML pattern. sklearn Pipeline, pure function feature engineering, walk-forward validation are established best practices. Component boundaries clean. Integration with Phase 1 code is isolated (no modifications). |
| Pitfalls | MEDIUM-HIGH | Overfitting on small datasets, temporal leakage, and calibration issues are well-documented in ML literature. Walsh & Joshi (2024) and Wharton study provide direct evidence for calibration over accuracy. Valoscribe-specific data quality issues documented in codebase analysis. Single-tournament meta bias is theoretically sound but magnitude of impact on our features not empirically quantified. |

**Overall confidence:** MEDIUM-HIGH

Research is grounded in academic literature (Valorant prediction studies, sports betting calibration research), established ML best practices (small dataset handling, temporal validation), and project-specific analysis (Valoscribe data quality, Champions 2025 constraints). The main uncertainties are empirical: whether 71 maps is enough to learn anything, which features survive feature selection, whether cross-tournament generalization works. These are validatable during execution, not resolvable from research alone.

### Gaps to Address

**Data quality uncertainty:** Valoscribe reports 87% validation rate (62/71 maps pass) but does not quantify error rates within passing maps. Phantom kills from replays, killfeed attribution bugs, and ability tracking issues may exist in "validated" maps. **Mitigation:** Phase 0 audit establishes ground truth for 5-10 maps via manual VOD comparison. This bounds the noise floor.

**Team Elo construction:** Research identifies Elo as critical pre-match feature, but we do not have existing Elo ratings. Must build from VCT historical match results. **Mitigation:** VLR.gg provides match history going back years. Start with simple Elo (K=32), validate against BDepanfilis Bayesian Elo system for Valorant if time permits. Phase 1 can use team win rate as Elo proxy if full Elo construction delays timeline.

**Polymarket market efficiency unknown:** Research flags that prediction markets may already be well-calibrated (arbitrage bots extracted $40M+ in 2024-2025). If Polymarket VCT prices are efficient, edge may be smaller than spread. **Mitigation:** Phase 4 includes market efficiency assessment — collect historical Polymarket prices for VCT matches, calculate Brier score of raw market prices. Compare model calibration vs market calibration. If market is already at Brier score 0.20 and model achieves 0.22, there is no edge. This must be validated before real money deployment.

**Feature importance instability with small samples:** With 71 maps and leave-one-out CV, feature importance estimates have high variance. SHAP values may suggest economy is top feature in one fold and team identity in another. **Mitigation:** Bootstrap feature importance across folds. Report confidence intervals, not just point estimates. If top 3 features change across folds, model is unstable — need more data or fewer features.

**Cross-tournament generalization unknown:** Champions 2025 → Kickoff 2026 performance drop is theoretically expected (meta shift, roster changes) but magnitude is unknown. Model could drop from 65% to 55% (acceptable) or 65% to 50% (useless). **Mitigation:** Phase 4 empirical validation is the only way to resolve this. If drop is severe, pivot to Bayesian Elo approach or wait for 200+ cross-tournament maps before trusting ML.

## Sources

### Primary (HIGH confidence)

**Stack:**
- [XGBoost 3.2.0 PyPI](https://pypi.org/project/xgboost/) — Version, Python requirements verified Feb 2026
- [XGBoost Documentation](https://xgboost.readthedocs.io/en/stable/) — API, serialization, categorical support
- [SHAP 0.50.0 PyPI](https://pypi.org/project/shap/) — Version, Python >=3.11 requirement verified
- [scikit-learn 1.8.0 Calibration Module](https://scikit-learn.org/stable/modules/calibration.html) — CalibratedClassifierCV, temperature scaling
- [Optuna 4.7.0 Documentation](https://optuna.readthedocs.io/) — Version verified Jan 2026

**Features:**
- [Round Outcome Prediction in VALORANT Using Tactical Features (arXiv 2510.17199)](https://arxiv.org/html/2510.17199v1) — 81% accuracy with tactical features, 29,506 rounds dataset
- [Valorant Economy and Ultimate Prediction (TechRxiv)](https://www.techrxiv.org/users/916972/articles/1289732) — Loadout value dominates feature importance, 60.61% accuracy
- [VCT Champions 2025 Statistics (Liquipedia)](https://liquipedia.net/valorant/VCT/2025/Champions/Statistics) — Map-specific attack/defense win rates
- [Valorant Economy System (TheSpike.gg)](https://www.thespike.gg/valorant/beginner-guides/valorant-economy-guide) — Win: 3000, loss bonus escalation, spike plant: 300

**Architecture:**
- [scikit-learn Pipeline Documentation](https://scikit-learn.org/stable/modules/generated/sklearn.pipeline.Pipeline.html) — Standard ML pipeline patterns
- [Walk-Forward Validation Guide (Medium)](https://medium.com/@ahmedfahad04/understanding-walk-forward-validation-in-time-series-analysis-a-practical-guide-ea3814015abf) — Temporal validation best practices

**Pitfalls:**
- [Machine Learning for Sports Betting: Accuracy vs Calibration (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S266682702400015X) — Walsh & Joshi (2024), calibration-optimized models 69.86% higher returns
- [Sports Betting Kelly Criterion Investigation (Wharton)](https://wsb.wharton.upenn.edu/wp-content/uploads/2023/05/Beggy_2023__Betting_Kelly.pdf) — Full Kelly → bankruptcy in 100% of realistic scenarios
- [Log Loss vs Brier Score (DRatings)](https://www.dratings.com/log-loss-vs-brier-score/) — Log loss superior for sports prediction

### Secondary (MEDIUM confidence)

**Stack:**
- [XGBoost vs LightGBM Comparison (Neptune.ai)](https://neptune.ai/blog/xgboost-vs-lightgbm) — Performance comparison on tabular data
- [SHAP for Counter-Strike (Jing et al. 2025)](https://journals.sagepub.com/doi/10.1177/17479541251388864) — SHAP + XGBoost in esports ML

**Features:**
- [Valorant Win Probability Thesis (CalState)](https://scholarworks.calstate.edu/concern/projects/pk02cj680) — Logistic regression on VCT inaugural season, 1400+ games
- [CS:GO Round Winner Classification (Kaggle)](https://www.kaggle.com/datasets/christianlillelund/csgo-round-winner-classification) — 122K round snapshots, feature engineering patterns

**Pitfalls:**
- [AI Model Calibration for Sports Betting (Sports-AI.dev)](https://www.sports-ai.dev/blog/ai-model-calibration-brier-score) — Platt scaling and reliability diagrams
- [Valorant Bayesian Elo System (GitHub/BDepanfilis)](https://github.com/BDepanfilis/Valorant-Bayesian-Elo-System) — Time decay, regional bias for Valorant Elo
- [Polymarket Arbitrage Bot Exploitation (Mitrade)](https://www.mitrade.com/insights/news/live-news/article-3-1063250-20250823) — $40M+ arbitrage profits 2024-2025

### Tertiary (LOW confidence, needs validation)

**Project-specific:**
- `.planning/codebase-valoscribe/CONCERNS.md` — 87% validation rate, killfeed bugs, 9/71 map failures
- `.planning/codebase-valoscribe/ARCHITECTURE.md` — No replay detection, phase detection limitations
- `.planning/codebase-valoscribe/COMPARISON.md` — Data characteristics vs this project

**Community patterns:**
- [Pistol Round Impact Analysis (Medium/@_SushantJha)](https://medium.com/@_SushantJha/importance-of-the-first-pistol-round-a-story-from-vct-berlin-c5935b34f138) — 74% map win rate when winning both pistols (needs verification on our data)
- First blood 65-70% round win rate — commonly cited, not verified with our dataset

---
*Research completed: 2026-02-13*
*Ready for roadmap: yes*
*Key constraint: 71 maps is prototype dataset, not production foundation — discipline and validation required*
