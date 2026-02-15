# Phase 13: VOD Processing Pipeline - Context

**Gathered:** 2026-02-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Automated pipeline that downloads 169 queued YouTube VODs, processes each through Valoscribe's OCR pipeline, validates output quality, and tracks progress. Target: 80-100 successfully processed maps (combined with existing 71 = 150+ total). Experiment design, model training, and quality threshold tuning are separate phases (14-15).

</domain>

<decisions>
## Implementation Decisions

### Batch execution strategy
- Explicit batch size via CLI flag (e.g., `--batch 20`) — pipeline stops after batch completes
- Sequential processing: one VOD at a time (download → process → cleanup → next)
- VODs processed by tournament: complete one tournament fully before starting the next
- Auto-resume: pipeline checks manifest status on start, continues with next unprocessed VOD automatically

### Failure & skip policy
- Download failures (private, deleted, region-locked): skip immediately, mark as `download_failed` in manifest
- Processing failures (OCR errors, crashes, corrupt output): skip immediately, mark as `processing_failed` in manifest
- No retries on either failure type — skip and move on
- Circuit breaker: stop batch after N consecutive failures (likely systemic issue worth investigating)
- Log error reason/exception message in manifest for each failure

### Quality gate thresholds
- Flag but include: no maps auto-excluded during processing
- Store quality metrics per map in manifest — experiments in Phase 14 decide their own filtering thresholds
- Metrics captured: Valoscribe's existing validation_results (OCR confidence, replay detection, alive coherence) PLUS pipeline-level checks (expected round count vs actual, team name matching success, event completeness)
- Batch summary report generated after each batch: maps processed, quality distribution, failures, flagged outliers

### Storage & cleanup
- Processed output stays in Valoscribe (`D:\Git\valoscribe\data\processed\{map_id}\`) — this repo references via manifest paths
- Pre-flight disk space check before starting batch — warn and abort if insufficient
- Partial output cleaned up on failure: delete incomplete events.jsonl/frames.csv/metadata.json, record error in manifest
- No corrupt/incomplete data left behind in processed directory

### Claude's Discretion
- VOD file retention after processing (delete vs keep — balance disk space vs re-processing ability)
- Cross-validation of Valoscribe output against VLR.gg scraped data (round scores, team names)
- Retry-failed mechanism (whether to include a `--retry-failed` flag for re-attempting previously failed VODs)
- Exact consecutive failure threshold for circuit breaker (3-5 range)
- Download timeout and temporary file handling

</decisions>

<specifics>
## Specific Ideas

- Pipeline should feel like a batch job you kick off and walk away from — explicit batch sizes, auto-resume, no interactive prompts
- Tournament-ordered processing enables per-tournament quality assessment (e.g., "Masters Bangkok had 95% success rate, VCT Americas had 80%")
- Error reasons in manifest are the primary diagnostic tool — no need to preserve partial output files
- Summary report after each batch provides visibility without needing to query the manifest manually

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 13-vod-processing-pipeline*
*Context gathered: 2026-02-15*
