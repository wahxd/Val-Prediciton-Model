# Phase 6: Valoscribe Adaptation - Context

**Gathered:** 2026-02-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Modify Valoscribe to extract ALL possible data from VCT broadcast VODs, port the ReplayDetector for improved accuracy, and validate output consistency on the original 71 Champions 2025 maps. This phase works IN Valoscribe's codebase (no longer read-only). Output format documentation lives in this repo.

</domain>

<decisions>
## Implementation Decisions

### Data Extraction Scope
- **Guiding principle:** Minimum complexity first, then evaluate incremental complexity vs incremental value add to future model
- Economy: Buy phase loadouts via new OCR (team-level) + kill feed weapons (already captured). Buy phase serves as ground truth for validating derived economy in Phase 8
- Ult tracking: Usage events only (detect when an ult is used). No continuous charge % tracking
- Player stats: Derive from existing kill events (K/D/A, first kills, first deaths per round). No new scoreboard OCR yet
- Timeouts: Capture timeout events (momentum signal)
- Side tracking: Explicit attacker/defender field per team per round (eliminates off-by-one bugs downstream)
- Skip for now: Spike plant site (A/B), agent ability usage beyond ults

### Output Format & Structure
- Extend existing files (events.jsonl, frames.csv, metadata.json) with new event types and fields — no separate files
- No schema versioning needed — all 71 maps will be reprocessed with modified pipeline, so old format is temporary
- Just update Phase 5 Pydantic loaders for new event types (extra='allow' already handles gracefully)
- Output adapter: Separate module in Valoscribe (clean boundary between extraction and output)
- Schema documentation: Lives in this repo (consumer-side), not in Valoscribe

### Valoscribe Change Boundaries
- Open restructuring — free to refactor Valoscribe wherever it makes integration cleaner
- Update CLAUDE.md to remove "Valoscribe is READ-ONLY" convention — both repos are actively developed
- Git workflow: Feature branch + PR on Valoscribe repo
- ReplayDetector: Port to Valoscribe's GameStateManager, then remove from this repo (single source of truth)

### Regression & Validation
- Regression definition: Fewer false events from improved replay detection = improvement, not regression. Only flag if valid events disappear
- 87% validation rate target: Per-event accuracy (replay segments correctly detected across all maps), not per-map pass/fail
- Failed maps: Flag and continue — consistent with Phase 5's approach (maps flagged for review, never auto-excluded)
- Validation method: Reuse Phase 5 quality scoring + audit tools for before/after comparison on existing data
- Baseline preservation: Copy original Valoscribe output to separate backup folder (D:\Git\valoscribe-baseline\) before reprocessing

### Claude's Discretion
- Economy extraction granularity (per-player vs team-level credits) — based on what's reliably extractable from broadcast
- Round win condition handling — derive from existing events or add explicit field
- Buy phase loadout format — event in events.jsonl vs columns in frames.csv, based on downstream consumption needs

</decisions>

<specifics>
## Specific Ideas

- "Start at the bare minimum complexity needed, then do an analysis of incremental complexity necessary versus incremental potential value add to our future model"
- Buy phase loadout capture is specifically for ground truth validation of the derived economy model (Phase 8), not just for direct features
- All 71 maps will be reprocessed after modifications — old format is temporary, not a long-term concern
- Phase 5 tools already exist for quality scoring and audit — leverage them rather than building new validation

</specifics>

<deferred>
## Deferred Ideas

- VLR historical player stats (ACS, ADR, HS%, first kills, first deaths, K/D) — external data source, not VOD extraction. Evaluate for Phase 8 feature engineering or separate data ingestion phase
- Map veto (pick/ban) data — better sourced from VLR/Liquipedia than OCR. Needed for Phase 10 series prediction
- Scoreboard OCR for direct player stats — evaluate in Phase 8 whether derived stats from kill events are sufficient or if scoreboard capture adds meaningful signal
- Spike plant site (A/B) extraction — evaluate later whether site choice has predictive value

</deferred>

---

*Phase: 06-valoscribe-adaptation*
*Context gathered: 2026-02-13*
