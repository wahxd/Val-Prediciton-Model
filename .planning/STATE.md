# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-12)

**Core value:** Reliable, timestamped event logs from live VCT matches — consistent enough across multiple matches to train a prediction model.
**Current focus:** Phase 1 - Event Detection Foundation

## Current Position

Phase: 1 of 4 (Event Detection Foundation)
Plan: 3 of 4 in current phase
Status: In progress
Last activity: 2026-02-13 — Completed 01-03-PLAN.md (Event Emitter and Quality Metrics)

Progress: [███░░░░░░░] 19%

## Performance Metrics

**Velocity:**
- Total plans completed: 3
- Average duration: 4 min
- Total execution time: 0.2 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-event-detection-foundation | 3 | 12 min | 4 min |

**Recent Trend:**
- Last 5 plans: 01-03 (4 min), 01-02 (3 min), 01-01 (5 min)
- Trend: Stable

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Event-based logging (not continuous snapshots) — Only state changes matter for prediction, reduces noise and storage
- Team-level granularity first — Simpler CV extraction, extensible to player-level later
- VCT broadcasts only — Consistent overlay layout makes CV reliable
- Auto-detect teams/map from broadcast — Reduces manual input friction, essential for consistent match labeling
- Used kw_only=True on Pydantic dataclasses — Solves inheritance ordering issue, enforces explicit event construction
- Transition-based round start detection — Timer must jump from <30s to >=80s + 5v5, prevents false positives
- Timeout detection via 5-frame frozen timer — Conservative threshold avoids false positives from OCR flicker
- Win condition inference priority — spike_detonate > spike_defuse > elimination > timeout

### Pending Todos

None yet.

### Blockers/Concerns

**Phase 1 Concerns:**
- Replay detection must be robust from day one — single failure corrupts event logs with phantom events [ADDRESSED: ReplayDetector implemented with dual-condition detection]
- Debouncing parameters (3-frame vs 5-frame consensus) need empirical tuning on actual VCT footage
- OCR character whitelisting required to prevent garbage values (e.g., timer reading "1:3C" instead of "1:30") [ADDRESSED: OCR_WHITELISTS in ocr_config.py]
- structlog dependency should be added to requirements.txt when project dependencies are formalized

**General Concerns:**
- VCT broadcast overlay format may have changed since Jan 2025 — ROI coordinates must be validated against live 2026 VCT match before production use
- No validation that collected event data will actually improve prediction model accuracy — be ready to deprioritize low-value features based on model performance

## Session Continuity

Last session: 2026-02-13
Stopped at: Completed 01-03-PLAN.md (Event Emitter and Quality Metrics)
Resume file: None

---
*Next step: Execute remaining Phase 1 plan (01-04: Unit tests)*
