---
phase: 01-event-detection-foundation
plan: 03
subsystem: events
tags: [event-emitter, quality-metrics, structlog, state-diff, timeout-detection]

# Dependency graph
requires:
  - phase: 01-01
    provides: GameState model, StateTracker with 3-frame consensus
  - phase: 01-02
    provides: Event schemas (KillEvent, RoundEndEvent, etc.), timer_str_to_seconds utility
provides:
  - EventEmitter converting state diffs to typed event objects
  - QualityMetrics with structured JSON logging via structlog
  - Timeout detection with team attribution
  - Win condition inference from round event history
affects: [01-04, 02-event-storage, 03-pipeline-integration]

# Tech tracking
tech-stack:
  added: [structlog]
  patterns: [transition-based detection, frozen-timer timeout heuristic, event history inference]

key-files:
  created:
    - src/events/emitter.py
    - src/quality/metrics.py
  modified: []

key-decisions:
  - "Transition-based round start: requires timer jump from <30s to >=80s (not threshold)"
  - "Timeout detection via 5-frame timer freeze mid-round (~0.8s at 6fps)"
  - "Team attribution for timeouts: fewer alive > lower score > default left"
  - "Win condition priority: spike_detonate > spike_defuse > elimination > timeout"
  - "Spike defuse vs detonate distinguished by timer threshold (<5s = detonate)"

patterns-established:
  - "EventEmitter pattern: receive changes dict + current/previous state, return event list"
  - "Base data dict unpacking: _build_base_data() returns kwargs for any event constructor"
  - "QualityMetrics pattern: log_* methods for each tracked metric, get_summary() for analysis"
  - "structlog JSON logging at module level with timestamp and log level processors"

# Metrics
duration: 4min
completed: 2026-02-13
---

# Phase 01 Plan 03: Event Emitter and Quality Metrics Summary

**EventEmitter mapping state diffs to 7 typed events (kill, round_end, round_start, spike_plant/defuse/detonate, timeout) with transition-based round start and frozen-timer timeout detection, plus QualityMetrics with structlog JSON logging and degradation warnings at 10/50/180 consecutive OCR failures**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-02-13T05:18:00Z
- **Completed:** 2026-02-13T05:22:00Z
- **Tasks:** 2
- **Files created:** 2

## Accomplishments
- EventEmitter correctly maps all state change types to typed event objects with full game state snapshots
- Transition-based round start detection prevents false positives on mid-round high timer values
- Tactical timeout detection via frozen timer with team attribution heuristic
- Win condition inference from round event history (spike_detonate > spike_defuse > elimination > timeout)
- QualityMetrics tracks per-field OCR confidence, consecutive failures, replay stats, and event counts
- Structured JSON logging via structlog with ISO timestamps

## Task Commits

Each task was committed atomically:

1. **Task 1: Create EventEmitter with state-to-event mapping, timeout detection, and transition-based round start** - `70e0f8c` (feat)
2. **Task 2: Create QualityMetrics with structured logging and degradation tracking** - `050bf09` (feat)

## Files Created/Modified
- `src/events/emitter.py` - EventEmitter class: state diff to typed event mapping, round start/timeout detection, win condition inference
- `src/quality/metrics.py` - QualityMetrics class: per-field OCR confidence tracking, degradation warnings, structlog JSON logging

## Decisions Made
- Transition-based round start requires timer to jump from <30s to >=80s AND alive counts 5v5 -- prevents false positives from replays and mid-round high timer values
- Timeout detection uses 5-frame frozen timer threshold (~0.8s at 6fps) -- conservative enough to avoid false positives from OCR reading same value twice
- Team attribution for timeouts uses alive count heuristic (fewer alive = more likely to call timeout), then score tiebreak, then default left
- Win condition inference priority: spike_detonate > spike_defuse > elimination > timeout -- checked via isinstance against round event history
- Spike defuse vs detonate distinguished by timer: <5 seconds remaining = detonation, otherwise defuse

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed missing structlog dependency**
- **Found during:** Task 2 (QualityMetrics)
- **Issue:** structlog package not installed in environment
- **Fix:** Ran `pip install structlog` (installed v25.5.0)
- **Files modified:** None (pip install only)
- **Verification:** Import succeeds, structured logging works
- **Committed in:** Part of task execution (not committed to repo -- runtime dependency)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minimal -- structlog was a planned dependency, just needed installation.

## Issues Encountered
None -- plan executed as written.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- EventEmitter and QualityMetrics complete the event detection pipeline logic
- Ready for 01-04 (unit tests) to validate all Phase 1 components
- structlog dependency should be added to requirements.txt when project dependencies are formalized

---
*Phase: 01-event-detection-foundation*
*Completed: 2026-02-13*
