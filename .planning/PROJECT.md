# Valorant Match Event Logger

## What This Is

A live event data collection pipeline that watches VCT (Valorant Champions Tour) broadcasts via computer vision, detects in-game state changes, and logs them as timestamped events. Each match produces a structured event log capturing kills, round results, spike events, economy shifts, agent compositions, and ultimates. This data feeds a future prediction model for identifying mispriced Valorant match contracts on Polymarket/Kalshi.

## Core Value

Reliable, timestamped event logs from live VCT matches — consistent enough across multiple matches to train a prediction model.

## Requirements

### Validated

- ✓ Extract game scores from VCT broadcast frames via OCR — existing
- ✓ Detect alive player counts per team via color/brightness sampling — existing
- ✓ Detect spike plant status via HSV color detection — existing
- ✓ Read round timer via OCR — existing
- ✓ Watch live Twitch/YouTube streams via streamlink at 6fps — existing
- ✓ ROI coordinate system for 1920x1080 VCT broadcast layout — existing
- ✓ Basic win probability prediction via logistic regression — existing
- ✓ Streamlit dashboard for VOD frame analysis — existing

### Active

- [ ] Detect state changes between frames and emit discrete events (kills, round ends, spike plant/defuse)
- [ ] Store timestamped event logs persistently per match (replace overwritten game_state.json)
- [ ] Auto-detect team names from broadcast overlay
- [ ] Auto-detect map name from broadcast overlay
- [ ] Extract agent compositions (which agents each team is playing) via CV
- [ ] Detect ultimate ability status/availability per team via CV
- [ ] Extract economy data per team and log economy events (eco/force/full buy shifts)
- [ ] Match session management (start/stop, match metadata, multi-map series support)
- [ ] Extensible event type system — easy to add new event types over time
- [ ] Run reliably across multiple VCT matches with consistent, comparable output

### Out of Scope

- Contract price data integration (Polymarket/Kalshi) — deferred to future milestone
- Prediction model training — deferred, this milestone is data collection only
- Player-level tracking (individual player stats) — design for it, build team-level first
- Non-VCT broadcast support — VCT-only for consistent overlay layout
- Real-time trading signals — future milestone after model is built
- Mobile or web deployment — local tool for now

## Context

- Existing codebase has a working vision pipeline (VCTVisionEngine) that extracts scores, alive counts, spike status, timer, and economy from 1920x1080 VCT broadcast frames
- Backend (GameWatcher) watches live streams via streamlink, processes at 6fps (every 10th frame from 60fps)
- Current system is stateless — each frame analyzed independently, state written to game_state.json (overwritten)
- The key gap is going from "frame state extraction" to "event detection and persistent logging"
- VCT broadcasts have a consistent overlay layout, making CV extraction reliable
- Config.py holds all ROI coordinates and color thresholds — single resolution (1920x1080) assumed
- Prediction model currently uses synthetic data — real match event data is the bottleneck

## Constraints

- **Data source**: Computer vision on VCT broadcast streams only — no game API access
- **Resolution**: 1920x1080 VCT broadcast layout (ROI coordinates are hardcoded for this)
- **Tech stack**: Python ecosystem (OpenCV, pytesseract, streamlink, scikit-learn) — extend, don't replace
- **Platform**: Windows 11 development environment (Tesseract-OCR binary dependency)
- **Storage**: Local-first — no cloud infrastructure for this milestone

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Event-based logging (not continuous snapshots) | Only state changes matter for prediction — kills, round ends, economy shifts. Reduces noise and storage. | — Pending |
| Team-level granularity first | Simpler CV extraction, extensible to player-level later. Team aggregates may be sufficient for initial model. | — Pending |
| VCT broadcasts only | Consistent overlay layout makes CV reliable. Expanding to other formats adds complexity without value yet. | — Pending |
| Manual contract price tracking (for now) | Focus engineering effort on game data pipeline. Prices can be manually noted or added later via API. | — Pending |
| Auto-detect teams/map from broadcast | Reduces manual input friction when watching multiple matches. Essential for consistent match labeling. | — Pending |

---
*Last updated: 2026-02-12 after initialization*
