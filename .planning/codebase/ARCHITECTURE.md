# Architecture

**Analysis Date:** 2026-02-12

## Pattern Overview

**Overall:** Three-Tier Pipeline Architecture (Vision → Analysis → Prediction)

**Key Characteristics:**
- Modular separation between computer vision, game state extraction, and ML prediction
- Real-time streaming architecture with frame-based processing
- Dual deployment modes: batch processing (dashboard) and continuous monitoring (backend watcher)
- Stateless frame analysis with JSON state serialization for inter-process communication

## Layers

**Vision Layer (Computer Vision):**
- Purpose: Extract game state information from raw video frames using OCR and color detection
- Location: `d:/Git/Val-Prediciton-Model/vision_engine.py`, `d:/Git/Val-Prediciton-Model/dashboard.py` (VCTVisionEngine class)
- Contains: Image preprocessing, OCR digit reading, color-based detection (alive players, spike status), ROI cropping
- Depends on: opencv-python, pytesseract, numpy
- Used by: Backend stream watcher and dashboard UI

**Processing Layer (Frame Analysis):**
- Purpose: Convert visual data into structured game state statistics
- Location: `d:/Git/Val-Prediciton-Model/backend.py` (GameWatcher class), `d:/Git/Val-Prediciton-Model/vision_engine.py` (analyze methods)
- Contains: Frame processing pipelines, state aggregation, economic calculations, alive player counting
- Depends on: Vision layer, config module
- Used by: Prediction layer and frontend dashboard

**Prediction Layer (Machine Learning):**
- Purpose: Calculate match outcome probabilities based on extracted game state features
- Location: `d:/Git/Val-Prediciton-Model/dashboard.py` (load_model function, LogisticRegression)
- Contains: Model training on synthetic data, feature engineering, probability calculations
- Depends on: Processing layer outputs, scikit-learn
- Used by: Streamlit dashboard for display

**Configuration Layer:**
- Purpose: Centralize coordinate mappings and hardcoded parameters for different resolutions/layouts
- Location: `d:/Git/Val-Prediciton-Model/config.py`
- Contains: ROI coordinates (timer, spike, scores), team avatar pixel positions, color thresholds for HSV detection
- Depends on: None
- Used by: Vision and processing layers

## Data Flow

**Live Stream Monitoring (backend.py):**

1. GameWatcher.connect_stream() → Resolves Twitch/YouTube URL to stream URL via streamlink
2. Frame capture loop → Reads frames from cv2.VideoCapture at 60fps, downsamples to 6fps (every 10th frame)
3. process_frame() → Applies vision engine to extract: timer text (OCR), spike status (color detection), alive player counts (brightness sampling)
4. JSON serialization → Atomically writes game_state.json for dashboard consumption

**Dashboard Analysis (dashboard.py):**

1. File upload → User uploads VOD file (.mp4, .jpg, .png) via streamlit file uploader
2. Frame selection → Slider selects specific frame from video for analysis
3. VCTVisionEngine.analyze() → Extracts score, alive counts, spike status, calculates score differential
4. Feature engineering → Assembles feature vector [score_diff, alive_diff, spike_planted]
5. Prediction → LogisticRegression.predict_proba() returns win probability for left team
6. Visualization → Renders analyzed frame with ROI boxes, metrics, and prediction gauge

**State Management:**
- No persistent state across frames
- Game state exists only in JSON output files or dashboard memory
- Current frame analysis independent from previous frames (stateless design)

## Key Abstractions

**VCTVisionEngine:**
- Purpose: Encapsulates all computer vision operations for VCT broadcast analysis
- Examples: `d:/Git/Val-Prediciton-Model/vision_engine.py` (standalone), embedded in `d:/Git/Val-Prediciton-Model/dashboard.py`
- Pattern: Class-based encapsulation with ROI coordinate system and image processing pipelines
- Methods: preprocess_image, read_number, check_alive_status, get_economy, analyze_vct_frame, detect_spike

**GameWatcher:**
- Purpose: Handles streaming connection and continuous frame extraction for live broadcasts
- Examples: `d:/Git/Val-Prediciton-Model/backend.py`
- Pattern: State machine managing connection lifecycle (connect → read loop → handle errors → reconnect)
- Methods: connect_stream, process_frame, run

**ROI (Region of Interest) Coordinate System:**
- Purpose: Map broadcast layout positions to pixel coordinates for consistent extraction across different screen resolutions
- Tuples format: (y_start, y_end, x_start, x_end)
- Examples: score regions (830-890, 1030-1090 x-range), spike area (940-980), player sidebars (1660 x for right team)

## Entry Points

**Backend Monitor (backend.py):**
- Location: `d:/Git/Val-Prediciton-Model/backend.py` main block
- Triggers: Manual script execution (python backend.py)
- Responsibilities: Establish stream connection, continuously extract game state, persist to JSON file

**Dashboard UI (dashboard.py):**
- Location: `d:/Git/Val-Prediciton-Model/dashboard.py` global scope + sidebar/main page sections
- Triggers: Streamlit app launch (streamlit run dashboard.py)
- Responsibilities: Serve interactive UI, handle file uploads, run vision analysis on demand, display predictions

## Error Handling

**Strategy:** Defensive sampling with fallback thresholds; try-except blocks for OCR failures

**Patterns:**
- Stream disconnection: GameWatcher catches read failures, reconnects stream automatically
- OCR failures: read_number returns 0 if image crop is empty (size == 0 check)
- Bounds checking: Alive player detection verifies y-coordinate within frame.shape[0]
- HSV thresholds: Multiple color range definitions (e.g., red spike detection with two HSV ranges for wraparound hues)

## Cross-Cutting Concerns

**Logging:** Print statements for debugging in GameWatcher.run(), no structured logging framework

**Validation:**
- Image crop size validation before OCR
- Alive count sanity checks (0-5 range)
- Economy value bounds (0-9000 credits)
- Frame bounds checking for pixel sampling

**Authentication:** Stream-level authentication handled by streamlink SDK (supports Twitch OAuth, YouTube)

---

*Architecture analysis: 2026-02-12*
