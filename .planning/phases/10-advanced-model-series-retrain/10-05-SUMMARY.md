---
phase: 10-advanced-model-series-retrain
plan: 05
subsystem: modeling
tags: [cross-tournament-validation, recency-weighting, meta-shift-detection, diagnostic-cv, leave-one-tournament-out]

# Dependency graph
requires:
  - phase: 09-01-temporal-cv
    provides: LeaveOneGroupOut temporal cross-validation pattern
  - phase: 10-03-thesis-validation
    provides: compare_feature_importance_across_groups for meta shift diagnosis
  - phase: 10-CONTEXT
    provides: Cross-tournament validation decisions (mixed temporal default, LOTO diagnostic, recency weights)
provides:
  - Leave-one-tournament-out CV for meta shift detection (diagnostic only, not primary validation)
  - Tournament-level recency weights (1.0, 0.7, 0.5, 0.3 for ≤5 tournaments)
  - Three-variant model comparison (Champions-only, mixed, recency-weighted)
  - Structured investigation report when >10pp accuracy drop detected
affects: [10-04-hyperparameter-tuning, future-retraining-workflows]

# Tech tracking
tech-stack:
  added: [scipy.stats]
  patterns: [Leave-one-tournament-out diagnostic CV, Tournament-level recency weighting, Three-variant training strategy comparison, Cross-tournament investigation reports]

key-files:
  created: [src/modeling/cross_tournament.py, tests/modeling/test_cross_tournament.py]
  modified: []

key-decisions:
  - "Leave-one-tournament-out CV is DIAGNOSTIC only (not primary validation)"
  - "Primary validation uses series_id grouping (LeaveOneGroupOut by series) from Phase 9"
  - "Mixed temporal training is DEFAULT (pool all tournaments by date, walk-forward)"
  - "Recency weights are tournament-level (1.0, 0.7, 0.5, 0.3) for ≤5 tournaments"
  - "Exponential decay for >5 tournaments (future-proof but not yet needed)"
  - "Meta shift detected when accuracy_range > 10pp (per CONTEXT)"
  - "Investigation report has 4 sections: statistical check, feature shift, thesis validation, trading implication"
  - "Single tournament gracefully handled (return empty results, can't do LOTO)"
  - "Three strategies compared: Champions-only (first tournament only), mixed (all equal), recency-weighted (sample_weight)"

patterns-established:
  - "Pattern 1: LOTO CV as diagnostic for meta shift (not as replacement for temporal CV)"
  - "Pattern 2: Tournament-level recency weighting via sample_weight parameter in model.fit()"
  - "Pattern 3: Three-variant comparison on same CV folds for fair evaluation"
  - "Pattern 4: Investigation report structure follows CONTEXT (evidence → diagnosis → thesis → trading)"

# Metrics
duration: 3min 10s
completed: 2026-02-14
---

# Phase 10 Plan 05: Cross-Tournament Validation & Recency Weighting Summary

**Leave-one-tournament-out diagnostic for meta shift detection, tournament-level recency weighting, three-variant model comparison, and structured investigation reports**

## Performance

- **Duration:** 3 min 10 sec
- **Started:** 2026-02-14T23:33:55Z
- **Completed:** 2026-02-14T23:37:07Z
- **Tasks:** 2
- **Files created:** 2

## Accomplishments

- leave_one_tournament_out_cv() diagnostic for meta shift detection (not primary CV)
- compute_recency_weights() assigns tournament-level weights (1.0, 0.7, 0.5, 0.3)
- compare_training_strategies() runs Champions-only, mixed, and recency-weighted on same CV
- generate_cross_tournament_report() produces structured investigation when >10pp drop
- Meta shift detection at accuracy_range > 10pp threshold (per CONTEXT)
- Report sections: statistical check (confidence intervals), feature shift (SHAP), thesis validation, trading implication
- Graceful handling of single tournament edge case (return empty results)
- SHAP importance computed per tournament fold when feature_names provided
- 17 comprehensive tests (5 LOTO + 4 recency weights + 3 strategy comparison + 5 report)
- Total Phase 10 modeling tests: 104 (17 new + 87 from previous plans)

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement cross-tournament validation and recency weighting** - `6e0865d` (feat)
2. **Task 2: Add tests for cross-tournament validation** - `f5a12d1` (test)

## Files Created/Modified

- `src/modeling/cross_tournament.py` - LOTO CV, recency weights, strategy comparison, investigation reports
- `tests/modeling/test_cross_tournament.py` - 17 tests covering all cross-tournament validation functionality

## Decisions Made

**LOTO CV as diagnostic, not primary validation:**
- Mixed temporal training (pool all tournaments by date, walk-forward) is DEFAULT
- Leave-one-tournament-out is DIAGNOSTIC for meta shift detection
- Primary validation remains LeaveOneGroupOut with series_id grouping (Phase 9 pattern)
- This prevents confusion: temporal CV (correct) vs tournament-level CV (diagnostic)

**Tournament-level recency weighting:**
- Fixed weights for ≤5 tournaments: most recent=1.0, one back=0.7, two back=0.5, three+=0.3
- Exponential decay for >5 tournaments (future-proof, implemented but not yet exercised)
- Meta shifts happen at patch/tournament boundaries, not continuously (per CONTEXT)
- Weights applied via sample_weight parameter in model.fit()

**Three-variant comparison strategy:**
- Champions-only: Train only on first tournament in tournament_order
- Mixed: Train on all samples equally weighted (default)
- Recency-weighted: Train on all samples with tournament-level weights
- All three evaluated on same test folds (LeaveOneGroupOut by series)
- Best strategy identified by lowest log_loss

**Investigation report structure:**
1. Statistical reality check: accuracy range, confidence intervals, threshold comparison
2. Feature shift diagnosis: SHAP importance overlap, stable vs unstable features
3. Thesis validation: Does Side×Map > Pistol > Economy hierarchy hold across tournaments?
4. Trading implication: Recommended strategy, retrain frequency, edge trustworthiness

**Meta shift detection threshold:**
- Accuracy drop > 10pp triggers full investigation report
- Below threshold: short report ("No meta shift detected, model generalizes well")
- Statistical check includes 95% confidence intervals on accuracy
- Feature shift uses compare_feature_importance_across_groups from thesis_validation (10-03)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed single tournament edge case**
- **Found during:** Task 2 (test_leave_one_tournament_single_tournament)
- **Issue:** LeaveOneGroupOut raises ValueError when groups < 2
- **Fix:** Check len(unique_tournaments) < 2 at start, return empty results gracefully
- **Files modified:** src/modeling/cross_tournament.py
- **Verification:** Test passes - returns empty per_tournament_results, NaN overall_log_loss
- **Committed in:** f5a12d1 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary fix for edge case handling. LeaveOneGroupOut requires ≥2 groups.

## Issues Encountered

None - implementation straightforward, tests comprehensive.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Phase 10 Plan 05 COMPLETE - Ready for Plan 04 (Hyperparameter Tuning):**
- Cross-tournament validation diagnostic available for meta shift detection
- Tournament-level recency weighting ready for use in training strategies
- Three-variant comparison framework ready for hyperparameter tuning experiments
- Investigation reports integrate with thesis_validation.py from Plan 03

**What Plan 04 (Hyperparameter Tuning) can do:**
- Run Optuna/GridSearchCV with cross-tournament diagnostic embedded
- Compare tuned models across tournaments to detect meta shifts
- Use recency-weighted strategy if mixed strategy shows meta shift
- Generate investigation reports when tuned model fails to generalize

**Integration points:**
- leave_one_tournament_out_cv() takes model_factory (same pattern as temporal_cross_validate)
- compute_recency_weights() produces sample_weight array for model.fit()
- compare_training_strategies() uses LeaveOneGroupOut from evaluation.py
- generate_cross_tournament_report() consumes compare_feature_importance_across_groups from thesis_validation.py

**Key design choices:**
- LOTO CV is diagnostic, NOT primary validation (prevents misuse)
- Primary validation remains series_id grouping (temporal walk-forward)
- Tournament weights are simple fixed values (1.0, 0.7, 0.5, 0.3) for ≤5 tournaments
- Report structure follows CONTEXT decisions (4 sections: check, shift, thesis, trading)

**Considerations:**
- Small dataset (71-117 maps across 2-3 tournaments) means LOTO folds are very small
- Accuracy variance high with small test sets (10-30 samples per tournament)
- Confidence intervals wide - statistical check section includes this caveat
- SHAP computation per fold is optional (feature_names parameter)
- Single tournament data returns empty results (can't do LOTO, need ≥2 tournaments)

---
*Phase: 10-advanced-model-series-retrain*
*Completed: 2026-02-14*
