# Coding Conventions

**Analysis Date:** 2026-02-13

## Naming Patterns

**Files:**
- Modules: `snake_case.py` (e.g., `killfeed_detector.py`, `game_state_manager.py`)
- Test files: `test_<module>.py` (e.g., `test_round_detector.py`, `test_game_state_manager.py`)
- Grouped by directory: `detectors/`, `orchestration/`, `utils/`, `types/`

**Functions:**
- Functions: `snake_case` (e.g., `detect()`, `_preprocess_crop()`, `_parse_round_number()`)
- Private/internal: Leading underscore `_method_name()` (e.g., `_load_templates()`, `_validate_kill_event()`)
- Public API: No underscore (e.g., `detect()`, `process_video()`)

**Variables:**
- Local variables: `snake_case` (e.g., `round_number`, `killer_agent`, `victim_side`)
- Constants: `UPPER_SNAKE_CASE` for module-level constants (e.g., `ROUND_START_GRACE_PERIOD`)
- Private module constants: Leading underscore `_DEFAULT_FMT`

**Types:**
- Classes: `PascalCase` (e.g., `KillfeedDetector`, `GameStateManager`, `PlayerStateTracker`)
- Pydantic models: `PascalCase` with `Info` suffix for detection types (e.g., `RoundInfo`, `ScoreInfo`, `AbilityInfo`)
- Type aliases: `PascalCase`

## Code Style

**Formatting:**
- Tool: Ruff (configured in `pyproject.toml`)
- Line length: 100 characters
- Target: Python 3.10+

**Linting:**
- Tool: Ruff with selected rules
- Rules: `["E", "F", "I", "N", "W"]` (Pyflakes, Pycodestyle, Import order, Naming, Warnings)
- Config: `pyproject.toml` section `[tool.ruff.lint]`

**Type Hints:**
- Use `from __future__ import annotations` at top of every module
- Type hints on function signatures: `def detect(self, frame: np.ndarray) -> Optional[RoundInfo]:`
- Return type annotations required for public methods
- Pydantic models for structured data (not raw dicts where possible)

## Import Organization

**Order:**
1. Future imports: `from __future__ import annotations`
2. Standard library: `from pathlib import Path`, `from typing import Optional`, `import re`
3. Third-party: `import cv2`, `import numpy as np`, `from pydantic import BaseModel`
4. Local absolute imports: `from valoscribe.detectors.cropper import Cropper`, `from valoscribe.utils.logger import get_logger`

**Path Aliases:**
- Not used. All imports are absolute: `from valoscribe.<module>.<submodule> import ClassName`

**Pattern:**
```python
from __future__ import annotations
from typing import Optional
from pathlib import Path

import cv2
import numpy as np

from valoscribe.detectors.cropper import Cropper
from valoscribe.types.detections import KillfeedAgentDetection
from valoscribe.utils.logger import get_logger
```

## Error Handling

**Patterns:**
- Log warnings/errors rather than raising exceptions for non-critical failures
- Return `None` for failed detections (graceful degradation)
- Use early returns to avoid deep nesting: `if crop.size == 0: log.warning(...); return None`
- Validation in Pydantic models for structured data (raises `ValidationError` automatically)

**Examples:**
```python
# Detection failure - return None
if round_crop.size == 0:
    log.warning("Round number crop is empty")
    return None

# Validation failure - log and continue
if not self._validate_kill_event(candidate):
    log.debug(f"Rejected kill: {candidate.killer_agent} -> {candidate.victim_agent}")
    continue

# Critical initialization - raise error
if len(templates) == 0:
    log.error(f"No templates loaded from {self.template_dir}")
```

## Logging

**Framework:** Standard library `logging` via custom wrapper

**Location:** `src/valoscribe/utils/logger.py`

**Pattern:**
```python
from valoscribe.utils.logger import get_logger

log = get_logger(__name__)
```

**Levels:**
- `log.debug()`: Detailed information for debugging (detector output, state transitions)
- `log.info()`: Key events (detector initialization, round start/end, match events)
- `log.warning()`: Recoverable issues (missing detections, parsing failures)
- `log.error()`: Serious problems (template loading failures, invalid state)

**When to Log:**
- Initialization: Log configuration on `__init__` completion
- Detection failures: Log why detection returned `None`
- State transitions: Log phase changes, round start/end
- Validation: Debug log rejected candidates with reasons

**Format:**
```python
log.info(f"Killfeed detector initialized (min_confidence: {min_confidence}, templates: {len(self.templates)})")
log.warning(f"Failed to parse round number from text: '{text}'")
log.debug(f"Template {template_key} confidence = {confidence:.3f}")
```

## Comments

**When to Comment:**
- Complex algorithms: Explain template matching logic, state validation rules
- Non-obvious decisions: Why preround uses different slot mapping than active round
- TODOs: Mark incomplete features with `# TODO: weapon detection`
- Workarounds: Document why certain checks exist (e.g., grace period for UI fade-in)

**JSDoc/TSDoc:**
- Python uses docstrings, not JSDoc
- Module docstrings at top: `"""Killfeed detector for Valorant using agent icon template matching."""`
- Class docstrings under class definition
- Method docstrings immediately after `def` signature

**Docstring Style:**
```python
def detect(self, frame: np.ndarray) -> Optional[RoundInfo]:
    """
    Detect round number from a frame.

    Args:
        frame: Input frame (1080p)

    Returns:
        RoundInfo if successfully detected, None otherwise
    """
```

## Function Design

**Size:**
- Keep methods under ~50 lines where possible
- Extract complex logic into private helper methods (e.g., `_preprocess_crop()`, `_parse_round_number()`)
- Large orchestration methods are acceptable if they coordinate multiple steps (e.g., `_process_active_round()` at ~250 lines)

**Parameters:**
- Positional for required: `def __init__(self, cropper: Cropper, ...)`
- Keyword-only for optional config: `def __init__(self, cropper: Cropper, *, min_confidence: float = 0.75)`
- Use `Optional[T]` for nullable parameters

**Return Values:**
- Return Pydantic models for structured data: `-> Optional[RoundInfo]`
- Return `None` for failures (not exceptions)
- Return tuples for multiple values: `-> tuple[Optional[RoundInfo], np.ndarray]`

## Module Design

**Exports:**
- Explicit `__init__.py` imports where needed
- No `__all__` usage observed
- Direct imports: `from valoscribe.detectors.round_detector import RoundDetector`

**Barrel Files:**
- Not used. Each module is imported directly by path.

**Package Structure:**
```
src/valoscribe/
├── commands/          # CLI commands (Typer apps)
├── detectors/         # CV detection modules
├── orchestration/     # High-level coordination
├── scraper/           # VLR metadata scraper
├── types/             # Pydantic models
├── utils/             # Shared utilities (logger, OCR)
├── video/             # Video I/O
└── __main__.py        # CLI entry point
```

**Private Helpers:**
- Use leading underscore for internal methods: `def _preprocess_crop(self, crop: np.ndarray):`
- Group related helpers near their caller
- Extract validation/parsing logic to testable private methods

---

*Convention analysis: 2026-02-13*
