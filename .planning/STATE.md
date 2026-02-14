# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-13)

**Core value:** A prediction model accurate enough to identify edge against Polymarket prices on VCT match outcomes.
**Current focus:** Phase 8 complete — ready for Phase 9 (Baseline Model & Evaluation)

## Current Position

Phase: 9 of 10 (Baseline Model & Evaluation)
Plan: 1 of 3 in phase (09-01 complete)
Status: In progress
Last activity: 2026-02-14 — Completed 09-01-PLAN.md (Evaluation framework & config schemas)

Progress: [#########░] 70% (v1 Phase 1 + v2 Phases 5-8 + 09-01 complete)

## Previous Milestone (v1)

**v1: Event Detection Foundation**
- Phase 1 complete: 4/4 plans, 7/7 must-haves, 65 tests
- Phases 2-4 shelved (Valoscribe adoption replaces custom storage/pipeline/metadata)
- Phase 1 code preserved for future live stream retrofit

## Performance Metrics

**Velocity:**
- Total plans completed: 19
- Average duration: 10.9 min
- Total execution time: 3.46 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-event-detection-foundation | 4 | 16 min | 4 min |
| 05-data-pipeline-validation | 4 | 14 min | 3.5 min |
| 06-valoscribe-adaptation | 4 | 20.3 min | 5.1 min |
| 07-dataset-expansion | 3 | 133.9 min | 44.6 min |
| 08-feature-engineering | 4 | 14.1 min | 3.5 min |
| 09-baseline-model-evaluation | 1 | 4 min | 4 min |
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
- Atomic JSON writes use temp-file-then-rename pattern — Prevents manifest corruption on crash, Windows-safe (07-01)
- VOD discovery is idempotent — Re-running scraper on same event adds only new VODs, safe for incremental updates (07-01)
- Rate limiting defaults to 1.5s between requests — Polite scraping prevents VLR.gg rate limiting (07-01)
- Maps without VOD URLs are skipped automatically — Reduces processing queue to only actionable VODs (07-01)
- ProcessingConfig uses EXPANSION_ env var prefix — Consistent with VALOSCRIBE_DATA_DIR pattern, namespace isolation for multi-developer setups (07-02)
- Orchestrator downloads series metadata once per match — Valoscribe scrape-vlr → split-metadata → per-map process-vod flow (07-02)
- VOD files deleted after successful processing — Default True, saves disk space during multi-day processing runs (07-02)
- CLI scripts use stdlib argparse — No typer/click dependency, simpler for standalone scripts (07-02)
- Progress monitoring includes ETA calculation — Average processing time × pending count for user planning (07-02)
- VLR.gg scraping verified against live pages — Selectors work correctly on real tournament pages (07-03)
- 46 VODs queued from two major tournaments — Masters Bangkok 2024 + VCT Americas 2024 Stage 1 for temporal diversity (07-03)
- Windows console encoding fixed for UTF-8 team names — sys.stdout.reconfigure + PYTHONIOENCODING (07-03)
- Processing remains manual start for user control — VOD processing takes 15-20 hours, user decides when to start (07-03)
- Economy tier thresholds: eco (0-2500), light_buy (2500-3500), half_buy (3500-3900), full_buy (3900+) — Based on Valorant buy costs and strategic value (08-01)
- Economy credit tracking is approximate — Goal is tier classification, not exact values; uses spending estimates per tier (08-01)
- TDD workflow for feature modules — RED (failing tests) → GREEN (implementation) → atomic commits pattern established (08-01)
- Round features handle missing sides field gracefully — Pre-Phase 6 data lacks sides tracking, infer from round number (08-02)
- Clutch detection uses single-player kill pattern — High-precision for 1vX scenarios without needing frame-based alive tracking (08-02)
- Multi-kills detected within 10-second window — Standard Valorant multi-kill timing convention (08-02)
- Anti-eco stats gracefully degrade without economy data — Returns zeros when Plan 01 data unavailable, full functionality when present (08-02)
- Side performance infers sides from round number when missing — R1-12 initial, R13-24 swapped, OT alternates (backward compatibility) (08-02)
- No team identity features in map vectors — LOCKED decision: purely game mechanics, no team names/IDs (08-03)
- All features from team1 perspective — Team2 features are inverse/complement, team order matters for consistency (08-03)
- Feature sets support composable inheritance — Enables experiment reproducibility and gradual feature addition (core → combat → economy) (08-03)
- Missing map data returns None values — Graceful degradation when economy/combat data unavailable, allows partial feature sets (08-03)
- Match features aggregate per-map features for series prediction — BO3/BO5 outcomes depend on series momentum, not just individual map performance (08-04)
- Pipeline produces pandas DataFrame output — Standard format for scikit-learn model training (08-04)
- Feature set filtering at pipeline level — Registry enforces reproducible experiments, prevents feature leakage (08-04)
- Graceful error handling skips bad maps — Continue processing with valid maps rather than fail entire batch (08-04)
- LeaveOneGroupOut temporal CV with series_id grouping — Prevents series leakage, no maps from same BO3/BO5 in both train and test (09-01)
- CalibratedClassifierCV wraps all models — Ensures predicted probabilities match observed frequencies for betting applications (09-01)
- matplotlib Agg backend for headless environments — Avoids Tk dependency in tests and production (09-01)
- Model factory pattern for cross-validation — Callable returns fresh estimator to avoid reusing fitted models (09-01)
- Frozen Pydantic configs for experiments — Immutable configuration prevents accidental mutation during training (09-01)

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

- Valoscribe data directory not yet populated — 46 VODs queued, processing awaits user start (07-03)
- Valoscribe's 71-map dataset will expand to 117+ maps — 46 VODs queued from Masters Bangkok + VCT Americas (07-03)
- Single-tournament bias (Champions 2025 only) — mitigated by adding Masters Bangkok + VCT Americas data (07-03)
- ~~Elo ratings must be constructed from VCT historical results~~ — DROPPED in Phase 8 (game mechanics features sufficient, no external data needed)
- VOD processing bottleneck: 15-20 hours for 46 maps — Phase 7 processing can run in background during Phases 8-9 (07-03)
- ReplayDetector metrics not yet validated on real VODs — will assess impact during Phase 7 processing (06-01)
- Pagination not yet handled in event scraper — may miss matches if VLR.gg paginates results (07-01)

## Session Continuity

Last session: 2026-02-14
Stopped at: Completed 09-01-PLAN.md (Evaluation framework & config schemas)
Resume file: None

---
*Next step: Phase 9 Plan 02 (Baseline Training) — Evaluation infrastructure ready, train logistic regression baseline*
