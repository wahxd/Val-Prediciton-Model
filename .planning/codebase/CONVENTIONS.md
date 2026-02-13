# Coding Conventions

**Analysis Date:** 2026-02-12

## Naming Patterns

**Files:**
- Lowercase with underscores: `backend.py`, `config.py`, `dashboard.py`, `vision_engine.py`
- Descriptive names indicate function/module purpose
- Main entry point is `dashboard.py` (Streamlit UI), `backend.py` (stream monitoring)

**Classes:**
- PascalCase: `GameWatcher`, `VCTVisionEngine`
- Domain-specific naming that clarifies responsibility
- Example: `VCTVisionEngine` clearly indicates vision processing for VCT (Valorant Champions Tour)

**Functions and Methods:**
- snake_case: `connect_stream()`, `process_frame()`, `preprocess_image()`, `read_number()`, `check_alive_status()`, `analyze_vct_frame()`
- Action verbs prefix: `connect_`, `process_`, `preprocess_`, `read_`, `check_`, `detect_`, `analyze_`
- Private methods not used (no leading underscore convention observed)

**Variables:**
- snake_case: `output_file`, `stream_url`, `frame_count`, `timer_text`, `spike_planted`, `team_a_alive`
- Constants (configuration): UPPERCASE: `TESSERACT_CMD`, `ROI_TIMER`, `ROI_SPIKE`, `TEAM_A_AVATARS`, `SPIKE_RED_LOWER`
- Descriptive names indicating meaning: `pixel_brightness`, `alive_count`, `saturation`, `value`
- Loop counters: single letters `i`, `x`, `y` for spatial coordinates

**Types/Data Structures:**
- Dictionaries for configuration: `ROIS = {'score_left': ..., 'score_right': ...}`
- Lists for coordinate collections: `TEAM_A_AVATARS = [(550, 70), ...]`
- Tuples for ROI specifications: `(y_start, y_end, x_start, x_end)`
- Dictionary returns from analysis functions: `{'timestamp': ..., 'timer': ..., 'spike_planted': ...}`

## Code Style

**Formatting:**
- No detected linting/formatting tool (no .pylintrc, .flake8, setup.cfg)
- Standard Python indentation: 4 spaces
- Line length varies, some lines exceed 100 characters
- Blank lines used to separate logical sections
- Comments use `#` for inline explanations

**Linting:**
- No linter configuration files detected
- Code style is informal, focused on functionality rather than strict conventions
- Import statements sometimes mixed (local imports after standard library without clear separation)

## Import Organization

**Order Observed:**
1. Standard library: `import cv2`, `import numpy as np`, `import pytesseract`, `import streamlink`, `import time`, `import json`
2. Third-party: `import streamlit as st`, `from sklearn.linear_model import LogisticRegression`
3. Local: `import config` (local configuration module)

**Path Aliases:**
- Common aliases used: `np` (numpy), `st` (streamlit), `cv2` (OpenCV)
- Consistency: aliases are standardized across files

## Error Handling

**Patterns:**
- Basic try-except blocks in critical sections: `backend.py` line 90-100
  ```python
  try:
      state = self.process_frame(frame)
      with open(self.output_file, 'w') as f:
          json.dump(state, f)
      print(f"Update: {state}")
  except Exception as e:
      print(f"Error processing frame: {e}")
  ```
- Broad exception catching (catches all Exception types)
- Error messages printed to console with context
- No custom exception classes defined
- Stream connection failures handled with print and retry: `backend.py` line 74-75, 81-82

**Validation:**
- Boundary checks for frame dimensions: `backend.py` line 53, `vision_engine.py` line 73
  ```python
  if y >= frame.shape[0]: break
  ```
- Sanity checks for values: `vision_engine.py` line 116
  ```python
  if 0 <= credits <= 9000:
  ```
- Empty image checks: `vision_engine.py` line 40
  ```python
  if image_crop.size == 0: return 0
  ```

## Logging

**Framework:** Console-based using `print()` statements only
- No logging module imported or used
- Direct console output for status and errors
- Example: `backend.py` line 20, 97, 100

**Patterns:**
- Informational: `print(f"Connecting to {self.stream_url}...")`, `print(f"Update: {state}")`
- Error reporting: `print(f"Error processing frame: {e}")`
- No debug levels (INFO, WARNING, ERROR) used
- All output goes to stdout

## Comments

**When to Comment:**
- Inline comments explain non-obvious operations: `backend.py` line 26, 32, 41
- Comments precede complex logic: `vision_engine.py` line 58-60
- Configuration documentation: `config.py` lines 7-22
- ROI definitions well-commented with coordinate system: `dashboard.py` lines 23-38

**JSDoc/TSDoc:**
- Minimal docstrings used
- Short docstrings on public methods: `vision_engine.py` line 39-40
  ```python
  def read_number(self, image_crop):
      """Reads integers from an image crop using Tesseract."""
  ```
- Not consistently applied to all functions
- No parameter or return type documentation

## Function Design

**Size:**
- Methods range from 5-15 lines typically
- Largest method: `dashboard.py` analyze function ~110 lines (includes UI markup)
- Processing methods focused: `check_alive_status()` ~20 lines, `analyze_vct_frame()` ~25 lines

**Parameters:**
- Most methods take 1-3 parameters
- No type hints used
- Optional parameters use defaults: `preprocess_image(img, invert=True)`
- Image/frame objects passed by reference (numpy arrays)

**Return Values:**
- Dictionaries for complex results: `analyze()` returns game state dict
- Integers for count operations: `read_number()` returns int, `count_alive()` returns int
- Booleans for detection: `detect_spike()` returns bool, `connect_stream()` returns bool
- None implicitly returned for side-effect methods: `run()`, `connect_stream()`

## Module Design

**Exports:**
- Classes exposed directly: `GameWatcher`, `VCTVisionEngine`
- No __all__ definitions observed
- No package structure (single directory, no __init__.py)

**Barrel Files:**
- Not used (not a structured package)
- Each .py file is independent module or contains single class

## Configuration Management

**Approach:**
- Centralized configuration in `config.py`
- Constants defined at module level (UPPERCASE)
- Configuration parameters passed to class constructors when needed
- Example: `GameWatcher.__init__(self, stream_url, output_file="game_state.json")`

**Patterns:**
- ROI coordinates hardcoded as configuration constants: `ROI_TIMER`, `ROI_SPIKE`
- Team avatar coordinates as list of tuples: `TEAM_A_AVATARS`, `TEAM_B_AVATARS`
- Color thresholds as configuration: `SPIKE_RED_LOWER`, `SPIKE_RED_UPPER`
- Tesseract path optional configuration: `TESSERACT_CMD = None`

---

*Convention analysis: 2026-02-12*
