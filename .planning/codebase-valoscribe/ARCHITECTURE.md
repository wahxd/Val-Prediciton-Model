# Architecture

**Analysis Date:** 2026-02-13

## Pattern Overview

**Overall:** Pipeline Architecture with State Machine Orchestration

**Key Characteristics:**
- Frame-by-frame video processing pipeline with phase-based routing
- Central orchestrator (GameStateManager) coordinates all detectors and state trackers
- Event-driven output with deduplication and validation
- Template matching + OCR hybrid computer vision approach

## Layers

**CLI Commands Layer:**
- Purpose: User interface and workflow orchestration
- Location: `src/valoscribe/commands/`
- Contains: Typer CLI commands organized by domain (detect, extract, orchestrate, scrape, utils)
- Depends on: Orchestration layer, detectors, video readers, scrapers
- Used by: End users via `valoscribe` CLI

**Orchestration Layer:**
- Purpose: Coordinate frame processing, manage game state, emit events
- Location: `src/valoscribe/orchestration/`
- Contains: GameStateManager, PhaseDetector, RoundManager, PlayerStateTracker, EventCollector, StateValidator, TimerManager, OutputWriter
- Depends on: Detectors, types, utils
- Used by: CLI commands (primarily `orchestrate process-vod`)

**Detection Layer:**
- Purpose: Extract information from video frames
- Location: `src/valoscribe/detectors/`
- Contains: Template-based detectors (agents, health, armor, score, spike, timer), OCR detectors (killfeed), ability/ultimate detectors, Cropper utility
- Depends on: Types (detection result models), utils (OCR, logger), config (HUD coordinates)
- Used by: Orchestration layer (via DetectorRegistry)

**Video I/O Layer:**
- Purpose: Read video frames, download VODs
- Location: `src/valoscribe/video/`
- Contains: VideoReader (frame-by-frame iterator), FileVideoSource, YouTube downloader
- Depends on: OpenCV, yt-dlp, types
- Used by: Orchestration layer, CLI commands

**Data Scraping Layer:**
- Purpose: Extract match metadata from VLR.gg
- Location: `src/valoscribe/scraper/`
- Contains: VLR scraper (BeautifulSoup + Playwright)
- Depends on: requests, BeautifulSoup, Playwright
- Used by: CLI commands (`scrape-vlr`)

**Types Layer:**
- Purpose: Define data structures and validation
- Location: `src/valoscribe/types/`
- Contains: Pydantic models for detections (AgentInfo, HealthInfo, KillfeedAgentDetection, etc.), video frame info
- Depends on: Pydantic
- Used by: All layers

**Utilities Layer:**
- Purpose: Shared cross-cutting concerns
- Location: `src/valoscribe/utils/`
- Contains: Logger, OCR engine (Tesseract wrapper)
- Depends on: pytesseract, logging
- Used by: All layers

## Data Flow

**VOD Processing Flow (Main Pipeline):**

1. **Initialization** - CLI command (`orchestrate process-vod`) receives video path, VLR metadata, config
2. **Setup** - GameStateManager initializes DetectorRegistry (all detectors), RoundManager (team/score tracking), TimerManager, EventCollector, OutputWriter
3. **Frame Iteration** - VideoReader yields frames at specified FPS (default 4fps)
4. **Phase Detection** - PhaseDetector analyzes frame (timer, score, spike, credits) → determines Phase (PREROUND, ACTIVE_ROUND, POST_ROUND, NON_GAME)
5. **Phase Routing:**
   - **PREROUND** → Detect agents (initialize PlayerStateTrackers on first preround), detect abilities/ultimates, check score changes
   - **ACTIVE_ROUND** → Detect player states (health, armor, abilities, ultimates), detect killfeed, validate kills, emit events
   - **POST_ROUND** → Same as active round + detect score changes, emit round_end events
6. **State Validation** - StateValidator validates ability/ultimate changes against game rules (max charges, rechargeability, Sage revival logic)
7. **Event Collection** - EventCollector aggregates events with deduplication (5-second window for killfeed)
8. **Output Writing** - OutputWriter writes frame states (CSV) and events (JSONL) to disk
9. **Finalization** - On video end, infer missing round_end/match_end events if needed

**State Management:**
- PlayerStateTracker maintains current/previous state for each of 10 players
- RoundManager tracks scores, round numbers, team sides (attack/defense swaps at halftime)
- TimerManager tracks game timer, spike timer, post-round timer
- EventCollector maintains event log with deduplication

## Key Abstractions

**GameStateManager:**
- Purpose: Central orchestrator for entire video processing pipeline
- Examples: `src/valoscribe/orchestration/game_state_manager.py`
- Pattern: Facade pattern - single entry point coordinating all subsystems

**PhaseDetector:**
- Purpose: State machine for detecting game phases
- Examples: `src/valoscribe/orchestration/phase_detector.py`
- Pattern: State pattern - phase enum with transition logic

**DetectorRegistry:**
- Purpose: Factory/Registry for all CV detectors with lazy initialization
- Examples: `src/valoscribe/orchestration/detector_registry.py`
- Pattern: Service locator - centralized access to detector instances

**PlayerStateTracker:**
- Purpose: Per-player state machine tracking health, abilities, alive/dead status
- Examples: `src/valoscribe/orchestration/player_state_tracker.py`
- Pattern: State tracker with revival detection (3-frame threshold), death detection (2-frame threshold)

**Cropper:**
- Purpose: Extract HUD regions from frames based on JSON config
- Examples: `src/valoscribe/detectors/cropper.py`
- Pattern: Configuration-driven coordinate mapping (loads `config/champs2025.json`)

**Template Detectors:**
- Purpose: Match template images against HUD regions
- Examples: `src/valoscribe/detectors/template_agent_detector.py`, `template_health_detector.py`, `template_score_detector.py`
- Pattern: Template matching with OpenCV (cv2.matchTemplate) + confidence thresholding

## Entry Points

**CLI Entry:**
- Location: `src/valoscribe/__main__.py`
- Triggers: Invoked via `valoscribe` command or `python -m valoscribe`
- Responsibilities: Initialize Typer app, register command groups (detect, extract, orchestrate), dispatch to command handlers

**Main Processing Command:**
- Location: `src/valoscribe/commands/orchestrate.py::process_vod()`
- Triggers: `valoscribe orchestrate process-vod <video> <metadata>`
- Responsibilities: Initialize GameStateManager, iterate frames via VideoReader, handle keyboard input (--show, --step modes), print events, generate outputs

**Batch Processing Script:**
- Location: `scripts/process_vlr_series.sh`
- Triggers: Called with VLR.gg match URL
- Responsibilities: Scrape metadata, download VOD, process each map, validate outputs

## Error Handling

**Strategy:** Defensive logging with graceful degradation

**Patterns:**
- Detection failures return None (not exceptions) - orchestrator handles missing data
- Validation rejects invalid detections (e.g., killfeed validation requires victim to be dead)
- Logging at DEBUG/INFO/WARNING levels for traceability
- Missing events inferred retroactively during finalization (round_end, match_end)
- Grace periods prevent false positives (2-second post-round-start grace for death detection)

## Cross-Cutting Concerns

**Logging:**
- Logger factory in `utils/logger.py`
- Per-module loggers via `get_logger(__name__)`
- DEBUG logging for detection details, INFO for major events, WARNING for anomalies

**Validation:**
- StateValidator validates player state transitions (ability usage, revivals)
- Kill validation checks team composition, victim alive status, no duplicate kills
- Score validation ensures monotonic increase, win conditions (13+ rounds, 2-round lead)

**Authentication:**
- Not applicable (public data from YouTube/VLR.gg, no auth required)

---

*Architecture analysis: 2026-02-13*
