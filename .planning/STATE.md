# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-14)

**Core value:** A prediction model accurate enough to identify edge against Polymarket prices on VCT match outcomes.
**Current focus:** v3 — Scale data & validate at volume

## Current Position

Milestone: v3 Scale Data & Validate at Volume
Phase: 12 - Data Sourcing / VLR.gg Scraping
Plan: 3 of 6 complete
Status: In progress
Last activity: 2026-02-15 — Completed 12-03-PLAN.md (YouTube VOD finder)

Progress: ██░░░░░░░░░░ 20% (1/5 phases complete, 3/6 plans in Phase 12)

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
- Total plans completed: 30 (v1: 4, v2: 22, v3: 4)
- Average duration: 8.3 min/plan
- Total execution time: ~4.6 hours

**v3 Progress:**
- 5 phases (11-15)
- 25 requirements
- Completed: 1 phase (11), 7/25 requirements (CLEAN-01 through CLEAN-05, SCRP-01, SCRP-02)
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
- httpx for async VLR.gg scraping (installed 12-01)
- hishel for HTTP caching (installed 12-01, caching deferred until hishel[async])
- pyrate-limiter for rate limiting (installed 12-01, 1 req/sec default)
- google-api-python-client for YouTube Data API (installed 12-01)
- rapidfuzz for team name normalization (installed 12-01)
- pytest-asyncio for async test support (installed 12-01)
- tqdm for progress visibility (planned)
- SQLite for experiment tracking (planned)

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

**Scraping infrastructure (Phase 12-01):**
- Async HTTP client with rate limiting (pyrate-limiter, 1 req/sec default)
- Extended VODRecord: player_stats, agent_compositions, player_vlr_ids, match_score, match_outcome
- TeamNormalizer: RapidFuzz fuzzy matching (>= 85 threshold), 30+ manual overrides
- Hishel caching deferred (requires hishel[async] extra)
- Impact: Foundation ready for VLR.gg scraping in 12-02+

**YouTube VOD finder (Phase 12-03):**
- YouTubeVODFinder: YouTube Data API v3 integration for map-specific VOD discovery
- Validates video accessibility (public + processed status)
- Quota tracking: 10,000 units/day limit, raises QuotaExhaustedError before exceeding
- Search optimization: videoDuration='long' filter to exclude highlights (<20min)
- Prefers VLR.gg URLs, falls back to YouTube search when missing/invalid
- Impact: Fills missing per-map VOD links that VLR.gg pages lack

## Session Continuity

Last session: 2026-02-15
Stopped at: Completed 12-03-PLAN.md (YouTube VOD finder)
Next: Continue Phase 12 (Plan 12-04: VLR.gg Match Scraper Integration)
Resume file: None

---
*v3 Scale Data & Validate at Volume — Phase 12 in progress (3/6 plans complete).*
