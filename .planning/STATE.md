# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-14)

**Core value:** A prediction model accurate enough to identify edge against Polymarket prices on VCT match outcomes.
**Current focus:** v3 — Scale data & validate at volume

## Current Position

Milestone: v3 Scale Data & Validate at Volume
Phase: 11 - Repo Cleanup & Organization
Plan: 2 of 2 complete
Status: Phase complete
Last activity: 2026-02-14 — Completed 11-02-PLAN.md (module structure reorganization)

Progress: ██░░░░░░░░░░ 20% (1/5 phases complete)

## Shipped Milestones

### v2 Prediction Model (2026-02-14)
- 6 phases (5-10), 24 plans, 340+ tests
- 36/38 requirements satisfied (2 operationally deferred: VSCR-03/04)
- 132 files, 19,042 LOC Python
- See: .planning/MILESTONES.md

### v1 Event Detection Foundation (2026-02-13)
- Phase 1 complete (4 plans, 65 tests), Phases 2-4 shelved
- Code preserved for future live stream retrofit

## Performance Metrics

**Velocity:**
- Total plans completed: 28 (v1: 4, v2: 22, v3: 2)
- Average duration: 9.5 min/plan
- Total execution time: ~4.4 hours

**v3 Progress:**
- 5 phases (11-15)
- 25 requirements
- Completed: 1 phase (11), 5/25 requirements (CLEAN-01 through CLEAN-05)
- Target: 150+ maps processed

## Accumulated Context

### v3 Roadmap Summary

**Phase 11: Repo Cleanup & Organization**
- Goal: Codebase organized for 150-map scale
- Requirements: CLEAN-01 through CLEAN-05
- Dependencies: None

**Phase 12: Data Sourcing / VLR.gg Scraping**
- Goal: Scraper retrieves 80-100 match VOD links
- Requirements: SCRP-01 through SCRP-06
- Dependencies: Phase 11

**Phase 13: VOD Processing Pipeline**
- Goal: Process 80-100 new maps via Valoscribe
- Requirements: PROC-01 through PROC-06
- Dependencies: Phase 12

**Phase 14: Scaled Experiments**
- Goal: Real-data experiments on 150-map dataset
- Requirements: EXPR-01 through EXPR-05
- Dependencies: Phase 13

**Phase 15: Model Iteration**
- Goal: Tune hyperparameters, validate edge
- Requirements: ITER-01 through ITER-03
- Dependencies: Phase 14

### Pending Todos

- Process 46 queued VODs through Valoscribe (~15-20hr processing time)
- Reprocess 71 Champions maps to verify VSCR-03/04 (can combine with VOD processing in Phase 13)
- Build VLR.gg scraper infrastructure (Phase 12)
- Validate Valoscribe CLI interface for batch processing (Phase 13)

### Blockers/Concerns

- Framework validated on synthetic data only; real-data results are unknown
- 46 VODs queued but not yet processed (15-20hr processing time)
- VSCR-03/04 operationally unverified (folded into VOD processing)
- VLR.gg scraping: site structure may change, need to handle rate limiting
- VOD availability decay: YouTube videos may be deleted/privatized (process within 48hr of scraping)
- ReplayDetector may fail on older tournaments with degraded video quality

### Key Decisions

**v3 structure:**
- 5 phases derived from requirement categories (CLEAN, SCRP, PROC, EXPR, ITER)
- Phase numbering starts at 11 (continues from v2 Phase 10)
- Sequential dependencies: 11 → 12 → 13 → 14 → 15
- Coverage: 25/25 requirements mapped (100%)

**Stack additions:**
- httpx for async VLR.gg scraping
- pyrate-limiter for rate limiting (1 req/sec)
- tqdm for progress visibility
- SQLite for experiment tracking

**Anti-decisions:**
- NO Airflow/Prefect (unjustified overhead for 150 maps)
- NO MLflow (defer until v4)
- NO Playwright/Selenium (VLR.gg is static HTML)

**Experiment organization (Phase 11):**
- experiments/v2_baseline/ contains all v2 archived experiments (9 total)
- Future v3 experiments will live alongside v2_baseline/ for clean separation
- Impact: No v2/v3 experiment conflicts

**Manifest reset (Phase 11):**
- data/processing/manifest.json reset to empty for Phase 12 rebuild
- Backup at manifest.v2_backup.json (46 entries, incomplete metadata)
- Phase 12 will repopulate with complete metadata
- Impact: Consistent data quality across all processed maps

**Module structure reorganization (Phase 11-02):**
- src/ has 6 packages: config, data, features, modeling, pipeline, scraping
- src/config/ centralizes all *Config classes (data, modeling, processing)
- src/scraping/ contains only VLR.gg web scraping (VLREventScraper)
- src/pipeline/ contains VOD processing orchestration (manifest, orchestrator)
- Circular import resolved via lazy import in VODOrchestrator
- Impact: Clean separation for Phase 12 (scraping) and Phase 13 (pipeline)

## Session Continuity

Last session: 2026-02-14
Stopped at: Completed Phase 11 Plan 02 (module structure reorganization)
Next: Start Phase 12 (Data Sourcing / VLR.gg Scraping)
Resume file: None

---
*v3 Scale Data & Validate at Volume — Phase 11 complete, ready for Phase 12.*
