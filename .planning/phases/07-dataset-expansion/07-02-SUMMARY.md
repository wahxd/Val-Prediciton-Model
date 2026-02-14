---
phase: 07-dataset-expansion
plan: 02
subsystem: orchestration
tags: [subprocess, valoscribe-cli, pydantic-settings, argparse, manifest, resumable-processing]

# Dependency graph
requires:
  - phase: 07-dataset-expansion
    plan: 01
    provides: VLR event scraper and processing manifest with atomic persistence
  - phase: 06-valoscribe-adaptation
    provides: Valoscribe CLI commands (download, scrape-vlr, split-metadata, orchestrate process-vod)
provides:
  - ProcessingConfig with environment variable loading (EXPANSION_ prefix)
  - VODOrchestrator wiring Valoscribe CLI commands into resumable pipeline
  - CLI scripts for discover/process/resume operations
  - Progress monitoring with ETA estimates
affects: [07-03, dataset-expansion, vod-processing]

# Tech tracking
tech-stack:
  added: [pydantic-settings>=2.7]
  patterns: [subprocess-orchestration, env-var-config, cli-with-argparse, progress-reporting]

key-files:
  created:
    - src/scraping/config.py
    - src/scraping/orchestrator.py
    - scripts/expand_dataset.py
    - scripts/summarize_progress.py
  modified:
    - src/scraping/__init__.py
    - .env.example

key-decisions:
  - "ProcessingConfig uses pydantic-settings with EXPANSION_ prefix for multi-developer consistency"
  - "Orchestrator downloads series metadata once, splits into per-map files, then processes each map"
  - "VOD files deleted after successful processing to save disk space (configurable)"
  - "CLI scripts use stdlib argparse (no typer/click dependency)"
  - "Progress monitoring includes ETA based on average processing time"

patterns-established:
  - "Subprocess orchestration: subprocess.run with check=True, capture_output=True, timeout"
  - "Config pattern: pydantic-settings with env_prefix for isolated config namespaces"
  - "CLI pattern: argparse with --discover-only, --process-only, --dry-run modes"
  - "Progress reporting: by-status counts, by-tournament breakdown, ETA calculation"

# Metrics
duration: 4.1min
completed: 2026-02-13
---

# Phase 07 Plan 02: Valoscribe Orchestration Summary

**VODOrchestrator wires Valoscribe CLI commands (download, scrape, process) into resumable pipeline with rate limiting, timeout handling, and CLI scripts for discover/process/monitor operations**

## Performance

- **Duration:** 4.1 min
- **Started:** 2026-02-14T06:27:32Z
- **Completed:** 2026-02-14T06:31:35Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- ProcessingConfig with pydantic-settings loads EXPANSION_ env vars (paths, timeouts, rate limits)
- VODOrchestrator wires Valoscribe CLI: scrape-vlr → split-metadata → download → process-vod
- Resumable pipeline with per-VOD state tracking and automatic cleanup
- expand_dataset.py CLI supports discover-only, process-only, and dry-run modes
- summarize_progress.py provides progress report with ETA, by-tournament stats, and failure details

## Task Commits

Each task was committed atomically:

1. **Task 1: Create config module + orchestrator** - `5ed693c` (feat)
2. **Task 2: Create CLI scripts + .env.example** - `5e1329d` (feat)

## Files Created/Modified

- `src/scraping/config.py` - ProcessingConfig with EXPANSION_ env vars and pydantic validation
- `src/scraping/orchestrator.py` - VODOrchestrator class wiring Valoscribe CLI commands
- `src/scraping/__init__.py` - Export ProcessingConfig, VODOrchestrator, ProcessingManifest, VODRecord
- `scripts/expand_dataset.py` - CLI for discover/process/resume with argparse
- `scripts/summarize_progress.py` - Progress monitoring with ETA and failure reports
- `.env.example` - Added EXPANSION_ config variables

## Decisions Made

**ProcessingConfig uses pydantic-settings with EXPANSION_ prefix**
- Rationale: Consistent with Phase 5 pattern (VALOSCRIBE_DATA_DIR), namespace isolation for multi-developer setup
- Implementation: BaseSettings with env_prefix = "EXPANSION_", loads from environment or defaults

**Orchestrator downloads series metadata once per match, splits into per-map files**
- Rationale: Valoscribe's scrape-vlr outputs series JSON with all maps, split-metadata creates per-map files needed by process-vod
- Flow: scrape-vlr (once) → split-metadata (once) → for each map: download VOD → process-vod

**VOD files deleted after successful processing**
- Rationale: VODs are multi-GB, processing runs over days/weeks, disk space is limited
- Implementation: try/finally in process_single_vod, configurable via delete_vod_after_processing (default: True)

**CLI scripts use stdlib argparse**
- Rationale: No typer/click dependency, simpler for standalone scripts, consistent with existing codebase patterns
- Implementation: argparse with --help, --dry-run, --discover-only, --process-only modes

**Progress monitoring includes ETA**
- Rationale: Processing runs for days/weeks, users need estimates for planning
- Implementation: Average processing time from completed VODs × pending count

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. Users can optionally set EXPANSION_ environment variables to override defaults.

## Next Phase Readiness

**Ready for Plan 03 (VOD processing execution)**
- Orchestrator wires Valoscribe CLI commands into resumable pipeline
- CLI scripts provide discover/process/monitor operations
- Configuration loads from environment with sensible defaults
- All Plan 01 tests still pass (16/16)

**Integration points verified:**
- Valoscribe CLI commands tested via --help (download, scrape-vlr, split-metadata, orchestrate process-vod)
- Imports work (VODOrchestrator, ProcessingConfig)
- Scripts show usage without errors (expand_dataset.py, summarize_progress.py)

**Blockers:**
None.

**Concerns:**
- VLR.gg HTML selectors in Plan 01's VLREventScraper not yet tested against live pages (only fixtures)
- YouTube rate limiting thresholds unknown - starting conservative (10s delays)
- Valoscribe processing time variance not yet measured (timeout set to 2 hours conservatively)

---
*Phase: 07-dataset-expansion*
*Completed: 2026-02-13*
