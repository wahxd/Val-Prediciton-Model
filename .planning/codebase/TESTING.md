# Testing Patterns

**Analysis Date:** 2026-02-12

## Test Framework

**Runner:**
- Not detected - No testing framework configured (no pytest, unittest, etc.)
- No test configuration files found (no pytest.ini, conftest.py, setup.cfg)

**Assertion Library:**
- Not applicable - no test framework in use

**Run Commands:**
- No test execution configured
- Manual testing via Streamlit dashboard in `dashboard.py`
- Manual testing via command-line execution of `backend.py`

## Test File Organization

**Location:**
- No test files present in codebase
- No separate test directory structure
- No test file naming convention established (no *_test.py or test_*.py files)

**Naming:**
- Not applicable - no test files exist

**Structure:**
- Not applicable - no test files exist

## Test Absence Analysis

**Current State:**
- Zero automated tests found across codebase
- All four Python modules lack corresponding test files:
  - `backend.py` - No test_backend.py or backend_test.py
  - `config.py` - No test_config.py
  - `dashboard.py` - No test_dashboard.py
  - `vision_engine.py` - No test_vision_engine.py

**Manual Testing Approach:**
- `backend.py` (lines 102-107): Contains hardcoded test URL
  ```python
  if __name__ == "__main__":
      URL = "https://www.youtube.com/watch?t=5&v=GoLVlVZAk6E&feature=youtu.be"
      bot = GameWatcher(URL)
      bot.run()
  ```
- `dashboard.py`: Streamlit interactive testing only
  - File upload interface for manual VOD/image analysis
  - Manual override section (lines 255-263) for testing predictions without vision

## Testable Components

**Unit Test Candidates:**

**Vision Processing (vision_engine.py):**
- `preprocess_image(img, invert=True)` - Image preprocessing with threshold
  - Testable with sample images
  - Return value: processed numpy array

- `read_number(image_crop)` - OCR digit extraction
  - Testable with number images
  - Return value: integer
  - Current safety: empty image returns 0

- `check_alive_status(frame, side='left')` - Player alive detection
  - Testable with synthetic frames
  - Return value: alive count (0-5)
  - Uses HSV color detection (saturation > 40, value > 50)

- `get_economy(frame, side='left')` - Total credits extraction
  - Testable with synthetic frames
  - Return value: total credits integer
  - Includes validation: 0 <= credits <= 9000

- `analyze_vct_frame(frame)` - Master analysis function
  - Testable with sample VCT broadcast frames
  - Return value: dictionary with keys: score_left, score_right, alive_left, alive_right, eco_left, eco_right
  - Currently no error handling for invalid frames

**Game State Processing (backend.py):**
- `process_frame(frame)` - Extract game state from video frame
  - Testable with synthetic or real frames
  - Return value: dictionary with timestamp, timer, spike_planted, team_a_alive, team_b_alive
  - No validation of return values

- `connect_stream()` - Stream connection logic
  - Difficult to test without mock streams
  - Return value: boolean

- `run()` - Main processing loop
  - Integration test candidate
  - Frame processing every 10th frame
  - Infinite loop (requires external termination)

**Configuration (config.py):**
- Constants only, no functions to test
- Hardcoded ROI coordinates should be validated against frame dimensions
- Color thresholds should be tested for robustness

## Mocking Opportunities

**What Should Be Mocked:**
- OpenCV video capture: `cv2.VideoCapture()` - mock to return synthetic frames
- Tesseract OCR: `pytesseract.image_to_string()` - mock to return known digit strings
- Streamlink: `streamlink.streams()` - mock to return test stream URLs
- File I/O: `open()` for JSON output in `backend.py` line 94
- Streamlit components: `st.file_uploader()`, `st.slider()`, etc. in `dashboard.py`

**Mocking Pattern Example (if using pytest-mock):**
```python
def test_read_number_with_valid_digits(mocker):
    engine = VCTVisionEngine()
    # Mock tesseract to return known digit string
    mocker.patch('pytesseract.image_to_string', return_value='42')

    result = engine.read_number(synthetic_image)
    assert result == 42
```

**What NOT to Mock:**
- NumPy array operations (core image processing)
- OpenCV color space conversions (cv2.cvtColor())
- OpenCV thresholding (cv2.threshold())
- Pixel sampling and arithmetic (actual detection logic)
- Dictionary operations and return values

## Fixtures and Test Data

**Test Data Needs:**
- Synthetic frames (numpy arrays) sized 1920x1080 for ROI testing
- Sample images with known OCR output (white text on black background)
- Frames with known alive player counts (colored vs gray health bars)
- Frames with spike planted indicator (red icon)
- Invalid inputs: empty images, mismatched dimensions, corrupted data

**Fixture Example (if testing implemented):**
```python
@pytest.fixture
def sample_frame_1080p():
    """Generate synthetic 1920x1080 BGR frame."""
    return np.zeros((1080, 1920, 3), dtype=np.uint8)

@pytest.fixture
def sample_score_image():
    """Generate synthetic score image with white text."""
    img = np.zeros((70, 60, 3), dtype=np.uint8)
    # Add white pixels to simulate "42"
    return img
```

**Location (if implemented):**
- Recommended: `tests/fixtures/` directory
- Or: `conftest.py` for shared fixtures

## Coverage

**Requirements:**
- Not enforced - No coverage measurement tool configured
- No minimum coverage threshold defined

**View Coverage (if pytest + pytest-cov installed):**
```bash
pytest --cov=. --cov-report=html
```

**Current Coverage (Estimated):**
- 0% - No automated tests exist
- Critical untested paths:
  - Stream connection failure scenarios
  - OCR error handling (when Tesseract fails or returns invalid data)
  - Frame boundary conditions (partial ROIs outside frame)
  - Invalid input validation

## Test Types Needed

**Unit Tests:**
- **Scope:** Individual functions in isolation with mocked dependencies
- **Approach (recommended):**
  - Test `preprocess_image()` with sample images
  - Test `read_number()` with mocked Tesseract
  - Test `check_alive_status()` with synthetic frames
  - Test `detect_spike()` with red color samples
  - Test `analyze_vct_frame()` end-to-end on single frame
  - Test coordinate validation in `backend.py`

**Integration Tests:**
- **Scope:** Multiple components working together
- **Approach (recommended):**
  - Vision engine + game watcher processing real or synthetic stream frames
  - Dashboard analysis with sample VOD files
  - Config + vision engine with different ROI values

**E2E Tests:**
- **Framework:** Not currently used
- **Recommended:** Manual testing via Streamlit dashboard and backend.py main execution
- **Challenges:**
  - External dependencies (Tesseract, stream sources)
  - GPU/hardware requirements for video processing
  - Long-running stream monitoring

## Common Testing Patterns (Recommended)

**Async Testing:**
- Not applicable - no async code present
- Stream reading is synchronous with `cv2.VideoCapture()`

**Error Testing (Recommended Pattern):**
```python
def test_read_number_with_empty_image():
    """Should return 0 for empty image."""
    engine = VCTVisionEngine()
    empty_img = np.array([])
    result = engine.read_number(empty_img)
    assert result == 0

def test_check_alive_status_frame_boundary():
    """Should handle frames shorter than expected Y coordinates."""
    engine = VCTVisionEngine()
    small_frame = np.zeros((300, 1920, 3), dtype=np.uint8)
    # Should break loop when y >= frame.shape[0]
    result = engine.check_alive_status(small_frame)
    assert result == 0  # No alive counts in small frame

def test_detect_spike_with_no_red_pixels():
    """Should return False when red pixel count <= 50."""
    engine = VCTVisionEngine()
    blue_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    blue_frame[:, :, 0] = 255  # All blue
    result = engine.detect_spike(blue_frame)
    assert result is False
```

## Testing Gaps

**High Priority (Untested Critical Paths):**
- `GameWatcher.connect_stream()` - Stream acquisition failure handling
- `process_frame()` - Complete game state extraction with boundary validation
- `VCTVisionEngine.analyze_vct_frame()` - Coordinate validation
- Tesseract dependency failure (if not installed)

**Medium Priority:**
- ROI coordinate validation
- Color threshold robustness
- Economy credit parsing and validation
- JSON output file writing in backend

**Low Priority:**
- Dashboard Streamlit UI (difficult to autotest)
- Configuration loading and defaults

---

*Testing analysis: 2026-02-12*
