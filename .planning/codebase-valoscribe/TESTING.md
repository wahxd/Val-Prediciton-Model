# Testing Patterns

**Analysis Date:** 2026-02-13

## Test Framework

**Runner:**
- pytest (version 7.4.0+)
- Config: Embedded in `pyproject.toml` (no separate `pytest.ini`)

**Assertion Library:**
- pytest's built-in assertions (`assert`)

**Run Commands:**
```bash
pytest                          # Run all tests
pytest -v                       # Verbose output
pytest tests/test_detectors/    # Run specific directory
pytest tests/test_detectors/test_round_detector.py  # Run specific file
pytest -k "test_detect"         # Run tests matching pattern
```

## Test File Organization

**Location:**
- Parallel structure: `tests/` mirrors `src/valoscribe/`
- Tests separated from source code

**Naming:**
- Test files: `test_<module>.py` (e.g., `test_round_detector.py`, `test_game_state_manager.py`)
- Test classes: `Test<ClassName>` (e.g., `TestRoundDetector`, `TestGameStateManager`)
- Test methods: `test_<behavior>` (e.g., `test_detect_success_full_format`, `test_init`)

**Structure:**
```
tests/
├── test_detectors/
│   ├── test_round_detector.py
│   ├── test_cropper.py
│   ├── test_ability_detector.py
│   └── __init__.py
├── test_orchestration/
│   ├── test_game_state_manager.py
│   ├── test_event_collector.py
│   └── __init__.py
├── test_utils/
│   ├── test_ocr.py
│   └── __init__.py
└── test_video/
    ├── test_reader.py
    └── __init__.py
```

## Test Structure

**Suite Organization:**
```python
"""Unit tests for round detector."""

from __future__ import annotations
from unittest.mock import Mock, MagicMock
import pytest
import numpy as np

from valoscribe.detectors.round_detector import RoundDetector
from valoscribe.types.detections import RoundInfo


class TestRoundDetector:
    """Tests for RoundDetector class."""

    @pytest.fixture
    def mock_cropper(self):
        """Create mock cropper."""
        cropper = Mock()
        cropper.crop_simple_region.return_value = np.zeros((20, 100, 3), dtype=np.uint8)
        return cropper

    @pytest.fixture
    def detector(self, mock_cropper, mock_ocr_engine):
        """Create round detector with mocked dependencies."""
        return RoundDetector(mock_cropper, mock_ocr_engine, min_confidence=0.5)

    def test_init(self, mock_cropper, mock_ocr_engine):
        """Test round detector initialization."""
        detector = RoundDetector(mock_cropper, mock_ocr_engine, min_confidence=0.7)
        assert detector.min_confidence == 0.7

    def test_detect_success_full_format(self, detector, mock_ocr_engine):
        """Test successful detection with 'ROUND X/24' format."""
        mock_ocr_engine.read_single_line.return_value = ("ROUND 12/24", 0.95)
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        result = detector.detect(frame)
        assert result.round_number == 12
```

**Patterns:**
- Class-based test organization (one class per source class)
- Fixtures for test dependencies (mocks, sample data)
- Descriptive test names: `test_<method>_<scenario>`
- Triple-quoted docstrings for test descriptions

## Mocking

**Framework:** `unittest.mock` (standard library)

**Patterns:**
```python
from unittest.mock import Mock, MagicMock

# Mock dependencies in fixtures
@pytest.fixture
def mock_cropper(self):
    """Create mock cropper."""
    cropper = Mock()
    cropper.crop_simple_region.return_value = np.zeros((20, 100, 3), dtype=np.uint8)
    return cropper

# Configure return values
mock_ocr_engine.read_single_line.return_value = ("ROUND 12/24", 0.95)

# Verify calls
mock_cropper.crop_simple_region.assert_called_once_with(frame, "round_number")

# Check call arguments
call_kwargs = mock_ocr_engine.read_single_line.call_args[1]
assert "whitelist" in call_kwargs
```

**What to Mock:**
- External dependencies: CV operations (cropper, OCR engine)
- Heavy I/O: Video readers, file operations
- Detectors when testing orchestration: Mock all detectors in `GameStateManager` tests
- Time-dependent operations: Not observed, but would mock `time.time()` if needed

**What NOT to Mock:**
- Pure functions: Parsing logic (e.g., `_parse_round_number()` tested directly)
- Pydantic models: Test actual validation behavior
- Simple data structures: numpy arrays, dicts

## Fixtures and Factories

**Test Data:**
```python
@pytest.fixture
def vlr_metadata(self):
    """Create sample VLR metadata."""
    return {
        "teams": [
            {"name": "NRG", "starting_side": "defense"},
            {"name": "FNATIC", "starting_side": "attack"},
        ],
        "players": [
            {"name": "player0", "team": "NRG", "agent": "sova"},
            # ... 10 players total
        ],
        "map": "Ascent",
    }

@pytest.fixture
def temp_dir(self):
    """Create temporary directory for test outputs."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)  # Cleanup

@pytest.fixture
def dummy_video_path(self, temp_dir):
    """Create a dummy video file."""
    import cv2
    video_path = temp_dir / "test_video.mp4"
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(video_path), fourcc, 30.0, (1920, 1080))
    for _ in range(10):
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        out.write(frame)
    out.release()
    return video_path
```

**Location:**
- Fixtures defined in test class or module
- No centralized `conftest.py` observed (fixtures are local)

**Pattern:**
- Use `@pytest.fixture` for reusable setup
- Use `yield` for cleanup: `yield temp_dir; shutil.rmtree(temp_dir)`
- Compose fixtures: `detector(self, mock_cropper, mock_ocr_engine)`

## Coverage

**Requirements:** Not enforced (no coverage tool configured in `pyproject.toml`)

**View Coverage:**
```bash
pytest --cov=valoscribe --cov-report=html  # If pytest-cov installed
pytest --cov=valoscribe --cov-report=term  # Terminal output
```

## Test Types

**Unit Tests:**
- Test individual classes in isolation
- Mock all external dependencies
- Focus on single method behavior
- Example: `tests/test_detectors/test_round_detector.py` tests `RoundDetector.detect()` with mocked cropper/OCR

**Integration Tests:**
- Test component interactions with minimal mocking
- Example: `tests/test_orchestration/test_game_state_manager.py` tests orchestration with real detectors on dummy video
- Use temporary files for I/O testing

**E2E Tests:**
- Not present in test suite
- CLI commands could be tested end-to-end but aren't currently

## Common Patterns

**Async Testing:**
- Not applicable (no async code in codebase)

**Error Testing:**
```python
def test_round_number_range_validation(self):
    """Test round number must be in valid range (1-24)."""
    # Valid cases
    RoundInfo(round_number=1, confidence=0.9)
    RoundInfo(round_number=24, confidence=0.9)

    # Invalid cases - expect Pydantic ValidationError
    with pytest.raises(Exception):
        RoundInfo(round_number=0, confidence=0.9)

    with pytest.raises(Exception):
        RoundInfo(round_number=25, confidence=0.9)
```

**Parametric Testing:**
```python
def test_parse_round_number_various_formats(self, detector):
    """Test parsing round numbers from various formats."""
    test_cases = [
        ("ROUND 5/24", 5),
        ("5/24", 5),
        ("ROUND 12", 12),
        ("  ROUND  5 / 24  ", 5),  # Extra whitespace
        ("ROUND 0/24", None),  # Invalid: 0
        ("INVALID", None),  # No numbers
    ]

    for text, expected in test_cases:
        result = detector._parse_round_number(text)
        assert result == expected, f"Failed for input: '{text}'"
```

**Numpy Array Testing:**
```python
# Create test frames
frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

# Test empty arrays
mock_cropper.crop_simple_region.return_value = np.array([])
assert result is None

# Check array properties
assert isinstance(preprocessed, np.ndarray)
assert preprocessed.size > 0
```

**Mock Verification:**
```python
# Verify method called
mock_cropper.crop_simple_region.assert_called_once_with(frame, "round_number")

# Check call arguments
call_kwargs = mock_ocr_engine.read_single_line.call_args[1]
assert "whitelist" in call_kwargs

# Verify not called
mock_cropper.crop_simple_region.assert_not_called()
```

**Fixture Cleanup:**
```python
@pytest.fixture
def temp_dir(self):
    """Create temporary directory for test outputs."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    # Cleanup after test
    shutil.rmtree(temp_dir)
```

---

*Testing analysis: 2026-02-13*
