# Roadmap: Valorant Match Prediction Model

## Milestones

- **v1 Event Detection** - Phases 1-4 (Phase 1 complete, Phases 2-4 shelved)
- **v2 Prediction Model** - Phases 5-10 (in progress)

## Phases

<details>
<summary>v1 Event Detection (Phases 1-4) — Phase 1 complete, Phases 2-4 shelved</summary>

**Phase Numbering:**
- Integer phases (1, 2, 3, 4): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [x] **Phase 1: Event Detection Foundation** - Core state change detection with data quality validation
- [ ] ~~**Phase 2: Event Storage & Session Management**~~ - Shelved (Valoscribe adoption)
- [ ] ~~**Phase 3: Pipeline Integration**~~ - Shelved (Valoscribe adoption)
- [ ] ~~**Phase 4: Metadata Auto-Detection**~~ - Shelved (Valoscribe adoption)

### Phase 1: Event Detection Foundation
**Goal**: Detect discrete game events (kills, round ends, spike events) from frame-by-frame state changes with robust replay detection and debouncing

**Depends on**: Nothing (first phase, extends existing VCTVisionEngine)

**Requirements**: EVNT-01, EVNT-02, EVNT-03, EVNT-04, EVNT-05, EVNT-06, EVNT-07, QUAL-01, QUAL-02, QUAL-03, QUAL-04, QUAL-05

**Success Criteria** (what must be TRUE):
  1. System detects round end events when score increments between frames
  2. System detects kill events when alive count decreases for either team
  3. System detects spike plant, defuse, and detonate events from spike status transitions
  4. System detects round start events when timer resets and alive counts return to 5v5
  5. System correctly identifies replay footage via timer regression and suppresses all event emission during replays
  6. State changes persist for 3+ consecutive frames before triggering events (no event storms from OCR flicker)
  7. System logs data quality warnings when OCR confidence is low or values are out of expected range

**Plans:** 4 plans

Plans:
- [x] 01-01-PLAN.md -- State management foundation (GameState model, StateTracker, StateValidator)
- [x] 01-02-PLAN.md -- Event schemas and replay detector (frozen event dataclasses, ReplayDetector)
- [x] 01-03-PLAN.md -- Event emitter and quality metrics (EventEmitter, QualityMetrics, structlog)
- [x] 01-04-PLAN.md -- Unit tests for all Phase 1 components (pytest suite)

### Phase 2: Event Storage & Session Management — SHELVED
### Phase 3: Pipeline Integration — SHELVED
### Phase 4: Metadata Auto-Detection — SHELVED

Phases 2-4 superseded by Valoscribe adoption. Valoscribe handles event storage, pipeline orchestration, and metadata extraction. See PROJECT.md Key Decisions.

</details>

## v2 Prediction Model

**Milestone Goal:** Build and validate a prediction model for VCT map winner + match winner using Valoscribe's processed event data, with calibrated probabilities suitable for identifying edge against Polymarket prices.

**Phase Numbering:**
- Integer phases (5, 6, 7, 8, 9, 10): Planned milestone work
- Decimal phases (7.1, 7.2): Urgent insertions if needed (marked with INSERTED)

**Key Insight:** VOD processing is the bottleneck (20-40 min per map). Valoscribe adaptation and dataset expansion are moved early so VOD processing runs in the background while feature engineering and modeling proceed on existing data.

- [x] **Phase 5: Data Pipeline & Validation** - Ingest Valoscribe output, understand full data format, quality scoring, audit
- [ ] **Phase 6: Valoscribe Adaptation** - Port ReplayDetector, add output adapter for ALL possible data, validate on 71 maps
- [ ] **Phase 7: Dataset Expansion (VOD Processing)** - Start processing additional VODs via modified Valoscribe (runs in background)
- [ ] **Phase 8: Feature Engineering** - Transform raw events into predictive features at round, map, and match level
- [ ] **Phase 9: Baseline Model & Evaluation** - Logistic regression baseline with walk-forward temporal validation
- [ ] **Phase 10: Advanced Model, Series Prediction & Retrain** - XGBoost, Optuna, BO3/BO5 series, retrain on expanded dataset

## Phase Details

### Phase 5: Data Pipeline & Validation
**Goal**: Reliably ingest all Valoscribe output (JSONL events, CSV frames, JSON metadata) with per-map quality scoring that separates usable training data from maps that should be excluded

**Depends on**: Nothing (first v2 phase; consumes Valoscribe output from external repo)

**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06, DATA-07

**Success Criteria** (what must be TRUE):
  1. Running the data loader on the Valoscribe data directory parses all 71 Champions 2025 maps into structured Python objects without errors
  2. Every loaded map has a quality score based on kill count vs expected, round progression consistency, and round start/end balance
  3. An audit report identifies which maps are usable for training and which should be excluded, with specific reasons for each exclusion
  4. The Valoscribe data directory path is configurable (not hardcoded) and no match data is duplicated into this repo
  5. A map index lists all available maps with metadata summary (teams, map name, date, event count, quality score)

**Plans:** 4 plans

Plans:
- [x] 05-01-PLAN.md -- Foundation: Pydantic schemas, config, dependencies, test fixtures
- [x] 05-02-PLAN.md -- Data loader: map discovery, JSONL/CSV/metadata parsing, map index
- [x] 05-03-PLAN.md -- Quality scoring: 5 quality signals, tiered scoring, data catalog
- [x] 05-04-PLAN.md -- Audit reports (JSON + Markdown), CLI wrapper, integration run

### Phase 6: Valoscribe Adaptation
**Goal**: Modify Valoscribe to output ALL possible extractable data (not just what the model might need), port the ReplayDetector for improved accuracy, and validate that output remains consistent on the original 71 maps

**Depends on**: Phase 5 (requires understanding of Valoscribe's current output format from data loading and audit)

**Requirements**: VSCR-01, VSCR-02, VSCR-03, VSCR-04

**Success Criteria** (what must be TRUE):
  1. Valoscribe's full output format is documented: every field, every event type, every piece of extractable data catalogued
  2. Valoscribe exports ALL extractable data via an output adapter (maximizing available signal for downstream feature engineering)
  3. ReplayDetector from Phase 1 is ported into Valoscribe's GameStateManager, and reprocessing the 71 Champions 2025 maps achieves a validation rate above 87%
  4. The modified Valoscribe pipeline produces output consistent with the original 71 maps (no regressions in previously passing maps)

**Plans:** 5 plans

Plans:
- [ ] 06-01-PLAN.md -- Port ReplayDetector to Valoscribe + integrate into GameStateManager
- [ ] 06-02-PLAN.md -- New data extraction: buy phase, ult usage, timeouts, side tracking
- [ ] 06-03-PLAN.md -- Output adapter module + file naming alignment
- [ ] 06-04-PLAN.md -- Schema documentation + Phase 5 Pydantic loader updates for new event types
- [ ] 06-05-PLAN.md -- Baseline backup, reprocessing 71 maps, before/after validation

### Phase 7: Dataset Expansion (VOD Processing)
**Goal**: Build a scraping + orchestration pipeline to discover VCT VODs from VLR.gg, process them through Valoscribe, and expand the training dataset beyond 71 maps -- runs in the background while Phases 8-9 execute

**Depends on**: Phase 6 (requires modified Valoscribe with output adapter and ReplayDetector)

**Requirements**: EXPN-01

**Success Criteria** (what must be TRUE):
  1. At least 30 additional VCT maps from a different tournament (not Champions 2025) are queued for processing via the modified Valoscribe pipeline
  2. Processing is running (or complete) in the background, with progress trackable (maps processed / maps total)

**Plans:** 3 plans

Plans:
- [ ] 07-01-PLAN.md -- Manifest module + VLR.gg event page discovery scraper
- [ ] 07-02-PLAN.md -- Orchestrator + CLI scripts (expand_dataset.py, summarize_progress.py)
- [ ] 07-03-PLAN.md -- End-to-end verification + queue 30+ maps for background processing

### Phase 8: Feature Engineering
**Goal**: Transform Valoscribe event data into predictive features at three levels (round, map, match) with a feature registry that enables reproducible experiments -- informed by ALL available data from the adapted Valoscribe output

**Depends on**: Phase 5 (requires parsed event data and quality-filtered map set); Phase 6 (requires knowledge of all available data fields)

**Requirements**: FEAT-01, FEAT-02, FEAT-03, FEAT-04, FEAT-05, FEAT-06, FEAT-07, FEAT-08

**Success Criteria** (what must be TRUE):
  1. Round-level features (score differential, alive differential, spike status, economy tier) are extractable from any loaded map's events
  2. Economy is reconstructed per-round from round outcomes using Valorant's deterministic economy rules, and each team-round is classified into an economy tier (pistol/eco/half-buy/full-buy)
  3. Map-level features aggregate round data into a single feature vector per map (final score, pistol round outcomes, first half score, win/loss streaks, first blood rate)
  4. Match-level features aggregate map features for BO3/BO5 series prediction, and team Elo ratings are computed from historical VCT results
  5. Named feature sets are defined in a feature registry (e.g., "baseline_5", "economy_extended") so experiments reference feature set names, not code

**Plans**: TBD

Plans:
- [ ] TBD (to be planned)

### Phase 9: Baseline Model & Evaluation
**Goal**: Train a logistic regression baseline on real VCT data with walk-forward temporal validation, proving there is predictive signal and establishing the evaluation framework that all future models must pass

**Depends on**: Phase 8 (requires feature engineering pipeline and at least the baseline feature set)

**Requirements**: MODL-01, MODL-03, MODL-04, MODL-05, MODL-07, EVAL-01, EVAL-02, EVAL-03, EVAL-04, EVAL-05, EVAL-06, EVAL-07

**Success Criteria** (what must be TRUE):
  1. A logistic regression model with L2 regularization achieves log loss below 0.693 (better than naive prior of always predicting 50%) on walk-forward temporal validation with chronological ordering
  2. Evaluation uses leave-one-series-out cross-validation grouped by series_id (no maps from the same series appear in both train and test), and train/test splits never look forward in time
  3. Calibration validation shows predicted probabilities are within +/-10% of observed frequencies on a reliability diagram, with Platt scaling applied post-training
  4. SHAP feature importance analysis confirms the model learns game mechanics (economy, momentum, side advantage) rather than memorizing team identity
  5. Evaluation reports (JSON metrics + matplotlib plots) are generated per experiment, covering log loss (primary), Brier score, calibration curve, and accuracy

**Plans**: TBD

Plans:
- [ ] TBD (to be planned)

### Phase 10: Advanced Model, Series Prediction & Retrain
**Goal**: Improve prediction quality with XGBoost gradient boosting, extend to series-level (BO3/BO5) win probability, and retrain on the expanded dataset from Phase 7 when VOD processing completes

**Depends on**: Phase 9 (requires baseline model and evaluation framework); Phase 7 (expanded dataset available for retrain)

**Requirements**: MODL-02, MODL-06, SERS-01, SERS-02, SERS-03, EXPN-02, EXPN-03, EXPN-04

**Success Criteria** (what must be TRUE):
  1. An XGBoost model with regularization constraints (max_depth=4, min_child_weight tuned for n=71) is trained and compared against the logistic regression baseline on the same walk-forward validation
  2. Hyperparameter tuning via Optuna Bayesian optimization finds a configuration that improves log loss over baseline (or confirms simpler model is sufficient)
  3. BO3/BO5 series win probabilities are computed from per-map win probabilities using the combinatorial formula, incorporating map veto data where available
  4. Series-level calibration is validated separately from map-level calibration, with its own reliability diagram
  5. Model is retrained on the expanded dataset (100+ maps from Phase 7) and log loss is compared to the Champions-only model
  6. Cross-tournament validation (train on Champions 2025, test on new tournament) produces a measurable log loss, and any accuracy drop >10pp is flagged with investigation findings

**Plans**: TBD

Plans:
- [ ] TBD (to be planned)

## Progress

**Execution Order:**
Phases execute: 5 -> 6 -> 7 -> 8 -> 9 -> 10
Phase 7 (VOD processing) runs in background while Phases 8-9 execute.
Phase 10 uses expanded dataset from Phase 7 when available.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Event Detection Foundation | v1 | 4/4 | Complete | 2026-02-13 |
| 2. Event Storage & Session Management | v1 | - | Shelved | - |
| 3. Pipeline Integration | v1 | - | Shelved | - |
| 4. Metadata Auto-Detection | v1 | - | Shelved | - |
| 5. Data Pipeline & Validation | v2 | 4/4 | Complete | 2026-02-13 |
| 6. Valoscribe Adaptation | v2 | 0/5 | Planned | - |
| 7. Dataset Expansion (VOD Processing) | v2 | 0/3 | Planned | - |
| 8. Feature Engineering | v2 | 0/TBD | Not started | - |
| 9. Baseline Model & Evaluation | v2 | 0/TBD | Not started | - |
| 10. Advanced Model, Series Prediction & Retrain | v2 | 0/TBD | Not started | - |

---
*Roadmap created: 2026-02-12 (v1)*
*v2 phases added: 2026-02-13*
*v2 phases restructured: 2026-02-13 (Valoscribe + VOD processing moved early)*
*Phase 5 planned: 2026-02-13 (4 plans in 3 waves)*
*Phase 5 complete: 2026-02-13 (4/4 plans, 5/5 must-haves verified, 44 tests)*
*Phase 6 planned: 2026-02-13 (5 plans in 4 waves)*
*Phase 7 planned: 2026-02-13 (3 plans in 3 waves)*
*Last updated: 2026-02-13*
