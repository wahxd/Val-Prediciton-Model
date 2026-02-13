# Project Research Summary

**Project:** Valorant VCT Event Detection & Logging Pipeline
**Domain:** Computer vision-based esports event data collection
**Researched:** 2026-02-12
**Confidence:** MEDIUM-HIGH

## Executive Summary

This project extends an existing Python computer vision pipeline to transform frame-by-frame broadcast analysis into a persistent event logging system for Valorant competitive matches. The research reveals that successful VCT event detection systems prioritize **state change detection over continuous snapshots**, **local-first storage over cloud complexity**, and **incremental adoption of existing CV infrastructure** rather than ground-up rewrites.

The recommended approach builds on the existing OpenCV + pytesseract stack with three critical additions: (1) upgrading to EasyOCR for better accuracy on stylized game fonts, (2) implementing a state machine to detect changes between frames and emit discrete events, and (3) using SQLite for persistent event storage with ACID guarantees. This architecture enables training data collection for prediction models while maintaining the proven frame extraction pipeline already in place.

The highest risk is **replay footage contamination** — VCT broadcasts frequently show replays during timeouts and between rounds, which appear identical to live gameplay to the CV system. Without replay detection, event logs become polluted with duplicate events that have incorrect timestamps, corrupting prediction model training data. Prevention requires multi-signal validation (timer regression detection, alive count coherence checks, score monotonicity verification) implemented from day one. Other critical risks include overlay format changes breaking hardcoded ROI coordinates and OCR debouncing failures creating event storms — both addressable through versioned configuration and temporal smoothing.

## Key Findings

### Recommended Stack

The stack extends existing Python CV infrastructure (OpenCV, streamlink) with event detection, state management, and persistent storage capabilities. The approach is **incremental adoption** — add new components alongside existing code rather than replacing proven frame extraction logic.

**Core technologies:**
- **EasyOCR (1.7.x+)**: Game overlay text extraction — Better accuracy than pytesseract on stylized fonts, GPU-accelerated, no Windows Tesseract installation complexity
- **SQLite + SQLAlchemy (2.0.x+)**: Event storage with ACID transactions — Zero-config persistence, excellent query performance for ML training data retrieval, built-in schema migration support
- **python-statemachine (2.1.x+)**: Game phase transitions — Explicit state machine for menu → agent_select → in_game → post_round flow prevents invalid event sequences
- **deepdiff (6.7.x+)**: State change detection — Semantic diffing of OCR results (team rosters, agent compositions) without manual field comparison
- **diskcache + imagehash (5.6.x+, 4.3.x+)**: Frame deduplication — Cache OCR results by perceptual hash, avoid re-processing identical frames from stream buffering

**Critical upgrade rationale:**
Pytesseract struggles with VCT's custom fonts and requires separate binary installation on Windows. EasyOCR is trained on synthetic data, handles stylized text better, and includes GPU acceleration critical for real-time processing (100-200ms/frame vs 300-500ms with pytesseract CPU mode).

**Storage rationale:**
SQLite provides ACID guarantees preventing data loss during stream interruptions, indexes on timestamps enable efficient temporal queries, and local-first storage aligns with project constraints. Export to Parquet for ML training consumption, but primary storage in SQLite.

### Expected Features

Event detection systems separate into **table stakes** (minimum viable), **differentiators** (competitive edge), and **anti-features** (tempting but low-value).

**Must have (table stakes):**
- **Round result events** — Win/loss detection via score increments, foundation for match outcome prediction
- **Kill detection** — Alive count deltas (team-level only, cannot identify individual players from broadcast)
- **Spike plant/defuse/detonate** — Critical economy shifts and tactical context
- **Economy snapshots** — Total team economy during buy phase determines eco/force/full buy classification
- **Team/map identification** — OCR team names and map for training data labeling
- **Match session management** — Persistent logs with start/stop metadata, multi-map series support

**Should have (competitive):**
- **First blood detection** — Team with first kill wins 65-70% of rounds (high prediction value, easy to derive from kill events)
- **Side detection** — Attacker vs defender identification (affects baseline win probabilities by 5-10%)
- **Round type classification** — Pistol/eco/force/full buy based on economy (adjusts win probability baseline)
- **Alive differential tracking** — 5v4 vs 5v3 progression reveals momentum (medium prediction value, already tracked)

**Defer (v2+):**
- **Agent compositions** — Requires 22-agent template library, meta shifts seasonally (defer to Phase 3+)
- **Ultimate status tracking** — Complex per-player pixel sampling, medium-high value but high CV difficulty (Phase 3+ with research flag)
- **Player-level stats** — Not visible in broadcast without killfeed OCR (low feasibility, defer indefinitely)

**Critical anti-features to avoid:**
- **VOD scraping historical data** — Overlay formats change seasonally, ROI coordinates break, fresh current-season data > stale historical data
- **Real-time price integration** — Out of scope for data collection milestone, adds complexity without improving data quality
- **Positioning/map control** — Minimap too small and inconsistently shown in broadcasts, unreliable extraction

### Architecture Approach

The architecture wraps existing `VCTVisionEngine` with event-oriented components following **event sourcing patterns** — append-only logs with state reconstruction, state change detection via diffing, persistent event store with match session management.

**Major components:**

1. **StateTracker** — Maintains previous/current frame state, detects changes (score increments → round end, alive count decrements → kills, spike status transitions → plant/defuse). Encapsulates state ownership for testability and thread safety.

2. **EventEmitter** — Transforms `StateChange` objects into timestamped `Event` objects with match context. Separates diffing logic from serialization/formatting for single responsibility.

3. **EventStore** — Append-only JSONL event logs per match. Crash-safe buffered writes, one file per match with hierarchical directory structure for scaling to 1M+ events.

4. **EventPipeline** — Orchestrator coordinating frame processing, state tracking, event emission, and storage. Isolates `VCTVisionEngine` (stateless) from event system (stateful).

5. **MetadataExtractor** — Auto-detects team names and map from broadcast overlay using OCR with majority-vote validation across first 10 frames.

**Data flow:**
Stream → Frame (6fps) → VCTVisionEngine.analyze() → StateTracker.update() → EventEmitter.emit_events() → EventStore.append() → Persistent JSONL log

**Build order:**
Phase 1 builds state diffing foundation (StateTracker, unit tests), Phase 2 adds event emission + storage (EventEmitter, EventStore, integration tests), Phase 3 integrates pipeline with existing GameWatcher, Phase 4 adds metadata extraction, Phase 5 implements match session management for BO3/BO5 series.

### Critical Pitfalls

**1. Replay footage creating phantom events**
VCT broadcasts show replays during timeouts and between rounds. Without detection, duplicate events with wrong timestamps corrupt event logs. A single 30-second replay injects 5-10 false kill events. **Prevention:** Multi-signal validation — timer regression detection (timer increases = replay), alive count coherence (counts should only decrease except at round reset), score monotonicity (score never decreases). OCR for "REPLAY" text overlay. Must implement in Phase 1 before processing any matches.

**2. Hardcoded ROI coordinates breaking on overlay updates**
VCT updates broadcast graphics between events (Champions vs Masters vs Kickoff overlays vary). Hardcoded coordinates suddenly extract garbage. System appears to work (no crashes) but logs invalid data. **Prevention:** Overlay version detection via fingerprinting constant elements, multi-version ROI config sets (VCT_2024_CHAMPIONS, VCT_2025_KICKOFF), runtime sanity checks (if OCR fails >10 frames, alert wrong ROI), consolidate config.py vs vision_engine.py duplicate ROI definitions. Address in Phase 2 before multi-match processing.

**3. State debouncing failures creating event storms**
OCR flickers between correct/incorrect values (timer reads "1:30", "1", "1:30", "1:3C"). Each flicker triggers state change. Single kill generates 5-10 duplicate events as alive_count oscillates. **Prevention:** Require state to persist for 3-5 consecutive frames before emitting event, confidence thresholds on OCR results, hysteresis on brightness thresholds for alive detection, event deduplication (check if identical event occurred in last 2 seconds). Critical for Phase 1 — determines data quality.

**4. Buy phase vs combat phase state conflation**
Economy data only visible during buy phase (first 30-45s of round). During combat, economy UI hidden. Code reads economy ROI during combat, gets 0 or noise, logs false "economy dropped to 0" events. **Prevention:** Phase detection state machine (buy phase = timer 1:40-1:10, combat = timer <1:10 or spike planted), cache last valid economy during combat, only emit buy_type events during buy phase. Required for Phase 2 economy extraction — attempting without phase awareness produces unusable data.

**5. Frame-level vs event-level timestamp precision confusion**
Frame capture at 6fps = every ~166ms. Actual game events at 60fps. Two kills 50ms apart appear simultaneous. Can't distinguish "trade kill" (50ms) from "double kill" (1000ms). **Prevention:** Use round timer OCR as game_time timestamp, store both wall_clock_time (frame capture) and game_time (timer), include frame_number for exact ordering, accept ~166ms uncertainty and document it. Timestamp strategy decision in Phase 1 — changing schema after data collection requires reprocessing all matches.

**Additional moderate pitfalls:**
- Stream quality variations (1080p → 720p mid-match) breaking brightness thresholds → Requires adaptive calibration in Phase 2
- Team/map OCR typos ("LOUD" → "L0UD") propagating → Fuzzy matching against whitelist in Phase 1
- Round transition detection failures → Multi-signal detection (score + timer + alive) in Phase 1
- Agent/ultimate CV detection too fragile (<70% accuracy) → Defer to Phase 3 with research flag, may need alternative approach

## Implications for Roadmap

Based on research, suggested phase structure prioritizes **foundation before features** — build reliable state change detection and event storage before attempting complex CV extractions (agents, ultimates).

### Phase 1: Event Detection Foundation
**Rationale:** Core state diffing and event emission logic with zero external dependencies. Easy to test in isolation. Establishes data quality patterns that all later phases depend on.

**Delivers:**
- StateTracker component (score/alive/spike change detection)
- GameState and StateChange dataclasses
- Replay detection (timer regression, alive coherence, score monotonicity)
- State debouncing (3-frame consensus)
- OCR character whitelisting and validation
- Round transition detection (multi-signal: score + timer + alive)
- Unit tests with mock state sequences

**Addresses features:**
- Round result detection (table stakes)
- Kill event detection (table stakes)
- Spike plant/defuse events (table stakes)

**Avoids pitfalls:**
- Pitfall #1: Replay footage (multi-signal validation from day one)
- Pitfall #3: Event storms (debouncing before any events logged)
- Pitfall #5: Timestamp confusion (decision on timestamp strategy upfront)

**Research flag:** None — state diffing is deterministic logic, no external research needed.

### Phase 2: Event Emission & Persistent Storage
**Rationale:** Depends on StateTracker but not on CV pipeline complexity. Can test with mock state changes before full integration.

**Delivers:**
- Event dataclass with typed schema
- EventEmitter component (StateChange → Event transformation)
- EventStore component (JSONL append-only writer)
- Match session management (match_id, start/stop, metadata)
- Integration tests (state → events → file validation)

**Addresses features:**
- Persistent event logging (replaces game_state.json overwriting)
- Match session management (table stakes)

**Avoids pitfalls:**
- Pitfall #11: Overwriting game_state.json (persistent append-only log)
- Pitfall #12: No session management (match_id and map_number metadata)

**Research flag:** None — event sourcing patterns are well-established.

### Phase 3: Pipeline Integration
**Rationale:** Integrates all components with existing VCTVisionEngine. Proves full pipeline works without requiring new CV features yet.

**Delivers:**
- EventPipeline orchestrator
- Refactored GameWatcher (uses pipeline instead of direct processing)
- End-to-end tests (mock frame → event log)
- ROI consolidation (config.py vs vision_engine.py cleanup)

**Addresses features:**
- Full pipeline operational (all table stakes features working)

**Avoids pitfalls:**
- Pitfall #15: Config duplication (single source of truth before building on it)
- Pitfall #14: No graceful degradation (error handling for OCR failures)

**Research flag:** None — integration of existing components.

### Phase 4: Metadata Auto-Detection
**Rationale:** Extends CV capabilities with team/map extraction. Not blocking for core event pipeline (can use placeholder metadata). Moderate complexity requiring OCR tuning.

**Delivers:**
- MetadataExtractor component
- ROI definitions for team names, map name
- OCR preprocessing for text (vs existing digit OCR)
- Majority-vote validation (10-frame consensus)
- Fuzzy matching against team/map whitelists

**Addresses features:**
- Team identification (table stakes)
- Map identification (table stakes)

**Avoids pitfalls:**
- Pitfall #7: Team/map OCR typos (fuzzy matching, validation)

**Research flag:** LOW — May need tuning of OCR preprocessing parameters for team name text, but basic approach is straightforward.

### Phase 5: Economy & Round Classification
**Rationale:** Builds on working pipeline. Requires phase detection state machine to distinguish buy phase vs combat.

**Delivers:**
- Game phase state machine (buy/combat/post-round)
- Economy event emission during buy phase only
- Buy type classification (eco/force/full)
- Round type detection (pistol vs gun rounds)
- Side detection (attacker/defender)

**Addresses features:**
- Economy snapshots (table stakes)
- Round type classification (differentiator)
- Side detection (differentiator)
- First blood (differentiator — derived from kill events)

**Avoids pitfalls:**
- Pitfall #4: Buy/combat conflation (phase state machine first)

**Research flag:** None — economy logic is deterministic once phase detection works.

### Phase 6: Advanced Features (Post-MVP)
**Rationale:** Deferred features requiring either complex CV (agent/ultimate detection) or alternative data sources.

**Delivers (if feasible):**
- Agent composition extraction (template matching with 22-agent library)
- Ultimate status tracking (per-player pixel sampling)
- Alive differential trending
- Momentum streak detection

**Addresses features:**
- Agent compositions (differentiator)
- Ultimate tracking (differentiator)

**Avoids pitfalls:**
- Pitfall #10: Agent/ultimate CV fragility (requires deep research, may pivot to manual entry or API)

**Research flag:** HIGH — Agent/ultimate extraction from broadcast is high-difficulty CV problem. Needs feasibility research with actual VCT frames before committing to implementation. Consider alternatives (manual entry, VCT API, pre-game agent select screen extraction).

### Phase Ordering Rationale

**Dependency-driven sequencing:**
- Phases 1-3 must be sequential: StateTracker → EventEmitter/EventStore → EventPipeline integration
- Phase 4 (metadata) and Phase 5 (economy) can be parallelized or reordered — neither blocks the other
- Phase 6 is post-MVP, explicitly deferred until core pipeline proven

**Risk-based prioritization:**
- Critical pitfalls (replay detection, debouncing, round transitions) addressed in Phase 1 before any data collection
- Moderate pitfalls (overlay versioning, phase conflation) addressed in phases 2-5 before multi-match production use
- High-risk CV features (agent/ultimate) deferred to Phase 6 with research gate

**Incremental validation:**
- Each phase ends with working integration tests
- Phase 3 completes MVP (persistent event logs from live streams)
- Phases 4-5 enhance MVP with metadata and economy
- Phase 6 is optional based on prediction model performance needs

### Research Flags

**Phases needing deeper research during planning:**
- **Phase 6 (Agent/Ultimate Detection):** Complex CV problem with <70% estimated accuracy from broadcast. Needs research on:
  - Template matching with skin variations
  - Pre-game agent select screen extraction (larger, clearer images)
  - VCT API availability for agent comp data
  - Manual entry UX as fallback
  - Cost/benefit analysis: Is agent comp data worth the CV complexity?

**Phases with standard patterns (skip research-phase):**
- **Phase 1:** State diffing is deterministic logic, no domain research needed
- **Phase 2:** Event sourcing is well-established pattern
- **Phase 3:** Integration follows standard orchestrator pattern
- **Phase 4:** OCR extraction similar to existing timer/score (may need parameter tuning but no research)
- **Phase 5:** Economy logic is game mechanics (well-documented in Valorant guides)

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM | EasyOCR, SQLAlchemy, python-statemachine recommended based on training data; requires Context7/official docs verification of versions and Windows compatibility |
| Features | MEDIUM-HIGH | Table stakes features (score, kills, economy, spike) reliably extractable from VCT broadcasts; differentiators (agents, ultimates) require CV validation |
| Architecture | HIGH | Event sourcing, state diffing, append-only logs are proven patterns; component boundaries follow single-responsibility and testability principles |
| Pitfalls | HIGH | Based on existing codebase analysis (config.py, vision_engine.py, backend.py); replay detection and debouncing are known critical issues in esports CV |

**Overall confidence:** MEDIUM-HIGH

Stack recommendations need version verification, but architectural approach is sound. Feature priorities align with CV extraction feasibility (table stakes = high feasibility, differentiators = medium, anti-features = low/impossible).

### Gaps to Address

**Version verification (during Phase 1 setup):**
- Confirm EasyOCR 1.7.x supports Windows GPU (CUDA) with current PyTorch
- Verify SQLAlchemy 2.0.x API stability and migration from 1.4 (if relevant)
- Test python-statemachine 2.1.x on Windows 11

**Empirical tuning (during implementation):**
- Optimal debouncing parameters (3-frame vs 5-frame consensus) — test on actual VCT footage
- OCR preprocessing settings for team names/map (different font than timer/score digits)
- Replay detection threshold tuning (how much timer regression = definite replay?)

**2026 VCT broadcast verification (Phase 1 validation):**
- Cannot confirm overlay format unchanged since training data cutoff (Jan 2025)
- ROI coordinates may be stale if Riot redesigned overlay in 2025-2026
- Test extraction pipeline against live VCT match before multi-match production use

**Agent meta current state (Phase 6 only):**
- Training data from Jan 2025 — agent balance patches since then may shift composition importance
- New agents released? Current roster is ~22 agents per training data
- Only relevant if Phase 6 agent detection is pursued

**Prediction market validation (post-data collection):**
- Research assumes event data will be used for prediction models
- No validation of which features actually improve prediction accuracy
- Be ready to deprioritize low-value features based on model performance

## Sources

### Primary (HIGH confidence)

**Existing codebase analysis:**
- `d:\Git\Val-Prediciton-Model\config.py` — ROI definitions, thresholds, current stack
- `d:\Git\Val-Prediciton-Model\vision_engine.py` — Frame extraction methods, OCR approaches
- `d:\Git\Val-Prediciton-Model\backend.py` — Processing loop, state handling (overwriting game_state.json issue)
- `d:\Git\Val-Prediciton-Model\PROJECT.md` — Project context, constraints, goals

**Established architectural patterns:**
- Event Sourcing Pattern (Martin Fowler) — Append-only event logs, state reconstruction
- State Machine Pattern — State transitions trigger events
- Computer Vision Pipelines — Frame extraction → processing → output separation

### Secondary (MEDIUM confidence)

**Training data (as of Jan 2025):**
- Valorant game mechanics (economy system, round structure, spike mechanics)
- VCT broadcast overlay characteristics (what's visible, what's hidden)
- Python CV ecosystem (OpenCV, pytesseract limitations, EasyOCR capabilities)
- Esports prediction systems (feature engineering, win probability impacts)

**Limitations:**
- Cannot verify VCT broadcast overlay format for 2026 (WebSearch unavailable)
- Cannot verify current agent roster or meta shifts since Jan 2025
- Win probability estimates based on general FPS principles, not Valorant-specific empirical studies

### Tertiary (LOW confidence)

**Requires verification:**
- EasyOCR version 1.7.x Windows GPU support — Check https://github.com/JaidedAI/EasyOCR
- SQLAlchemy 2.0.x API — Check https://docs.sqlalchemy.org/
- python-statemachine 2.1.x — Check https://python-statemachine.readthedocs.io/
- VCT 2026 overlay format — Test against live match or recent VOD

---

**Research completed:** 2026-02-12
**Ready for roadmap:** Yes

**Next step:** Roadmap creation with phase-specific planning. Phase 1 (Event Detection Foundation) has no research flags and can begin implementation immediately. Phase 6 (Agent/Ultimate Detection) requires feasibility research before commitment.
