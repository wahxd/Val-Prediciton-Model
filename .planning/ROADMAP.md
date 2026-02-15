# Roadmap: Valorant Match Prediction Model

## Milestones

- **v1 Event Detection** -- Phase 1 complete, Phases 2-4 shelved (shipped 2026-02-13)
- **v2 Prediction Model** -- Phases 5-10 (shipped 2026-02-14)
- **v3 Scale Data & Validate at Volume** -- Phases 11-15 (in progress)

## Phases

<details>
<summary>v1 Event Detection (Phase 1) -- SHIPPED 2026-02-13</summary>

- [x] **Phase 1: Event Detection Foundation** -- 4/4 plans, 65 tests
- ~~Phase 2: Event Storage & Session Management~~ -- Shelved
- ~~Phase 3: Pipeline Integration~~ -- Shelved
- ~~Phase 4: Metadata Auto-Detection~~ -- Shelved

</details>

<details>
<summary>v2 Prediction Model (Phases 5-10) -- SHIPPED 2026-02-14</summary>

- [x] **Phase 5: Data Pipeline & Validation** -- 4/4 plans, 44 tests (2026-02-13)
- [x] **Phase 6: Valoscribe Adaptation** -- 5/5 plans, 39 tests (2026-02-13)
- [x] **Phase 7: Dataset Expansion** -- 3/3 plans, 16 tests (2026-02-14)
- [x] **Phase 8: Feature Engineering** -- 4/4 plans, 79 tests (2026-02-14)
- [x] **Phase 9: Baseline Model & Evaluation** -- 3/3 plans, 66 tests (2026-02-14)
- [x] **Phase 10: Advanced Model, Series Prediction & Retrain** -- 5/5 plans, 96 tests (2026-02-14)

Full details: [milestones/v2-ROADMAP.md](milestones/v2-ROADMAP.md)

</details>

---

## v3 Scale Data & Validate at Volume (Phases 11-15)

**Goal:** Scale training dataset from 71 maps to 150+ maps via VLR.gg scraping and automated VOD processing. Run real-data experiments to validate whether the model has predictive edge.

**Target outcome:** Model performance validated on real VCT data with confidence intervals, ready for v4 trading infrastructure decision.

### Phase 11: Repo Cleanup & Organization ✓

**Goal:** Codebase and data directories organized for scaling to 150+ maps with clear module boundaries.

**Dependencies:** None (foundation for all v3 work)

**Requirements:** CLEAN-01, CLEAN-02, CLEAN-03, CLEAN-04, CLEAN-05

**Plans:** 2/2 complete

Plans:
- [x] 11-01-PLAN.md -- Delete dead code, stray files, superseded scripts; organize experiments and data
- [x] 11-02-PLAN.md -- Reorganize src/ modules (pipeline + config packages), update imports

**Completed:** 2026-02-14

---

### Phase 12: Data Sourcing / VLR.gg Scraping

**Goal:** VLR.gg scraper retrieves match metadata and VOD links for 80-100 additional maps.

**Dependencies:** Phase 11 (clean repo structure)

**Requirements:** SCRP-01, SCRP-02, SCRP-03, SCRP-04, SCRP-05, SCRP-06

**Success Criteria:**
1. VLREventScraper extracts match results (teams, map scores, outcomes) from VLR.gg tournament pages
2. YouTube VOD links extracted and validated (accessibility check before queueing)
3. Player stats (ACS, K/D/A, KAST%, ADR, HS%, FK/FD) scraped per map as metadata
4. Agent compositions extracted per map for future analysis
5. Rate-limited scraping (1 req/sec) with caching prevents VLR.gg flooding and supports resume after interruption
6. Team name normalization maps VLR.gg names to Valoscribe outputs (canonical identifiers established)
7. ProcessingManifest populated with 80-100 VODRecords from 2-3 tournaments ready for processing

---

### Phase 13: VOD Processing Pipeline

**Goal:** Automated pipeline processes 80-100 new maps through Valoscribe with resumability and quality validation.

**Dependencies:** Phase 12 (manifest of VOD targets), Valoscribe CLI interface validated

**Requirements:** PROC-01, PROC-02, PROC-03, PROC-04, PROC-05, PROC-06

**Success Criteria:**
1. VODOrchestrator executes download → process → cleanup workflow for queued VODs
2. YouTube VODs downloaded via Valoscribe/yt-dlp integration
3. Downloaded VODs processed through Valoscribe OCR pipeline automatically (events.jsonl, frames.csv, metadata.json)
4. Quality validation gates applied per map (OCR success rate, replay count distribution, alive coherence)
5. Processing resumes from last completed VOD after interruption (atomic state transitions, no re-processing)
6. Progress tracking reports completion status, ETA, and failure rate with per-VOD status visibility
7. 80-100 new maps successfully processed and quality-validated (combined with existing 71 = 150+ total)

---

### Phase 14: Scaled Experiments

**Goal:** Real-data experiments run on combined 150-map dataset with walk-forward validation and cross-tournament analysis.

**Dependencies:** Phase 13 (150+ processed maps)

**Requirements:** EXPR-01, EXPR-02, EXPR-03, EXPR-04, EXPR-05

**Success Criteria:**
1. Checkpoint prediction experiments complete on 150-map dataset (compare vs 71-map baseline)
2. Full-map prediction experiments complete on 150-map dataset
3. Walk-forward temporal CV validates generalization without data leakage
4. Log loss and calibration metrics computed with bootstrapped confidence intervals (assess statistical significance)
5. Cross-tournament validation compares performance across multiple tournaments (Champions 2025, Masters Bangkok 2024, VCT Americas 2024)
6. Results tracked in SQLite experiment database for comparison and reproducibility

---

### Phase 15: Model Iteration

**Goal:** Model hyperparameters tuned and feature importance validated on larger dataset.

**Dependencies:** Phase 14 (baseline experiments complete)

**Requirements:** ITER-01, ITER-02, ITER-03

**Success Criteria:**
1. XGBoost and logistic regression hyperparameters re-tuned via Optuna on 150-map dataset (compare optimal params vs 71-map tuning)
2. SHAP feature importance analysis reveals which features drive predictions at scale (validate game mechanics dominance holds)
3. Performance comparison documents improvement from 71-map baseline to 150-map dataset with statistical significance testing
4. Final assessment determines if model shows predictive edge sufficient for v4 trading infrastructure (decision point documented)

---

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Event Detection Foundation | v1 | 4/4 | Complete | 2026-02-13 |
| 2. Event Storage & Session Management | v1 | - | Shelved | - |
| 3. Pipeline Integration | v1 | - | Shelved | - |
| 4. Metadata Auto-Detection | v1 | - | Shelved | - |
| 5. Data Pipeline & Validation | v2 | 4/4 | Complete | 2026-02-13 |
| 6. Valoscribe Adaptation | v2 | 5/5 | Complete | 2026-02-13 |
| 7. Dataset Expansion (VOD Processing) | v2 | 3/3 | Complete | 2026-02-14 |
| 8. Feature Engineering | v2 | 4/4 | Complete | 2026-02-14 |
| 9. Baseline Model & Evaluation | v2 | 3/3 | Complete | 2026-02-14 |
| 10. Advanced Model, Series Prediction & Retrain | v2 | 5/5 | Complete | 2026-02-14 |
| 11. Repo Cleanup & Organization | v3 | 2/2 | Complete | 2026-02-14 |
| 12. Data Sourcing / VLR.gg Scraping | v3 | 0/? | Pending | - |
| 13. VOD Processing Pipeline | v3 | 0/? | Pending | - |
| 14. Scaled Experiments | v3 | 0/? | Pending | - |
| 15. Model Iteration | v3 | 0/? | Pending | - |

---
*Roadmap created: 2026-02-12*
*v2 milestone shipped: 2026-02-14*
*v3 roadmap added: 2026-02-14*
*Last updated: 2026-02-14*
