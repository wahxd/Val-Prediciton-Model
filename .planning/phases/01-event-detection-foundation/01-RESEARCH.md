# Phase 1: Event Detection Foundation - Research

**Researched:** 2026-02-12
**Domain:** Event detection from VCT broadcast frames using OCR, computer vision, and state machine patterns
**Confidence:** HIGH

## Summary

Phase 1 transforms the existing stateless frame-by-frame CV extractor (`VCTVisionEngine`) into an event-based logging system with robust replay protection and data quality validation. The implementation extends existing code by adding state tracking, debouncing, and event emission layers on top of the working OCR/CV foundation.

**Key Technical Challenges:**
1. **Replay detection** - Broadcast replays create phantom duplicate events if not suppressed
2. **OCR noise** - pytesseract produces flickering values requiring multi-frame consensus
3. **State coherence** - Alive counts and scores must follow game logic (monotonic, valid ranges)
4. **Tactical timeout tracking** - New explicit event type requiring team attribution detection

**Primary recommendation:** Build state machine layer on top of existing `VCTVisionEngine` using `collections.deque` for frame buffering, dataclasses for immutable event types, and JSONL for append-only event storage. Focus on debouncing and replay detection before any event emission.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Detection thresholds & debouncing:**
- 3-frame consensus required before confirming state change (~100ms at 30fps)
- Minimum OCR confidence: 0.7 (70%) for extracted values to be used in state tracking
- Invalid values (alive count > 5, malformed timers) are discarded and frame is skipped
- Log warning when 10+ consecutive frames fail OCR confidence or validation checks

**Replay detection strategy:**
- Detection trigger: Timer regression AND score validation (both conditions required)
- Suppression duration: Until timer progresses forward past the regression point
- Error tolerance: Equal concern for false positives (phantom events from missed replays) and false negatives (missed real events)
- Tactical timeouts tracked as explicit events: Log TIMEOUT events with team attribution (which team called it) - timeouts are momentum indicators crucial for prediction

**Event granularity & metadata:**
- Team-level aggregates only (Team A: 3 alive, Team B: 5 alive) - no per-player tracking in Phase 1
- Snapshot format: Each event includes full game state at moment of event (score, alive counts, round timer, spike status)
- Spike events (plant/defuse/detonate) include round timer at event time for timing analysis
- Round-end events infer win condition from event sequence (elimination vs spike detonation vs defuse vs timeout)

**Data quality handling:**
- Quality reporting: Console warnings for significant issues (50+ consecutive frame failures), full details to log file
- Quality metrics: Track per-field OCR confidence, debounce statistics, replay detection triggers for post-stream analysis
- Extended degradation response: After 30+ seconds of poor OCR quality, pause and prompt user to check ROI alignment or stream quality
- OCR character whitelisting by field type: Timer [0-9:], Alive count [0-5], Score [0-9] to prevent garbage values

### Claude's Discretion

- Exact log message formatting and verbosity levels
- Specific data structure for quality metrics storage
- Implementation details of character whitelisting in Tesseract configuration

### Deferred Ideas (OUT OF SCOPE)

- Per-player state tracking (individual alive status, agent picks, player names) - future phase
- Spike site location detection (A/B/C site from minimap) - mentioned as potential Phase 2 work
- Real-time quality dashboard - comprehensive monitoring interface deferred to future phase
- Frame-by-frame quality logging - comprehensive debug mode not needed for Phase 1

</user_constraints>

---

## Standard Stack

### Core Libraries

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| opencv-python | Latest (4.x) | Video frame capture, image preprocessing, color detection | Industry standard for CV, already in use |
| pytesseract | Latest (0.3.13+) | OCR for extracting scores, timers, text overlays | Python wrapper for Tesseract 5.x, supports confidence scores |
| streamlink | Latest | Live stream URL resolution from YouTube/Twitch | De facto standard for stream extraction, handles adaptive bitrate |
| numpy | Latest | Pixel manipulation, array operations for CV | Required by OpenCV, efficient array operations |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-statemachine | 2.5.0+ | FSM for round phase tracking (buy/combat/post) | Event-driven transitions, observer pattern for side effects |
| structlog | Latest | Structured JSON logging with context | Provides structured logs for quality metrics, easier to analyze than stdlib logging |
| pytest-freezegun | Latest | Mock time for debouncing tests | Testing time-dependent debouncing logic |
| pydantic | 2.x | Event schema validation | Runtime validation for dataclass events, ensures data quality |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| python-statemachine | pytransitions | pytransitions has more features (hierarchical states) but heavier; python-statemachine is simpler for flat phase machine |
| structlog | stdlib logging with json.dumps | structlog provides better context binding and cleaner API; stdlib is adequate if no budget for deps |
| pydantic dataclasses | frozen dataclasses | pydantic adds runtime validation; plain frozen dataclasses are lighter but miss validation |
| JSONL files | SQLite | JSONL is simpler for append-only, easier to inspect/debug; SQLite better for queries but overkill for Phase 1 |

**Installation:**
```bash
pip install opencv-python pytesseract streamlink numpy python-statemachine structlog pytest-freezegun pydantic
```

**System Dependency:**
Tesseract-OCR binary must be installed separately:
- Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
- Configure path in `config.py` or add to PATH

---

## Architecture Patterns

### Recommended Project Structure

```
src/
├── vision_engine.py      # Existing VCTVisionEngine (no changes)
├── config.py             # Existing ROI/threshold configs (consolidate duplicates)
├── state/                # NEW: State management
│   ├── tracker.py        # StateTracker: frame history, diffing
│   ├── debouncer.py      # Debouncer: 3-frame consensus logic
│   └── validator.py      # Validators: range checks, coherence rules
├── events/               # NEW: Event emission
│   ├── schemas.py        # Event dataclasses (frozen, validated)
│   ├── emitter.py        # EventEmitter: state diffs -> events
│   └── store.py          # EventStore: JSONL append-only persistence
├── pipeline/             # NEW: Orchestration
│   ├── event_pipeline.py # EventPipeline: orchestrates state -> events
│   └── session.py        # MatchSession: metadata, match_id
├── quality/              # NEW: Replay detection & quality monitoring
│   ├── replay_detector.py # ReplayDetector: timer regression detection
│   └── metrics.py        # QualityMetrics: confidence tracking
└── backend.py            # REFACTOR: Use EventPipeline instead of direct JSON write
```

### Pattern 1: State Tracking with Ring Buffer

**What:** Use `collections.deque(maxlen=3)` to maintain sliding window of last 3 frame states for debouncing.

**When to use:** Every state field needs debouncing per user requirements (3-frame consensus).

**Example:**
```python
# Source: Python stdlib collections.deque documentation
from collections import deque
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class GameState:
    score_left: int
    score_right: int
    alive_left: int
    alive_right: int
    timer: str
    spike_planted: bool
    frame_number: int
    timestamp: float

class StateTracker:
    def __init__(self):
        self.history = deque(maxlen=3)  # Ring buffer: auto-evicts oldest

    def update(self, state: GameState) -> None:
        self.history.append(state)

    def has_consensus(self, field: str) -> bool:
        """Check if field value is stable across all 3 frames."""
        if len(self.history) < 3:
            return False

        values = [getattr(s, field) for s in self.history]
        return len(set(values)) == 1  # All same value

    def get_stable_value(self, field: str) -> Optional[any]:
        """Return field value only if it has 3-frame consensus."""
        if self.has_consensus(field):
            return getattr(self.history[-1], field)
        return None
```

**Why ring buffer:** Automatic oldest-item eviction with O(1) append/pop, thread-safe, built-in. Avoids manual index management and off-by-one errors.

---

### Pattern 2: Replay Detection via Timer Regression + Score Validation

**What:** Detect when timer increases (regression) AND score hasn't changed (not a new round), then suppress all event emission until timer progresses forward past regression point.

**When to use:** Every frame before event emission. This is CRITICAL - missed replays create phantom duplicate events.

**Example:**
```python
# Replay detection state machine pattern
from dataclasses import dataclass
from typing import Optional

@dataclass
class ReplayState:
    is_suppressed: bool = False
    regression_timer: Optional[str] = None  # Timer value at regression detection
    last_score: tuple[int, int] = (0, 0)

class ReplayDetector:
    def __init__(self):
        self.state = ReplayState()

    def check_frame(self, current_timer: str, current_score: tuple[int, int],
                    previous_timer: str, previous_score: tuple[int, int]) -> bool:
        """
        Returns True if events should be suppressed (replay detected).

        Detection: Timer regression AND score unchanged
        Exit: Timer progresses beyond regression point
        """
        # Convert timer strings to seconds for comparison
        current_sec = self._timer_to_seconds(current_timer)
        prev_sec = self._timer_to_seconds(previous_timer)

        # Detect regression: timer increased AND score unchanged
        if current_sec > prev_sec and current_score == previous_score:
            self.state.is_suppressed = True
            self.state.regression_timer = previous_timer
            self.state.last_score = current_score
            return True  # Suppress events

        # Exit replay: timer progressed beyond regression point
        if self.state.is_suppressed:
            regression_sec = self._timer_to_seconds(self.state.regression_timer)
            if current_sec < regression_sec:  # Timer moved forward past regression
                self.state.is_suppressed = False
                self.state.regression_timer = None
            return self.state.is_suppressed

        return False  # Not in replay

    def _timer_to_seconds(self, timer: str) -> int:
        """Convert MM:SS or M:SS to integer seconds."""
        try:
            parts = timer.split(':')
            return int(parts[0]) * 60 + int(parts[1])
        except (ValueError, IndexError):
            return 0  # Invalid timer format
```

**Why both conditions:** Timer regression alone has false positives (round transitions). Score validation alone misses replays shown during same score. Combining both gives high precision.

---

### Pattern 3: Frozen Dataclasses for Immutable Events

**What:** Use `@dataclass(frozen=True)` for event types to ensure immutability after creation. Add Pydantic validation for runtime checks.

**When to use:** All event schemas. Events are historical facts - they must never be mutated after creation.

**Example:**
```python
# Source: Python dataclasses docs + Pydantic integration
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from pydantic.dataclasses import dataclass as pydantic_dataclass

@pydantic_dataclass(frozen=True)
class BaseEvent:
    event_type: str
    timestamp: float
    frame_number: int
    game_time: str  # Timer OCR value (e.g., "1:23")

    # Full state snapshot at event time
    score_left: int
    score_right: int
    alive_left: int
    alive_right: int
    spike_planted: bool

@pydantic_dataclass(frozen=True)
class KillEvent(BaseEvent):
    event_type: Literal["kill"] = "kill"
    team: Literal["left", "right"]  # Which team lost a player
    alive_before: int
    alive_after: int

@pydantic_dataclass(frozen=True)
class RoundEndEvent(BaseEvent):
    event_type: Literal["round_end"] = "round_end"
    winner: Literal["left", "right"]
    win_condition: Literal["elimination", "spike_detonate", "spike_defuse", "timeout"]
    final_score: tuple[int, int]

@pydantic_dataclass(frozen=True)
class TimeoutEvent(BaseEvent):
    event_type: Literal["timeout"] = "timeout"
    team: Literal["left", "right"]  # Team that called timeout
```

**Why frozen:** Prevents accidental mutation. Enables safe hashing for deduplication. Makes events cacheable. Pydantic adds runtime validation to catch data quality issues early.

---

### Pattern 4: JSONL Append-Only Event Store

**What:** Store events as newline-delimited JSON (JSONL) with atomic flush after each event. One file per match.

**When to use:** Persistent event storage. JSONL is standard for append-only logs, easier to inspect than binary formats, supports streaming reads.

**Example:**
```python
# JSONL event persistence pattern
import json
from pathlib import Path
from dataclasses import asdict
from typing import List
from datetime import datetime

class EventStore:
    def __init__(self, match_id: str, output_dir: Path):
        self.match_id = match_id
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Filename: YYYY-MM-DD_match-id_events.jsonl
        date_str = datetime.now().strftime("%Y-%m-%d")
        self.log_file = self.output_dir / f"{date_str}_{match_id}_events.jsonl"

    def append(self, event: BaseEvent) -> None:
        """Append single event with immediate flush."""
        with self.log_file.open('a') as f:
            json.dump(asdict(event), f)
            f.write('\n')
            f.flush()  # Ensure written to disk immediately

    def append_batch(self, events: List[BaseEvent]) -> None:
        """Append multiple events atomically."""
        with self.log_file.open('a') as f:
            for event in events:
                json.dump(asdict(event), f)
                f.write('\n')
            f.flush()

    def read_events(self) -> List[dict]:
        """Read all events from log file."""
        if not self.log_file.exists():
            return []

        events = []
        with self.log_file.open('r') as f:
            for line in f:
                events.append(json.loads(line.strip()))
        return events
```

**Why JSONL:** Human-readable for debugging, standard format for log aggregation tools, supports streaming reads, survives crashes (each line is complete), no schema migration issues when adding fields.

---

### Pattern 5: Tesseract OCR with Confidence Scores and Character Whitelisting

**What:** Use `pytesseract.image_to_data()` to get per-word confidence scores, apply character whitelisting per field type, reject values below 0.7 confidence threshold.

**When to use:** All OCR operations. User requirement: 0.7 minimum confidence, character whitelisting by field type.

**Example:**
```python
# Source: pytesseract documentation, PyImageSearch character whitelisting guide
import pytesseract
import cv2
import re
from typing import Optional, Tuple
from dataclasses import dataclass

@dataclass
class OCRResult:
    text: str
    confidence: float
    is_valid: bool

class EnhancedOCR:
    # PSM 7 = single text line (for timer, score)
    # PSM 6 = uniform block of text

    def read_timer(self, img_crop) -> OCRResult:
        """
        Extract timer with format validation and character whitelisting.
        Expected format: M:SS or MM:SS (e.g., "1:30", "12:45")
        """
        config = r'--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789:'
        data = pytesseract.image_to_data(img_crop, config=config,
                                         output_type=pytesseract.Output.DICT)

        # Extract text and confidence
        text = ' '.join([data['text'][i] for i in range(len(data['text']))
                        if int(data['conf'][i]) > 0]).strip()

        # Calculate average confidence (exclude -1 values)
        confs = [int(data['conf'][i]) for i in range(len(data['conf']))
                if int(data['conf'][i]) > 0]
        avg_conf = sum(confs) / len(confs) if confs else 0

        # Validate format: M:SS or MM:SS
        is_valid = bool(re.match(r'^\d{1,2}:\d{2}$', text)) and avg_conf >= 70

        return OCRResult(text=text, confidence=avg_conf/100, is_valid=is_valid)

    def read_score(self, img_crop) -> OCRResult:
        """
        Extract score (single digit 0-13).
        Character whitelist: 0-9 only
        """
        config = r'--psm 6 --oem 3 -c tessedit_char_whitelist=0123456789'
        data = pytesseract.image_to_data(img_crop, config=config,
                                         output_type=pytesseract.Output.DICT)

        # Extract text and confidence
        text = ''.join([data['text'][i] for i in range(len(data['text']))
                       if int(data['conf'][i]) > 0]).strip()

        confs = [int(data['conf'][i]) for i in range(len(data['conf']))
                if int(data['conf'][i]) > 0]
        avg_conf = sum(confs) / len(confs) if confs else 0

        # Validate: single or double digit, 0-13 range
        try:
            score_val = int(text)
            is_valid = 0 <= score_val <= 13 and avg_conf >= 70
        except ValueError:
            is_valid = False
            score_val = 0

        return OCRResult(text=str(score_val), confidence=avg_conf/100, is_valid=is_valid)

    def read_alive_count(self, img_crop) -> OCRResult:
        """
        Extract alive count (0-5).
        Character whitelist: 0-5 only
        """
        config = r'--psm 6 --oem 3 -c tessedit_char_whitelist=012345'
        data = pytesseract.image_to_data(img_crop, config=config,
                                         output_type=pytesseract.Output.DICT)

        text = ''.join([data['text'][i] for i in range(len(data['text']))
                       if int(data['conf'][i]) > 0]).strip()

        confs = [int(data['conf'][i]) for i in range(len(data['conf']))
                if int(data['conf'][i]) > 0]
        avg_conf = sum(confs) / len(confs) if confs else 0

        # Validate: single digit, 0-5 range
        try:
            count = int(text)
            is_valid = 0 <= count <= 5 and avg_conf >= 70
        except ValueError:
            is_valid = False
            count = 0

        return OCRResult(text=str(count), confidence=avg_conf/100, is_valid=is_valid)
```

**Key details:**
- PSM 7 for single-line text (timer)
- PSM 6 for uniform block (score, alive count)
- `tessedit_char_whitelist` prevents OCR from outputting invalid characters
- Confidence threshold 0.7 (70%) per user requirements
- Format validation with regex (timer must match M:SS pattern)
- Range validation (score 0-13, alive 0-5)

---

### Pattern 6: Structured Logging with Quality Metrics

**What:** Use structlog for JSON-formatted logs with bound context. Track per-field OCR confidence, debounce statistics, replay detection triggers.

**When to use:** All logging. User requirement: quality metrics for post-stream analysis, console warnings for significant issues.

**Example:**
```python
# Source: structlog documentation
import structlog
from structlog.stdlib import LoggerFactory

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

class QualityMetrics:
    def __init__(self):
        self.consecutive_failures = 0
        self.total_frames = 0
        self.ocr_confidence_sum = {'timer': 0, 'score': 0, 'alive': 0}
        self.ocr_confidence_count = {'timer': 0, 'score': 0, 'alive': 0}
        self.replay_detections = 0

    def log_ocr_result(self, field: str, confidence: float, is_valid: bool):
        """Track OCR quality per field type."""
        self.total_frames += 1

        if is_valid:
            self.ocr_confidence_sum[field] += confidence
            self.ocr_confidence_count[field] += 1
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1

        # User requirement: warn at 10+ consecutive failures
        if self.consecutive_failures >= 10:
            logger.warning(
                "ocr_degradation",
                field=field,
                consecutive_failures=self.consecutive_failures,
                avg_confidence=self.get_avg_confidence(field)
            )

        # User requirement: pause at 30+ seconds of failures (30fps * 30s = 900 frames, but we process at 6fps = 180 frames)
        if self.consecutive_failures >= 180:  # 30 seconds at 6fps
            logger.error(
                "ocr_extended_degradation",
                consecutive_failures=self.consecutive_failures,
                recommendation="Check ROI alignment or stream quality"
            )

    def log_replay_detection(self, timer_regression: str, current_score: tuple):
        """Track replay detection triggers."""
        self.replay_detections += 1
        logger.info(
            "replay_detected",
            regression_timer=timer_regression,
            current_score=current_score,
            total_replays=self.replay_detections
        )

    def get_avg_confidence(self, field: str) -> float:
        """Calculate average OCR confidence for field type."""
        count = self.ocr_confidence_count.get(field, 0)
        if count == 0:
            return 0.0
        return self.ocr_confidence_sum[field] / count

    def get_summary(self) -> dict:
        """Get quality metrics summary for post-stream analysis."""
        return {
            'total_frames': self.total_frames,
            'replay_detections': self.replay_detections,
            'avg_confidence': {
                field: self.get_avg_confidence(field)
                for field in ['timer', 'score', 'alive']
            },
            'ocr_success_rate': {
                field: self.ocr_confidence_count[field] / max(1, self.total_frames)
                for field in ['timer', 'score', 'alive']
            }
        }
```

**Why structlog:** JSON output easy to parse for analysis, context binding avoids repetitive key-value pairs, processor pipeline allows adding metadata (timestamps, log levels) automatically.

---

### Anti-Patterns to Avoid

- **Anti-pattern: Modifying existing VCTVisionEngine code** - Keep it stateless and untouched. Wrap it instead. Existing code works; changes risk breaking it.

- **Anti-pattern: Single-frame state change detection** - OCR flickers create event storms. Always use 3-frame debouncing per user requirements.

- **Anti-pattern: Ignoring replay detection** - Phantom duplicate events corrupt training data. Replay detection is foundational, not optional.

- **Anti-pattern: Overwriting event logs** - Current `game_state.json` overwrite pattern loses history. Use append-only JSONL.

- **Anti-pattern: Hard-coding event types in pipeline** - Use event type registration pattern (dict mapping event_type -> handler) for extensibility.

- **Anti-pattern: Blocking on OCR failures** - If timer OCR fails, continue processing other fields with last known timer value. Graceful degradation.

- **Anti-pattern: Using wall clock time as game time** - Use OCR'd timer value for event timestamps. Wall clock time is for debugging only.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| State machine for round phases | Custom if/else phase tracking | `python-statemachine` library | Handles transitions, guards, callbacks cleanly; avoids spaghetti conditionals |
| Frame buffering for debouncing | Manual list/array management | `collections.deque(maxlen=N)` | Built-in ring buffer, thread-safe, O(1) operations, auto-eviction |
| Event schema validation | Manual type checks | `pydantic` dataclasses | Runtime validation, clear error messages, free serialization |
| Structured logging | `json.dumps()` on dicts | `structlog` | Context binding, processor pipeline, cleaner API than stdlib |
| Time mocking in tests | Manual datetime patching | `pytest-freezegun` | Clean fixture-based time control, avoids brittle mock.patch |
| Replay detection heuristics | Complex multi-condition logic | State machine with explicit states (NORMAL, REPLAY_SUSPECTED, REPLAY_CONFIRMED) | Easier to test, debug, and reason about edge cases |

**Key insight:** Computer vision event detection involves complex state management. Hand-rolling state machines, ring buffers, and validation logic creates subtle bugs (off-by-one errors, race conditions, missed edge cases). Use battle-tested libraries.

---

## Common Pitfalls

### Pitfall 1: Replay Footage Creating Phantom Events

**What goes wrong:** VCT broadcasts show replays during timeouts and between rounds. Without detection, system logs duplicate kills/rounds with wrong timestamps. A 30-second replay injects 5-10 false events.

**Why it happens:**
- Replays use same overlay as live footage (scores, alive counts visible)
- Timer may continue running or reset during replays
- No visual "REPLAY" indicator in all replay types
- State extraction works identically on replay vs live

**How to avoid:**
1. Implement timer regression detection: if timer increases AND score unchanged, enter replay suppression mode
2. Suppress all event emission until timer progresses forward past regression point
3. Track previous 3 frames of timer + score for comparison
4. Log replay detection triggers for post-stream quality analysis

**Warning signs:**
- Event log shows more kills than possible in a round (8+ kills in 5v5 round)
- Alive count increases mid-round without score change
- Timestamp order violations in event log
- Same kill sequence appears twice with different timestamps

**From existing research:** This is the #1 critical pitfall. Phantom events corrupt training data irreversibly. Implement before processing any matches.

---

### Pitfall 2: OCR Flicker Creating Event Storms

**What goes wrong:** pytesseract is non-deterministic on marginal inputs. Timer OCR flickers between "1:30" and "1:3C" across frames. Without debouncing, single kill generates 5-10 duplicate kill events as alive_count oscillates.

**Why it happens:**
- Stream compression artifacts affect OCR consistency
- Brightness-based alive detection sensitive to lighting changes
- Processing at 6fps means events happen between frames
- OCR confidence varies frame-to-frame on same ROI

**How to avoid:**
1. Use 3-frame consensus: state change only confirmed if stable across 3 consecutive frames (user requirement)
2. Reject OCR results below 0.7 confidence threshold (user requirement)
3. Apply character whitelisting to prevent garbage characters (timer=[0-9:], score=[0-9])
4. Use `collections.deque(maxlen=3)` for automatic frame buffering
5. Validate field values (alive count 0-5, score 0-13, timer format M:SS)

**Warning signs:**
- Event log has 50+ events per round (should be 5-15)
- Multiple identical events within 2 seconds
- Log file size exceeds 1MB per match (should be 50-200KB)
- Kill events when alive_count delta is 0

**From existing research:** Pitfall #3 in existing analysis. Debouncing is the difference between usable and unusable data.

---

### Pitfall 3: Hardcoded ROI Coordinates Breaking on Overlay Updates

**What goes wrong:** VCT updates broadcast overlay between seasons. Hardcoded ROI coordinates suddenly extract wrong data. All OCR returns garbage but system continues running (silent failure).

**Why it happens:**
- Riot updates graphics every few months (Champions vs Masters overlays)
- Different stream sources (YouTube vs Twitch) may use slightly different layouts
- Codebase has TWO conflicting ROI systems (config.py vs vision_engine.py)

**How to avoid:**
1. Consolidate ROI definitions to single source of truth (config.py)
2. Add startup ROI validation: test OCR on first frame, expect reasonable values
3. Implement runtime sanity checks: if score OCR fails 10+ consecutive frames, alert ROI misalignment
4. Log stream metadata (resolution, source) to correlate with accuracy issues
5. Phase 1 cleanup: fix config.py vs vision_engine.py duplication before building on it

**Warning signs:**
- OCR consistently returns empty strings
- Score/timer never changes despite visible round progression
- Alive counts stay at 0 or 5 entire match
- Log warnings show 10+ consecutive OCR failures

**From existing research:** Pitfall #2 in existing analysis. Silent failure mode makes this dangerous.

---

### Pitfall 4: Invalid State Transitions Not Detected

**What goes wrong:** Alive count increases mid-round (impossible in Valorant), score decreases (impossible), or spike plants before round starts. Events logged despite violating game logic.

**Why it happens:**
- OCR errors produce out-of-range values
- No state coherence validation
- Round boundaries not clearly marked
- No state machine enforcing valid transitions

**How to avoid:**
1. Implement state validators per user requirements:
   - Alive count only decreases within round (QUAL-02)
   - Score only increases within half (QUAL-03)
   - Spike can only plant after round starts
2. Discard frames with invalid values immediately (user requirement)
3. Track previous round state to detect resets
4. Log validation failures for quality metrics

**Warning signs:**
- Alive count goes from 3 to 5 mid-round
- Score decreases (12 to 11)
- Spike planted at timer 1:40 (buy phase)
- Events logged with alive_count > 5

**From user constraints:** Validation is explicit requirement (QUAL-02, QUAL-03). Invalid values discarded, not auto-corrected.

---

### Pitfall 5: Timeout Events Not Attributed to Calling Team

**What goes wrong:** System detects tactical timeout but doesn't track which team called it. User requirement says timeouts are momentum indicators - team attribution is critical.

**Why it happens:**
- Timeout detection is new requirement (not in existing code)
- VCT overlay may show timeout with team indicator (requires new ROI)
- Timeout detection logic not yet defined

**How to avoid:**
1. Research VCT timeout overlay: is there a team indicator? Text like "TEAM A TIMEOUT"?
2. If yes: add OCR ROI for timeout text, extract team name
3. If no: track game state context (which team is losing rounds) for heuristic attribution
4. Create TimeoutEvent schema with team field (Literal["left", "right"])
5. Log timeout events with explicit team attribution

**Warning signs:**
- Timeout events logged without team field
- Cannot correlate timeouts with momentum shifts in analysis
- User requirement not satisfied

**From user constraints:** "Tactical timeouts tracked as explicit events: Log TIMEOUT events with team attribution (which team called it) - timeouts are momentum indicators crucial for prediction."

---

### Pitfall 6: Timestamp Precision Confusion

**What goes wrong:** Events timestamped with frame capture time (wall clock) instead of game time (OCR timer). Two kills 50ms apart appear simultaneous. Can't distinguish trade kills from double kills.

**Why it happens:**
- Processing at 6fps means 166ms between frames
- Multiple game events can occur between processed frames
- time.time() gives frame processing time, not game event time
- No access to game server timestamps

**How to avoid:**
1. Use OCR'd timer as primary event timestamp (user requirement: include round timer in events)
2. Convert timer string to seconds remaining for sortable timestamps
3. Store both game_time (timer) and wall_clock_time (frame capture) in events
4. Accept precision limits: events in same frame have ~166ms uncertainty
5. Document timestamp strategy upfront (changing later requires reprocessing all data)

**Warning signs:**
- Event timestamps don't align with timer values
- Multiple events have identical timestamps
- Events appear out of logical order (round end before final kill)

**From user constraints:** "Spike events (plant/defuse/detonate) include round timer at event time for timing analysis."

---

## Code Examples

Verified patterns from official sources and existing codebase.

### Example 1: State Tracker with 3-Frame Consensus

```python
# Pattern: Ring buffer for debouncing with consensus detection
from collections import deque
from dataclasses import dataclass
from typing import Optional, Any

@dataclass(frozen=True)
class GameState:
    score_left: int
    score_right: int
    alive_left: int
    alive_right: int
    timer: str
    spike_planted: bool
    frame_number: int
    timestamp: float
    ocr_confidence: dict  # Per-field confidence scores

class StateTracker:
    """
    Tracks frame state history and detects stable state changes.
    Uses 3-frame consensus per user requirements.
    """
    def __init__(self):
        self.history: deque[GameState] = deque(maxlen=3)
        self.confirmed_state: Optional[GameState] = None

    def update(self, state: GameState) -> None:
        """Add new state to history (auto-evicts oldest if full)."""
        self.history.append(state)

    def get_stable_fields(self) -> dict[str, Any]:
        """
        Return dict of field->value for all fields with 3-frame consensus.
        Returns empty dict if < 3 frames in history.
        """
        if len(self.history) < 3:
            return {}

        stable = {}
        fields = ['score_left', 'score_right', 'alive_left', 'alive_right',
                 'timer', 'spike_planted']

        for field in fields:
            values = [getattr(state, field) for state in self.history]
            # Check if all 3 values are identical
            if len(set(values)) == 1:
                stable[field] = values[-1]  # Return current value

        return stable

    def detect_changes(self, previous_confirmed: Optional[GameState]) -> dict[str, tuple[Any, Any]]:
        """
        Compare current stable state with previous confirmed state.
        Returns dict of field->(old_value, new_value) for changed fields.
        """
        current_stable = self.get_stable_fields()
        if not current_stable or previous_confirmed is None:
            return {}

        changes = {}
        for field, new_val in current_stable.items():
            old_val = getattr(previous_confirmed, field)
            if old_val != new_val:
                changes[field] = (old_val, new_val)

        return changes
```

---

### Example 2: Replay Detector with Timer Regression

```python
# Pattern: Timer regression detection with score validation
from dataclasses import dataclass
from typing import Optional
import re

@dataclass
class ReplayState:
    is_suppressed: bool = False
    regression_timer_sec: Optional[int] = None
    last_score: tuple[int, int] = (0, 0)

class ReplayDetector:
    """
    Detects replay footage via timer regression + score validation.
    User requirement: both conditions required for detection.
    """
    def __init__(self):
        self.state = ReplayState()

    def should_suppress_events(self, current_timer: str, current_score: tuple[int, int],
                               previous_timer: str, previous_score: tuple[int, int]) -> bool:
        """
        Returns True if events should be suppressed (replay active).

        Detection: Timer regression (increases) AND score unchanged
        Exit: Timer progresses forward past regression point
        """
        current_sec = self._timer_to_seconds(current_timer)
        prev_sec = self._timer_to_seconds(previous_timer)

        # Skip if timer parse failed
        if current_sec is None or prev_sec is None:
            return self.state.is_suppressed  # Maintain current state

        # Detect NEW replay: timer increased AND score same
        if current_sec > prev_sec and current_score == previous_score:
            self.state.is_suppressed = True
            self.state.regression_timer_sec = prev_sec
            self.state.last_score = current_score
            return True

        # Check if still in replay
        if self.state.is_suppressed:
            # Exit condition: timer moved forward past regression point
            if current_sec < self.state.regression_timer_sec:
                self.state.is_suppressed = False
                self.state.regression_timer_sec = None
            return self.state.is_suppressed

        return False

    def _timer_to_seconds(self, timer: str) -> Optional[int]:
        """Convert MM:SS or M:SS to integer seconds. Returns None if invalid."""
        match = re.match(r'^(\d{1,2}):(\d{2})$', timer)
        if not match:
            return None

        try:
            minutes = int(match.group(1))
            seconds = int(match.group(2))
            return minutes * 60 + seconds
        except ValueError:
            return None
```

---

### Example 3: Event Emission from State Changes

```python
# Pattern: State diff -> typed events with validation
from typing import List, Optional
from dataclasses import asdict

class EventEmitter:
    """
    Transforms state changes into typed Event objects.
    Each state diff triggers appropriate event type.
    """
    def emit_events(self, changes: dict, current_state: GameState,
                    previous_state: GameState) -> List[BaseEvent]:
        """
        Generate events from detected state changes.
        User requirement: each event includes full game state snapshot.
        """
        events = []
        base_data = {
            'timestamp': current_state.timestamp,
            'frame_number': current_state.frame_number,
            'game_time': current_state.timer,
            'score_left': current_state.score_left,
            'score_right': current_state.score_right,
            'alive_left': current_state.alive_left,
            'alive_right': current_state.alive_right,
            'spike_planted': current_state.spike_planted,
        }

        # Score change -> Round end event
        if 'score_left' in changes or 'score_right' in changes:
            winner = 'left' if current_state.score_left > previous_state.score_left else 'right'
            win_condition = self._infer_win_condition(changes, previous_state, current_state)

            events.append(RoundEndEvent(
                **base_data,
                winner=winner,
                win_condition=win_condition,
                final_score=(current_state.score_left, current_state.score_right)
            ))

        # Alive count decrease -> Kill event
        if 'alive_left' in changes and current_state.alive_left < previous_state.alive_left:
            events.append(KillEvent(
                **base_data,
                team='left',
                alive_before=previous_state.alive_left,
                alive_after=current_state.alive_left
            ))

        if 'alive_right' in changes and current_state.alive_right < previous_state.alive_right:
            events.append(KillEvent(
                **base_data,
                team='right',
                alive_before=previous_state.alive_right,
                alive_after=current_state.alive_right
            ))

        # Spike planted -> SpikeEvent
        if 'spike_planted' in changes:
            old_planted, new_planted = changes['spike_planted']
            if not old_planted and new_planted:
                events.append(SpikeEvent(
                    **base_data,
                    event_type='spike_plant',
                    spike_action='plant'
                ))

        return events

    def _infer_win_condition(self, changes: dict, prev: GameState, curr: GameState) -> str:
        """
        Infer how round was won from event sequence.
        User requirement: infer from event sequence.
        """
        # Check recent events for spike detonation/defuse
        # This is simplified - real implementation would check event history
        if curr.alive_left == 0 or curr.alive_right == 0:
            return 'elimination'
        elif prev.spike_planted and not curr.spike_planted:
            # Spike no longer planted - either defused or detonated
            # Need more context to distinguish - placeholder logic
            return 'spike_defuse'  # or 'spike_detonate' based on winner
        else:
            return 'timeout'  # Timer ran out
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Frame-by-frame JSON overwrite | Append-only JSONL event log | Phase 1 requirement | Enables historical analysis, survives crashes |
| Single-frame state detection | 3-frame consensus debouncing | User requirement | Eliminates event storms from OCR flicker |
| Ignore replay footage | Timer regression + score validation | Phase 1 requirement | Prevents phantom duplicate events |
| Wall clock timestamps | Game timer (OCR) as event time | User requirement | Enables accurate timing analysis |
| Manual type checks | Pydantic dataclass validation | Current best practice | Catches data quality issues at creation time |
| String-based logging | Structured JSON logging (structlog) | Current best practice | Enables automated quality metrics analysis |

**Deprecated/outdated:**
- **game_state.json overwriting**: Current approach loses event history. Replace with JSONL append-only log.
- **Config duplication**: config.py and vision_engine.py have conflicting ROI definitions. Consolidate to single source (config.py).
- **No confidence thresholds**: Current OCR usage doesn't check confidence. Add 0.7 threshold per user requirements.
- **Brightness-only alive detection**: vision_engine.py uses only brightness for alive status. Works but fragile. Keep for Phase 1, research alternatives for Phase 2.

---

## Open Questions

### Question 1: Timeout Team Attribution Detection Method

**What we know:**
- User requirement: timeouts must have team attribution
- Timeouts are momentum indicators for prediction
- VCT broadcasts show tactical timeouts

**What's unclear:**
- Does VCT overlay show which team called timeout with text/indicator?
- If yes, what ROI coordinates and OCR approach?
- If no, what heuristic can attribute timeout to team?

**Recommendation:**
1. Watch VCT match with timeout, screenshot overlay during timeout
2. Check for "TEAM A TIMEOUT" or similar text indicator
3. If visible: add ROI for timeout text, OCR team name, fuzzy match to team metadata
4. If not visible: use game context heuristic (team losing momentum more likely to call timeout)
5. Mark as LOW confidence if using heuristic, HIGH if OCR'd from overlay

### Question 2: Optimal OCR Image Preprocessing Pipeline

**What we know:**
- Current approach: grayscale, threshold, invert (vision_engine.py)
- PyImageSearch recommends: upscale 2x, denoise, adaptive threshold

**What's unclear:**
- Does current preprocessing achieve 0.7+ confidence consistently?
- Would upscaling/denoising improve confidence without slowing processing?
- Optimal threshold values for VCT overlay (current: 180)

**Recommendation:**
1. Add OCR confidence logging to existing code (no changes to preprocessing)
2. Run on sample match, measure per-field average confidence
3. If < 0.7 average: experiment with preprocessing enhancements (upscale, denoise)
4. Benchmark processing time vs confidence gain
5. Phase 1 can use current preprocessing if confidence acceptable, defer optimization to Phase 2

### Question 3: Spike Defuse vs Detonate Distinction

**What we know:**
- Both transitions: spike_planted=True -> spike_planted=False
- User requirement: distinguish defuse from detonate for win condition inference

**What's unclear:**
- How to detect which occurred? Different overlay indicators?
- Does timer matter? (Defuse usually has more time remaining)
- Is there a color change or icon difference?

**Recommendation:**
1. Analyze VCT footage: screenshot spike defuse and spike detonate moments
2. Check for visual differences (overlay text, icon color, timer state)
3. If distinguishable: add detection logic (ROI or color threshold)
4. If not distinguishable from overlay: use round outcome context (winning team attackers = detonate, defenders = defuse)
5. Log confidence level for win_condition inference

---

## Sources

### Primary (HIGH confidence)

**Existing Codebase Analysis:**
- `vision_engine.py` - Current CV extraction methods (stateless, working)
- `config.py` - ROI definitions and thresholds (needs consolidation)
- `backend.py` - Frame processing loop (needs refactor to pipeline)
- `.planning/research/PITFALLS.md` - Domain-specific pitfalls (comprehensive)
- `.planning/research/ARCHITECTURE.md` - Recommended architecture patterns
- `.planning/REQUIREMENTS.md` - Phase 1 requirements (EVNT-01 through QUAL-05)

**Official Python Documentation:**
- [collections.deque](https://docs.python.org/3/library/collections.html#collections.deque) - Ring buffer for frame history
- [dataclasses](https://docs.python.org/3/library/dataclasses.html) - Frozen dataclasses for immutable events
- [Python logging](https://docs.python.org/3/howto/logging.html) - Stdlib logging patterns

**Library Documentation:**
- [pytesseract PyPI](https://pypi.org/project/pytesseract/) - OCR confidence scores, PSM modes
- [python-statemachine](https://python-statemachine.readthedocs.io/) - FSM patterns for round phases
- [structlog](https://www.structlog.org/) - Structured JSON logging
- [Pydantic dataclasses](https://docs.pydantic.dev/latest/concepts/dataclasses/) - Runtime validation

### Secondary (MEDIUM confidence)

**Community Guides (2026):**
- [PyImageSearch: Tesseract PSM Modes](https://pyimagesearch.com/2021/11/15/tesseract-page-segmentation-modes-psms-explained-how-to-improve-your-ocr-accuracy/) - PSM 7 for single line, character whitelisting
- [PyImageSearch: Character Whitelisting](https://pyimagesearch.com/2021/09/06/whitelisting-and-blacklisting-characters-with-tesseract-and-python/) - tessedit_char_whitelist configuration
- [Better Stack: Python Logging Best Practices](https://betterstack.com/community/guides/logging/python/python-logging-best-practices/) - Structured logging, log levels
- [Real Python: Python Deque](https://realpython.com/python-deque/) - Deque as ring buffer, maxlen parameter
- [Pytest with Eric: Freezegun Guide](https://pytest-with-eric.com/plugins/python-freezegun/) - Time mocking for debouncing tests

**Esports Data Practices:**
- [Number Analytics: Event Tracking in Esports](https://www.numberanalytics.com/blog/ultimate-guide-event-tracking-esports) - Best practices for event logging, naming conventions
- [Medium: Valorant Broadcast UI Evolution](https://medium.com/@janushshah/the-5-year-journey-of-valorants-broadcast-ui-from-clutter-to-clarity-f0bc4b60c46d) - VCT overlay changes over time

### Tertiary (LOW confidence - needs verification)

**WebSearch Findings:**
- Video OCR best practices (upscaling to 2x, denoising, adaptive thresholding) - not yet tested on VCT overlays
- Frame differencing for motion detection - standard CV technique but not directly applicable to state tracking
- Timeout overlay indicators - visual confirmation needed from actual VCT broadcast

---

## Metadata

**Confidence breakdown:**
- **Standard stack: HIGH** - Libraries verified from official docs, already in use (opencv, pytesseract) or standard for use case (structlog, pydantic)
- **Architecture patterns: HIGH** - Based on existing project ARCHITECTURE.md research, Python stdlib docs, established CV pipeline patterns
- **Pitfalls: HIGH** - From existing PITFALLS.md analysis of codebase, supplemented with domain expertise
- **User constraints: HIGH** - Directly from CONTEXT.md user decisions
- **OCR techniques: MEDIUM** - Tesseract docs verified, but optimal preprocessing for VCT overlays needs empirical testing
- **Timeout detection: LOW** - Requires visual confirmation of VCT overlay during timeout

**Research date:** 2026-02-12
**Valid until:** 30 days (libraries stable, VCT overlay may update with new tournament season)

**Next steps for planner:**
1. Create tasks for state tracking layer (StateTracker, Debouncer, ReplayDetector)
2. Create tasks for event emission (event schemas, EventEmitter, EventStore)
3. Create tasks for pipeline orchestration (EventPipeline, MatchSession)
4. Create tasks for quality monitoring (QualityMetrics, structured logging)
5. Create tasks for cleanup (consolidate config.py vs vision_engine.py ROI defs)
6. Create verification tasks (test replay detection, debouncing, OCR confidence thresholds)
