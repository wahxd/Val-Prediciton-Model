# Valorant Match Prediction Model

## What This Is

A prediction framework for VCT (Valorant Champions Tour) match outcomes (map winner + series winner), trained on real match event data extracted by Valoscribe. Includes a 34-feature engineering pipeline, logistic regression and XGBoost models with Platt scaling calibration, BO3/BO5 series prediction, and cross-tournament validation. End goal: identify mispriced Valorant match contracts on Polymarket for automated asymmetric betting.

## Core Value

A prediction model accurate enough to identify edge against Polymarket prices on VCT match outcomes.

## Current State: v2 Shipped

**v2 Prediction Model shipped 2026-02-14.** The framework is built and tested (340+ tests). Next step: run experiments on real VCT data, then build v3 trading infrastructure if the model shows predictive edge.

See `.planning/MILESTONES.md` for full milestone history.

## Requirements

### Validated

- ✓ Extract game scores from VCT broadcast frames via OCR — existing
- ✓ Detect alive player counts per team via color/brightness sampling — existing
- ✓ Detect spike plant status via HSV color detection — existing
- ✓ Read round timer via OCR — existing
- ✓ Watch live Twitch/YouTube streams via streamlink at 6fps — existing
- ✓ ROI coordinate system for 1920x1080 VCT broadcast layout — existing
- ✓ Basic win probability prediction via logistic regression — existing (synthetic data)
- ✓ Streamlit dashboard for VOD frame analysis — existing
- ✓ Event detection foundation (StateTracker, EventEmitter, ReplayDetector, debouncing) — v1
- ✓ Data quality validation (replay detection, alive coherence, score monotonicity) — v1
- ✓ Ingest Valoscribe JSONL event logs into structured training dataset — v2
- ✓ Feature engineering pipeline (34 features across 7 categories with YAML registry) — v2
- ✓ Map winner prediction model trained on real VCT data (logistic regression + XGBoost) — v2
- ✓ Match/series winner prediction model (BO3/BO5 with momentum adjustment) — v2
- ✓ Model evaluation with walk-forward temporal CV, calibration, log loss, SHAP — v2
- ✓ Process additional VCT VODs via Valoscribe for expanded training set (46 VODs queued) — v2
- ✓ Cross-tournament validation and recency weighting — v2
- ✓ Hyperparameter tuning via Optuna Bayesian optimization — v2

### Active

(No active requirements — next milestone not yet planned)

### Out of Scope

- Contract price data integration (Polymarket/Kalshi) — v3 milestone
- Kelly criterion position sizing — v3 milestone
- Automated trade execution — v3 milestone
- Live stream event detection — v3 milestone (retrofit Valoscribe for live)
- Real-time prediction during live matches — v3 milestone
- Mobile or web deployment — local tool for now
- Deep learning / neural nets — dataset too small; gradient boosting outperforms at n=71
- Player-level prediction features — overfits on small dataset
- Per-agent win rate features — meta shifts between patches, unstable signal

## Context

- **Codebase:** 19,042 lines of Python across src/, tests/, scripts/
- **Tech stack:** Python (scikit-learn, XGBoost, Optuna, pandas, numpy, SHAP, matplotlib)
- **Valoscribe** (D:\Git\valoscribe) is actively developed alongside this repo — OutputAdapter, BuyPhaseDetector, TimeoutDetector, ReplayDetector ported in v2
- **Data:** 71 Champions 2025 maps processed, 46 additional VODs queued (Masters Bangkok 2024, VCT Americas 2024)
- **Features:** 34 map-level features in 7 categories (score, pistol, halves, momentum, combat, side performance, economy)
- **Models:** Logistic regression baseline + XGBoost with conservative regularization
- **Evaluation:** Walk-forward temporal CV, leave-one-series-out grouping, log loss primary metric
- **Framework validated on synthetic data;** real-data experiments are the immediate next step
- **Known operational debt:** VSCR-03/04 (ReplayDetector validation rate and regression check) require 71-map reprocessing (~20-40hr)

## Constraints

- **Data source**: Valoscribe's processed JSONL event logs from VCT VODs (Champions 2025 + expansion tournaments)
- **Tech stack**: Python ecosystem (scikit-learn, XGBoost, Optuna, pandas, numpy, SHAP)
- **Platform**: Windows 11 development environment
- **Storage**: Local-first — no cloud infrastructure
- **Training data**: 71 maps available, 46 more queued, expandable by processing more VODs

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Event-based logging (not continuous snapshots) | Only state changes matter for prediction | ✓ Good — validated in Phase 1 |
| Adopt Valoscribe for data, actively develop alongside | Valoscribe solved hard CV problems. Actively adapted in Phase 6 with new detectors and adapters. | ✓ Good — enabled rapid feature engineering |
| Prediction scope: map winner + match winner | Binary outcomes with clear contracts on Polymarket | ✓ Good — clean signal, maps to BO3/BO5 series |
| v2 = model only, v3 = trading + live | Ship the model first, validate edge before building trading infrastructure | ✓ Good — framework complete, ready for validation |
| Shelve v1 Phases 2-4 | Valoscribe provides storage/pipeline/metadata capabilities | ✓ Good — avoided duplication |
| Walk-forward temporal validation only | Never random splits; prevents future data leakage | ✓ Good — foundational to evaluation framework |
| Log loss as primary metric | Calibration matters more than accuracy for betting applications | ✓ Good — drives model design and evaluation |
| No team identity features | Purely game mechanics; prevents overfitting to team names | ✓ Good — SHAP validates game mechanics dominance |
| Drop Elo features (FEAT-05) | External data unavailable; game mechanics features sufficient | ✓ Good — simplified pipeline, no external dependencies |
| Economy reconstruction from round outcomes | Deterministic Valorant economy rules enable tier classification without buy-phase OCR | ✓ Good — 4 tiers working reliably |
| Momentum as simple score modifier (0.03) | Not feature-based; series calibration validates | ✓ Good — avoids overcomplication |
| Leave-one-tournament-out CV is diagnostic only | Mixed temporal training is default; LOTO for investigation | ✓ Good — avoids overfitting to tournament structure |

---
*Last updated: 2026-02-14 after v2 milestone completion*
