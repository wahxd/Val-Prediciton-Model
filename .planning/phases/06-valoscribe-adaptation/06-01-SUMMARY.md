---
phase: 06-valoscribe-adaptation
plan: 01
subsystem: quality
tags: [replay-detection, valoscribe, broadcast-analysis, data-quality]

# Dependency graph
requires:
  - phase: 01-event-detection-foundation
    provides: ReplayDetector logic validated against Champions 2025 data
provides:
  - ReplayDetector class in Valoscribe at src/valoscribe/quality/replay_detector.py
  - Replay detection integrated into GameStateManager.process_frame()
  - 12 unit tests covering all replay detection scenarios
  - Updated CLAUDE.md reflecting active Valoscribe development
affects: [07-vod-processing, 08-feature-engineering, quality-validation]

# Tech tracking
tech-stack:
  added: [valoscribe.quality.replay_detector]
  patterns:
    - Replay detection via timer regression + unchanged score (dual condition)
    - Suppression state machine (enter on regression, exit on progression or score change)
    - Integration point: between phase detection and event generation in GameStateManager

key-files:
  created:
    - D:\Git\valoscribe\src\valoscribe\quality\__init__.py
    - D:\Git\valoscribe\src\valoscribe\quality\replay_detector.py
    - D:\Git\valoscribe\tests\test_orchestration\test_replay_detector.py
  modified:
    - D:\Git\valoscribe\src\valoscribe\orchestration\game_state_manager.py
    - D:\git\Val-Prediciton-Model\CLAUDE.md

key-decisions:
  - "Ported ReplayDetector to Valoscribe as single source of truth (eliminates duplication)"
  - "Integrated replay check between phase detection and event generation (minimal invasiveness)"
  - "Updated CLAUDE.md to reflect active Valoscribe development (Phase 6 strategy shift)"

patterns-established:
  - "Valoscribe quality package: home for data quality tools (replay detection, future validation)"
  - "Replay check in process_frame(): detections still run (state tracking), events suppressed during replays"
  - "Metrics logging at video completion: transparency for replay impact assessment"

# Metrics
duration: 5min
completed: 2026-02-13
---

# Phase 6 Plan 1: Replay Detection Integration Summary

**ReplayDetector ported to Valoscribe with 12 passing tests, integrated into GameStateManager to suppress false events from broadcast replays**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-13T21:58:34Z
- **Completed:** 2026-02-13T22:03:09Z
- **Tasks:** 2
- **Files modified:** 5 (3 in Valoscribe, 1 in prediction model, 1 test file)

## Accomplishments

- ReplayDetector ported from prediction model repo to Valoscribe with identical logic
- Integrated replay check into GameStateManager.process_frame() between detection and event emission
- 12 unit tests passing (normal play, timer regression, score changes, suppression, metrics)
- CLAUDE.md updated: Valoscribe is now "actively developed alongside this repo" (no longer read-only)

## Task Commits

### Valoscribe repo (D:\Git\valoscribe):

1. **Task 1: Port ReplayDetector and integrate into GameStateManager** - `f87c476` (feat)
2. **Task 2 (Part A): Add ReplayDetector tests** - `4c33e23` (test)

### Prediction model repo (D:\git\Val-Prediciton-Model):

3. **Task 2 (Part B): Update CLAUDE.md** - `b6a5137` (docs)

## Files Created/Modified

### Valoscribe (D:\Git\valoscribe)
- `src/valoscribe/quality/__init__.py` - Quality validation tools package
- `src/valoscribe/quality/replay_detector.py` - ReplayDetector class with timer_str_to_seconds utility
- `src/valoscribe/orchestration/game_state_manager.py` - Added replay check in process_frame(), replay metrics logging
- `tests/test_orchestration/test_replay_detector.py` - 12 unit tests for replay detection logic

### Prediction model (D:\git\Val-Prediciton-Model)
- `CLAUDE.md` - Updated to reflect active Valoscribe development, removed READ-ONLY constraint

## Decisions Made

**1. Single source of truth: ReplayDetector lives in Valoscribe**
- **Rationale:** Eliminates duplication between repos. Valoscribe processes VODs, replay detection must happen there first. Prediction model consumes clean output.
- **Impact:** Phase 1 ReplayDetector becomes historical reference. Valoscribe version is canonical going forward.

**2. Integration point: Between phase detection and event generation**
- **Rationale:** Minimal invasiveness. Detections still run (maintains state tracking), but events are suppressed during replay segments.
- **Impact:** Replay frames still contribute to frame state CSV (continuity), but no duplicate events in events.jsonl.

**3. CLAUDE.md update: Valoscribe is actively developed**
- **Rationale:** Phase 6 strategy requires modifying Valoscribe. "DO NOT modify" constraint was blocking progress.
- **Impact:** Developers can now contribute to Valoscribe alongside prediction model. ReplayDetector is first Phase 6 contribution.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. ReplayDetector ported cleanly with identical logic, tests passed on first run, integration worked as designed.

## Next Phase Readiness

### Ready for Phase 6 Plans 2-5:
- **Plan 2 (Economy tracking):** Can use same integration pattern (GameStateManager.process_frame)
- **Plan 3 (Weapon detection):** Can use same integration pattern
- **Plan 4 (Ability tracking):** Can use same integration pattern
- **Plan 5 (Combat metadata):** Can use same integration pattern

### Blockers/Concerns:
- Valoscribe git repo was newly initialized (was not a repo before). Feature branch created, but need to decide on merge/PR workflow.
- ReplayDetector metrics will be validated during Phase 7 VOD processing (impact on 71-map dataset TBD).
- Integration assumes phase_detections contains timer and score - validated via manual inspection, not yet tested on real VOD.

---
*Phase: 06-valoscribe-adaptation*
*Completed: 2026-02-13*
