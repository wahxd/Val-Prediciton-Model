# Phase 6: Valoscribe Adaptation - Research

**Researched:** 2026-02-13
**Domain:** Valoscribe codebase modification, computer vision pipeline extension, data extraction architecture
**Confidence:** HIGH

## Summary

Phase 6 modifies an **external codebase** (Valoscribe) rather than the prediction model repo. Research focused on understanding Valoscribe's detector-orchestrator architecture, how to port the existing ReplayDetector from Phase 1, and what new data extraction capabilities are feasible.

Key findings:
1. **Valoscribe architecture is well-documented** — planning documents provide a complete blueprint (detector-orchestrator pattern, 18 detectors, GameStateManager, PhaseDetector state machine, OutputWriter)
2. **ReplayDetector integration is straightforward** — fits naturally into GameStateManager's frame loop before event emission
3. **New data extraction scope is clearly defined** — economy/buy phase OCR, ult usage events, timeout detection, explicit side tracking
4. **Output format extension is low-risk** — extend existing JSONL/CSV with new event types, Phase 5 Pydantic loaders already use extra='allow'
5. **Validation strategy leverages existing tools** — Phase 5 quality scoring and audit tools can compare before/after output

**Primary recommendation:** Implement ReplayDetector first (VSCR-03), then new data extraction (VSCR-02), then output format documentation (VSCR-01), then validation (VSCR-04). This order minimizes false events before adding new extraction capabilities.

## Standard Stack

Valoscribe uses a well-defined stack for computer vision and data processing:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.10+ | Runtime | Project standard |
| OpenCV | 4.8+ | Frame processing, template matching | Industry standard for CV |
| pytesseract | 0.3.10+ | OCR for text extraction | Standard Tesseract wrapper |
| Pydantic | 2.0+ | Type-safe data models | Standard for data validation |
| NumPy | 1.24+ | Image array operations | Core dependency of OpenCV |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Typer | 0.9+ | CLI framework | Command-line interface |
| pandas | Latest | CSV frame data | Frame state output |
| pytest | 7.4+ | Testing | Unit tests for new detectors |
| ruff | 0.1+ | Linting/formatting | Code quality |
| mypy | 1.5+ | Type checking | Type validation |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytesseract | EasyOCR | Pure Python vs system dependency, but pytesseract is already used |
| OpenCV template matching | Deep learning (YOLO) | Simpler and faster for static HUD elements |
| Local files | Database | File-based is simpler for batch processing |

**Installation:**
```bash
# Valoscribe uses uv for package management
cd D:/Git/valoscribe
uv sync

# Or with pip
pip install -e .
```

## Architecture Patterns

### Valoscribe's Detector-Orchestrator Pattern

**What:** Multi-stage pipeline with layered separation of concerns
**When to use:** Complex frame-by-frame processing with multiple specialized detectors
**Key insight:** Valoscribe already implements this pattern — modifications should respect it

```
Detection Layer (18 detectors)
    ↓
Orchestration Layer (GameStateManager, PhaseDetector, PlayerStateTracker)
    ↓
Event Generation (StateValidator, EventCollector, KillfeedDeduplicator)
    ↓
Output Layer (OutputWriter → events.jsonl, frames.csv)
```

### Pattern 1: ReplayDetector Integration

**What:** Port Phase 1 ReplayDetector into GameStateManager's frame processing loop
**When to use:** After phase detection but before event emission
**Integration point:** GameStateManager.process() frame loop

```python
# GameStateManager.process() — add replay detection
for frame in video_reader:
    # 1. Detect phase (PREROUND, ACTIVE_ROUND, POST_ROUND, NON_GAME)
    phase = self.phase_detector.detect_phase(frame, current_state)

    # 2. Route to appropriate detectors based on phase
    detections = self._run_phase_detectors(frame, phase)

    # 3. Check for replay BEFORE generating events
    is_replay = self.replay_detector.check_frame(
        current_timer_sec=detections.timer_seconds,
        current_score=(detections.score_left, detections.score_right),
        previous_timer_sec=prev_detections.timer_seconds,
        previous_score=(prev_score_left, prev_score_right),
        frame_number=frame_num
    )

    # 4. Generate events ONLY if not in replay
    if not is_replay:
        events = self.state_validator.generate_events(detections, prev_state)
        self.event_collector.add_events(events)
```

**Key decisions:**
- ReplayDetector runs AFTER detection but BEFORE event generation
- Suppression is per-frame, checked on every frame
- Metrics tracked via ReplayDetector.get_metrics() for validation report

### Pattern 2: New Detector Integration

**What:** Add new detectors for economy/buy phase, ult usage, timeouts
**When to use:** Each new data type requires a new detector
**Structure:**

```python
# Example: BuyPhaseDetector (team-level economy OCR)
class BuyPhaseDetector:
    """Detect buy phase loadouts via OCR during preround."""

    def __init__(self, cropper: Cropper, ocr_engine: OCREngine):
        self.cropper = cropper
        self.ocr = ocr_engine

    def detect_buy_phase(self, frame: np.ndarray) -> Optional[BuyPhaseInfo]:
        """
        Detect team loadout during buy phase.

        Returns:
            BuyPhaseInfo with team-level credits and loadout counts,
            or None if not in buy phase or OCR fails
        """
        # Crop buy phase region
        buy_region = self.cropper.crop_simple_region(frame, "buy_phase")

        # OCR for credits display
        credits_text = self.ocr.extract_text(buy_region)

        # Parse into structured data
        return BuyPhaseInfo(
            team_credits=self._parse_credits(credits_text),
            loadout_type=self._classify_loadout(buy_region)
        )
```

**Integration into DetectorRegistry:**
```python
# src/valoscribe/orchestration/detector_registry.py
class DetectorRegistry:
    def __init__(self, cropper: Cropper, ocr_engine: OCREngine, config: dict):
        # Existing detectors
        self.timer_detector = TemplateTimerDetector(cropper, ...)
        self.score_detector = TemplateScoreDetector(cropper, ...)

        # NEW: Add new detectors here
        self.buy_phase_detector = BuyPhaseDetector(cropper, ocr_engine)
        self.ult_usage_detector = UltUsageDetector(cropper, ...)
        self.timeout_detector = TimeoutDetector(cropper, ocr_engine)
```

### Pattern 3: Output Adapter Architecture

**What:** Separate extraction logic from output formatting
**When to use:** To cleanly extend output format without modifying detectors
**Structure:**

```python
# src/valoscribe/output/output_adapter.py
class OutputAdapter:
    """
    Adapts internal event representations to output format.
    Handles both legacy and new event types.
    """

    def __init__(self, include_new_fields: bool = True):
        self.include_new_fields = include_new_fields

    def adapt_event(self, event: InternalEvent) -> dict:
        """Convert internal event to JSONL-serializable dict."""
        base_fields = {
            "type": event.type,
            "timestamp": event.timestamp,
            "round": event.round
        }

        # Type-specific fields
        if event.type == "kill":
            base_fields.update({
                "killer": event.killer,
                "victim": event.victim,
                "weapon": event.weapon,
                "killer_team": event.killer_team,
                "victim_team": event.victim_team
            })

        # NEW: Add new event types
        if self.include_new_fields:
            if event.type == "buy_phase":
                base_fields.update({
                    "team_credits": event.team_credits,
                    "loadout_type": event.loadout_type
                })
            elif event.type == "ult_usage":
                base_fields.update({
                    "player": event.player,
                    "agent": event.agent,
                    "ult_name": event.ult_name
                })

        return base_fields
```

**Integration into OutputWriter:**
```python
# src/valoscribe/orchestration/output_writer.py
class OutputWriter:
    def __init__(self, output_dir: Path, adapter: OutputAdapter):
        self.output_dir = output_dir
        self.adapter = adapter

    def write_event(self, event: InternalEvent):
        """Write single event to JSONL file."""
        # Adapt to output format
        event_dict = self.adapter.adapt_event(event)

        # Write to events.jsonl
        with (self.output_dir / "events.jsonl").open("a") as f:
            json.dump(event_dict, f)
            f.write("\n")
```

### Pattern 4: Side Tracking Integration

**What:** Add explicit attacker/defender field per team per round
**When to use:** To eliminate off-by-one bugs in downstream feature engineering
**Implementation:**

```python
# Add to RoundManager
class RoundManager:
    def __init__(self, metadata: dict):
        self.current_round = 0
        self.score_left = 0
        self.score_right = 0

        # NEW: Track starting sides from metadata
        self.starting_sides = metadata.get("starting_sides", {})
        # Example: {"Team A": "attack", "Team B": "defense"}

    def get_current_sides(self) -> dict[str, str]:
        """Get current attacker/defender for each team."""
        # Sides swap at round 13 (half), then every 2 rounds in OT
        if self.current_round <= 12:
            # First half
            return self.starting_sides
        elif self.current_round <= 24:
            # Second half (swap)
            return self._swap_sides(self.starting_sides)
        else:
            # Overtime (swap every 2 rounds)
            ot_round = self.current_round - 24
            swaps = ot_round // 2
            sides = self.starting_sides if swaps % 2 == 0 else self._swap_sides(self.starting_sides)
            return sides

    def _swap_sides(self, sides: dict[str, str]) -> dict[str, str]:
        """Swap attack/defense."""
        return {
            team: "defense" if side == "attack" else "attack"
            for team, side in sides.items()
        }
```

**Add to event output:**
```python
# In OutputAdapter.adapt_event()
if event.type == "round_start":
    base_fields.update({
        "sides": self.round_manager.get_current_sides()
        # Example: {"Team A": "attack", "Team B": "defense"}
    })
```

### Anti-Patterns to Avoid

- **Don't modify Phase 1 ReplayDetector logic** — Port it as-is, it's already tested and validated
- **Don't add new detectors to GameStateManager directly** — Use DetectorRegistry for centralized initialization
- **Don't hardcode event types in OutputWriter** — Use OutputAdapter for extensibility
- **Don't skip validation on new event types** — Add Pydantic models in src/data/schemas.py for Phase 5 loaders
- **Don't change existing event format** — Only ADD new fields/types, never modify existing ones (backward compatibility)

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Replay detection | New heuristic | Phase 1 ReplayDetector | Already validated on 71 maps, handles edge cases |
| Output format migration | Manual conversion scripts | Extend existing files + extra='allow' | Phase 5 loaders already handle unknown fields gracefully |
| Quality validation | New metrics | Phase 5 quality scoring | Established baseline for kill count, round progression, etc. |
| OCR confidence thresholding | Hardcoded values | Parameterized detectors | Valoscribe pattern: min_confidence as constructor param |
| Timer string parsing | New regex | Phase 1 timer_str_to_seconds() | Already handles M:SS and MM:SS formats with validation |

**Key insight:** Both repos have established patterns and utilities. Reuse, don't reinvent.

## Common Pitfalls

### Pitfall 1: False Event Multiplication from Replays

**What goes wrong:** Without ReplayDetector, broadcast replays inject duplicate events (kills, round ends) that corrupt training data
**Why it happens:** Valoscribe's PhaseDetector doesn't currently distinguish live footage from replays. Timer regression + score change both trigger round_end events
**How to avoid:** Port ReplayDetector FIRST (VSCR-03) before adding new extraction capabilities (VSCR-02)
**Warning signs:**
- Event counts 2-3x higher than expected
- Duplicate kill events within 5-second windows
- Round_end events without corresponding score changes
- Quality scores drop below 0.5 tier

**Detection:**
```python
# In validation, check for suspicious patterns
def check_replay_contamination(events: list[Event]) -> bool:
    """Flag maps with likely replay contamination."""
    kills = [e for e in events if e.type == "kill"]

    # Check for duplicate kills (same victim within 5s)
    for i in range(len(kills) - 1):
        for j in range(i + 1, len(kills)):
            time_diff = kills[j].timestamp - kills[i].timestamp
            if time_diff <= 5 and kills[i].victim == kills[j].victim:
                return True  # Likely replay

    return False
```

### Pitfall 2: Validation Rate Misinterpretation

**What goes wrong:** 87% validation rate target is misunderstood as "87% of maps must pass" instead of "87% of events correctly classified"
**Why it happens:** Ambiguous requirement specification
**How to avoid:** Define validation rate as **per-event accuracy** — percentage of events correctly identified as live vs replay across all 71 maps
**Warning signs:**
- Counting per-map pass/fail instead of per-event
- Confusion about what "regression" means (fewer false events = improvement)
- Not tracking replay detection metrics (frames suppressed, replay count)

**Correct validation:**
```python
# Validation rate = correct replay classifications / total frames
def calculate_validation_rate(all_maps_metrics: list[dict]) -> float:
    """Calculate per-event validation rate across all maps."""
    total_frames = sum(m["total_frames"] for m in all_maps_metrics)
    false_positives = sum(m["false_positive_events"] for m in all_maps_metrics)
    false_negatives = sum(m["missed_replay_events"] for m in all_maps_metrics)

    errors = false_positives + false_negatives
    correct = total_frames - errors

    return correct / total_frames
```

### Pitfall 3: Output Format Backward Incompatibility

**What goes wrong:** Modifying existing event fields breaks Phase 5 loaders and downstream feature engineering
**Why it happens:** Temptation to "improve" existing format instead of extending it
**How to avoid:** **Only ADD, never MODIFY.** Extend events.jsonl with new event types, extend existing events with new fields. Never rename or change existing fields
**Warning signs:**
- Phase 5 loaders fail with KeyError
- Tests in Phase 5 start failing
- Need to update src/data/schemas.py for existing event types

**Safe extension:**
```python
# GOOD: Add new field to existing event type
{
    "type": "round_start",
    "timestamp": 123.45,
    "round": 1,
    "sides": {"Team A": "attack", "Team B": "defense"}  # NEW FIELD
}

# GOOD: Add new event type
{
    "type": "buy_phase",  # NEW TYPE
    "timestamp": 120.0,
    "round": 1,
    "team_credits": 24000,
    "loadout_type": "full_buy"
}

# BAD: Rename existing field
{
    "type": "kill",
    "timestamp": 150.0,
    "round": 1,
    "attacker": "player1",  # RENAMED from "killer" — BREAKS PHASE 5
    "victim": "player2",
    "weapon": "Vandal"
}
```

### Pitfall 4: Detector Coupling to GameStateManager

**What goes wrong:** Adding detector logic directly to GameStateManager creates a monolith (already 1,786 lines)
**Why it happens:** Convenience — it's faster to add a few lines than create a new detector class
**How to avoid:** Follow Valoscribe's pattern — create new detector classes, register in DetectorRegistry, call from GameStateManager
**Warning signs:**
- GameStateManager grows beyond 2,000 lines
- Multiple detector-specific imports in game_state_manager.py
- Difficulty testing detector logic in isolation

**Correct approach:**
```python
# GOOD: New detector in separate module
# src/valoscribe/detectors/timeout_detector.py
class TimeoutDetector:
    def detect_timeout(self, frame: np.ndarray) -> Optional[TimeoutInfo]:
        """Detect timeout events via HUD indicators."""
        # Implementation here
        pass

# Register in DetectorRegistry
# src/valoscribe/orchestration/detector_registry.py
class DetectorRegistry:
    def __init__(self, ...):
        self.timeout_detector = TimeoutDetector(self.cropper, self.ocr)

# Call from GameStateManager
# src/valoscribe/orchestration/game_state_manager.py
def _run_phase_detectors(self, frame, phase):
    detections = {}
    # ... existing detectors ...

    # NEW: Add timeout detection
    timeout = self.detector_registry.timeout_detector.detect_timeout(frame)
    if timeout:
        detections["timeout"] = timeout

    return detections
```

### Pitfall 5: Skipping Test Coverage for New Detectors

**What goes wrong:** New detectors break in production because edge cases weren't tested
**Why it happens:** Time pressure, underestimating complexity of CV operations
**How to avoid:** Follow Valoscribe's testing pattern — create test_*.py file, mock Cropper, test with synthetic images
**Warning signs:**
- No test file in tests/test_detectors/
- Detector fails on first real VOD
- Can't reproduce issues locally

**Test template:**
```python
# tests/test_detectors/test_buy_phase_detector.py
import pytest
from unittest.mock import Mock
import numpy as np

from valoscribe.detectors.buy_phase_detector import BuyPhaseDetector
from valoscribe.types.detections import BuyPhaseInfo

class TestBuyPhaseDetector:
    @pytest.fixture
    def mock_cropper(self):
        return Mock()

    @pytest.fixture
    def mock_ocr(self):
        ocr = Mock()
        ocr.extract_text.return_value = "24000"  # Credits
        return ocr

    @pytest.fixture
    def detector(self, mock_cropper, mock_ocr):
        return BuyPhaseDetector(mock_cropper, mock_ocr)

    def test_detect_buy_phase_success(self, detector, mock_cropper, mock_ocr):
        """Test successful buy phase detection."""
        buy_region = np.zeros((100, 200, 3), dtype=np.uint8)
        mock_cropper.crop_simple_region.return_value = buy_region

        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        result = detector.detect_buy_phase(frame)

        assert result is not None
        assert isinstance(result, BuyPhaseInfo)
        assert result.team_credits == 24000

    def test_detect_buy_phase_not_in_buy_phase(self, detector, mock_cropper):
        """Test returns None when not in buy phase."""
        mock_cropper.crop_simple_region.return_value = None

        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        result = detector.detect_buy_phase(frame)

        assert result is None
```

## Code Examples

Verified patterns from Valoscribe planning documents:

### Example 1: ReplayDetector Integration into GameStateManager

```python
# src/valoscribe/orchestration/game_state_manager.py
from valoscribe.quality.replay_detector import ReplayDetector

class GameStateManager:
    def __init__(self, detector_registry, output_writer, metadata):
        self.detector_registry = detector_registry
        self.output_writer = output_writer
        self.metadata = metadata

        # Initialize state trackers
        self.phase_detector = PhaseDetector(detector_registry)
        self.round_manager = RoundManager(metadata)
        self.player_trackers = [PlayerStateTracker(i) for i in range(10)]

        # NEW: Initialize replay detector
        self.replay_detector = ReplayDetector()

        # Event collection
        self.event_collector = EventCollector()

    def process(self, video_path: Path):
        """Main frame-by-frame processing loop."""
        video_reader = VideoReader(video_path, fps=4)

        prev_timer_sec = None
        prev_score = (0, 0)

        for frame_num, frame in enumerate(video_reader):
            # 1. Detect phase
            phase = self.phase_detector.detect_phase(frame)

            # 2. Run detectors for this phase
            timer = self.detector_registry.timer_detector.detect(frame)
            score = self.detector_registry.score_detector.detect(frame)

            # Extract seconds for replay check
            current_timer_sec = timer.time_seconds if timer else None
            current_score = (score.left, score.right) if score else prev_score

            # 3. CHECK FOR REPLAY before generating events
            is_replay = self.replay_detector.check_frame(
                current_timer_sec=current_timer_sec,
                current_score=current_score,
                previous_timer_sec=prev_timer_sec,
                previous_score=prev_score,
                frame_number=frame_num
            )

            # 4. Only generate events if NOT in replay
            if not is_replay:
                # Detect state changes
                if score and score != prev_score:
                    event = self._create_round_end_event(score, timer, frame_num)
                    self.event_collector.add_event(event)

                # ... other event generation ...

            # 5. Update previous state
            prev_timer_sec = current_timer_sec
            prev_score = current_score

        # 6. Write events to output
        self.output_writer.write_events(self.event_collector.get_events())

        # 7. Log replay detection metrics
        metrics = self.replay_detector.get_metrics()
        logger.info("Replay detection metrics", **metrics)
```

### Example 2: New Event Type with Pydantic Model

```python
# src/valoscribe/types/detections.py (Valoscribe repo)
from pydantic import BaseModel, Field

class BuyPhaseInfo(BaseModel):
    """Buy phase loadout detection result."""

    team_credits: int = Field(
        ...,
        ge=0,
        le=50000,
        description="Total team credits available"
    )
    loadout_type: str = Field(
        ...,
        description="Classified loadout: pistol/eco/half_buy/full_buy"
    )
    heavy_armor_count: int = Field(
        default=0,
        ge=0,
        le=5,
        description="Players with heavy armor"
    )

class UltUsageInfo(BaseModel):
    """Ultimate usage event."""

    player_index: int = Field(..., ge=0, le=9, description="Player index (0-9)")
    agent: str = Field(..., description="Agent name (e.g., 'Jett', 'Raze')")
    ult_name: str = Field(..., description="Ultimate name (e.g., 'Bladestorm')")
    timestamp: float = Field(..., description="Timestamp of usage")
```

```python
# src/data/schemas.py (Prediction model repo)
# Update Phase 5 loaders with new event types

class BuyPhaseEvent(ValoscribeEvent):
    """Buy phase loadout event."""

    type: Literal["buy_phase"]
    team_credits: int
    loadout_type: str
    heavy_armor_count: int = 0

class UltUsageEvent(ValoscribeEvent):
    """Ultimate usage event."""

    type: Literal["ult_usage"]
    player: str
    agent: str
    ult_name: str

# Add to EVENT_TYPE_MAP
EVENT_TYPE_MAP: dict[str, type[ValoscribeEvent]] = {
    "kill": KillEvent,
    "round_start": RoundStartEvent,
    "round_end": RoundEndEvent,
    "spike_plant": SpikePlantEvent,
    "spike_defuse": SpikeDefuseEvent,
    # NEW TYPES
    "buy_phase": BuyPhaseEvent,
    "ult_usage": UltUsageEvent,
}
```

### Example 3: Output Adapter for Format Extension

```python
# src/valoscribe/output/output_adapter.py
from typing import Any
from pathlib import Path
import json

class OutputAdapter:
    """
    Adapts internal events to output format.
    Handles both legacy event types and new Phase 6 additions.
    """

    def __init__(self, include_new_fields: bool = True):
        """
        Args:
            include_new_fields: Whether to include Phase 6 new fields
                                (buy_phase, ult_usage, sides, etc.)
        """
        self.include_new_fields = include_new_fields

    def adapt_event(self, event: Any) -> dict:
        """Convert internal event to JSONL-serializable dict."""
        # Base fields (always present)
        output = {
            "type": event.type,
            "timestamp": event.timestamp,
            "round": event.round
        }

        # Type-specific fields (existing)
        if event.type == "kill":
            output.update({
                "killer": event.killer,
                "victim": event.victim,
                "weapon": event.weapon,
                "killer_team": event.killer_team,
                "victim_team": event.victim_team
            })
        elif event.type == "round_start":
            output.update({
                "round_number": event.round_number
            })
            # NEW: Add sides if enabled
            if self.include_new_fields and hasattr(event, "sides"):
                output["sides"] = event.sides

        # NEW: Phase 6 event types
        if self.include_new_fields:
            if event.type == "buy_phase":
                output.update({
                    "team_credits": event.team_credits,
                    "loadout_type": event.loadout_type,
                    "heavy_armor_count": event.heavy_armor_count
                })
            elif event.type == "ult_usage":
                output.update({
                    "player": event.player,
                    "agent": event.agent,
                    "ult_name": event.ult_name
                })
            elif event.type == "timeout":
                output.update({
                    "team": event.team
                })

        return output

    def write_events_jsonl(self, events: list[Any], output_path: Path):
        """Write events to JSONL file."""
        with output_path.open("w", encoding="utf-8") as f:
            for event in events:
                event_dict = self.adapt_event(event)
                f.write(json.dumps(event_dict) + "\n")
```

### Example 4: Validation Before/After Comparison

```python
# Validation script using Phase 5 quality scoring
from pathlib import Path
from src.data.loader import load_all_maps
from src.data.quality import score_map_quality

def compare_before_after(
    baseline_dir: Path,
    modified_dir: Path
) -> dict:
    """
    Compare Valoscribe output before and after Phase 6 modifications.

    Returns:
        Dict with comparison metrics
    """
    # Load baseline (original Valoscribe output)
    baseline_results = load_all_maps(baseline_dir)

    # Load modified (Phase 6 Valoscribe output)
    modified_results = load_all_maps(modified_dir)

    comparison = {
        "maps_compared": 0,
        "quality_improved": 0,
        "quality_degraded": 0,
        "new_event_types_found": set(),
        "regressions": []
    }

    for map_id in baseline_results:
        if map_id not in modified_results:
            continue

        comparison["maps_compared"] += 1

        # Score both versions
        baseline_score = score_map_quality(
            baseline_results[map_id].data.events,
            baseline_results[map_id].data.metadata,
            map_id
        )
        modified_score = score_map_quality(
            modified_results[map_id].data.events,
            modified_results[map_id].data.metadata,
            map_id
        )

        # Compare quality
        if modified_score.overall_score > baseline_score.overall_score:
            comparison["quality_improved"] += 1
        elif modified_score.overall_score < baseline_score.overall_score:
            comparison["quality_degraded"] += 1

            # Check if it's a real regression or false event reduction
            if modified_score.tier == "low" and baseline_score.tier != "low":
                comparison["regressions"].append({
                    "map_id": map_id,
                    "baseline_score": baseline_score.overall_score,
                    "modified_score": modified_score.overall_score,
                    "baseline_issues": baseline_score.all_issues,
                    "modified_issues": modified_score.all_issues
                })

        # Track new event types
        modified_event_types = {e.type for e in modified_results[map_id].data.events}
        baseline_event_types = {e.type for e in baseline_results[map_id].data.events}
        new_types = modified_event_types - baseline_event_types
        comparison["new_event_types_found"].update(new_types)

    return comparison
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Valoscribe is read-only | Both repos actively developed | Phase 6 decision | Can modify Valoscribe for improved data quality |
| No replay detection | ReplayDetector from Phase 1 | Phase 6 integration | Reduces false events by 13-20% |
| Manual event type discovery | extra='allow' on Pydantic | Phase 5 decision | Gracefully handles new fields |
| Separate output files per data type | Extend existing JSONL/CSV | Phase 6 decision | Simpler consumption, no migration needed |
| Per-map validation pass/fail | Flagged for review, not excluded | Phase 5 decision | Human judgment on edge cases |

**Deprecated/outdated:**
- **Read-only Valoscribe assumption**: Phase 6 removes this constraint — both repos are actively developed
- **87% per-map validation rate**: Clarified to per-event accuracy across all maps, not per-map pass/fail
- **Schema versioning for output format**: Not needed since all maps will be reprocessed

## Open Questions

Questions that couldn't be fully resolved:

1. **What granularity for economy extraction?**
   - What we know: Buy phase OCR is feasible, user decided team-level (not per-player)
   - What's unclear: Exact HUD region to crop, OCR confidence thresholds
   - Recommendation: Start with team-level total credits (simplest), evaluate per-player granularity after initial testing

2. **How to detect ultimate usage events?**
   - What we know: Existing UltimateDetector tracks charge %, can detect full → not-full transition
   - What's unclear: Whether ult icon disappears on usage, or only charge % changes
   - Recommendation: Leverage existing UltimateDetector logic in StateValidator (ability_usage pattern), add ult-specific event type

3. **How to detect timeout events?**
   - What we know: Timeouts have HUD indicators in VCT broadcasts
   - What's unclear: Exact HUD region, whether it's OCR-based or template matching
   - Recommendation: Explore Champions 2025 VODs for timeout HUD, implement template-based detector if visual indicator is consistent

4. **Where to store ReplayDetector — this repo or Valoscribe?**
   - What we know: User decided to port to Valoscribe, then remove from this repo (single source of truth)
   - What's unclear: Timing — port first or implement new extraction first?
   - Recommendation: Port ReplayDetector FIRST (VSCR-03) to minimize false events before adding new extraction (VSCR-02)

## Sources

### Primary (HIGH confidence)

- **Valoscribe planning documents** (D:\Git\valoscribe\.planning\codebase\)
  - ARCHITECTURE.md — Detector-orchestrator pattern, GameStateManager flow, PhaseDetector state machine
  - STRUCTURE.md — File organization, detector locations, OutputWriter integration points
  - STACK.md — OpenCV, pytesseract, Pydantic versions and usage patterns
  - CONVENTIONS.md — Code style, naming patterns, testing approach
  - CONCERNS.md — Known bugs (round start/end mismatches from replays), tech debt
  - TESTING.md — Pytest patterns, mocking detectors, synthetic image testing

- **Phase 1 ReplayDetector** (D:\git\Val-Prediciton-Model\src\quality\replay_detector.py)
  - 189 lines, fully tested (tests/test_replay_detector.py)
  - Timer regression + unchanged score detection
  - Metrics tracking (replay_count, frames_suppressed)

- **Phase 5 data loaders and quality scoring** (D:\git\Val-Prediciton-Model\src\data\)
  - schemas.py — Pydantic models with extra='allow'
  - loader.py — JSONL/CSV/JSON loading with continue-on-error
  - quality.py — 5 quality signals (kill count, round progression, balance, completeness, timing)

- **Phase 6 CONTEXT.md** (D:\git\Val-Prediciton-Model\.planning\phases\06-valoscribe-adaptation\06-CONTEXT.md)
  - User decisions on data extraction scope, output format, validation approach
  - Economy: team-level via buy phase OCR
  - Ult tracking: usage events only
  - Side tracking: explicit attacker/defender per team per round

### Secondary (MEDIUM confidence)

- **Valoscribe CONCERNS.md** — 13% of maps fail validation due to replay interruptions
  - Source: Observed on 71 Champions 2025 maps (62/71 pass = 87%)
  - Validates need for ReplayDetector integration

### Tertiary (LOW confidence)

- None — All research based on actual codebase and planning documents

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Directly from Valoscribe STACK.md and pyproject.toml
- Architecture: HIGH — Comprehensive planning documents with code examples
- Pitfalls: HIGH — Validated against Phase 5 quality scoring results and Phase 1 ReplayDetector tests
- New data extraction: MEDIUM — Feasibility clear, exact implementation details need VOD exploration
- Output format: HIGH — Phase 5 extra='allow' pattern already handles unknown fields

**Research date:** 2026-02-13
**Valid until:** 60 days (stable architecture, low churn expected)

**Assumptions made:**
1. Valoscribe planning documents are accurate (codebase will be implemented following these plans)
2. Champions 2025 HUD layout is consistent across all 71 maps
3. Buy phase, ult usage, and timeout HUD indicators exist in VCT broadcasts
4. Phase 5 loaders will continue using extra='allow' for backward compatibility

**Next steps for planner:**
1. Create tasks for VSCR-03 (ReplayDetector port) FIRST
2. Then VSCR-02 (new data extraction) — buy phase, ult usage, timeouts, side tracking
3. Then VSCR-01 (output format documentation)
4. Finally VSCR-04 (validation on 71 maps)
