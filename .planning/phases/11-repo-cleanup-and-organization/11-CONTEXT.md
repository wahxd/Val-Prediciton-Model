# Phase 11: Repo Cleanup & Organization - Context

**Gathered:** 2026-02-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Reorganize codebase and data directories so the project scales cleanly from 71 maps to 150+. Clear module boundaries, remove dead code, establish naming conventions. No new features or capabilities.

</domain>

<decisions>
## Implementation Decisions

### Module structure
- Create new `src/pipeline/` package for VOD processing orchestration (VODOrchestrator, ProcessingManifest, ProcessingConfig) — moved out of `src/scraping/`
- `src/scraping/` retains only VLR.gg web scraping code (VLREventScraper)
- Delete all v1 event detection code: `src/events/`, `src/state/`, `src/quality/` (1,485 LOC, zero active consumers, ReplayDetector canonical in Valoscribe, preserved at git tag v2.0)
- Delete associated v1 test files (test_event_emitter, test_validator, test_state_tracker, test_ocr_config, test_integration, test_replay_detector)
- Delete stray root files: backend.py, dashboard.py, vision_engine.py, config.py, nul, "synthesize research example" folder
- Centralize config into `src/config/` package (consolidate src/data/config.py, src/scraping/config.py, src/modeling/config.py, root config.py)
- Experiment tracking stays in `src/modeling/` (experiment.py + future SQLite tracking). Extract to separate package only if Phase 14 scope demands it

### Data directory layout
- Processed maps stay merged flat in Valoscribe's `data/processed/` — data loader works as-is, provenance lives in metadata/manifest, walk-forward CV stays trivial
- Keep `data/` and `experiments/` as separate top-level directories (different purposes, different lifecycles)
- Delete `data/analysis.db` (stale artifact)
- Reset `data/processing/manifest.json` to empty — Phase 12 rebuilds with complete metadata (existing 46 entries have empty dates, null patch versions, and will create merge problems)

### Experiment handling
- Delete smoke test directories: `experiments/smoke_test/`, `experiments/smoke_test_validation/`
- Move 9 real experiment directories into `experiments/v2_baseline/` (checkpoint_lr, checkpoint_xgb, checkpoint_r6/r12/r18_lr, real_lr_core, real_lr_full, real_xgb_core, real_xgb_full) — structural separation for Phase 14 comparison

### Script organization
- Keep `scripts/run_real_experiment.py` and `scripts/run_checkpoint_prediction.py` (experiment config domain knowledge, reference for Phase 14)
- Delete `scripts/compare_baseline.py` (Phase 6 validation tool, phase shipped)
- Delete `scripts/expand_dataset.py` (superseded by src/pipeline/ in Phase 12/13)
- Delete `scripts/summarize_progress.py` (superseded by Phase 13 progress tracking)
- Delete `scripts/CHECKPOINT_PREDICTION_PLAN.md` (historical planning artifact, script already exists)

### Claude's Discretion
- Exact internal structure of `src/config/` (submodules vs single file)
- How to handle `__pycache__` directories during cleanup
- Whether to update import paths in kept scripts or leave as-is (they'll need Phase 14 updates anyway)
- Test file reorganization to match new module structure

</decisions>

<specifics>
## Specific Ideas

- Post-cleanup `src/` should have exactly 6 packages: `config`, `data`, `features`, `modeling`, `pipeline`, `scraping` — each active and meaningful
- The pipeline/scraping split mirrors Phase 12 (scraping) and Phase 13 (VOD processing) being separate phases
- Experiment runners in scripts/ should be treated as "reference implementations" — worth keeping for domain knowledge even if they need updating later

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 11-repo-cleanup-and-organization*
*Context gathered: 2026-02-14*
