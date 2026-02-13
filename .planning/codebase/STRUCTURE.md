# Codebase Structure

**Analysis Date:** 2026-02-12

## Directory Layout

```
Val-Prediciton-Model/
├── backend.py                  # Live stream monitoring & continuous state extraction
├── dashboard.py                # Streamlit UI for VOD analysis & prediction display
├── vision_engine.py            # Standalone VCT vision engine (reusable reference implementation)
├── config.py                   # Coordinate mappings & detection thresholds for 1920x1080 layout
├── requirements.txt            # Python package dependencies
└── .planning/
    └── codebase/              # GSD documentation directory
```

## Directory Purposes

**Root Directory:**
- Purpose: Main application code and configuration
- Contains: Entry point scripts, shared configuration, vision engine implementations
- Key files: `backend.py`, `dashboard.py`, `vision_engine.py`, `config.py`

**.planning/codebase/:**
- Purpose: Architecture and design documentation for GSD planning tools
- Contains: Codebase analysis documents (ARCHITECTURE.md, STRUCTURE.md, etc.)
- Auto-generated: Yes (by /gsd:map-codebase command)

## Key File Locations

**Entry Points:**
- `d:/Git/Val-Prediciton-Model/backend.py`: Continuous live stream monitor (run via `python backend.py`)
- `d:/Git/Val-Prediciton-Model/dashboard.py`: Interactive web UI (run via `streamlit run dashboard.py`)

**Configuration:**
- `d:/Git/Val-Prediciton-Model/config.py`: ROI coordinate system, color thresholds, team avatar positions
- `d:/Git/Val-Prediciton-Model/requirements.txt`: Package versions and external dependencies

**Core Logic:**
- `d:/Git/Val-Prediciton-Model/vision_engine.py`: Standalone VCTVisionEngine class with core vision algorithms
- `d:/Git/Val-Prediciton-Model/backend.py`: GameWatcher class for stream handling and frame extraction
- `d:/Git/Val-Prediciton-Model/dashboard.py`: VCTVisionEngine (embedded), load_model (ML), and Streamlit UI

**Testing:**
- Not present in codebase (no test directory)

## Naming Conventions

**Files:**
- snake_case.py for Python modules
- Examples: `backend.py`, `vision_engine.py`, `config.py`, `dashboard.py`

**Classes:**
- PascalCase for class names
- Examples: GameWatcher, VCTVisionEngine
- Pattern: Descriptive noun-verb pairs (Watcher, Engine)

**Functions and Methods:**
- snake_case for function and method names
- Action-oriented verbs with clear intent
- Examples: connect_stream, process_frame, analyze_vct_frame, check_alive_status, read_number, preprocess_image

**Variables:**
- snake_case for local and instance variables
- Descriptive names indicating data type or purpose
- Examples: roi_score_left, alive_count, team_a_alive, current_stats

**Constants:**
- UPPER_SNAKE_CASE for configuration constants
- Examples: TESSERACT_CMD, ROI_TIMER, SPIKE_RED_LOWER, LEFT_SIDEBAR_X

**Module-Level Variables:**
- lowercase_with_underscores
- Examples: frame_count, stream_url, output_file

## Where to Add New Code

**New Vision Detection Feature:**
- Primary code: Add method to VCTVisionEngine class in `d:/Git/Val-Prediciton-Model/vision_engine.py` or `d:/Git/Val-Prediciton-Model/dashboard.py`
- Configuration: Add ROI coordinates to `d:/Git/Val-Prediciton-Model/config.py` if coordinate-based
- Example: New detect_bomb_timer() method for timer extraction

**New Prediction Model:**
- Primary code: Create new model function in `d:/Git/Val-Prediciton-Model/dashboard.py` (or separate module if complex)
- Training data: Expand synthetic data generation in load_model() or add real dataset pipeline
- Integration: Replace model.predict_proba() calls in dashboard UI with new model inference

**New Feature Integration:**
- Vision extraction: Add new method to VCTVisionEngine.analyze_vct_frame() return dict
- Dashboard display: Add new metric to col_data section in dashboard.py main page
- Backend persistence: Add field to process_frame() return dict and JSON output

**Utilities & Helpers:**
- Shared image processing: Add to VCTVisionEngine class methods (preprocess_image, read_number already serve this role)
- New external integrations: Create in root directory as separate module (e.g., `stream_handler.py`)

## Special Directories

**.planning/codebase/:**
- Purpose: Contains GSD analysis documents (ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, CONCERNS.md)
- Generated: Yes, by /gsd:map-codebase command
- Committed: Yes, documentation should be version controlled
- Note: Non-code directory used for architecture and planning references

## File Organization Summary

**By Responsibility:**

| File | Responsibility | Key Classes/Functions |
|------|---------------|-----------------------|
| `config.py` | Configuration & coordinates | ROI_TIMER, TEAM_A_AVATARS, SPIKE_RED_LOWER, TESSERACT_CMD |
| `vision_engine.py` | Standalone vision library | VCTVisionEngine (8+ methods) |
| `backend.py` | Live stream monitoring | GameWatcher.connect_stream(), process_frame(), run() |
| `dashboard.py` | Interactive UI + embedded vision | load_model(), VCTVisionEngine, Streamlit UI components |
| `requirements.txt` | Dependency specification | streamlit, opencv-python, pytesseract, scikit-learn, etc. |

---

*Structure analysis: 2026-02-12*
