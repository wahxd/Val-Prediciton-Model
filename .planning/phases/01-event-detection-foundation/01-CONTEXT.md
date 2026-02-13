# Phase 1: Event Detection Foundation - Context

**Gathered:** 2026-02-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Detect discrete game events (kills, round ends, spike events, timeouts) from VCT broadcast frames using computer vision and OCR. Focus on reliable state change detection with robust replay protection and data quality validation. Team-level tracking only - individual player tracking is separate phase.

</domain>

<decisions>
## Implementation Decisions

### Detection thresholds & debouncing
- 3-frame consensus required before confirming state change (~100ms at 30fps)
- Minimum OCR confidence: 0.7 (70%) for extracted values to be used in state tracking
- Invalid values (alive count > 5, malformed timers) are discarded and frame is skipped
- Log warning when 10+ consecutive frames fail OCR confidence or validation checks

### Replay detection strategy
- Detection trigger: Timer regression AND score validation (both conditions required)
- Suppression duration: Until timer progresses forward past the regression point
- Error tolerance: Equal concern for false positives (phantom events from missed replays) and false negatives (missed real events)
- **Tactical timeouts tracked as explicit events**: Log TIMEOUT events with team attribution (which team called it) - timeouts are momentum indicators crucial for prediction

### Event granularity & metadata
- Team-level aggregates only (Team A: 3 alive, Team B: 5 alive) - no per-player tracking in Phase 1
- Snapshot format: Each event includes full game state at moment of event (score, alive counts, round timer, spike status)
- Spike events (plant/defuse/detonate) include round timer at event time for timing analysis
- Round-end events infer win condition from event sequence (elimination vs spike detonation vs defuse vs timeout)

### Data quality handling
- Quality reporting: Console warnings for significant issues (50+ consecutive frame failures), full details to log file
- Quality metrics: Track per-field OCR confidence, debounce statistics, replay detection triggers for post-stream analysis
- Extended degradation response: After 30+ seconds of poor OCR quality, pause and prompt user to check ROI alignment or stream quality
- OCR character whitelisting by field type: Timer [0-9:], Alive count [0-5], Score [0-9] to prevent garbage values

### Claude's Discretion
- Exact log message formatting and verbosity levels
- Specific data structure for quality metrics storage
- Implementation details of character whitelisting in Tesseract configuration

</decisions>

<specifics>
## Specific Ideas

- Tactical timeouts as momentum shift indicators: "Depending on which team called a Timeout, this may be an indicator of a momentum shift. Momentum is a very crucial player in Valorant."
- Conservative data quality approach: Higher confidence threshold (0.7 vs 0.6) and discard invalid frames rather than auto-correct

</specifics>

<deferred>
## Deferred Ideas

- Per-player state tracking (individual alive status, agent picks, player names) - future phase
- Spike site location detection (A/B/C site from minimap) - mentioned as potential Phase 2 work
- Real-time quality dashboard - comprehensive monitoring interface deferred to future phase
- Frame-by-frame quality logging - comprehensive debug mode not needed for Phase 1

</deferred>

---

*Phase: 01-event-detection-foundation*
*Context gathered: 2026-02-12*
