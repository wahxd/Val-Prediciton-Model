---
phase: 10-advanced-model-series-retrain
plan: 02
subsystem: modeling
tags: [series-prediction, bo3, bo5, probability, momentum, calibration, scipy]

# Dependency graph
requires:
  - phase: 09-baseline-model-evaluation
    provides: Map-level win probability predictions from baseline model
provides:
  - BO3/BO5 series win probability computation from per-map predictions
  - Conditional probability tracking at each score state (0-0, 1-0, etc.)
  - Momentum adjustment based on series score differential
  - Series-level calibration validation with small-sample caveats
affects: [10-05-cross-tournament-validation, future-series-betting]

# Tech tracking
tech-stack:
  added: []  # No new dependencies (uses stdlib)
  patterns:
    - "Recursive conditional probability calculation for series outcomes"
    - "Momentum adjustment via score differential modifier (default 0.03)"
    - "Probability clamping to [0.05, 0.95] at map level to avoid degenerate series predictions"
    - "Series calibration with relaxed threshold (60%) due to small sample size"

key-files:
  created:
    - src/modeling/series.py
    - tests/modeling/test_series.py
  modified: []

key-decisions:
  - "Momentum is simple score modifier (not feature-based from completed maps)"
  - "Map veto/pick data not available - series prediction uses average per-map probability"
  - "Series calibration uses 5 bins (vs 10 for maps) due to small sample size (~20-30 series)"
  - "Series calibration threshold relaxed to 60% (vs 70% for maps) with explicit small-sample caveat"
  - "Default momentum = 0.03 (3% adjustment per map lead)"

patterns-established:
  - "series_win_probability(p_map, format, score, momentum) → recursive calculation"
  - "compute_series_probabilities() returns overall + conditional probabilities"
  - "validate_series_calibration() with explicit caveat text about small samples"

# Metrics
duration: 4min
completed: 2026-02-14
---

# Phase 10 Plan 02: BO3/BO5 Series Prediction Summary

**Recursive conditional probability for BO3/BO5 series win prediction with momentum adjustment based on score state**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-14T23:24:34Z
- **Completed:** 2026-02-14T23:28:02Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Series win probability computation for BO3 (2 wins needed) and BO5 (3 wins needed) formats
- Momentum adjustment increases winning team's probability by 3% per map lead (configurable)
- Conditional probabilities computed at all score states (0-0, 1-0, 1-1, etc.)
- Series-level calibration validation with small-sample caveats (~20-30 series)
- 31 comprehensive tests covering symmetry, amplification, momentum, edge cases, and calibration

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement BO3/BO5 series probability with momentum adjustment** - `9db15ec` (feat)
2. **Task 2: Add comprehensive tests for series prediction** - `b09b3ea` (test)

## Files Created/Modified
- `src/modeling/series.py` - Series win probability functions (BO3/BO5), conditional probability computation, series calibration validation
- `tests/modeling/test_series.py` - 31 tests covering BO3/BO5 basic behavior, momentum adjustment, edge cases, calibration

## Decisions Made

1. **Momentum is simple score modifier**: Adjustment based on series score differential (0-1 vs 1-0), NOT feature-based analysis of completed maps. Keeps computation simple and avoids overfitting to small series samples.

2. **Map veto/pick data not available**: Per CONTEXT.md decisions, map veto/pick data is not available. Series prediction uses average of per-map win probabilities rather than map-specific adjustments.

3. **Default momentum = 0.03**: Within Claude's discretion range (0.02-0.05 from CONTEXT), chosen 0.03 (3% per map lead) as reasonable middle ground. Series calibration will validate this choice.

4. **Series calibration uses 5 bins with relaxed threshold**: Small sample size (~20-30 series) means fewer bins (5 vs 10 for maps) and relaxed pass threshold (60% vs 70%). Explicit caveat text warns about directional-only calibration.

5. **Probabilities clamped to [0.05, 0.95] at map level**: Prevents degenerate series predictions where single map at 0.0 or 1.0 makes entire series deterministic. Clamping happens at individual map probability, not final series probability.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

**Test type handling (numpy.bool_ vs Python bool)**
- **Issue:** validate_series_calibration returns numpy.bool_ which failed isinstance(result['passes'], bool) check
- **Resolution:** Updated test to accept both Python bool and numpy.bool_ types
- **Impact:** Test now handles numpy scalar types correctly (common pattern when using numpy arrays)

## Next Phase Readiness

Series prediction module ready for integration:
- **Next step (Plan 10-03):** Thesis validation framework to check if feature importance aligns with game mechanics hierarchy
- **Future integration:** Series predictions can be computed from map-level model outputs for BO3/BO5 match betting
- **Validation needed:** Series calibration on real VCT data will validate momentum adjustment magnitude (currently 0.03)

**No blockers.** Module is standalone and tested.

---
*Phase: 10-advanced-model-series-retrain*
*Completed: 2026-02-14*
