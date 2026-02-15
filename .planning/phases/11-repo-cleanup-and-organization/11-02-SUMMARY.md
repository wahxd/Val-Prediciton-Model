---
phase: 11-repo-cleanup-and-organization
plan: 02
subsystem: architecture
tags: [python, module-structure, imports, refactoring]

# Dependency graph
requires:
  - phase: 11-01
    provides: Dead code removed, clean slate for reorganization
provides:
  - 6-package module structure (config, data, features, modeling, pipeline, scraping)
  - Centralized configuration in src/config/
  - Separated VLR.gg scraping from VOD processing pipeline
  - Test structure mirrors source structure
affects: [12-data-sourcing-vlr-scraping, 13-vod-processing-pipeline, 14-scaled-experiments]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Centralized configuration pattern (src/config/)
    - Lazy imports to break circular dependencies

key-files:
  created:
    - src/config/__init__.py
    - src/config/data.py
    - src/config/modeling.py
    - src/config/processing.py
    - src/pipeline/__init__.py
    - src/pipeline/manifest.py
    - src/pipeline/orchestrator.py
    - tests/config/__init__.py
    - tests/pipeline/__init__.py
  modified:
    - src/data/cli.py
    - src/modeling/baseline.py
    - src/modeling/calibration.py
    - src/modeling/experiment.py
    - src/modeling/tuning.py
    - src/scraping/__init__.py
    - src/scraping/vlr_events.py
    - tests/data/test_schemas.py
    - tests/modeling/test_*.py (7 files)
    - tests/test_scraping/test_vlr_events.py

key-decisions:
  - "Broke circular import (scraping ↔ pipeline) with lazy import in orchestrator.py"
  - "Left scripts/ imports unchanged (Phase 14 will update reference implementations)"

patterns-established:
  - "Config centralization: all *Config classes live in src/config/"
  - "Package separation: scraping (web) vs pipeline (VOD processing)"
  - "Test directory mirrors src/ structure (tests/config/, tests/pipeline/)"

# Metrics
duration: 12min
completed: 2026-02-14
---

# Phase 11 Plan 02: Module Structure Reorganization Summary

**6-package architecture established: centralized config, separated scraping/pipeline, test structure mirrors source**

## Performance

- **Duration:** 12 min
- **Started:** 2026-02-14T22:22:00Z
- **Completed:** 2026-02-14T22:34:00Z
- **Tasks:** 2 (committed together as single refactor)
- **Files modified:** 25 (12 source, 7 tests, 4 new __init__.py files, 2 moved test directories)

## Accomplishments

- **CLEAN-03 complete:** src/ has 6 packages with clear separation of concerns
- **Centralized configuration:** All *Config classes consolidated in src/config/
- **Phase 12/13 separation:** VLR.gg scraping isolated from VOD processing pipeline
- **Test alignment:** Test directory structure mirrors src/ (tests/config/, tests/pipeline/)
- **All imports resolved:** 315 tests collected with no import errors

## Task Commits

Both tasks committed together (per plan specification for reorganization):

1. **Tasks 1+2: Module reorganization** - `913fa83` (refactor)
   - Created src/pipeline/ and src/config/ packages
   - Moved 6 files (manifest.py, orchestrator.py, 3 config files)
   - Updated 19 import statements across source and tests
   - Created 4 test directories (config/, pipeline/)

## Files Created/Modified

**Created:**
- `src/config/__init__.py` - Centralized config exports (DataPipelineConfig, ModelConfig, ExperimentConfig, ProcessingConfig)
- `src/config/data.py` - Data pipeline configuration (moved from src/data/)
- `src/config/modeling.py` - Model and experiment configuration (moved from src/modeling/)
- `src/config/processing.py` - VOD processing configuration (moved from src/scraping/)
- `src/pipeline/__init__.py` - Pipeline package exports (ProcessingManifest, VODRecord, VODOrchestrator)
- `src/pipeline/manifest.py` - Processing manifest management (moved from src/scraping/)
- `src/pipeline/orchestrator.py` - VOD processing orchestration (moved from src/scraping/)
- `tests/config/__init__.py` - Config test package
- `tests/pipeline/__init__.py` - Pipeline test package

**Modified:**
- `src/data/cli.py` - Import from src.config.data
- `src/modeling/baseline.py` - Import from src.config.modeling
- `src/modeling/calibration.py` - Import from src.config.modeling
- `src/modeling/experiment.py` - Import from src.config.modeling
- `src/modeling/tuning.py` - Import from src.config.modeling
- `src/scraping/__init__.py` - Export only VLREventScraper (removed ProcessingConfig, ProcessingManifest, VODOrchestrator)
- `src/scraping/vlr_events.py` - Import from src.pipeline.manifest
- All test files (12 total) - Updated to import from src.config.*

## Decisions Made

**1. Circular import resolution via lazy import**
- **Issue:** src.scraping.vlr_events → src.pipeline.manifest → src.pipeline.orchestrator → src.scraping.vlr_events
- **Decision:** Move `from src.scraping.vlr_events import VLREventScraper` inside `VODOrchestrator.scrape_and_populate()` method
- **Rationale:** VLREventScraper only used in one method; lazy import breaks cycle without architectural changes
- **Impact:** Imports resolve cleanly, no circular dependency errors

**2. Leave scripts/ imports unchanged**
- **Context:** Plan notes scripts will need Phase 14 updates anyway (real-data experiment reference implementations)
- **Decision:** Did not update scripts/run_real_experiment.py or scripts/run_checkpoint_prediction.py
- **Rationale:** Avoid double-work; Phase 14 will refactor scripts as part of experiment framework updates
- **Impact:** Scripts may have stale imports but are not part of test suite

**3. Use `git add -A` for commit (exception to project convention)**
- **Context:** Plan explicitly allows `git add -A` for this reorganization commit due to many file moves
- **Decision:** Used `git add -A` instead of individual `git add` commands
- **Rationale:** 25 files changed (6 moved with git mv, 19 modified imports, 4 new __init__.py) - individually staging error-prone
- **Verification:** `git status` check after staging confirmed only intended files

## Deviations from Plan

**None - plan executed exactly as written**

The plan anticipated the circular import issue and specified the lazy import solution. All import updates were specified in the plan.

## Issues Encountered

**1. Circular import during initial import testing**
- **Problem:** `from src.scraping import VLREventScraper` failed with "cannot import name 'VLREventScraper' from partially initialized module"
- **Root cause:** src.scraping → src.pipeline → src.scraping cycle
- **Resolution:** Moved VLREventScraper import inside VODOrchestrator.scrape_and_populate() method (as planned)
- **Verification:** All package imports tested successfully after fix

## User Setup Required

None - no external service configuration required. This is a pure code reorganization.

## Next Phase Readiness

**Phase 12 (Data Sourcing / VLR.gg Scraping) ready:**
- ✅ src/scraping/ contains only VLREventScraper (VLR.gg web scraping)
- ✅ Clean separation from VOD processing (now in src/pipeline/)
- ✅ All imports resolve correctly
- ✅ 315 tests collected

**Phase 13 (VOD Processing Pipeline) ready:**
- ✅ src/pipeline/ owns VODOrchestrator + ProcessingManifest
- ✅ ProcessingConfig centralized in src/config/
- ✅ Pipeline package exports established

**Phase 14 (Scaled Experiments) ready:**
- ✅ Centralized config in src/config/ (ModelConfig, ExperimentConfig)
- ✅ Test structure supports new experiment test suites
- ⚠️ Scripts will need import updates (expected, part of Phase 14 scope)

**No blockers.** Module structure provides foundation for all v3 phases.

---
*Phase: 11-repo-cleanup-and-organization*
*Completed: 2026-02-14*
