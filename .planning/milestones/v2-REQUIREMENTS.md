# Requirements Archive: v2 Prediction Model

**Archived:** 2026-02-14
**Status:** SHIPPED (with 2 operationally deferred requirements)

This is the archived requirements specification for v2.
For current requirements, see `.planning/REQUIREMENTS.md` (created for next milestone).

---

## v1 Requirements (Previous Milestone)

### State Extraction (Existing)

- [x] **EXTR-01**: Extract game scores from VCT broadcast frames via OCR
- [x] **EXTR-02**: Detect alive player counts per team via color/brightness sampling
- [x] **EXTR-03**: Detect spike plant status via HSV color detection
- [x] **EXTR-04**: Read round timer via OCR
- [x] **EXTR-05**: Watch live Twitch/YouTube streams via streamlink at 6fps

### Event Detection (Phase 1 -- Complete)

- [x] **EVNT-01**: Detect round end events when score increments between frames
- [x] **EVNT-02**: Detect kill events when alive count decreases for either team
- [x] **EVNT-03**: Detect spike plant events when spike status transitions to planted
- [x] **EVNT-04**: Detect spike defuse events when spike status transitions from planted to not-planted
- [x] **EVNT-05**: Detect spike detonate events when spike status transitions to detonated
- [x] **EVNT-06**: Detect round start events when timer resets and alive counts return to 5v5
- [x] **EVNT-07**: State changes persist for 3+ consecutive frames before emitting event

### Data Quality (Phase 1 -- Complete)

- [x] **QUAL-01**: Detect replay footage via timer regression
- [x] **QUAL-02**: Validate alive count coherence
- [x] **QUAL-03**: Validate score monotonicity
- [x] **QUAL-04**: Suppress all event emission during detected replay segments
- [x] **QUAL-05**: Log data quality warnings when OCR confidence is low

### v1 Phases 2-4 (Shelved)

Shelved requirements (STOR-01 through STOR-04, SESS-01 through SESS-04, META-01 through META-05, PIPE-01 through PIPE-04) -- superseded by Valoscribe adoption. See PROJECT.md Key Decisions.

## v2 Requirements

### Data Ingestion

- [x] **DATA-01**: Parse Valoscribe JSONL event logs into structured Python objects (Pydantic models) -- Validated Phase 5
- [x] **DATA-02**: Parse Valoscribe CSV frame states into pandas DataFrames -- Validated Phase 5
- [x] **DATA-03**: Parse Valoscribe match metadata JSON (teams, players, agents, maps, sides) -- Validated Phase 5
- [x] **DATA-04**: Index all available processed maps with metadata summary -- Validated Phase 5
- [x] **DATA-05**: Score data quality per map (kill count vs expected, round progression consistency) -- Validated Phase 5
- [x] **DATA-06**: Generate audit report identifying usable vs excluded maps -- Validated Phase 5
- [x] **DATA-07**: Configuration-based path to Valoscribe data directory -- Validated Phase 5

### Valoscribe Adaptation

- [x] **VSCR-01**: Catalogue Valoscribe's full output format -- Validated Phase 6 (469-line schema doc)
- [x] **VSCR-02**: Add output adapter to Valoscribe for ALL extractable data -- Validated Phase 6 (OutputAdapter + BuyPhase/Timeout detectors)
- [~] **VSCR-03**: Port ReplayDetector into Valoscribe's GameStateManager to improve validation rate above 87% -- Code complete (192 lines, 12 tests), metric unverified (requires 20-40hr reprocessing)
- [~] **VSCR-04**: Validate modified Valoscribe pipeline produces consistent output on 71 maps -- Scripts ready (compare_baseline.py, 418 lines), analysis unverified (requires reprocessing)

### Feature Engineering

- [x] **FEAT-01**: Extract round-level features from events -- Validated Phase 8 (11 features)
- [x] **FEAT-02**: Reconstruct per-round economy from round outcomes -- Validated Phase 8 (deterministic economy rules)
- [x] **FEAT-03**: Classify economy tier per team per round -- Validated Phase 8 (4 tiers)
- [x] **FEAT-04**: Aggregate round features into map-level features -- Validated Phase 8 (34 features, 7 categories)
- ~~**FEAT-05**: Build team Elo ratings from VCT historical match results~~ -- Dropped (Elo requires external data unavailable; game mechanics features sufficient per Phase 8 context)
- [x] **FEAT-06**: Compute map-specific team win rates and starting side advantage -- Validated Phase 8
- [x] **FEAT-07**: Aggregate map features into match/series-level features for BO3/BO5 -- Validated Phase 8
- [x] **FEAT-08**: Feature registry with named feature sets for experiments -- Validated Phase 8 (5 sets, YAML, inheritance)

### Model Training

- [x] **MODL-01**: Logistic regression baseline with L2 regularization -- Validated Phase 9
- [x] **MODL-02**: XGBoost gradient boosting model with regularization constraints -- Validated Phase 10
- [x] **MODL-03**: Configuration-driven model training (ModelConfig) -- Validated Phase 9
- [x] **MODL-04**: Post-training probability calibration via Platt scaling -- Validated Phase 9
- [x] **MODL-05**: Model serialization using XGBoost native JSON format -- Validated Phase 9/10
- [x] **MODL-06**: Hyperparameter tuning via Optuna Bayesian optimization -- Validated Phase 10
- [x] **MODL-07**: SHAP feature importance analysis -- Validated Phase 9

### Evaluation

- [x] **EVAL-01**: Walk-forward temporal validation with chronological ordering -- Validated Phase 9
- [x] **EVAL-02**: Leave-one-series-out cross-validation grouped by series_id -- Validated Phase 9
- [x] **EVAL-03**: Primary metric: log loss -- Validated Phase 9
- [x] **EVAL-04**: Secondary metrics: Brier score, calibration curve, accuracy -- Validated Phase 9
- [x] **EVAL-05**: Baseline comparison: model must beat naive prior (log loss < 0.693) -- Validated Phase 9
- [x] **EVAL-06**: Calibration validation: predicted probabilities within +/-10% -- Validated Phase 9
- [x] **EVAL-07**: Generate evaluation reports (JSON metrics + matplotlib plots) -- Validated Phase 9

### Series Prediction

- [x] **SERS-01**: Compute BO3/BO5 series win probability from per-map win probabilities -- Validated Phase 10
- [~] **SERS-02**: Incorporate map veto data into per-map predictions -- N/A (map veto data not available; uses average of per-map probabilities)
- [x] **SERS-03**: Series-level calibration validation -- Validated Phase 10

### Dataset Expansion

- [x] **EXPN-01**: Process 30-50 additional VCT maps from other tournaments -- Validated Phase 7 (46 VODs queued)
- [x] **EXPN-02**: Cross-tournament validation: train on Champions 2025, test on new tournament data -- Validated Phase 10
- [x] **EXPN-03**: Retrain model on expanded dataset and measure improvement -- Validated Phase 10
- [x] **EXPN-04**: Assess cross-tournament generalization gap -- Validated Phase 10

## v3 Requirements (Deferred)

### Trading Infrastructure

- **TRAD-01**: Kelly criterion position sizing from calibrated model probabilities
- **TRAD-02**: Polymarket API integration for automated contract execution
- **TRAD-03**: Market efficiency assessment (compare model calibration vs market calibration)
- **TRAD-04**: Paper trading mode for validation before real money deployment

### Live Stream Support

- **LIVE-01**: Retrofit Valoscribe for live stream input via streamlink
- **LIVE-02**: Real-time prediction updates during live VCT matches
- **LIVE-03**: Crash-safe event storage for live sessions

## Out of Scope

| Feature | Reason |
|---------|--------|
| Deep learning / neural network models | 71 maps far too small; gradient boosting outperforms on tabular data at this scale |
| Automated feature engineering (featuretools/tsfresh) | Domain features outperform automated approaches at n=71 |
| MLflow / W&B experiment tracking | Overkill for single developer; local JSON experiment logs sufficient |
| Player-level prediction features | Overfit on 71 maps; player skill captured by team Elo |
| Per-agent win rate features | Meta shifts between patches; unstable signal |
| Real-time trade execution | v3 milestone -- model must be validated first |
| Non-VCT tournament support | VCT-only for consistent data quality |
| Cloud deployment | Local-first for this milestone |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| EXTR-01 | Existing | Complete |
| EXTR-02 | Existing | Complete |
| EXTR-03 | Existing | Complete |
| EXTR-04 | Existing | Complete |
| EXTR-05 | Existing | Complete |
| EVNT-01 | v1 Phase 1 | Complete |
| EVNT-02 | v1 Phase 1 | Complete |
| EVNT-03 | v1 Phase 1 | Complete |
| EVNT-04 | v1 Phase 1 | Complete |
| EVNT-05 | v1 Phase 1 | Complete |
| EVNT-06 | v1 Phase 1 | Complete |
| EVNT-07 | v1 Phase 1 | Complete |
| QUAL-01 | v1 Phase 1 | Complete |
| QUAL-02 | v1 Phase 1 | Complete |
| QUAL-03 | v1 Phase 1 | Complete |
| QUAL-04 | v1 Phase 1 | Complete |
| QUAL-05 | v1 Phase 1 | Complete |
| DATA-01 | Phase 5 | Complete |
| DATA-02 | Phase 5 | Complete |
| DATA-03 | Phase 5 | Complete |
| DATA-04 | Phase 5 | Complete |
| DATA-05 | Phase 5 | Complete |
| DATA-06 | Phase 5 | Complete |
| DATA-07 | Phase 5 | Complete |
| VSCR-01 | Phase 6 | Complete |
| VSCR-02 | Phase 6 | Complete |
| VSCR-03 | Phase 6 | Deferred (code complete, operationally unverified) |
| VSCR-04 | Phase 6 | Deferred (code complete, operationally unverified) |
| FEAT-01 | Phase 8 | Complete |
| FEAT-02 | Phase 8 | Complete |
| FEAT-03 | Phase 8 | Complete |
| FEAT-04 | Phase 8 | Complete |
| FEAT-05 | Phase 8 | Dropped |
| FEAT-06 | Phase 8 | Complete |
| FEAT-07 | Phase 8 | Complete |
| FEAT-08 | Phase 8 | Complete |
| MODL-01 | Phase 9 | Complete |
| MODL-02 | Phase 10 | Complete |
| MODL-03 | Phase 9 | Complete |
| MODL-04 | Phase 9 | Complete |
| MODL-05 | Phase 9 | Complete |
| MODL-06 | Phase 10 | Complete |
| MODL-07 | Phase 9 | Complete |
| EVAL-01 | Phase 9 | Complete |
| EVAL-02 | Phase 9 | Complete |
| EVAL-03 | Phase 9 | Complete |
| EVAL-04 | Phase 9 | Complete |
| EVAL-05 | Phase 9 | Complete |
| EVAL-06 | Phase 9 | Complete |
| EVAL-07 | Phase 9 | Complete |
| SERS-01 | Phase 10 | Complete |
| SERS-02 | Phase 10 | N/A (data unavailable) |
| SERS-03 | Phase 10 | Complete |
| EXPN-01 | Phase 7 | Complete |
| EXPN-02 | Phase 10 | Complete |
| EXPN-03 | Phase 10 | Complete |
| EXPN-04 | Phase 10 | Complete |

---

## Milestone Summary

**Shipped:** 36 of 38 active v2 requirements (94.7%)
**Adjusted:**
- FEAT-05 (Elo ratings) dropped -- external data unavailable, game mechanics features sufficient
- SERS-02 (map veto data) marked N/A -- data source unavailable, uses averaged per-map probabilities

**Dropped:**
- FEAT-05: Elo requires external historical results data not available in Valoscribe pipeline

**Operationally Deferred:**
- VSCR-03: ReplayDetector validation rate -- code complete (192 lines, 12 tests), requires 71-map reprocessing to verify metric
- VSCR-04: No regressions analysis -- scripts ready (418 lines), requires reprocessing to compare

---
*Archived: 2026-02-14 as part of v2 milestone completion*
