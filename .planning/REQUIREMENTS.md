# Requirements: Valorant Match Event Logger

**Defined:** 2026-02-12
**Core Value:** Reliable, timestamped event logs from live VCT matches — consistent enough across multiple matches to train a prediction model.

## v1 Requirements

### State Extraction (Existing)

- [x] **EXTR-01**: Extract game scores from VCT broadcast frames via OCR
- [x] **EXTR-02**: Detect alive player counts per team via color/brightness sampling
- [x] **EXTR-03**: Detect spike plant status via HSV color detection
- [x] **EXTR-04**: Read round timer via OCR
- [x] **EXTR-05**: Watch live Twitch/YouTube streams via streamlink at 6fps

### Event Detection

- [ ] **EVNT-01**: Detect round end events when score increments between frames
- [ ] **EVNT-02**: Detect kill events when alive count decreases for either team
- [ ] **EVNT-03**: Detect spike plant events when spike status transitions to planted
- [ ] **EVNT-04**: Detect spike defuse events when spike status transitions from planted to not-planted without detonation
- [ ] **EVNT-05**: Detect spike detonate events when spike status transitions to detonated
- [ ] **EVNT-06**: Detect round start events when timer resets and alive counts return to 5v5
- [ ] **EVNT-07**: State changes persist for 3+ consecutive frames before emitting event (debouncing)

### Data Quality

- [ ] **QUAL-01**: Detect replay footage via timer regression (timer value increases instead of decreasing)
- [ ] **QUAL-02**: Validate alive count coherence (counts only decrease within a round, reset at round start)
- [ ] **QUAL-03**: Validate score monotonicity (score never decreases within a match half)
- [ ] **QUAL-04**: Suppress all event emission during detected replay segments
- [ ] **QUAL-05**: Log data quality warnings when OCR confidence is low or values are out of expected range

### Storage

- [ ] **STOR-01**: Store events as timestamped append-only JSONL files (one per match)
- [ ] **STOR-02**: Each event includes wall_clock_time, game_time (from timer OCR), frame_number, and event type
- [ ] **STOR-03**: Event log survives stream interruptions and application crashes (flush after each event)
- [ ] **STOR-04**: Match event logs stored in organized directory structure (by date/match)

### Match Session

- [ ] **SESS-01**: Create match session with unique match_id at session start
- [ ] **SESS-02**: Store match metadata (teams, map, date, stream URL) in session header
- [ ] **SESS-03**: Support manual start/stop of match sessions
- [ ] **SESS-04**: Support multi-map series (BO3/BO5) with per-map event logs linked to series

### Metadata Detection

- [ ] **META-01**: Auto-detect team names from broadcast overlay via OCR
- [ ] **META-02**: Auto-detect map name from broadcast overlay via OCR
- [ ] **META-03**: Use majority-vote validation across first 10 frames for detection confidence
- [ ] **META-04**: Fuzzy match detected names against known team/map whitelists
- [ ] **META-05**: Fall back to manual input prompt when auto-detection confidence is low

### Pipeline Integration

- [ ] **PIPE-01**: Event pipeline orchestrates: frame capture → state extraction → state diffing → event emission → storage
- [ ] **PIPE-02**: Refactor GameWatcher to use event pipeline instead of direct game_state.json writing
- [ ] **PIPE-03**: Pipeline handles stream reconnection without losing match session context
- [ ] **PIPE-04**: Extensible event type registration (adding new event types doesn't require modifying existing code)

## v2 Requirements

### Economy & Round Classification

- **ECON-01**: Extract team economy during buy phase
- **ECON-02**: Classify buy type (eco/force/full buy)
- **ECON-03**: Detect side (attacker/defender)
- **ECON-04**: Detect first blood per round
- **ECON-05**: Classify round type (pistol vs gun round)

### Advanced CV

- **ADCV-01**: Detect agent compositions via template matching
- **ADCV-02**: Track ultimate ability availability per team

## Out of Scope

| Feature | Reason |
|---------|--------|
| Player-level tracking | Not visible in broadcast without killfeed OCR — defer indefinitely |
| Contract price integration (Polymarket/Kalshi) | Separate milestone — data collection first |
| Prediction model training | Separate milestone — need data before model |
| Non-VCT broadcast support | Different overlays add complexity without value yet |
| Real-time trading signals | Future milestone after model is built |
| VOD historical scraping | Overlay formats change seasonally, ROIs break |
| Map positioning/minimap analysis | Minimap too small and inconsistently shown in broadcasts |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| EXTR-01 | Existing | Complete |
| EXTR-02 | Existing | Complete |
| EXTR-03 | Existing | Complete |
| EXTR-04 | Existing | Complete |
| EXTR-05 | Existing | Complete |
| EVNT-01 | TBD | Pending |
| EVNT-02 | TBD | Pending |
| EVNT-03 | TBD | Pending |
| EVNT-04 | TBD | Pending |
| EVNT-05 | TBD | Pending |
| EVNT-06 | TBD | Pending |
| EVNT-07 | TBD | Pending |
| QUAL-01 | TBD | Pending |
| QUAL-02 | TBD | Pending |
| QUAL-03 | TBD | Pending |
| QUAL-04 | TBD | Pending |
| QUAL-05 | TBD | Pending |
| STOR-01 | TBD | Pending |
| STOR-02 | TBD | Pending |
| STOR-03 | TBD | Pending |
| STOR-04 | TBD | Pending |
| SESS-01 | TBD | Pending |
| SESS-02 | TBD | Pending |
| SESS-03 | TBD | Pending |
| SESS-04 | TBD | Pending |
| META-01 | TBD | Pending |
| META-02 | TBD | Pending |
| META-03 | TBD | Pending |
| META-04 | TBD | Pending |
| META-05 | TBD | Pending |
| PIPE-01 | TBD | Pending |
| PIPE-02 | TBD | Pending |
| PIPE-03 | TBD | Pending |
| PIPE-04 | TBD | Pending |

**Coverage:**
- v1 requirements: 27 new + 5 existing = 32 total
- Mapped to phases: 5 (existing)
- Unmapped: 27 ⚠️ (pending roadmap creation)

---
*Requirements defined: 2026-02-12*
*Last updated: 2026-02-12 after initial definition*
