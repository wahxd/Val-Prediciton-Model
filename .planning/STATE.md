# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-13)

**Core value:** A prediction model accurate enough to identify edge against Polymarket prices on VCT match outcomes.
**Current focus:** Phase 5 complete — ready for Phase 6

## Current Position

Phase: 6 of 10 (Valoscribe Adaptation) — IN PROGRESS
Plan: 4 of 5 in phase (06-01, 06-02, 06-03, 06-04 complete)
Status: In progress
Last activity: 2026-02-13 — Completed 06-04-PLAN.md (schema documentation & parser updates)

Progress: [#####░░░░░] 40% (v1 Phase 1 + v2 Phase 5 complete + 06-01, 06-02, 06-03, 06-04 complete)

## Previous Milestone (v1)

**v1: Event Detection Foundation**
- Phase 1 complete: 4/4 plans, 7/7 must-haves, 65 tests
- Phases 2-4 shelved (Valoscribe adoption replaces custom storage/pipeline/metadata)
- Phase 1 code preserved for future live stream retrofit

## Performance Metrics

**Velocity:**
- Total plans completed: 12
- Average duration: 3.6 min
- Total execution time: 0.9 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-event-detection-foundation | 4 | 16 min | 4 min |
| 05-data-pipeline-validation | 4 | 14 min | 3.5 min |
| 06-valoscribe-adaptation | 4 | 20.3 min | 5.1 min |
| quick tasks | 2 | 5 min | ~3 min |

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Adopt Valoscribe for data, actively develop alongside this repo — Phase 6 adapts Valoscribe to emit richer data (06-01: replay detection, economy, weapons, abilities)
- Prediction scope: map winner + match winner — Binary outcomes matching Polymarket contracts
- v2 = model only, v3 = trading + live — Ship model first, validate edge before building trading
- Shelve v1 Phases 2-4 — Valoscribe provides storage/pipeline/metadata capabilities
- Walk-forward temporal validation only — Never random train/test splits (research finding)
- Log loss as primary metric — Calibration matters more than accuracy for betting (research finding)
- Start with logistic regression baseline — Prove signal exists before adding complexity (research finding)
- Restructure v2 phases — Adapt Valoscribe early, start VOD processing ASAP, do feature engineering while VODs process
- Use extra='allow' on Pydantic models for discovery phase — Preserve unknown fields from Valoscribe, tighten in Phase 6 (05-01)
- Config uses bare VALOSCRIBE_DATA_DIR env var — No prefix for simpler multi-developer setup (05-01)
- Dual-format audit reports: JSON for programmatic consumption, Markdown for human dashboard (05-04)
- Maps flagged for review, never auto-excluded — with 71 maps, human decides per-map (05-03)
- ReplayDetector ported to Valoscribe as single source of truth — Eliminates duplication, Valoscribe is canonical (06-01)
- Replay check integrated between phase detection and event generation — Detections run, events suppressed during replays (06-01)
- CLAUDE.md updated: Valoscribe is actively developed — No longer read-only, Phase 6 contributions enabled (06-01)
- OutputAdapter uses default parameter pattern — No GameStateManager changes needed, works with existing code (06-03)
- Output filenames standardized to events.jsonl/frames.csv — Matches Phase 5 loader expectations (06-03)
- Unknown event types gracefully handled — Pass through all fields for future extensibility (06-03)
- Buy phase detector requires 3/5 players with credit detections to classify loadout — Balances accuracy with OCR unreliability (06-02)
- Timeout detector uses round_number crop region and de-duplicates via state tracking — Most reliable region for overlay text (06-02)
- All round events include explicit side tracking — Uses RoundManager.get_current_sides() which handles halftime and OT swaps (06-02)
- Schema documentation lives in prediction model repo (consumer-side) — Per CONTEXT.md, docs/valoscribe-output-schema.md is single source of truth (06-04)
- New fields on existing events use Optional defaults — Backward compatibility with Phase 5 loaders maintained (sides field on round events) (06-04)
- Game mechanics reference centralized in schema doc — Economy, sides, round numbering documented with data formats for feature engineering context (06-04)

### Pending Todos

- ~~Set up CLAUDE.md with project-specific content (from quick task 002 research)~~ — DONE (06-01)
- Update settings.local.json with expanded permissions + MCP servers (from quick task 002 research)
- Run full audit when Valoscribe data becomes available (after Phase 7 VOD processing)
- Decide on Valoscribe git workflow (merge feature branches? PR review? direct commits?) — Repo newly initialized in 06-01

### Quick Tasks Completed

| # | Description | Date | Directory |
|---|-------------|------|-----------|
| 002 | Claude Code QoL integrations research (MCP servers, plugins, skills, repos) | 2026-02-13 | [002-claude-code-qol-integrations-research](./quick/002-claude-code-qol-integrations-research/) |

### Blockers/Concerns

- Valoscribe data directory not yet populated — full audit run deferred to after Phase 7 VOD processing
- Valoscribe's 71-map dataset may be insufficient for reliable model training — VOD processing moved to Phase 7
- Single-tournament bias (Champions 2025 only) — cross-tournament validation in Phase 10
- Elo ratings must be constructed from VCT historical results — no existing ratings available (Phase 8)
- VOD processing bottleneck: 20-40 min per map — Phase 7 starts processing early, runs in background during Phases 8-9
- ReplayDetector metrics not yet validated on real VODs — will assess impact during Phase 7 processing (06-01)

## Session Continuity

Last session: 2026-02-13
Stopped at: Completed 06-04-PLAN.md (schema documentation & parser updates)
Resume file: None

---
*Next step: /gsd:execute-phase 6 --plan 05 (final plan in Phase 6)*
