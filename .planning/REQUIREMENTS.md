# Requirements: Valorant Match Prediction Model

**Defined:** 2026-02-13
**Core Value:** A prediction model accurate enough to identify edge against Polymarket prices on VCT match outcomes.

## v1 Requirements (Previous Milestone)

### State Extraction (Existing)

- [x] **EXTR-01**: Extract game scores from VCT broadcast frames via OCR
- [x] **EXTR-02**: Detect alive player counts per team via color/brightness sampling
- [x] **EXTR-03**: Detect spike plant status via HSV color detection
- [x] **EXTR-04**: Read round timer via OCR
- [x] **EXTR-05**: Watch live Twitch/YouTube streams via streamlink at 6fps

### Event Detection (Phase 1 — Complete)

- [x] **EVNT-01**: Detect round end events when score increments between frames
- [x] **EVNT-02**: Detect kill events when alive count decreases for either team
- [x] **EVNT-03**: Detect spike plant events when spike status transitions to planted
- [x] **EVNT-04**: Detect spike defuse events when spike status transitions from planted to not-planted
- [x] **EVNT-05**: Detect spike detonate events when spike status transitions to detonated
- [x] **EVNT-06**: Detect round start events when timer resets and alive counts return to 5v5
- [x] **EVNT-07**: State changes persist for 3+ consecutive frames before emitting event

### Data Quality (Phase 1 — Complete)

- [x] **QUAL-01**: Detect replay footage via timer regression
- [x] **QUAL-02**: Validate alive count coherence
- [x] **QUAL-03**: Validate score monotonicity
- [x] **QUAL-04**: Suppress all event emission during detected replay segments
- [x] **QUAL-05**: Log data quality warnings when OCR confidence is low

### v1 Phases 2-4 (Shelved)

Shelved requirements (STOR-01 through STOR-04, SESS-01 through SESS-04, META-01 through META-05, PIPE-01 through PIPE-04) — superseded by Valoscribe adoption. See PROJECT.md Key Decisions.

## v2 Requirements

### Data Ingestion

- [x] **DATA-01**: Parse Valoscribe JSONL event logs into structured Python objects (Pydantic models)
- [x] **DATA-02**: Parse Valoscribe CSV frame states into pandas DataFrames
- [x] **DATA-03**: Parse Valoscribe match metadata JSON (teams, players, agents, maps, sides)
- [x] **DATA-04**: Index all available processed maps with metadata summary (team names, map, date, event count)
- [x] **DATA-05**: Score data quality per map (kill count vs expected, round progression consistency, round start/end balance)
- [x] **DATA-06**: Generate audit report identifying which maps are usable vs should be excluded
- [x] **DATA-07**: Configuration-based path to Valoscribe data directory (no data duplication into this repo)

### Valoscribe Adaptation

- [ ] **VSCR-01**: Catalogue Valoscribe's full output format — every field, event type, and extractable data point documented
- [ ] **VSCR-02**: Add output adapter to Valoscribe that exports ALL extractable data (maximizing available signal, not limited to known feature needs)
- [ ] **VSCR-03**: Port ReplayDetector into Valoscribe's GameStateManager to improve validation rate above 87%
- [ ] **VSCR-04**: Validate modified Valoscribe pipeline produces consistent output on the original 71 Champions 2025 maps

### Feature Engineering

- [x] **FEAT-01**: Extract round-level features from events (score differential, alive differential, spike status, economy tier)
- [x] **FEAT-02**: Reconstruct per-round economy from round outcomes using Valorant's deterministic economy rules (win/loss bonus escalation, kill rewards, spike plant bonus)
- [x] **FEAT-03**: Classify economy tier per team per round (pistol/eco/half-buy/full-buy) from reconstructed economy
- [x] **FEAT-04**: Aggregate round features into map-level features (final score, pistol round outcomes, first half score, win/loss streaks, first blood rate)
- [ ] ~~**FEAT-05**: Build team Elo ratings from VCT historical match results~~ — Dropped (Elo requires external data unavailable; game mechanics features sufficient per Phase 8 context)
- [x] **FEAT-06**: Compute map-specific team win rates and starting side advantage per map
- [x] **FEAT-07**: Aggregate map features into match/series-level features for BO3/BO5 prediction
- [x] **FEAT-08**: Feature registry that defines named feature sets for experiments (e.g., "baseline_5", "economy_extended")

### Model Training

- [x] **MODL-01**: Logistic regression baseline with L2 regularization and 3-5 features (Elo differential, map win rate, starting side, score differential, economy tier)
- [x] **MODL-02**: XGBoost gradient boosting model with regularization constraints (max_depth=4, min_child_weight tuned for n=71)
- [x] **MODL-03**: Configuration-driven model training (ModelConfig specifies model type, hyperparameters, feature set name)
- [x] **MODL-04**: Post-training probability calibration via Platt scaling (CalibratedClassifierCV)
- [x] **MODL-05**: Model serialization using XGBoost native JSON format (not joblib/pickle)
- [x] **MODL-06**: Hyperparameter tuning via Optuna Bayesian optimization for XGBoost
- [x] **MODL-07**: SHAP feature importance analysis to validate model learns game mechanics (economy, momentum) not just team identity

### Evaluation

- [x] **EVAL-01**: Walk-forward temporal validation with chronological ordering (never random splits)
- [x] **EVAL-02**: Leave-one-series-out cross-validation grouped by series_id to prevent leakage
- [x] **EVAL-03**: Primary metric: log loss (calibrated probability quality)
- [x] **EVAL-04**: Secondary metrics: Brier score, calibration curve (reliability diagram), accuracy
- [x] **EVAL-05**: Baseline comparison: model must beat naive prior (log loss < 0.693) and "always pick higher-ranked team"
- [x] **EVAL-06**: Calibration validation: predicted probabilities within ±10% of observed frequencies on reliability diagram
- [x] **EVAL-07**: Generate evaluation reports (JSON metrics + matplotlib plots) per experiment

### Series Prediction

- [x] **SERS-01**: Compute BO3/BO5 series win probability from per-map win probabilities using combinatorial formula
- [~] **SERS-02**: Incorporate map veto data (which team picked which map) into per-map predictions where available — N/A (map veto data not available per CONTEXT decision; uses average of per-map probabilities)
- [x] **SERS-03**: Series-level calibration validation (separate from map-level)

### Dataset Expansion

- [x] **EXPN-01**: Process 30-50 additional VCT maps from other tournaments via modified Valoscribe pipeline
- [x] **EXPN-02**: Cross-tournament validation: train on Champions 2025, test on new tournament data
- [x] **EXPN-03**: Retrain model on expanded dataset and measure improvement in log loss and calibration
- [x] **EXPN-04**: Assess cross-tournament generalization gap (if >10pp accuracy drop, flag for investigation)

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
| Real-time trade execution | v3 milestone — model must be validated first |
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
| VSCR-01 | Phase 6 | Pending |
| VSCR-02 | Phase 6 | Pending |
| VSCR-03 | Phase 6 | Pending |
| VSCR-04 | Phase 6 | Pending |
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

**Coverage:**
- v2 requirements: 40 total
- Mapped to phases: 40
- Unmapped: 0

**Phase Distribution:**
- Phase 5: 7 requirements (DATA-01 to DATA-07)
- Phase 6: 4 requirements (VSCR-01 to VSCR-04)
- Phase 7: 1 requirement (EXPN-01)
- Phase 8: 8 requirements (FEAT-01 to FEAT-08)
- Phase 9: 12 requirements (MODL-01/03/04/05/07, EVAL-01 to EVAL-07)
- Phase 10: 8 requirements (MODL-02/06, SERS-01 to SERS-03, EXPN-02 to EXPN-04)

---
*Requirements defined: 2026-02-13*
*Last updated: 2026-02-14 — Phase 10 complete (MODL-02/06, SERS-01/03, EXPN-02/03/04; SERS-02 N/A)*
