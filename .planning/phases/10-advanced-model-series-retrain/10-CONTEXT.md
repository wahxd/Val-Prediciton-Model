# Phase 10: Advanced Model, Series Prediction & Retrain - Context

**Gathered:** 2026-02-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Improve map-level predictions with XGBoost gradient boosting and Optuna hyperparameter tuning, extend to series-level (BO3/BO5) win probability using combinatorial math with momentum adjustment, and retrain on the expanded dataset (Champions + Masters Bangkok + VCT Americas). Includes thesis validation framework embedded in evaluation to distinguish real signal from noise.

Exchange comparison (Polymarket/Kalshi) and reusable analysis skills are explicitly deferred to future phases.

</domain>

<decisions>
## Implementation Decisions

### XGBoost constraints & comparison
- Very conservative regularization: max_depth=3-4, high min_child_weight, few trees — prioritize not overfitting over squeezing performance with n=71-117
- XGBoost must beat logistic regression by more than 1 standard error of the CV estimate AND calibration must not degrade — improvement within CV noise is not sufficient
- Keep both models regardless of outcome — future data may change the ranking
- Report includes skepticism: flag whether improvement survives holdout check, recommend defaults if it doesn't

### Thesis validation (embedded in evaluation)
- Every experiment report validates the model against a game-mechanics thesis hierarchy:
  1. **Side x Map** — which side on which map is the dominant structural advantage
  2. **Pistol rounds** — winning pistols cascades into economy for 2-3 rounds
  3. **Economy management** — matters after pistols, but pistols are the entry point
  4. **Momentum/streaks** — overrated, only meaningful when a team is already winning
  5. **Individual combat** — clutch moments are real but too rare/noisy to predict reliably
- SHAP feature importance must align with this hierarchy — if model disagrees, that's either a finding worth investigating or a sign of overfitting
- This thesis is testable: cross-tournament stability of the hierarchy validates it, instability challenges it
- Thesis validation is more valuable than hyperparameter tuning for identifying genuine edge

### Optuna tuning strategy
- 50-100 trials with tightly constrained search space (conservative regularization already limits parameter ranges)
- Temporal holdout sanity check: tune on older data, validate on most recent matches — if tuned config doesn't beat reasonable defaults on holdout, tuning was noise
- Log loss only as Optuna objective — Platt scaling handles calibration as a separate pipeline step; ECE is too noisy at n=71 to be a useful optimization target
- Optuna pruning enabled (MedianPruner) to kill bad trials early
- Grid search for logistic regression (6-20 configs over C and penalty), Optuna for XGBoost — fair comparison requires both models at their best
- Report + skepticism: present best config but flag whether improvement over defaults survives holdout

### Series prediction approach
- Conditional / momentum-adjusted: winning/losing prior maps adjusts subsequent map win probability
- Simple score modifier — adjustment based on series score (0-1, 1-0, etc), not feature-based from completed maps
- Map veto/pick data not available — just maps played, no pick/ban information
- Series-level calibration reported with explicit caveats about small sample size (~20-30 series) — directional, not definitive

### Cross-tournament validation
- Mixed temporal training as default: pool all tournaments by date, walk-forward through the timeline
- Leave-one-tournament-out as a diagnostic for meta shift detection (not primary validation)
- Three model variants compared: Champions-only vs. mixed (all data pooled) vs. recency-weighted
- Tournament-level weights for recency weighting (most recent = 1.0, one back = 0.7, etc) — meta shifts happen at patch boundaries which align with tournament boundaries, not continuously
- Tournament weights evolve to exponential decay when dataset grows past 5+ tournaments
- Cross-tournament diagnostic report structure when >10pp accuracy drop:
  1. Statistical reality check — is the drop beyond CV noise? Confidence intervals, not just point estimates
  2. Feature shift diagnosis — SHAP comparison between tournaments, which features gained/lost importance
  3. Thesis validation — does Side×Map > Pistol > Economy hierarchy hold across tournaments?
  4. Trading implication — which features are stable across metas (trustworthy) vs. meta-dependent (signal may expire), recommended retrain frequency

### Claude's Discretion
- Specific XGBoost hyperparameter ranges within the "very conservative" constraint
- Optuna sampler and pruner configuration details
- Exact tournament weight values for recency weighting (the comparison shows whether weighting helps; exact values are secondary)
- Series momentum modifier magnitude
- Report formatting and visualization choices

</decisions>

<specifics>
## Specific Ideas

- Thesis assessment inspired by academic research synthesis format (see `synthesize research example/example.md`) — structured as evidence → diagnosis → thesis check → trading implication
- "Momentum is overrated within maps, but between maps in a series the psychological weight of going down 0-1 in a BO3 is a different dynamic"
- "Individual skill/clutch plays are noise in a prediction model — you can only clutch so many times"
- "Side x Map is the most important thing — what side are you on for what map"
- "Economy doesn't apply for pistol, so pistol is its own category separate from economy management"

</specifics>

<deferred>
## Deferred Ideas

- **Exchange comparison phase** — Connect to Kalshi/Polymarket scraping repo to compare model probabilities against market-implied probabilities. Identify where model disagrees with market and whether disagreements correlate with correct outcomes. This is where actual trading edge is validated.
- **Reusable probability analysis skill** — XML-formatted skill for standardized thesis assessment across models and markets. Build after doing the analysis manually first to understand the workflow before automating.
- **Map veto/pick data integration** — If VLR.gg or other sources provide pick/ban data, incorporate into series prediction for map comfort adjustment.
- **Patch-based weighting** — Weight by game patch proximity rather than tournament. More principled than tournament weights when dataset grows large enough.

</deferred>

---

*Phase: 10-advanced-model-series-retrain*
*Context gathered: 2026-02-14*
