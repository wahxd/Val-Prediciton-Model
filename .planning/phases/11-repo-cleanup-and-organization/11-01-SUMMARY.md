---
phase: 11-repo-cleanup-and-organization
plan: 01
subsystem: project-infrastructure
tags: [cleanup, dead-code-removal, organization, v2-archive]
requires: [v2.0-tag]
provides: [clean-codebase, organized-experiments, reset-manifest]
affects: [12-data-sourcing, 13-vod-processing]
tech-stack:
  added: []
  patterns: [milestone-based-experiment-organization]
key-files:
  created:
    - experiments/v2_baseline/
    - data/processing/manifest.v2_backup.json
  modified:
    - src/__init__.py
    - data/processing/manifest.json
  deleted:
    - backend.py
    - dashboard.py
    - vision_engine.py
    - config.py
    - nul
    - synthesize research example/
    - src/events/
    - src/state/
    - src/quality/
    - tests/test_event_emitter.py
    - tests/test_integration.py
    - tests/test_ocr_config.py
    - tests/test_replay_detector.py
    - tests/test_state_tracker.py
    - tests/test_validator.py
    - scripts/compare_baseline.py
    - scripts/expand_dataset.py
    - scripts/summarize_progress.py
    - scripts/CHECKPOINT_PREDICTION_PLAN.md
    - data/analysis.db
decisions:
  - id: CLEAN-ORG-01
    what: Milestone-based experiment organization
    why: experiments/v2_baseline/ subdirectory provides clear separation between v2 and future v3 experiments
    impact: Future experiments won't conflict with archived baseline results
  - id: CLEAN-ORG-02
    what: Reset manifest for Phase 12 rebuild
    why: Existing 46-entry manifest has incomplete metadata (missing dates, patch versions); simpler to rebuild from scratch than repair
    impact: Phase 12 will repopulate manifest with complete metadata during VOD discovery
metrics:
  duration: 3 minutes
  loc-removed: 4661
  loc-added: 1
  tests-passing: 315
  commits: 3
completed: 2026-02-14
---

# Phase 11 Plan 01: Dead Code Removal and Repository Organization Summary

**One-liner:** Removed 1,485 LOC of v1 dead code, organized experiments into v2_baseline/, reset processing manifest for Phase 12 rebuild

## What Was Delivered

### Dead Code Removal (Task 1)
- **Deleted 1,485 LOC of v1 event detection modules** (src/events/, src/state/, src/quality/) preserved at v2.0 tag
- **Deleted 6 v1 test files** (test_event_emitter, test_integration, test_ocr_config, test_replay_detector, test_state_tracker, test_validator)
- **Removed stray root files** (backend.py, dashboard.py, vision_engine.py, config.py, nul)
- **Removed 'synthesize research example' folder** (leftover from early research)
- **Deleted superseded scripts** (compare_baseline.py, expand_dataset.py, summarize_progress.py, CHECKPOINT_PREDICTION_PLAN.md)
- **Kept reference implementations** (run_real_experiment.py, run_checkpoint_prediction.py for Phase 14 comparison)
- **Updated src/__init__.py docstring** from "event detection and state management" to "match prediction model"

### Experiment Organization (Task 2)
- **Created experiments/v2_baseline/ subdirectory** with 9 experiment results:
  - checkpoint_lr, checkpoint_xgb
  - checkpoint_r6_lr, checkpoint_r12_lr, checkpoint_r18_lr
  - real_lr_core, real_lr_full
  - real_xgb_core, real_xgb_full
- **Deleted smoke test directories** (incomplete preliminary experiments)
- **Removed stale data/analysis.db** (replaced by experiment-specific metrics.json files)
- **Backed up processing manifest** to manifest.v2_backup.json (46 entries, incomplete metadata)
- **Reset manifest.json to empty** for Phase 12 rebuild with complete metadata

### Additional Cleanup (Task 2 follow-up)
- **Removed gitignored artifacts** (__pycache__/config.cpython-313.pyc, smoke_test outputs)

## Verification Results

All success criteria met:

- ✅ **CLEAN-01:** Root and scripts/ contain only active files
- ✅ **CLEAN-02:** Corrupted/unused files removed (analysis.db, stray root files)
- ✅ **CLEAN-04:** data/ directory cleaned (manifest reset, backup preserved)
- ✅ **CLEAN-05:** Experiment files organized (v2_baseline/ with 9 experiments)
- ✅ **Test collection:** 315 tests pass with no import errors from deleted modules

## Implementation Highlights

### Clean Separation of v1 and v2 Code
- v1 event detection code (1,485 LOC) preserved at v2.0 tag for future live stream retrofit
- No active code depends on deleted modules (verified via successful test collection)
- src/ directory now contains only v3-relevant packages: data/, features/, modeling/, scraping/

### Milestone-Based Experiment Organization
- experiments/v2_baseline/ provides clear temporal separation
- Future v3 experiments will live alongside v2_baseline/ (not mixed with it)
- Each experiment directory contains complete artifacts (model.json, metrics.json, visualizations)

### Manifest Reset Rationale
- Existing 46-entry manifest has incomplete metadata:
  - Missing dates (all entries show empty string)
  - Missing patch_version (all null)
  - All status="pending" (no processing records)
- Simpler to rebuild from scratch in Phase 12 than repair incomplete data
- Backup preserved at manifest.v2_backup.json for reference

## Deviations from Plan

None - plan executed exactly as written. All deletions, moves, and resets completed successfully.

## Decisions Made

**CLEAN-ORG-01: Milestone-based experiment organization**
- Created experiments/v2_baseline/ subdirectory
- Future v3 experiments will live at experiments/{experiment_name}/
- Impact: Clear separation prevents accidental v2/v3 experiment conflicts

**CLEAN-ORG-02: Reset manifest for Phase 12 rebuild**
- Existing 46 entries have incomplete metadata (no dates, no patch versions)
- Backup preserved at manifest.v2_backup.json
- Phase 12 will repopulate with complete metadata during VOD discovery
- Impact: Cleaner data quality, consistent metadata across all processed maps

## Key Files

**Created:**
- experiments/v2_baseline/ (9 experiment subdirectories)
- data/processing/manifest.v2_backup.json (46 entries)

**Modified:**
- src/__init__.py (updated docstring for v3)
- data/processing/manifest.json (reset to empty {"records": []})

**Deleted:**
- 27 files total (v1 modules, tests, stray files, superseded scripts)
- Key: src/events/, src/state/, src/quality/ (1,485 LOC)
- Stray: backend.py, dashboard.py, vision_engine.py, config.py, nul
- Scripts: compare_baseline.py, expand_dataset.py, summarize_progress.py

## Metrics

- **Duration:** 3 minutes
- **LOC removed:** 4,661 (including comments/whitespace)
- **LOC added:** 1 (updated docstring)
- **Commits:** 3
- **Tests passing:** 315 (no regressions)
- **Files modified:** 27 deleted, 57 moved, 2 modified, 2 created

## Next Phase Readiness

### Blockers
None. Phase 12 can proceed immediately.

### Concerns
None. Clean codebase with clear directory structure.

### Recommendations

1. **Phase 12:** When rebuilding manifest, ensure complete metadata (dates, patch_version, tournament) for all entries
2. **Phase 13:** Continue using manifest.json as single source of truth for processing status
3. **Phase 14:** Reference experiments/v2_baseline/ for comparison with v3 scaled results

## Quality Assessment

**Impact:** High - Removed 4,661 LOC of dead code and organized codebase for v3 scaling

**Risk:** None - All changes committed atomically, v1 code preserved at v2.0 tag

**Test Coverage:** 315 tests passing, no regressions from deletions

**Documentation:** Complete - all deletions and moves documented in commit messages

---

*Repository cleaned and organized for v3 scaling. Phase 12 ready to proceed.*
