---
phase: 13
plan: 01
subsystem: pipeline
tags: [quality-validation, batch-processing, manifest, config]
requires: [12-04]
provides: [quality-metrics-storage, granular-failure-tracking, batch-config]
affects: [13-02, 13-03]
tech-stack:
  added: []
  patterns: [quality-validator-wrapper, atomic-json-storage]
key-files:
  created:
    - src/pipeline/quality_validator.py
    - tests/pipeline/test_manifest_extensions.py
    - tests/pipeline/test_quality_validator.py
  modified:
    - src/pipeline/manifest.py
    - src/config/processing.py
    - src/pipeline/__init__.py
decisions:
  - id: PROC-04-quality-storage
    choice: Store quality_metrics as dict in VODRecord
    rationale: "JSON-serializable dict format allows flexible quality metric storage without schema migration; all QualityScore fields converted to dict on storage"
  - id: PROC-05-granular-failures
    choice: Add download_failed and processing_failed status types
    rationale: "Distinguishes download failures (private/deleted/region-locked VODs) from processing failures (OCR errors, crashes); enables targeted retry logic"
  - id: PROC-01-batch-sizing
    choice: Default batch_size=20, circuit_breaker_threshold=5
    rationale: "20 VODs per batch = ~15hr processing time (45min/VOD); circuit breaker after 5 consecutive failures prevents runaway retry loops"
metrics:
  tests: 15
  files_changed: 6
  loc_added: 658
  duration: 245s
  completed: 2026-02-15
---

# Phase 13 Plan 01: Manifest & Config Extensions Summary

**One-liner:** Extended manifest with quality_metrics storage and granular failure statuses, added batch processing config fields, created QualityValidator wrapper for pipeline integration

## What Was Built

### Core Deliverables

1. **VODRecord.quality_metrics field** (manifest.py)
   - Optional dict field stores complete quality validation results
   - JSON-serializable format with overall_score, tier, checks, flagged_for_review
   - Backward compatible: old records without quality_metrics load with field=None

2. **Granular failure statuses** (manifest.py)
   - Extended StatusType literal with download_failed and processing_failed
   - download_failed: private/deleted/region-locked YouTube VODs
   - processing_failed: OCR errors, Valoscribe crashes, corrupt output
   - Existing "failed" status retained for backward compatibility

3. **Batch processing config fields** (processing.py)
   - batch_size: Number of VODs per batch run (default 20)
   - circuit_breaker_threshold: Stop after N consecutive failures (default 5)
   - download_timeout_seconds: Timeout per download (default 1800 = 30min)
   - min_disk_space_gb: Minimum free space before starting batch (default 10.0)

4. **QualityValidator** (quality_validator.py)
   - validate_map_output(output_dir, map_id) -> dict
   - QualityValidator class with validate(map_id) method
   - Loads events.jsonl and metadata.json from Valoscribe output
   - Calls score_map_quality from src/data/quality.py
   - Returns dict with overall_score, tier, checks, total_events, total_rounds
   - Graceful handling: missing/empty files return low quality score with issues

### Testing

**15 tests, all passing:**

- 7 tests for manifest extensions (test_manifest_extensions.py)
  - quality_metrics field creation and serialization
  - new status types (download_failed, processing_failed)
  - manifest.get_by_status with new statuses
  - backward compatibility (old records without quality_metrics)
  - JSON round-trip preservation

- 8 tests for QualityValidator (test_quality_validator.py)
  - complete output validation (events + metadata)
  - missing events (returns low quality)
  - empty events file (returns low quality)
  - missing metadata (still runs checks)
  - non-existent output dir (returns low quality)
  - QualityValidator class wrapper
  - JSON serializability
  - malformed events handling (skips gracefully)

All 29 pipeline tests pass (no regressions).

## Deviations from Plan

None - plan executed exactly as written.

## Integration Points

**Upstream dependencies:**
- Phase 12-04: VLR.gg scraping provides VODRecords ready for processing

**Downstream enablers:**
- Phase 13-02: BatchProcessor will use circuit_breaker_threshold and batch_size
- Phase 13-03: CLI will use QualityValidator after Valoscribe processing completes

**Data flow:**
```
Valoscribe output (events.jsonl, metadata.json)
  → QualityValidator.validate(map_id)
    → score_map_quality (src/data/quality.py)
      → quality_metrics dict
        → VODRecord.quality_metrics (manifest storage)
          → Phase 14 experiments filter on quality tier
```

## Decisions Made

### Quality Metrics Storage Format

**Decision:** Store quality_metrics as flexible dict instead of structured dataclass

**Rationale:**
- QualityScore dataclass (src/data/quality.py) contains nested QualityCheck objects
- Direct dataclass storage would require Pydantic models or custom serialization
- Dict format is JSON-serializable by default (no schema migration needed)
- All QualityScore fields convert cleanly to dict: overall_score, tier, checks, etc.

**Impact:**
- Simple JSON round-trip via manifest save/load
- Easy filtering in Phase 14: `[r for r in records if r.quality_metrics["tier"] == "high"]`
- Trade-off: No type hints on quality_metrics contents (acceptable for storage-only field)

### Granular Failure Statuses

**Decision:** Add download_failed and processing_failed to StatusType

**Rationale:**
- Download failures (private/deleted VODs) are unrecoverable → skip permanently
- Processing failures (OCR errors, crashes) may be retryable → attempt again
- Generic "failed" status doesn't distinguish these cases
- Phase 13-02 BatchProcessor needs this distinction for retry logic

**Impact:**
- Manifest queries: `manifest.get_by_status("download_failed")` for reporting
- Retry logic: only retry processing_failed, not download_failed
- Existing "failed" status preserved for backward compatibility

### Batch Sizing & Circuit Breaker

**Decision:** Default batch_size=20, circuit_breaker_threshold=5

**Rationale:**
- 169 queued VODs × 45min/VOD = ~127hr total processing time
- Batch of 20 = ~15hr processing time (manageable overnight run)
- Circuit breaker after 5 consecutive failures prevents runaway retries
- User can override via EXPANSION_BATCH_SIZE and EXPANSION_CIRCUIT_BREAKER_THRESHOLD env vars

**Impact:**
- 169 VODs will require ~9 batch runs (169 / 20 = 8.45)
- If 5 consecutive failures occur, batch stops (investigate before retrying)
- 30min download timeout prevents hanging on large VODs

## Technical Debt & Improvements

**None identified.** Clean implementation with full test coverage.

## Next Phase Readiness

**Phase 13-02 (BatchProcessor) is ready:**
- ✅ Manifest has quality_metrics field for storing validation results
- ✅ Manifest has download_failed and processing_failed statuses
- ✅ ProcessingConfig has batch_size and circuit_breaker_threshold
- ✅ QualityValidator ready for integration after Valoscribe processing

**Phase 13-03 (CLI) is ready:**
- ✅ QualityValidator can be imported: `from src.pipeline import QualityValidator`
- ✅ validate_map_output function available for standalone validation
- ✅ All config fields available via ProcessingConfig()

**No blockers.**

## Files Changed

**Created:**
- `src/pipeline/quality_validator.py` (137 lines) - Quality validation wrapper
- `tests/pipeline/test_manifest_extensions.py` (289 lines) - Manifest extension tests
- `tests/pipeline/test_quality_validator.py` (232 lines) - QualityValidator tests

**Modified:**
- `src/pipeline/manifest.py` (+4 lines) - Added quality_metrics field, new status types
- `src/config/processing.py` (+7 lines) - Added batch processing config fields
- `src/pipeline/__init__.py` (+2 lines) - Exported QualityValidator and validate_map_output

**Total:** 658 LOC added, 6 files changed

## Commits

- `d3afa33`: feat(13-01): extend manifest and config for batch processing
- `7851aaa`: feat(13-01): add QualityValidator for pipeline integration

## Performance Notes

**Execution time:** 245 seconds (~4.1 minutes)

**Quality validation performance:** Not yet measured (will benchmark in Phase 13-02 during batch processing).

**Estimated validation overhead:** ~5-10 seconds per map (loading events.jsonl + running 5 quality checks).

---

*Phase 13 Plan 01 complete. Foundation ready for BatchProcessor (13-02) and CLI (13-03).*
