# Project Milestones: Valorant Match Prediction Model

## v2.0 Prediction Model (Shipped: 2026-02-14)

**Delivered:** Complete prediction framework for VCT map winner + match winner with calibrated probabilities, 34-feature engineering pipeline, XGBoost and logistic regression models, BO3/BO5 series prediction, and cross-tournament validation -- ready for real-data experiments.

**Phases completed:** 5-10 (24 plans total)

**Key accomplishments:**

- Built data ingestion pipeline for Valoscribe JSONL/CSV/JSON with 5-signal quality scoring and tiered audit reports (Phase 5)
- Adapted Valoscribe with OutputAdapter, BuyPhase/Timeout detectors, and ported ReplayDetector for improved accuracy (Phase 6)
- Built VOD discovery and processing pipeline with 46 maps queued from Masters Bangkok 2024 and VCT Americas 2024 (Phase 7)
- Engineered 34 predictive features across 7 categories (score, pistol, halves, momentum, combat, side performance, economy) with composable YAML feature registry (Phase 8)
- Established walk-forward evaluation framework with logistic regression baseline, SHAP explainability, and Platt scaling calibration (Phase 9)
- Added XGBoost gradient boosting, Optuna Bayesian tuning, BO3/BO5 series prediction with momentum, thesis validation, and cross-tournament validation with recency weighting (Phase 10)

**Stats:**

- 132 files created/modified
- 19,042 lines of Python
- 6 phases, 24 plans, 340+ tests (all passing)
- 2 days from start to ship (2026-02-13 to 2026-02-14)

**Git range:** `feat(05-01)` to `docs(10)`

**Known caveats:**
- VSCR-03/04 code complete but operationally unverified (requires 20-40hr VOD reprocessing)
- Framework is validated on synthetic data; real-data experiments are the next step

**What's next:** Run experiments on real VCT data, process queued VODs, then build v3 trading infrastructure if model shows predictive edge.

---

## v1.0 Event Detection Foundation (Shipped: 2026-02-13)

**Delivered:** Core event detection system for VCT broadcast frames -- kills, round events, spike events with replay detection and data quality validation.

**Phases completed:** 1 (4 plans; Phases 2-4 shelved after Valoscribe adoption)

**Key accomplishments:**

- StateTracker with 3-frame debouncing for OCR stability
- EventEmitter for kills, round start/end, spike plant/defuse/detonate
- ReplayDetector via timer regression analysis
- Data quality validation (alive coherence, score monotonicity)

**Stats:**

- 4 plans, 65 tests
- Phase 1 code preserved for future live stream retrofit

**What's next:** v2 Prediction Model (build on Valoscribe data instead of raw frame processing)

---

*Last updated: 2026-02-14*
