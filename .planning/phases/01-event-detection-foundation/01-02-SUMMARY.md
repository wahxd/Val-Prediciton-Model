---
phase: 01-event-detection-foundation
plan: 02
subsystem: events, quality
tags: [pydantic, dataclasses, frozen, replay-detection, timer-parsing, event-schemas]

# Dependency graph
requires:
  - phase: none
    provides: standalone components (no dependencies on other plans)
provides:
  - Frozen Pydantic dataclasses for all 7 VCT event types with full game state snapshots
  - ReplayDetector with timer regression + score validation detection
  - timer_str_to_seconds utility for M:SS/MM:SS timer conversion
  - event_to_dict helper for JSONL serialization
affects:
  - 01-03 (event emitter will create event instances using these schemas)
  - 01-04 (integration will use ReplayDetector in the processing pipeline)
  - phase-02 (JSONL store will use event_to_dict for persistence)

# Tech tracking
tech-stack:
  added: [pydantic.dataclasses]
  patterns: [frozen-dataclass-events, kw-only-inheritance, timer-regression-detection]

key-files:
  created:
    - src/events/__init__.py
    - src/events/schemas.py
    - src/quality/__init__.py
    - src/quality/replay_detector.py
  modified: []

key-decisions:
  - "Used kw_only=True on all pydantic dataclasses to solve Python dataclass inheritance ordering issue (non-default after default)"
  - "Made subclass-specific fields required (no defaults) to enforce explicit construction"

patterns-established:
  - "Frozen pydantic dataclasses with kw_only=True for all event types"
  - "Full game state snapshot in every event (score, alive counts, timer, spike status)"
  - "Dual-condition replay detection: timer regression AND unchanged score"
  - "timer_str_to_seconds as shared utility for timer string parsing"

# Metrics
duration: 3min
completed: 2026-02-13
---

# Phase 01 Plan 02: Event Schemas and Replay Detector Summary

**Frozen Pydantic event dataclasses for 7 VCT event types with full state snapshots, plus ReplayDetector using dual-condition timer regression and score validation**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-13T05:07:49Z
- **Completed:** 2026-02-13T05:11:10Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- All 7 event types (kill, round_end, round_start, spike_plant, spike_defuse, spike_detonate, timeout) as frozen Pydantic dataclasses with full game state snapshots
- ReplayDetector correctly identifies replay footage via timer regression + unchanged score, with suppression until timer passes regression point
- timer_str_to_seconds utility for M:SS/MM:SS conversion with invalid format handling
- event_to_dict helper for serialization to JSONL in Phase 2

## Task Commits

Each task was committed atomically:

1. **Task 1: Create frozen event schema dataclasses for all event types** - `9ef6aa8` (feat)
2. **Task 2: Create ReplayDetector with timer regression and score validation** - `c69c254` (feat)

## Files Created/Modified
- `src/events/__init__.py` - Package init re-exporting all event types
- `src/events/schemas.py` - Frozen Pydantic dataclasses for 7 event types with BaseEvent inheritance
- `src/quality/__init__.py` - Package init re-exporting ReplayDetector and timer utility
- `src/quality/replay_detector.py` - ReplayDetector class and timer_str_to_seconds utility

## Decisions Made
- Used `kw_only=True` on all Pydantic dataclasses to solve Python 3.13 dataclass inheritance ordering issue where non-default fields in subclasses cannot follow default fields from the base class
- Made subclass-specific fields required (no defaults) rather than giving dummy defaults, to enforce explicit and correct event construction at call sites

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed dataclass inheritance ordering with kw_only=True**
- **Found during:** Task 1 (Event schema creation)
- **Issue:** Python 3.13 dataclass raises TypeError when subclass with default `event_type` field is followed by non-default inherited fields like `timestamp`, `frame_number`, etc.
- **Fix:** Added `kw_only=True` to all `@pydantic_dataclass(frozen=True)` decorators, making all fields keyword-only and eliminating the ordering constraint
- **Files modified:** src/events/schemas.py
- **Verification:** All 7 event types create successfully, frozen mutation raises FrozenInstanceError
- **Committed in:** 9ef6aa8

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** kw_only=True is actually better API design -- forces explicit named arguments when creating events, preventing positional argument mistakes. No scope creep.

## Issues Encountered
None beyond the dataclass ordering issue addressed above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Event schemas ready for use by EventEmitter (plan 01-03)
- ReplayDetector ready for integration into processing pipeline (plan 01-04)
- timer_str_to_seconds available as shared utility for StateTracker and other components

---
*Phase: 01-event-detection-foundation*
*Completed: 2026-02-13*
