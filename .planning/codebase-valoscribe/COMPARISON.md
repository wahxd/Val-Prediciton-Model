# Valoscribe vs Val-Prediction-Model: Comparison & Recommendation

**Date:** 2026-02-13

## Executive Summary

Valoscribe is a mature, production-proven VOD analysis pipeline that solves ~80% of what our project needs. It has real processed data from 71 Champions 2025 maps and player-level detection granularity far beyond our current team-level approach. **Recommendation: Adopt Valoscribe as the foundation and retrofit for live streaming**, porting our unique innovations (replay detection, debouncing) into it.

---

## Side-by-Side Comparison

| Dimension | Val-Prediction-Model (Ours) | Valoscribe (External) |
|-----------|---------------------------|----------------------|
| **Maturity** | Phase 1 of 4 complete, 12 source files | Production-ready, 47+ source files |
| **Detection** | Team-level only (scores, alive counts, timer, spike) | Player-level (health, armor, abilities, ultimates, agents, killfeed, credits) |
| **Detectors** | 0 CV detectors (relies on existing VCTVisionEngine) | 14+ detectors (template matching + OCR hybrid) |
| **Input** | Live streams via streamlink @ 6fps | YouTube VODs via yt-dlp @ 4fps |
| **Replay Detection** | Yes (dual-condition: timer regression + alive resets) | **No** (contributes to 13% failure rate) |
| **Debouncing** | 3-frame consensus on all tracked fields | Per-detector thresholds (2-frame death, 3-frame revival) |
| **Event Types** | kill, round_start, round_end, spike_plant/defuse/detonate, timeout | kill (with killer/victim/weapon), round_start/end, ability_used, ultimate_used, spike_plant, match_start/end |
| **Output** | Planned JSONL (not built yet) | JSONL events + CSV frame states (working) |
| **Metadata** | Planned auto-detection (Phase 4) | VLR.gg scraper (teams, players, agents, maps, starting sides) |
| **Real Data** | None yet | 71 processed maps, 200-850 events/map, 87% validation rate |
| **Tests** | 65 unit tests | Detector unit tests + validation scripts |
| **Architecture** | StateTracker -> EventEmitter -> (future store) | GameStateManager -> DetectorRegistry -> EventCollector -> OutputWriter |
| **Tech Stack** | Python, Pydantic, structlog, pytest | Python, OpenCV, Pydantic, pytesseract, Typer, yt-dlp, BeautifulSoup |

## What Valoscribe Does Better

1. **Player-level detection** -- Tracks all 10 players individually (health, armor, abilities, ultimate charge, credits, alive/dead). Strictly superior to our team-level aggregates for prediction model training.

2. **Template matching system** -- 14+ specialized detectors with agent portrait templates for both attack/defense sides. Handles mirror compositions, agent identification, and killfeed parsing.

3. **Proven accuracy** -- 62/71 maps (87%) pass all validation checks on real Champions 2025 data. Not theoretical -- actual processed match data exists and can be used immediately for model training.

4. **Rich event data** -- Kill events include killer name, victim name, agent attribution, headshot status. Our kills only track "left team lost a player."

5. **VLR.gg integration** -- Automatic metadata scraping (teams, players, agents, maps, VOD URLs, starting sides). We planned this for Phase 4; they have it working.

6. **CLI tooling** -- Full Typer CLI with detect/extract/orchestrate/scrape commands, batch processing scripts, individual detector testing.

7. **Existing dataset** -- Processed data from VCT Champions 2025 is immediately available for prediction model training without writing any new code.

## What Our Project Does Better

1. **Replay detection** -- Our ReplayDetector uses dual-condition detection (timer regression + alive count resets). Valoscribe has NO replay detection, and it's their single biggest source of errors (9/71 map failures).

2. **Debouncing** -- Our 3-frame consensus approach is clean and universal. Valoscribe uses ad-hoc per-detector thresholds. Our approach would improve their detection stability.

3. **Designed for live** -- Our architecture assumes live stream input via streamlink. Valoscribe assumes downloaded VOD files. Live support is essential for our prediction model use case (real-time Polymarket/Kalshi pricing).

4. **Crash-safe storage design** -- Our Phase 2 plans flush-after-each-event JSONL storage. Valoscribe's OutputWriter buffers and writes at end. For live use, crash safety matters.

5. **Event schema design** -- Our frozen dataclasses with full state snapshots per event are cleaner for ML consumption than Valoscribe's event format.

## What Neither Project Has

- Economy analysis (eco/force/full buy classification)
- Weapon identification in kill events
- Multi-tournament HUD config library
- Real-time processing optimization
- Prediction model training pipeline
- Contract price data integration (Polymarket/Kalshi)

---

## Recommendation: Adopt Valoscribe + Retrofit

### Why

1. **Valoscribe already solved the hard CV problems.** Template matching, agent detection, killfeed parsing, HUD coordinate calibration -- these took significant engineering effort and are proven on real data.

2. **Real data is the bottleneck.** Our prediction model can't train without match event data. Valoscribe has 71 maps of processed data ready to use *today*.

3. **Player-level >> team-level.** Our team-level approach was explicitly chosen for simplicity, but Valoscribe proves player-level is achievable. More granular data = better prediction model.

4. **Our unique innovations port easily.** ReplayDetector and StateTracker consensus logic are self-contained modules that slot cleanly into Valoscribe's orchestration pipeline.

5. **Remaining work shifts from "build detectors" to "add live support."** This is a smaller, more focused engineering task.

### What We'd Port FROM Our Project INTO Valoscribe

| Component | What It Does | Where It Goes in Valoscribe |
|-----------|-------------|---------------------------|
| ReplayDetector | Detects broadcast replays via timer regression + alive resets | `orchestration/replay_detector.py` (new) -- called by GameStateManager before event emission |
| StateTracker consensus | 3-frame debouncing for stable state detection | Could enhance PhaseDetector and state validation logic |
| Event schema philosophy | Frozen dataclasses with full state snapshots | Enhance EventCollector output format for ML consumption |
| Crash-safe JSONL storage | Flush-after-each-event persistence | Replace/enhance OutputWriter for live streaming use |

### What We'd Build NEW in Valoscribe

| Feature | Purpose | Scope |
|---------|---------|-------|
| Live stream input | streamlink integration replacing yt-dlp VOD input | New `video/stream.py` module |
| Session management | Start/stop match sessions, multi-map series | New `orchestration/session_manager.py` |
| Real-time optimization | Frame skipping for stable states, reduced processing | Modify GameStateManager frame loop |
| Prediction model pipeline | Feature extraction from event logs -> model training | New `ml/` module |

### What We'd Abandon

- Our Phase 1 source code (superseded by Valoscribe's richer detection)
- Our current ROADMAP phases 2-4 (restructured around Valoscribe integration)
- Team-level-only approach (Valoscribe gives us player-level for free)

---

## Impact on Milestones

### Current Roadmap (Would Be Replaced)

1. ~~Event Detection Foundation~~ (done, but superseded)
2. ~~Event Storage & Session Management~~
3. ~~Pipeline Integration~~
4. ~~Metadata Auto-Detection~~

### Proposed New Roadmap

**Phase 1: Valoscribe Integration & Live Stream Support**
- Fork/import Valoscribe into our project
- Add streamlink live stream input (new VideoSource)
- Integrate ReplayDetector into GameStateManager
- Validate detection works on live VCT stream frames
- *Unblocks everything else*

**Phase 2: Session Management & Crash-Safe Storage**
- Add match session lifecycle (start/stop/metadata)
- Implement flush-after-each-event JSONL storage
- Add multi-map series support (BO3/BO5)
- Port debouncing improvements
- *Produces reliable live match event logs*

**Phase 3: Prediction Model Training**
- Feature extraction from Valoscribe's existing 71-map dataset
- Train initial model (logistic regression -> gradient boosting)
- Validate model on held-out matches
- Iterate on feature engineering
- *First working prediction model*

**Phase 4: Real-Time Prediction Pipeline**
- Connect live event stream to trained model
- Real-time win probability updates during matches
- Polymarket/Kalshi price comparison interface
- Dashboard for live monitoring
- *End goal achieved*

### Key Advantage of New Roadmap

- **Phase 3 can start immediately** using Valoscribe's existing processed data -- no need to wait for live stream support to begin model training.
- Phases 1-2 (engineering) and Phase 3 (data science) can run in parallel.

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Valoscribe HUD config doesn't work for 2026 VCT | Medium | High | Test against current broadcast ASAP; HUD configs are JSON and adjustable |
| Live stream processing too slow (real-time constraint) | Medium | High | Frame skipping, GPU acceleration, reduce detector count for live mode |
| Valoscribe codebase too complex to modify | Low | Medium | Well-organized architecture; changes are additive (new modules), not invasive |
| Valoscribe author's code diverges from our fork | Low | Low | Our use case (live + prediction) diverges from their use case (batch analytics) |
| 71-map dataset insufficient for model training | Medium | Medium | Continue collecting data via live stream; augment with manual labeling |

---

## Decision Needed

**Option A: Adopt Valoscribe (Recommended)**
- Rewrite roadmap around Valoscribe integration
- Start model training on existing data immediately
- Retrofit live stream support
- Higher ceiling, faster to usable prediction model

**Option B: Continue Current Path**
- Finish our Phase 2-4 roadmap as planned
- Build all detection from scratch (team-level only)
- Slower path to prediction model
- More control, less external dependency

**Option C: Hybrid -- Use Valoscribe Data Only**
- Don't adopt codebase, just use processed data for model training
- Continue building our own live pipeline
- Best of both worlds but duplicate engineering effort

---
*Analysis complete: 2026-02-13*
