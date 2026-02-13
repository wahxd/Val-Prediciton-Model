# Phase 5: Data Pipeline & Validation - Context

**Gathered:** 2026-02-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Reliably ingest all Valoscribe output (JSONL events, CSV frames, JSON metadata) with per-map quality scoring that separates usable training data from maps that should be excluded. Also serves as a data exploration/documentation exercise — catalog what Valoscribe actually produces. No data is duplicated into this repo — Valoscribe directory is referenced externally.

</domain>

<decisions>
## Implementation Decisions

### Quality filtering strategy
- Claude's discretion on filtering approach (tiered vs binary, threshold strictness) — optimize for dataset size vs noise tradeoff given only 71 maps
- Quality signals to check:
  - Kill count vs expected (from roadmap success criteria)
  - Round progression consistency (from roadmap success criteria)
  - Round start/end balance (from roadmap success criteria)
  - Event completeness: every round should have expected events (round start, kills, spike events, round end) — missing events indicate OCR gaps
  - Timing consistency: timestamps must make sense (no impossible gaps, rounds in reasonable time range) — catches replay detection failures
  - Ultimate ability usage: if Valoscribe captures ult data, maps with that data are higher quality (maps without aren't excluded, just noted as lower signal)
- Maps are flagged for manual review, NOT auto-excluded — with only 71 maps, user decides per-map
- Cross-check Valoscribe's own validation_results (from metadata.json) against our independent quality checks — disagreements are interesting and should be highlighted

### Audit & reporting output
- Output location: `data/audit/` in this repo
- Dual format: JSON (programmatic access for downstream phases) + Markdown (human review)
- Markdown report: single file with table of contents, sections per map — not separate files
- Summary table columns: teams, map name, quality score, event counts (total events, kills, rounds), issue flags, final match score
- Executive summary at top: aggregate counts by quality tier + dataset readiness
- Per-map detail includes round-by-round breakdown showing where specific issues were detected (not just map-level aggregates)
- Rerun behavior: full regenerate by default, incremental mode available via flag (for when dataset grows in Phase 7+)
- Per-map quality scores are scope for Phase 5; series-level data integrity checks belong to Phase 8

### Pipeline workflow
- Python API as the core (Phase 8+ imports directly), thin CLI wrapper for convenience
- Load and audit are separate but composable — can load without auditing, or audit pre-loaded data; CLI convenience command runs both together
- Map discovery: auto-discover by scanning Valoscribe data directory + optional filtering to specific maps
- Error handling: continue on error, collect all failures, report everything at the end — maximizes usable data
- Progress output: show per-map progress (e.g., "Loading map 23/71: TH vs PRX on Ascent...")
- Valoscribe data path: environment variable (`VALOSCRIBE_DATA_DIR`) with CLI `--data-dir` override — multi-person project, each dev sets in their own `.env` (gitignored), `.env.example` in repo

### Valoscribe data expectations
- Phase 5 is also a data exploration exercise — don't assume we know the full format, discover and document it
- Preserve all fields, even unrecognized ones — don't discard data we haven't categorized yet
- Auto-generate a data catalog: all event types found, all fields per event type, value ranges, completeness stats
- File completeness per map is unknown — loader should discover and report what's actually present (events.jsonl, frames.csv, metadata.json) rather than assuming all 3 exist

### Claude's Discretion
- Quality filtering approach (tiered vs binary) and specific thresholds
- Diagnostic detail level per map
- Pre-validation strategy (upfront directory check vs per-map failure)
- Verbose/debug mode design (-v flag behavior)
- Python API return type design (dict by map_id, list with filtering, etc.)
- Separate overrides file vs direct edit for review workflow
- Map discovery implementation details (directory scanning, expected structure)

</decisions>

<specifics>
## Specific Ideas

- Multi-person project: config should use env vars + .env (gitignored) so each developer can point to their own Valoscribe installation
- Audit report should feel like a data quality dashboard — scan the summary table, drill into per-map round-by-round breakdowns for flagged maps
- Valoscribe's self-reported validation_results vs our independent checks: highlight disagreements specifically (Valoscribe says pass but we detect issues, or vice versa)

</specifics>

<deferred>
## Deferred Ideas

- Series-level data integrity checks (same teams across maps, map order, missing maps) — Phase 8 concern
- Scheduled/automated reprocessing — out of scope

</deferred>

---

*Phase: 05-data-pipeline-validation*
*Context gathered: 2026-02-13*
