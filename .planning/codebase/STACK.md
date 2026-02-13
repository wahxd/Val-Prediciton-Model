# Technology Stack

**Analysis Date:** 2026-02-12

## Languages

**Primary:**
- Python 3.x - All application code and ML models

**Not Detected:**
- No JavaScript, TypeScript, Go, Rust, or other languages

## Runtime

**Environment:**
- Python interpreter (no specific version pinned in requirements)

**Package Manager:**
- pip
- Lockfile: Missing (only requirements.txt with unpinned versions)

## Frameworks

**Core:**
- Streamlit - Web UI framework for dashboard (`d:\Git\Val-Prediciton-Model\dashboard.py`)
- OpenCV (cv2) - Computer vision for frame processing and OCR

**Machine Learning:**
- scikit-learn - Logistic Regression model for win probability prediction (`d:\Git\Val-Prediciton-Model\dashboard.py` lines 8, 139-140)

**Stream Processing:**
- streamlink - Live stream extraction and video capture (`d:\Git\Val-Prediciton-Model\backend.py` line 5)

**Image Processing & Recognition:**
- pytesseract - Optical Character Recognition for reading game state text (scores, timers) (`d:\Git\Val-Prediciton-Model\backend.py` line 3, `dashboard.py` line 3)

## Key Dependencies

**Critical:**
- opencv-python - Video frame capture, color detection, image preprocessing
- pytesseract - OCR engine for extracting text from game interface (scores, player stats)
- streamlink - Stream resolution and URL extraction from live streams (YouTube, Twitch)
- scikit-learn - ML model training and inference for win probability

**Data Processing:**
- numpy - Numerical operations for pixel analysis, color thresholding
- pandas - Data manipulation (imported in `dashboard.py` line 5, used in model training)

**Utilities:**
- watchdog - File system monitoring (imported in `requirements.txt`)

## Configuration

**Environment:**
- Configuration is code-based in `d:\Git\Val-Prediciton-Model\config.py`
- Tesseract executable path: Configurable (default: `C:\Program Files\Tesseract-OCR\tesseract.exe`)
- Region of Interest (ROI) coordinates hardcoded for 1920x1080 resolution
- Color thresholds for spike detection defined in config

**Build:**
- No build process detected
- No bundling, compilation, or packaging tools

**Key Configs:**
- ROI_TIMER, ROI_SPIKE: Game HUD region coordinates
- TEAM_A_AVATARS, TEAM_B_AVATARS: Player avatar pixel locations
- SPIKE_RED_LOWER, SPIKE_RED_UPPER: HSV color thresholds for spike detection

## Platform Requirements

**Development:**
- Python 3.x with pip
- Tesseract-OCR binary (system dependency)
- Windows 11 Pro (development environment, hardcoded paths suggest Windows)

**Production:**
- Python runtime with dependencies
- Tesseract-OCR installed and in PATH or configured
- Access to video streams (YouTube, Twitch VODs via streamlink)
- 1920x1080 display resolution assumed for coordinate calculations

**External System Dependencies:**
- Tesseract-OCR (separate binary installation required)
- System video codec support (handled by OpenCV backend)

---

*Stack analysis: 2026-02-12*
