# Milestone v2: Prediction Model

**Status:** SHIPPED 2026-02-14
**Phases:** 5-10
**Total Plans:** 24

## Overview

Build and validate a prediction model for VCT map winner + match winner using Valoscribe's processed event data, with calibrated probabilities suitable for identifying edge against Polymarket prices.

**Key Insight:** VOD processing is the bottleneck (20-40 min per map). Valoscribe adaptation and dataset expansion were moved early so VOD processing runs in the background while feature engineering and modeling proceed on existing data.

## Phases

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

**Deliverables:** 7 modules (1730 LOC), 44 tests, 7/7 requirements satisfied
**Completed:** 2026-02-13

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
- [x] 06-01-PLAN.md -- Port ReplayDetector to Valoscribe + integrate into GameStateManager
- [x] 06-02-PLAN.md -- New data extraction: buy phase, ult usage, timeouts, side tracking
- [x] 06-03-PLAN.md -- Output adapter module + file naming alignment
- [x] 06-04-PLAN.md -- Schema documentation + Phase 5 Pydantic loader updates for new event types
- [x] 06-05-PLAN.md -- Baseline backup, reprocessing 71 maps, before/after validation

**Deliverables:** OutputAdapter (159 LOC), BuyPhaseDetector (204 LOC), TimeoutDetector (126 LOC), ReplayDetector port (192 LOC), schema docs (469 lines), compare_baseline.py (418 LOC), 39 tests
**Completed:** 2026-02-13 (VSCR-03/04 operationally deferred — code complete, 71-map reprocessing not executed)

### Phase 7: Dataset Expansion (VOD Processing)

**Goal**: Build a scraping + orchestration pipeline to discover VCT VODs from VLR.gg, process them through Valoscribe, and expand the training dataset beyond 71 maps -- runs in the background while Phases 8-9 execute

**Depends on**: Phase 6 (requires modified Valoscribe with output adapter and ReplayDetector)

**Requirements**: EXPN-01

**Success Criteria** (what must be TRUE):
  1. At least 30 additional VCT maps from a different tournament (not Champions 2025) are queued for processing via the modified Valoscribe pipeline
  2. Processing is running (or complete) in the background, with progress trackable (maps processed / maps total)

**Plans:** 3 plans

Plans:
- [x] 07-01-PLAN.md -- Manifest module + VLR.gg event page discovery scraper
- [x] 07-02-PLAN.md -- Orchestrator + CLI scripts (expand_dataset.py, summarize_progress.py)
- [x] 07-03-PLAN.md -- End-to-end verification + queue 30+ maps for background processing

**Deliverables:** VLREventScraper, ProcessingManifest (atomic JSON), VODOrchestrator, 46 VODs queued (23 Masters Bangkok 2024, 23 VCT Americas 2024 S1), 16 tests
**Completed:** 2026-02-14

### Phase 8: Feature Engineering

**Goal**: Transform Valoscribe event data into predictive features at three levels (round, map, match) with a feature registry that enables reproducible experiments -- informed by ALL available data from the adapted Valoscribe output

**Depends on**: Phase 5 (requires parsed event data and quality-filtered map set); Phase 6 (requires knowledge of all available data fields)

**Requirements**: FEAT-01, FEAT-02, FEAT-03, FEAT-04, FEAT-05, FEAT-06, FEAT-07, FEAT-08

**Success Criteria** (what must be TRUE):
  1. Round-level features (score differential, alive differential, spike status, economy tier) are extractable from any loaded map's events
  2. Economy is reconstructed per-round from round outcomes using Valorant's deterministic economy rules, and each team-round is classified into an economy tier (pistol/eco/half-buy/full-buy)
  3. Map-level features aggregate round data into a single feature vector per map (final score, pistol round outcomes, first half score, win/loss streaks, first blood rate)
  4. Match-level features aggregate map features for BO3/BO5 series prediction with series momentum features
  5. Named feature sets are defined in a feature registry (e.g., "baseline_5", "economy_extended") so experiments reference feature set names, not code

**Plans:** 4 plans

Plans:
- [x] 08-01-PLAN.md -- Economy reconstruction & tier classification (TDD)
- [x] 08-02-PLAN.md -- Round-level & combat feature extractors
- [x] 08-03-PLAN.md -- Map-level aggregation & feature registry
- [x] 08-04-PLAN.md -- Match-level series features & pipeline integration

**Deliverables:** 34 features across 7 categories, 5 named feature sets (YAML registry with inheritance), economy module (355 LOC), combat (503 LOC), pipeline (320 LOC), 79 tests
**Completed:** 2026-02-14

### Phase 9: Baseline Model & Evaluation

**Goal**: Train a logistic regression baseline on real VCT data with walk-forward temporal validation, proving there is predictive signal and establishing the evaluation framework that all future models must pass

**Depends on**: Phase 8 (requires feature engineering pipeline and at least the baseline feature set)

**Requirements**: MODL-01, MODL-03, MODL-04, MODL-05, MODL-07, EVAL-01, EVAL-02, EVAL-03, EVAL-04, EVAL-05, EVAL-06, EVAL-07

**Success Criteria** (what must be TRUE):
  1. A logistic regression model with L2 regularization achieves log loss below 0.693 on walk-forward temporal validation
  2. Evaluation uses leave-one-series-out cross-validation grouped by series_id
  3. Calibration validation shows predicted probabilities are within +/-10% of observed frequencies
  4. SHAP feature importance analysis confirms the model learns game mechanics
  5. Evaluation reports (JSON metrics + matplotlib plots) are generated per experiment

**Plans:** 3 plans

Plans:
- [x] 09-01-PLAN.md -- Configuration schemas & evaluation framework (ModelConfig, ExperimentConfig, temporal CV, report generation)
- [x] 09-02-PLAN.md -- Baseline trainer, calibration wrapper & JSON serialization
- [x] 09-03-PLAN.md -- SHAP explainability, baseline comparisons & end-to-end experiment runner

**Deliverables:** 7 modules (config, evaluation, baseline, calibration, explainability, experiment), smoke test: log loss 0.4565 < 0.6931 naive baseline, 66 tests
**Completed:** 2026-02-14

### Phase 10: Advanced Model, Series Prediction & Retrain

**Goal**: Improve prediction quality with XGBoost gradient boosting, extend to series-level (BO3/BO5) win probability, and retrain on the expanded dataset from Phase 7 when VOD processing completes

**Depends on**: Phase 9 (requires baseline model and evaluation framework); Phase 7 (expanded dataset available for retrain)

**Requirements**: MODL-02, MODL-06, SERS-01, SERS-02, SERS-03, EXPN-02, EXPN-03, EXPN-04

**Success Criteria** (what must be TRUE):
  1. An XGBoost model with regularization constraints is trained and compared against the logistic regression baseline
  2. Hyperparameter tuning via Optuna Bayesian optimization finds a configuration that improves log loss over baseline
  3. BO3/BO5 series win probabilities are computed from per-map win probabilities using the combinatorial formula
  4. Series-level calibration is validated separately from map-level calibration
  5. Model is retrained on the expanded dataset and log loss is compared
  6. Cross-tournament validation produces a measurable log loss with >10pp drop flagged

**Plans:** 5 plans

Plans:
- [x] 10-01-PLAN.md -- XGBoost trainer, ModelConfig extensions, dependencies
- [x] 10-02-PLAN.md -- BO3/BO5 series win probability with momentum adjustment
- [x] 10-03-PLAN.md -- Thesis validation framework (feature hierarchy check)
- [x] 10-04-PLAN.md -- Hyperparameter tuning (Optuna XGBoost + GridSearchCV logistic regression)
- [x] 10-05-PLAN.md -- Cross-tournament validation, recency weighting, retrain comparison

**Deliverables:** XGBoostTrainer (20 tests), Optuna tuning (24 tests), series prediction (18 tests), thesis validation (21 tests), cross-tournament validation (17 tests), 96 tests total
**Completed:** 2026-02-14

---

## Milestone Summary

**Decimal Phases:** None (no urgent insertions required during v2)

**Key Decisions:**

- Adopt Valoscribe for data, actively develop alongside this repo (Phase 6)
- Walk-forward temporal validation only, never random splits (Phase 9)
- Log loss as primary metric: calibration > accuracy for betting (Phase 9)
- No team identity features in map vectors (LOCKED, Phase 8)
- Elo features dropped: game mechanics sufficient, no external data needed (Phase 8)
- Economy tier thresholds: eco (<2500), light (2500-3500), half (3500-3900), full (3900+) (Phase 8)
- Momentum is simple score modifier (0.03 default), not feature-based (Phase 10)
- Map veto data unavailable: series uses average per-map probabilities (Phase 10)
- Leave-one-tournament-out CV is diagnostic only, mixed temporal training is default (Phase 10)
- Tournament-level recency weights: 1.0, 0.7, 0.5, 0.3 for recent tournaments (Phase 10)

**Issues Resolved:**

- Valoscribe output format fully catalogued and documented (469-line schema)
- Economy reconstruction from round outcomes without buy-phase OCR data
- Windows console encoding for UTF-8 team names (sys.stdout.reconfigure)
- datetime.utcnow() deprecation fixed for Python 3.13+
- matplotlib Agg backend for headless test environments

**Issues Deferred:**

- VSCR-03/04: ReplayDetector validation metrics require 71-map reprocessing (~20-40hr)
- Tournament metadata flow: no bridge from VOD manifest to modeling pipeline
- Force buy rounds placeholder in map features (needs buy phase data from reprocessing)
- E2E convenience scripts (train_model.py, predict_series.py) not yet built
- Series grouping requires manual map → series_id assignment

**Technical Debt Incurred:**

- Phase 6: ReplayDetector ported but 87% validation rate unverified on real data
- Phase 8: Anti-eco stats return zeros when economy data unavailable (graceful degradation)
- Phase 8: Team extraction fallback returns generic names when metadata incomplete
- Phase 10: All modules are framework-only; actual experiments on real data are user's next step

---

_For current project status, see .planning/STATE.md_
_Archived: 2026-02-14_
