# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-14)

**Core value:** A prediction model accurate enough to identify edge against Polymarket prices on VCT match outcomes.
**Current focus:** v3 — Scale data & validate at volume

## Current Position

Milestone: v3 Scale Data & Validate at Volume
Phase: 13 - VOD Processing Pipeline
Plan: 2 of 3 complete
Status: In progress
Last activity: 2026-02-15 — Completed 13-02-PLAN.md (BatchProcessor with tqdm, circuit breaker, tournament ordering)

Progress: ████░░░░░░░░ 40% (2/5 phases complete)

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
- Total plans completed: 34 (v1: 4, v2: 22, v3: 8)
- Average duration: 7.8 min/plan
- Total execution time: ~4.95 hours

**v3 Progress:**
- 5 phases (11-15)
- 25 requirements
- Completed: 2 phases (11, 12), 16/25 requirements (CLEAN-01 through CLEAN-05, SCRP-01 through SCRP-06, PROC-01 through PROC-06)
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

- Process 169 queued VODs through Valoscribe (~127hr processing time at 45min/map)
- Validate Valoscribe CLI interface for batch processing (Phase 13)
- Run real-data experiments on 150+ map dataset (Phase 14)

### Blockers/Concerns

- Framework validated on synthetic data only; real-data results are unknown
- 169 VODs queued but not yet processed (~127hr processing time)
- 40 maps skipped due to missing YouTube URLs (19.1% of maps found)
- VLR.gg scraping: site structure may change, need to handle rate limiting
- VOD availability decay: YouTube videos may be deleted/privatized (process within 48hr of scraping)
- ReplayDetector may fail on older tournaments with degraded video quality
- Processing time: 169 maps × 45min = ~127 hours (recommend batch processing)

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
- tqdm for progress visibility (planned for Phase 13)
- SQLite for experiment tracking (planned for Phase 14)

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
- src/scraping/ contains VLR.gg web scraping (VLREventScraper, VLRMatchScraper, TournamentScraper, YouTubeVODFinder)
- src/pipeline/ contains VOD processing orchestration (manifest, orchestrator)
- Circular import resolved via lazy import in VODOrchestrator
- Impact: Clean separation for Phase 12 (scraping) and Phase 13 (pipeline)

**Scraping infrastructure (Phase 12-01):**
- Async HTTP client with rate limiting (pyrate-limiter, 1 req/sec default)
- Extended VODRecord: player_stats, agent_compositions, player_vlr_ids, match_score, match_outcome
- TeamNormalizer: RapidFuzz fuzzy matching (>= 85 threshold), 30+ manual overrides
- Hishel caching deferred (requires hishel[async] extra)
- Impact: Foundation ready for VLR.gg scraping in 12-02+

**VLR.gg player stats scraper (Phase 12-02):**
- VLRMatchScraper: Parse VLR.gg match pages for player stats (ACS, K/D/A, KAST%, ADR, HS%, FK/FD), agent compositions, player VLR IDs
- VLREventScraper rewritten to async with httpx + pyrate-limiter
- Removed Valoscribe scrape_match dependency (VLRMatchScraper handles all parsing)
- 17 tests (10 VLRMatchScraper + 7 async VLREventScraper), all passing
- Impact: Rich metadata extraction ready for tournament scraping

**YouTube VOD finder (Phase 12-03):**
- YouTubeVODFinder: YouTube Data API v3 integration for map-specific VOD discovery
- Validates video accessibility (public + unlisted + processed status)
- Quota tracking: 10,000 units/day limit, raises QuotaExhaustedError before exceeding
- Search optimization: videoDuration='long' filter to exclude highlights (<20min)
- Prefers VLR.gg URLs, falls back to YouTube search when missing/invalid
- Impact: Fills missing per-map VOD links that VLR.gg pages lack

**Tournament scraper integration (Phase 12-04):**
- TournamentScraper: Wires VLREventScraper + YouTubeVODFinder + ProcessingManifest
- CLI script: scripts/scrape_tournaments.py for automated tournament scraping
- 169 VODRecords populated: Masters Bangkok 2024 (83 maps), VCT Americas 2024 Stage 1 (86 maps)
- All records have: player_stats, agent_compositions, player_vlr_ids, match_score, match_outcome
- YouTube API quota used: 0 (VLR.gg URLs trusted directly without validation)
- 40 maps skipped (19.1%) due to missing YouTube URLs on VLR.gg pages
- VLR.gg date parsing: Converts "Month DD, YYYY" text to ISO "YYYY-MM-DD"
- Accepts unlisted YouTube VODs (event organizers often upload as unlisted)
- Impact: Manifest ready for Phase 13 VOD processing pipeline

**Manifest & config extensions (Phase 13-01):**
- VODRecord.quality_metrics: Dict field stores quality validation results (overall_score, tier, checks)
- Granular failure statuses: download_failed (private/deleted VODs) vs processing_failed (OCR errors)
- Batch processing config: batch_size=20, circuit_breaker_threshold=5, download_timeout_seconds=1800
- QualityValidator: Bridges Valoscribe output files to quality scoring system
- JSON-serializable metrics dict enables Phase 14 filtering by quality tier
- Impact: Foundation ready for BatchProcessor (13-02) and CLI (13-03)

**Batch processing engine (Phase 13-02):**
- BatchProcessor replaces VODOrchestrator.run_pipeline() as primary processing loop
- tqdm progress bars show current VOD, tournament, teams, and ETA
- Circuit breaker stops after 5 consecutive failures (prevents wasted processing time)
- Tournament ordering: processes all maps from one tournament before starting next
- Quality validation runs after each successful VOD, stores metrics in manifest
- Partial output cleanup: removes incomplete Valoscribe files on processing failure
- Granular failure statuses in VODOrchestrator: download_failed vs processing_failed
- Impact: Ready for CLI wrapper (13-03), ready to process 169 VODs

## Session Continuity

Last session: 2026-02-15
Stopped at: Completed 13-02-PLAN.md (BatchProcessor with tqdm, circuit breaker, tournament ordering)
Next: 13-03 — Batch processing CLI
Resume file: None

---
*v3 Scale Data & Validate at Volume — Phase 13 in progress (2/3 plans complete).*
