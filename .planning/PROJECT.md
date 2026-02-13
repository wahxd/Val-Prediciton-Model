# Valorant Match Prediction Model

## What This Is

A prediction model for VCT (Valorant Champions Tour) match outcomes, trained on real match event data extracted by Valoscribe (external VOD analysis pipeline). Predicts map winner and match winner for VCT series. Data comes from Valoscribe's processed JSONL event logs (71+ Champions 2025 maps). End goal: identify mispriced Valorant match contracts on Polymarket for automated asymmetric betting.

## Core Value

A prediction model accurate enough to identify edge against Polymarket prices on VCT match outcomes.

## Current Milestone: v2 Prediction Model

**Goal:** Build and validate a prediction model for VCT map winner + match winner using Valoscribe's processed event data.

**Target features:**
- Ingest Valoscribe's JSONL event logs as training data
- Feature engineering from match events (kills, economy, agent comps, round progression)
- Train and validate model for map-level and match-level predictions
- Measure accuracy against held-out matches

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
- ✓ Event detection foundation (StateTracker, EventEmitter, ReplayDetector, debouncing) — v1 Phase 1
- ✓ Data quality validation (replay detection, alive coherence, score monotonicity) — v1 Phase 1

### Active

- [ ] Ingest Valoscribe JSONL event logs into structured training dataset
- [ ] Feature engineering pipeline (match events → predictive features)
- [ ] Map winner prediction model trained on real VCT data
- [ ] Match/series winner prediction model (BO3/BO5)
- [ ] Model evaluation with measured accuracy, calibration, and log loss
- [ ] Process additional VCT VODs via Valoscribe for expanded training set

### Out of Scope

- Contract price data integration (Polymarket/Kalshi) — v3 milestone
- Kelly criterion position sizing — v3 milestone
- Automated trade execution — v3 milestone
- Live stream event detection — v3 milestone (retrofit Valoscribe for live)
- Replay detection improvements to Valoscribe — later, not blocking model training
- Real-time prediction during live matches — v3 milestone
- Mobile or web deployment — local tool for now

## Context

- Valoscribe (D:\Git\valoscribe) is a mature VOD analysis pipeline with 47+ source files, 14+ CV detectors, player-level detection
- Valoscribe has 71 processed Champions 2025 maps with 200-850 events/map, 87% validation rate
- Valoscribe produces JSONL events (kills with killer/victim/weapon, round events, ability usage) and CSV frame states
- This repo keeps Valoscribe as a separate dependency — consume its output data, don't modify its code
- Phase 1 event detection code (StateTracker, ReplayDetector) preserved for future live stream retrofit
- Existing basic logistic regression model uses synthetic data — needs to be retrained on real Valoscribe data
- v1 Phases 2-4 (storage, pipeline integration, metadata detection) shelved — Valoscribe handles this

## Constraints

- **Data source**: Valoscribe's processed JSONL event logs from VCT Champions 2025 VODs
- **Tech stack**: Python ecosystem (scikit-learn, pandas, numpy) — extend existing, add ML libraries as needed
- **Platform**: Windows 11 development environment
- **Storage**: Local-first — no cloud infrastructure
- **Training data**: 71 maps minimum, expandable by processing more VODs via Valoscribe

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Event-based logging (not continuous snapshots) | Only state changes matter for prediction — kills, round ends, economy shifts. Reduces noise and storage. | ✓ Good — validated in Phase 1 |
| Adopt Valoscribe for data, keep as separate repo | Valoscribe solved hard CV problems (player-level detection, 71 maps processed). No need to rebuild. Consume output data here. | — Pending |
| Prediction scope: map winner + match winner | Binary outcomes with clear contracts on Polymarket. Simpler than round-level or prop bets. | — Pending |
| v2 = model only, v3 = trading + live | Ship the model first, validate it has edge before building trading infrastructure. | — Pending |
| Shelve v1 Phases 2-4 | Storage, pipeline integration, metadata detection no longer needed — Valoscribe provides these capabilities. Phase 1 code preserved for future live retrofit. | — Pending |

---
*Last updated: 2026-02-13 after v2 milestone start*
