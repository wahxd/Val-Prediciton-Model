---
phase: 09-baseline-model-evaluation
plan: 01
subsystem: modeling
tags: [pydantic, sklearn, matplotlib, cross-validation, calibration, evaluation]

# Dependency graph
requires:
  - phase: 08-feature-engineering
    provides: FeatureRegistry and FeaturePipeline for feature set management
provides:
  - ModelConfig and ExperimentConfig schemas for type-safe experiment configuration
  - temporal_cross_validate for series-grouped leave-one-out CV
  - compute_metrics for log_loss, brier_score, accuracy calculation
  - generate_evaluation_report for JSON metrics and matplotlib calibration plots
affects: [09-02-baseline-training, 09-03-model-evaluation, 10-advanced-modeling]

# Tech tracking
tech-stack:
  added: [matplotlib]
  patterns: [Pydantic v2 frozen configs, LeaveOneGroupOut temporal CV, CalibratedClassifierCV for Platt scaling, Agg backend for headless plotting]

key-files:
  created: [src/modeling/__init__.py, src/modeling/config.py, src/modeling/evaluation.py, tests/modeling/test_config.py, tests/modeling/test_evaluation.py]
  modified: []

key-decisions:
  - "Use LeaveOneGroupOut with series_id grouping to prevent series leakage in cross-validation"
  - "Wrap models in CalibratedClassifierCV to ensure well-calibrated probabilities for betting applications"
  - "Use matplotlib Agg backend for headless/test environments to avoid Tk dependency"
  - "Skip folds with single-class training data rather than fail (graceful degradation)"
  - "Auto-reduce calibration_cv when it exceeds min class count to avoid CV errors"

patterns-established:
  - "Pattern 1: Frozen Pydantic configs for immutable experiment configuration"
  - "Pattern 2: Model factory pattern (callable returning fresh estimator) to avoid reusing fitted models"
  - "Pattern 3: Temporal CV with explicit series grouping to enforce no-leakage guarantee"
  - "Pattern 4: Experiment reports with JSON metrics + PNG plots for both programmatic and human consumption"

# Metrics
duration: 4min
completed: 2026-02-14
---

# Phase 9 Plan 01: Evaluation Framework & Configuration Schemas Summary

**Pydantic config schemas with frozen validation, LeaveOneGroupOut temporal CV with series grouping, and matplotlib-based evaluation reports (JSON metrics + calibration plots)**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-14T19:04:55Z
- **Completed:** 2026-02-14T19:09:24Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Type-safe ModelConfig and ExperimentConfig with Pydantic v2 validation and immutability
- Temporal cross-validation with LeaveOneGroupOut preventing series leakage
- CalibratedClassifierCV integration for Platt scaling (sigmoid) and isotonic calibration
- Evaluation report generation with JSON metrics and matplotlib plots (calibration curve, prediction distribution)
- 27 tests covering validation, edge cases, and report generation

## Task Commits

Each task was committed atomically:

1. **Task 1: Configuration schemas and modeling module init** - `e8bc41a` (feat)
2. **Task 2: Evaluation framework with temporal CV and report generation** - `31a5c24` (feat)

## Files Created/Modified
- `src/modeling/__init__.py` - Module initialization
- `src/modeling/config.py` - ModelConfig and ExperimentConfig Pydantic schemas
- `src/modeling/evaluation.py` - compute_metrics, temporal_cross_validate, generate_evaluation_report
- `tests/modeling/test_config.py` - 14 tests for config validation and immutability
- `tests/modeling/test_evaluation.py` - 13 tests for metrics, CV, and report generation

## Decisions Made

**Configuration design:**
- Used Pydantic v2 frozen configs for immutability (prevents accidental mutation during experiments)
- Validated model_type, solver, calibration_method via field validators
- Added to_json() method for JSON serialization (handles Path objects)

**Temporal cross-validation:**
- LeaveOneGroupOut with series_id grouping ensures no maps from same BO3/BO5 in both train and test
- Model factory pattern (callable) prevents reusing fitted models across folds
- Gracefully handles edge cases: single-class folds skipped, calibration_cv auto-reduced when needed

**Calibration:**
- Wrap all models in CalibratedClassifierCV for Platt scaling (ensures predicted probabilities match observed frequencies)
- Default to sigmoid method (Platt scaling), support isotonic for Phase 10 experiments
- Use ensemble=True to average predictions from internal CV folds

**Plotting:**
- Use matplotlib Agg backend to avoid Tk dependency in headless/test environments
- Generate calibration curve (reliability diagram) with 10 bins
- Generate prediction distribution histogram with 0.5 threshold line
- Save at 150 DPI with plt.close() to avoid memory leaks

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed matplotlib dependency**
- **Found during:** Task 2 (evaluation.py import)
- **Issue:** matplotlib not installed, ImportError when importing pyplot
- **Fix:** Ran `python -m pip install matplotlib`
- **Files modified:** (user site-packages)
- **Verification:** Import succeeds, tests pass
- **Committed in:** Part of Task 2 testing

**2. [Rule 3 - Blocking] Fixed matplotlib Tk backend error in tests**
- **Found during:** Task 2 (test_evaluation.py)
- **Issue:** matplotlib defaulted to Tk backend, failed in headless test environment with TclError
- **Fix:** Added `matplotlib.use('Agg')` before importing pyplot in evaluation.py
- **Files modified:** src/modeling/evaluation.py
- **Verification:** All 13 tests pass without Tk errors
- **Committed in:** 31a5c24 (Task 2 commit)

**3. [Rule 3 - Blocking] Fixed platform-specific path test assertion**
- **Found during:** Task 1 (test_config.py)
- **Issue:** Test asserted output_dir == "custom/path" but Windows Path uses backslashes
- **Fix:** Changed assertion to platform-agnostic checks (isinstance(str), contains "custom" and "path")
- **Files modified:** tests/modeling/test_config.py
- **Verification:** Test passes on Windows
- **Committed in:** e8bc41a (Task 1 commit)

---

**Total deviations:** 3 auto-fixed (3 blocking)
**Impact on plan:** All auto-fixes necessary to unblock tests and imports. No scope creep.

## Issues Encountered

**matplotlib dependency missing:**
- Expected matplotlib to be in requirements.txt from research phase
- Installed via pip during execution (transitive dependencies already present)
- Should add to requirements.txt in Phase 10 for clean environment setup

**Windows path separators in tests:**
- Test assumed Unix-style path separators
- Fixed with platform-agnostic string checks
- Lesson: Use Path objects in code, string containment checks in tests

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for Phase 9 Plan 02 (Baseline Training):**
- Configuration schemas validate experiment parameters
- Temporal CV framework prevents series leakage
- Calibration wrapper ensures well-calibrated probabilities
- Evaluation report infrastructure ready to document baseline results

**Ready for Phase 9 Plan 03 (Model Evaluation):**
- compute_metrics provides log_loss, brier_score, accuracy
- Calibration curve plotting validates probability calibration
- JSON metrics enable programmatic comparison across experiments

**Considerations:**
- Small dataset (71 maps) means regularization and calibration are critical (RESEARCH.md guidance)
- Temporal validation depends on series_id metadata from Phase 8 pipeline
- Log loss is primary metric (calibration > accuracy for betting applications)

---
*Phase: 09-baseline-model-evaluation*
*Completed: 2026-02-14*
