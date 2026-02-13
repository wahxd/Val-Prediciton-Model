# Roadmap: Valorant Match Event Logger

## Overview

Transform the existing VCT frame analysis pipeline into a persistent event logging system. Starting with foundational state change detection and replay protection, then building event storage with match session management, integrating everything into a unified pipeline, and finally adding metadata auto-detection for team/map identification. By completion, the system will produce reliable, timestamped event logs from live VCT matches ready for prediction model training.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3, 4): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Event Detection Foundation** - Core state change detection with data quality validation
- [ ] **Phase 2: Event Storage & Session Management** - Persistent JSONL event logs with match sessions
- [ ] **Phase 3: Pipeline Integration** - Unified EventPipeline orchestrating full workflow
- [ ] **Phase 4: Metadata Auto-Detection** - Auto-extract team names and map from broadcast overlay

## Phase Details

### Phase 1: Event Detection Foundation
**Goal**: Detect discrete game events (kills, round ends, spike events) from frame-by-frame state changes with robust replay detection and debouncing

**Depends on**: Nothing (first phase, extends existing VCTVisionEngine)

**Requirements**: EVNT-01, EVNT-02, EVNT-03, EVNT-04, EVNT-05, EVNT-06, EVNT-07, QUAL-01, QUAL-02, QUAL-03, QUAL-04, QUAL-05

**Success Criteria** (what must be TRUE):
  1. System detects round end events when score increments between frames
  2. System detects kill events when alive count decreases for either team
  3. System detects spike plant, defuse, and detonate events from spike status transitions
  4. System detects round start events when timer resets and alive counts return to 5v5
  5. System correctly identifies replay footage via timer regression and suppresses all event emission during replays
  6. State changes persist for 3+ consecutive frames before triggering events (no event storms from OCR flicker)
  7. System logs data quality warnings when OCR confidence is low or values are out of expected range

**Plans**: TBD

Plans:
- [ ] TBD (to be planned)

### Phase 2: Event Storage & Session Management
**Goal**: Store events as persistent, crash-safe JSONL logs organized by match sessions with metadata

**Depends on**: Phase 1 (requires StateTracker and event detection logic)

**Requirements**: STOR-01, STOR-02, STOR-03, STOR-04, SESS-01, SESS-02, SESS-03, SESS-04

**Success Criteria** (what must be TRUE):
  1. Events are stored as timestamped JSONL files (one per match) with wall_clock_time, game_time, frame_number, and event type
  2. Event logs survive stream interruptions and application crashes (flush after each event)
  3. User can manually start/stop match sessions with unique match_id
  4. Match sessions store metadata (teams, map, date, stream URL) in session header
  5. System supports multi-map series (BO3/BO5) with per-map event logs linked to series
  6. Event logs are organized in directory structure by date/match

**Plans**: TBD

Plans:
- [ ] TBD (to be planned)

### Phase 3: Pipeline Integration
**Goal**: Integrate event detection and storage into existing GameWatcher with extensible event type system

**Depends on**: Phase 2 (requires EventStore and EventEmitter components)

**Requirements**: PIPE-01, PIPE-02, PIPE-03, PIPE-04

**Success Criteria** (what must be TRUE):
  1. EventPipeline orchestrates full workflow: frame capture → state extraction → state diffing → event emission → storage
  2. GameWatcher uses EventPipeline instead of directly writing game_state.json
  3. Pipeline handles stream reconnection without losing match session context
  4. Adding new event types doesn't require modifying existing pipeline code (extensible registration system)
  5. End-to-end test can process mock frames through full pipeline to verified JSONL output

**Plans**: TBD

Plans:
- [ ] TBD (to be planned)

### Phase 4: Metadata Auto-Detection
**Goal**: Auto-detect team names and map from broadcast overlay with confidence validation

**Depends on**: Phase 3 (requires working EventPipeline)

**Requirements**: META-01, META-02, META-03, META-04, META-05

**Success Criteria** (what must be TRUE):
  1. System auto-detects team names from broadcast overlay via OCR with majority-vote validation across first 10 frames
  2. System auto-detects map name from broadcast overlay via OCR with majority-vote validation
  3. Detected names are fuzzy-matched against known team/map whitelists for validation
  4. System falls back to manual input prompt when auto-detection confidence is low
  5. Session metadata is automatically populated with detected teams/map without manual intervention (when confidence is high)

**Plans**: TBD

Plans:
- [ ] TBD (to be planned)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Event Detection Foundation | 0/TBD | Not started | - |
| 2. Event Storage & Session Management | 0/TBD | Not started | - |
| 3. Pipeline Integration | 0/TBD | Not started | - |
| 4. Metadata Auto-Detection | 0/TBD | Not started | - |

---
*Roadmap created: 2026-02-12*
*Last updated: 2026-02-12*
