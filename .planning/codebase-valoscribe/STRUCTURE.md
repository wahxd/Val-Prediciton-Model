# Codebase Structure

**Analysis Date:** 2026-02-13

## Directory Layout

```
valoscribe/
├── src/valoscribe/          # Main package
│   ├── commands/            # CLI command implementations
│   ├── config/              # HUD coordinate configs
│   ├── detectors/           # Computer vision detectors
│   ├── orchestration/       # State management and orchestration
│   ├── scraper/             # VLR.gg metadata scraper
│   ├── templates/           # Template images for matching
│   ├── types/               # Pydantic models and type definitions
│   ├── utils/               # Logging, OCR utilities
│   └── video/               # Video reading and YouTube downloading
├── scripts/                 # Batch processing scripts
├── tests/                   # Unit and integration tests
├── champs2025_processed_vods/  # Processed output data
├── pyproject.toml           # Project configuration
└── README.md                # Documentation
```

## Directory Purposes

**src/valoscribe/commands/**
- Purpose: CLI command implementations using Typer
- Contains: Command groups (detect, extract, orchestrate, scrape), utility commands
- Key files:
  - `orchestrate.py` - Main VOD processing command
  - `detect.py` - Individual detector testing commands
  - `scrape.py` - VLR.gg scraping command
  - `utils.py` - Download, read, crop, analyze utilities

**src/valoscribe/config/**
- Purpose: HUD coordinate configuration files
- Contains: JSON files mapping UI element locations for different tournament broadcasts
- Key files:
  - `champs2025.json` - VCT Champions 2025 Paris broadcast HUD layout

**src/valoscribe/detectors/**
- Purpose: Computer vision detection components
- Contains: Template matchers, OCR detectors, cropper utility
- Key files:
  - `cropper.py` - HUD region extraction from frames
  - `template_agent_detector.py` - Agent icon matching (preround scoreboard)
  - `active_round_agent_detector.py` - Agent icon matching (in-round HUD)
  - `template_health_detector.py` - Health number template matching
  - `template_armor_detector.py` - Armor number template matching
  - `template_score_detector.py` - Score digit template matching
  - `template_timer_detector.py` - Timer digit template matching
  - `template_spike_detector.py` - Spike planted indicator detection
  - `killfeed_detector.py` - Killfeed agent icon matching
  - `ability_detector.py` - Ability charge blob detection (in-round)
  - `preround_ability_detector.py` - Ability charge blob detection (preround)
  - `ultimate_detector.py` - Ultimate charge blob detection (in-round)
  - `preround_ultimate_detector.py` - Ultimate charge blob detection (preround)

**src/valoscribe/orchestration/**
- Purpose: State management, event generation, output writing
- Contains: Orchestrators, state trackers, validators, managers
- Key files:
  - `game_state_manager.py` - Main orchestrator coordinating entire pipeline
  - `phase_detector.py` - Phase state machine (PREROUND/ACTIVE_ROUND/POST_ROUND)
  - `detector_registry.py` - Factory for detector instances
  - `player_state_tracker.py` - Per-player state tracking
  - `round_manager.py` - Score and round tracking
  - `event_collector.py` - Event aggregation and deduplication
  - `state_validator.py` - State transition validation
  - `timer_manager.py` - Game/spike/post-round timer tracking
  - `output_writer.py` - CSV/JSONL file writing

**src/valoscribe/scraper/**
- Purpose: Match metadata extraction from VLR.gg
- Contains: Web scraper using BeautifulSoup + Playwright
- Key files:
  - `vlr_scraper.py` - VLR.gg match page scraper

**src/valoscribe/templates/**
- Purpose: Template images for template matching
- Contains: Subdirectories for each template type
- Key subdirectories:
  - `preround_agents/` - Agent portrait images (attack/defense variants)
  - `killfeed_agents/` - Killfeed agent icons
  - `score_digits/` - Score digit templates (0-9)
  - `timer_digits/` - Timer digit templates (0-9, colon)

**src/valoscribe/types/**
- Purpose: Type definitions and data models
- Contains: Pydantic models for structured data
- Key files:
  - `detections.py` - Detection result models (AgentInfo, HealthInfo, KillfeedAgentDetection, etc.)
  - `video.py` - Video frame metadata (FrameInfo)

**src/valoscribe/utils/**
- Purpose: Shared utilities
- Contains: Logging, OCR engine
- Key files:
  - `logger.py` - Logger factory and configuration
  - `ocr.py` - Tesseract OCR wrapper

**src/valoscribe/video/**
- Purpose: Video input/output operations
- Contains: Frame reading, YouTube downloading
- Key files:
  - `reader.py` - VideoReader iterator for frame-by-frame processing
  - `youtube.py` - YouTube VOD downloader (yt-dlp wrapper)

**scripts/**
- Purpose: Batch processing automation
- Contains: Shell scripts for processing multiple matches
- Key files:
  - `process_vlr_series.sh` - Process entire series from VLR URL
  - `process_all_series_parallel.sh` - Parallel batch processing

**tests/**
- Purpose: Unit and integration tests
- Contains: Pytest test files
- Key files:
  - `test_detectors/test_ability_detector.py` - Ability detector tests

**champs2025_processed_vods/**
- Purpose: Output directory for processed VOD data
- Contains: Match directories with metadata and output files
- Generated: Yes
- Committed: No (data files, not code)

## Key File Locations

**Entry Points:**
- `src/valoscribe/__main__.py` - CLI application entry point
- `src/valoscribe/commands/orchestrate.py` - Main processing command

**Configuration:**
- `pyproject.toml` - Package dependencies, build config, tool settings (ruff, mypy)
- `src/valoscribe/config/champs2025.json` - HUD coordinate configuration

**Core Logic:**
- `src/valoscribe/orchestration/game_state_manager.py` - Central orchestrator (1787 lines)
- `src/valoscribe/orchestration/phase_detector.py` - Phase state machine (185 lines)
- `src/valoscribe/detectors/cropper.py` - HUD region extraction

**Testing:**
- `tests/test_detectors/test_ability_detector.py` - Detector unit tests

## Naming Conventions

**Files:**
- Snake_case for all Python files: `game_state_manager.py`, `template_agent_detector.py`
- Detector files prefixed by type: `template_*.py` (template matching), `preround_*.py` (preround-specific), `*_detector.py` (general pattern)

**Directories:**
- Lowercase, singular or plural based on content: `commands/`, `detectors/`, `orchestration/`, `utils/`

**Classes:**
- PascalCase: `GameStateManager`, `PhaseDetector`, `PlayerStateTracker`, `VideoReader`
- Detector suffix for detection components: `TemplateAgentDetector`, `KillfeedDetector`
- Info suffix for Pydantic models: `AgentInfo`, `HealthInfo`, `TimerInfo`

**Functions:**
- Snake_case: `detect_phase()`, `process_frame()`, `validate_kill_event()`
- Private methods prefixed with underscore: `_update_health()`, `_validate_ability()`

## Where to Add New Code

**New Detector:**
- Implementation: `src/valoscribe/detectors/[detector_name]_detector.py`
- Registration: Add to `DetectorRegistry._init_*_detectors()` method in `src/valoscribe/orchestration/detector_registry.py`
- Tests: `tests/test_detectors/test_[detector_name]_detector.py`

**New Detection Result Type:**
- Implementation: `src/valoscribe/types/detections.py` (add Pydantic model)

**New Orchestration Component:**
- Implementation: `src/valoscribe/orchestration/[component_name].py`
- Integration: Import and initialize in `GameStateManager.__init__()` or `GameStateManager._init_components()`

**New CLI Command:**
- Implementation: `src/valoscribe/commands/[command_group].py` (add command function)
- Registration: Add to `src/valoscribe/__main__.py` (either as command group via `app.add_typer()` or individual command via `app.command()`)

**New Event Type:**
- Event emission: Add to orchestration logic in `GameStateManager._process_*()` methods
- Event writing: No code change needed (EventCollector handles generic events)

**New HUD Config:**
- Configuration: Add new JSON file to `src/valoscribe/config/[tournament_name].json`
- Usage: Pass `--config-path` to `orchestrate process-vod` command

## Special Directories

**src/valoscribe/templates/**
- Purpose: Template images for OpenCV template matching
- Generated: No (manually created/extracted)
- Committed: Yes (required for detection)

**champs2025_processed_vods/**
- Purpose: Output directory for processed match data
- Generated: Yes (by processing pipeline)
- Committed: No (data directory, excluded in .gitignore)

**__pycache__/**
- Purpose: Python bytecode cache
- Generated: Yes (by Python interpreter)
- Committed: No (excluded in .gitignore)

---

*Structure analysis: 2026-02-13*
