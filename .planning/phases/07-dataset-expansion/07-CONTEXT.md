# Phase 7: Dataset Expansion (VOD Processing) - Context

**Gathered:** 2026-02-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Process additional VCT VODs through the modified Valoscribe pipeline to expand the training dataset beyond 71 Champions 2025 maps. This phase delivers a scraping + processing pipeline and the expanded dataset itself. Quality scoring and model training are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Tournament & VOD selection
- Source VODs from any available VCT matches — no tournament restriction
- Scrape YouTube links from VLR.gg match pages
- Volume-first priority — maximize total maps regardless of tournament source
- No fixed cap on maps — process as many as possible
- Extract map-level timestamps from VLR.gg to process individual maps (not full series VODs)
- Scrape match metadata from VLR.gg (teams, map name, date, tournament) for cross-referencing

### Processing workflow
- Orchestration script lives in this repo (prediction model), calls Valoscribe as external tool
- Simple sequential processing — one VOD at a time in a loop
- Log file with summary script for progress monitoring (X/Y maps done, ETA)
- Must be resumable — track which VODs are done, skip completed ones on restart
- Delete downloaded VOD files after successful processing to save disk space

### Quality gates
- Batch quality scoring after processing completes (not per-map during processing)
- Same convention as Phase 5: flag for review, never auto-exclude
- Cross-reference VLR.gg metadata with Valoscribe extracted metadata — flag mismatches for review
- Existing Phase 5 quality scoring handles garbage detection (no separate minimum threshold)

### Data organization
- New maps go into a separate directory from existing 71 (not mixed together)
- Output directory configurable via env var (consistent with VALOSCRIBE_DATA_DIR convention)
- Valoscribe generates map IDs (consistent with existing maps)
- Processing manifest (JSON/CSV) tracks all VODs: URL, status, map ID, timestamps, errors
- VLR.gg metadata centralized in the manifest (not per-map files)
- Manifest includes tournament and patch version tags for filtering in feature engineering
- Auto-generated summary report: total maps by tournament, success/fail rate, total processing time

### Claude's Discretion
- VOD downloading approach (yt-dlp integration vs Valoscribe-native)
- Failure handling strategy (retry logic, skip behavior)
- VLR.gg scraping scope and rate limiting
- Whether to update Phase 5 data loader for multi-directory support now or defer to Phase 8
- Scraping etiquette (request delays, user-agent)

</decisions>

<specifics>
## Specific Ideas

- "Scrape the YouTube link from VLR.gg and use the YouTube videos" — VLR.gg is the canonical source for VOD URLs
- Extract map timestamps from VLR.gg match pages to process individual maps rather than full series VODs
- Resumability is a hard requirement — processing runs in background over days/weeks

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 07-dataset-expansion*
*Context gathered: 2026-02-13*
