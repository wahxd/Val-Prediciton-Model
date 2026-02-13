# Architecture Patterns: CV-Based Event Detection Pipeline

**Domain:** Esports event logging from broadcast video
**Researched:** 2026-02-12
**Confidence:** HIGH (based on established CV pipeline patterns, event sourcing, and state machine architectures)

## Executive Summary

Transforming a stateless frame-by-frame CV extractor into an event-based logging system requires four core architectural patterns:

1. **State Diffing** - Compare consecutive frames to detect changes
2. **Event Emission** - Transform state changes into typed events
3. **Persistent Event Store** - Append-only log with match session management
4. **Extensible Event Types** - Schema that supports evolution without breaking changes

The recommended architecture builds **on top of** existing code by wrapping `VCTVisionEngine` with new components rather than rewriting it.

---

## Recommended Architecture

### High-Level Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         MATCH SESSION                                │
│  (Metadata: teams, map, start_time, match_id)                       │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────┐        ┌─────────────────┐        ┌──────────────┐
│  GameWatcher    │───────▶│  EventPipeline  │───────▶│  EventStore  │
│  (Frame Loop)   │ frames │  (Orchestrator) │ events │  (Persistent)│
└─────────────────┘        └─────────────────┘        └──────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
            ┌──────────────┐ ┌─────────────┐ ┌──────────────┐
            │ StateTracker │ │ EventEmitter│ │ MetadataOCR  │
            │  (Differs)   │ │ (Factories) │ │  (Teams/Map) │
            └──────────────┘ └─────────────┘ └──────────────┘
                    │
                    ▼
            ┌──────────────┐
            │VCTVisionEngine│
            │  (Existing)   │
            └──────────────┘
```

### Data Flow

```
1. GameWatcher.run() → reads frame at 6fps
2. EventPipeline.process_frame(frame, timestamp) orchestrates:
   a. VCTVisionEngine.analyze(frame) → raw state dict
   b. StateTracker.update(state) → compares with previous state
   c. StateTracker.detect_changes() → list of state diffs
   d. EventEmitter.emit_events(diffs) → typed Event objects
   e. EventStore.append(events) → writes to persistent log
3. StateTracker caches current state for next frame
4. Loop continues until match ends
```

---

## Component Boundaries

### 1. VCTVisionEngine (Existing - No Changes)

**Responsibility:** Extract raw game state from a single frame

**Interface:**
```python
def analyze(frame: np.ndarray) -> Dict[str, Any]:
    return {
        'score_left': int,
        'score_right': int,
        'alive_left': int,
        'alive_right': int,
        'spike_planted': bool,
        'eco_left': int,  # if available
        'eco_right': int
    }
```

**No modifications needed.** This component remains stateless and reusable.

---

### 2. StateTracker (New Component)

**Responsibility:** Maintain previous frame state and detect changes

**Interface:**
```python
class StateTracker:
    def __init__(self):
        self.current_state: Optional[GameState] = None
        self.previous_state: Optional[GameState] = None

    def update(self, raw_state: Dict[str, Any]) -> List[StateChange]:
        """
        Compares new state with previous state.
        Returns list of detected changes.
        """
        changes = []

        if self.current_state is None:
            # First frame - no diffs yet
            self.current_state = GameState.from_dict(raw_state)
            return []

        # Shift states
        self.previous_state = self.current_state
        self.current_state = GameState.from_dict(raw_state)

        # Detect changes
        changes.extend(self._detect_score_changes())
        changes.extend(self._detect_alive_changes())
        changes.extend(self._detect_spike_changes())
        changes.extend(self._detect_economy_changes())

        return changes

    def _detect_score_changes(self) -> List[StateChange]:
        """Score increase = round ended"""
        changes = []

        if self.current_state.score_left > self.previous_state.score_left:
            changes.append(StateChange(
                type='ROUND_END',
                winner='left',
                new_score=(self.current_state.score_left, self.current_state.score_right)
            ))

        if self.current_state.score_right > self.previous_state.score_right:
            changes.append(StateChange(
                type='ROUND_END',
                winner='right',
                new_score=(self.current_state.score_left, self.current_state.score_right)
            ))

        return changes

    def _detect_alive_changes(self) -> List[StateChange]:
        """Alive count decrease = kill(s)"""
        changes = []

        left_delta = self.current_state.alive_left - self.previous_state.alive_left
        if left_delta < 0:
            changes.append(StateChange(
                type='KILLS',
                team='left',
                count=abs(left_delta),
                remaining_alive=self.current_state.alive_left
            ))

        right_delta = self.current_state.alive_right - self.previous_state.alive_right
        if right_delta < 0:
            changes.append(StateChange(
                type='KILLS',
                team='right',
                count=abs(right_delta),
                remaining_alive=self.current_state.alive_right
            ))

        return changes

    def _detect_spike_changes(self) -> List[StateChange]:
        """Spike status transitions"""
        changes = []

        # Planted: False → True
        if not self.previous_state.spike_planted and self.current_state.spike_planted:
            changes.append(StateChange(type='SPIKE_PLANTED'))

        # Defused: True → False (with no score change)
        # Note: If score changed, round ended - spike defuse is implicit
        if self.previous_state.spike_planted and not self.current_state.spike_planted:
            # Check if score changed (already handled by round_end)
            if self.current_state.score_left == self.previous_state.score_left and \
               self.current_state.score_right == self.previous_state.score_right:
                changes.append(StateChange(type='SPIKE_DEFUSED'))

        return changes

    def _detect_economy_changes(self) -> List[StateChange]:
        """Economy threshold crossings (eco/force/full buy)"""
        # Define buy thresholds
        ECO_THRESHOLD = 10000
        FORCE_THRESHOLD = 18000

        changes = []

        # Left team economy shift
        prev_left_tier = self._economy_tier(self.previous_state.eco_left)
        curr_left_tier = self._economy_tier(self.current_state.eco_left)
        if prev_left_tier != curr_left_tier:
            changes.append(StateChange(
                type='ECONOMY_SHIFT',
                team='left',
                from_tier=prev_left_tier,
                to_tier=curr_left_tier,
                total_credits=self.current_state.eco_left
            ))

        # Right team economy shift
        prev_right_tier = self._economy_tier(self.previous_state.eco_right)
        curr_right_tier = self._economy_tier(self.current_state.eco_right)
        if prev_right_tier != curr_right_tier:
            changes.append(StateChange(
                type='ECONOMY_SHIFT',
                team='right',
                from_tier=prev_right_tier,
                to_tier=curr_right_tier,
                total_credits=self.current_state.eco_right
            ))

        return changes

    def _economy_tier(self, credits: int) -> str:
        """Classify buy type"""
        if credits < 10000:
            return 'ECO'
        elif credits < 18000:
            return 'FORCE'
        else:
            return 'FULL'
```

**Key Design Decisions:**
- **Stateful but simple** - Only tracks last 2 frames (previous + current)
- **Change detection logic isolated** - Easy to add new detectors without touching other code
- **Returns typed changes** - Not raw dicts, but structured `StateChange` objects

---

### 3. EventEmitter (New Component)

**Responsibility:** Transform `StateChange` objects into timestamped `Event` objects with match context

**Interface:**
```python
class EventEmitter:
    def __init__(self, match_id: str):
        self.match_id = match_id

    def emit_events(self, changes: List[StateChange], timestamp: float) -> List[Event]:
        """
        Converts state changes into Event objects with metadata.
        """
        events = []

        for change in changes:
            event = Event(
                match_id=self.match_id,
                timestamp=timestamp,
                event_type=change.type,
                data=change.to_dict()
            )
            events.append(event)

        return events
```

**Event Schema:**
```python
@dataclass
class Event:
    match_id: str           # Links event to match session
    timestamp: float        # Unix timestamp (from frame)
    event_type: str         # 'ROUND_END', 'KILLS', 'SPIKE_PLANTED', etc.
    data: Dict[str, Any]    # Type-specific payload

    def to_json(self) -> str:
        """Serialize to JSON for storage"""
        return json.dumps({
            'match_id': self.match_id,
            'timestamp': self.timestamp,
            'event_type': self.event_type,
            'data': self.data
        })
```

**Why separate StateTracker and EventEmitter?**
- **Single Responsibility:** StateTracker = diffing logic, EventEmitter = serialization/formatting
- **Testability:** Can test diffing without event format concerns
- **Extensibility:** Can add event enrichment (e.g., team names) in EventEmitter without touching StateTracker

---

### 4. EventStore (New Component)

**Responsibility:** Persistent, append-only event log per match

**Interface:**
```python
class EventStore:
    def __init__(self, storage_dir: str = "match_logs"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        self.current_match_file: Optional[Path] = None

    def start_match(self, match_id: str, metadata: MatchMetadata) -> None:
        """
        Creates a new event log file for a match.
        Writes metadata header.
        """
        filename = f"{match_id}_{metadata.start_time}.jsonl"
        self.current_match_file = self.storage_dir / filename

        # Write metadata as first line
        with open(self.current_match_file, 'w') as f:
            f.write(json.dumps({
                'type': 'MATCH_START',
                'match_id': match_id,
                'metadata': metadata.to_dict()
            }) + '\n')

    def append(self, events: List[Event]) -> None:
        """
        Appends events to current match log (JSONL format).
        """
        if not self.current_match_file:
            raise RuntimeError("No active match session")

        with open(self.current_match_file, 'a') as f:
            for event in events:
                f.write(event.to_json() + '\n')

    def end_match(self, metadata: Optional[Dict] = None) -> None:
        """
        Writes MATCH_END event and closes session.
        """
        if self.current_match_file:
            with open(self.current_match_file, 'a') as f:
                f.write(json.dumps({
                    'type': 'MATCH_END',
                    'timestamp': time.time(),
                    'metadata': metadata or {}
                }) + '\n')

            self.current_match_file = None
```

**Storage Format: JSONL (JSON Lines)**
- One event per line
- Easy to stream/parse incrementally
- Human-readable for debugging
- Append-only = crash-safe

**File Structure:**
```
match_logs/
  match_001_1675893023.jsonl
  match_002_1675897654.jsonl
  ...
```

**Example JSONL Content:**
```jsonl
{"type": "MATCH_START", "match_id": "match_001", "metadata": {"teams": ["G2", "NRG"], "map": "Bind"}}
{"match_id": "match_001", "timestamp": 1675893025.3, "event_type": "ROUND_END", "data": {"winner": "left", "new_score": [1, 0]}}
{"match_id": "match_001", "timestamp": 1675893089.7, "event_type": "KILLS", "data": {"team": "right", "count": 2, "remaining_alive": 3}}
{"match_id": "match_001", "timestamp": 1675893091.2, "event_type": "SPIKE_PLANTED", "data": {}}
{"type": "MATCH_END", "timestamp": 1675893500.0, "metadata": {"final_score": [13, 10]}}
```

---

### 5. EventPipeline (New Component - Orchestrator)

**Responsibility:** Coordinate frame processing, state tracking, event emission, and storage

**Interface:**
```python
class EventPipeline:
    def __init__(self, match_id: str, metadata: MatchMetadata):
        self.match_id = match_id
        self.vision = VCTVisionEngine()
        self.tracker = StateTracker()
        self.emitter = EventEmitter(match_id)
        self.store = EventStore()

        # Start match session
        self.store.start_match(match_id, metadata)

    def process_frame(self, frame: np.ndarray, timestamp: float) -> List[Event]:
        """
        Full pipeline: frame → state → changes → events → storage
        """
        # 1. Extract raw state
        raw_state = self.vision.analyze(frame)

        # 2. Detect changes
        changes = self.tracker.update(raw_state)

        # 3. Emit events
        events = self.emitter.emit_events(changes, timestamp)

        # 4. Persist events
        if events:
            self.store.append(events)

        return events

    def end_match(self):
        """Finalize match log"""
        self.store.end_match()
```

**Why an orchestrator component?**
- **Encapsulation:** GameWatcher doesn't need to know about state tracking or event emission
- **Testability:** Can test pipeline with mock frames
- **Reusability:** Same pipeline can be used for live streams or VOD processing

---

### 6. MatchMetadata Extractor (New Component)

**Responsibility:** Auto-detect team names and map from broadcast overlay

**Interface:**
```python
class MetadataExtractor:
    def __init__(self):
        # ROIs for metadata (1920x1080 VCT layout)
        self.ROI_TEAM_LEFT = (50, 100, 200, 400)   # Team name left
        self.ROI_TEAM_RIGHT = (50, 100, 1520, 1720) # Team name right
        self.ROI_MAP_NAME = (1000, 1050, 800, 1120) # Map name (varies by broadcast)

    def extract_teams(self, frame: np.ndarray) -> Tuple[str, str]:
        """
        OCR team names from overlay.
        Returns (left_team, right_team).
        """
        left_crop = frame[self.ROI_TEAM_LEFT[0]:self.ROI_TEAM_LEFT[1],
                          self.ROI_TEAM_LEFT[2]:self.ROI_TEAM_LEFT[3]]
        right_crop = frame[self.ROI_TEAM_RIGHT[0]:self.ROI_TEAM_RIGHT[1],
                           self.ROI_TEAM_RIGHT[2]:self.ROI_TEAM_RIGHT[3]]

        left_team = self._ocr_text(left_crop).strip()
        right_team = self._ocr_text(right_crop).strip()

        return left_team, right_team

    def extract_map(self, frame: np.ndarray) -> str:
        """
        OCR map name from overlay.
        """
        map_crop = frame[self.ROI_MAP_NAME[0]:self.ROI_MAP_NAME[1],
                         self.ROI_MAP_NAME[2]:self.ROI_MAP_NAME[3]]

        map_name = self._ocr_text(map_crop).strip()

        # Validate against known maps
        known_maps = ['Bind', 'Haven', 'Split', 'Ascent', 'Icebox', 'Breeze', 'Fracture', 'Pearl', 'Lotus', 'Sunset', 'Abyss']
        for known in known_maps:
            if known.lower() in map_name.lower():
                return known

        return map_name  # Return raw if no match

    def _ocr_text(self, img_crop: np.ndarray) -> str:
        """Generic OCR for text"""
        gray = cv2.cvtColor(img_crop, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

        # Allow letters and spaces
        config = r'--oem 3 --psm 7'
        text = pytesseract.image_to_string(thresh, config=config)

        return text
```

**Usage Pattern:**
```python
# At match start
extractor = MetadataExtractor()
left_team, right_team = extractor.extract_teams(first_frame)
map_name = extractor.extract_map(first_frame)

metadata = MatchMetadata(
    teams=[left_team, right_team],
    map=map_name,
    start_time=time.time()
)
```

**Reliability Strategy:**
- Run extraction on first 10 frames and use majority vote
- Allow manual override if OCR fails
- Cache extracted metadata for match session

---

### 7. GameWatcher Integration (Modify Existing)

**Current Code:**
```python
# backend.py (existing)
def run(self):
    while True:
        ret, frame = self.cap.read()

        if frame_count % 10 != 0:
            continue

        state = self.process_frame(frame)

        # PROBLEM: Overwrites JSON every frame
        with open(self.output_file, 'w') as f:
            json.dump(state, f)
```

**Refactored Integration:**
```python
# backend.py (modified)
class GameWatcher:
    def __init__(self, stream_url, match_id=None):
        self.stream_url = stream_url
        self.cap = None
        self.pipeline = None  # Initialized after metadata extraction
        self.match_id = match_id or f"match_{int(time.time())}"

    def run(self):
        if not self.connect_stream():
            return

        # Extract metadata from first valid frame
        metadata = self._extract_metadata()

        # Initialize event pipeline
        self.pipeline = EventPipeline(self.match_id, metadata)

        frame_count = 0
        while True:
            ret, frame = self.cap.read()
            if not ret:
                print("Stream ended. Finalizing match...")
                self.pipeline.end_match()
                break

            frame_count += 1
            if frame_count % 10 != 0:
                continue

            try:
                # Process frame through event pipeline
                timestamp = time.time()
                events = self.pipeline.process_frame(frame, timestamp)

                # Optional: Print events to console
                for event in events:
                    print(f"[{event.event_type}] {event.data}")

            except Exception as e:
                print(f"Error processing frame: {e}")

    def _extract_metadata(self) -> MatchMetadata:
        """Extract teams/map from first valid frames"""
        extractor = MetadataExtractor()

        # Try first 10 frames
        attempts = []
        for _ in range(10):
            ret, frame = self.cap.read()
            if not ret:
                continue

            try:
                left, right = extractor.extract_teams(frame)
                map_name = extractor.extract_map(frame)
                attempts.append((left, right, map_name))
            except:
                continue

        # Use majority vote or first valid result
        if attempts:
            left, right, map_name = attempts[0]  # Simplified - use first
        else:
            # Fallback to manual input or defaults
            left, right, map_name = "Team A", "Team B", "Unknown"

        return MatchMetadata(
            teams=[left, right],
            map=map_name,
            start_time=time.time()
        )
```

**Key Changes:**
1. Replace `process_frame()` with `pipeline.process_frame()`
2. Extract metadata before starting event pipeline
3. Call `pipeline.end_match()` when stream ends
4. Remove JSON overwrite logic

---

## State Management Pattern

### Problem: How to Track "Previous State"?

**Anti-Pattern (Avoid):**
```python
# Global variable = hard to test, thread-unsafe
previous_state = None

def process_frame(frame):
    global previous_state
    current = extract_state(frame)

    if previous_state:
        detect_changes(previous_state, current)

    previous_state = current  # Mutates global
```

**Recommended Pattern: Encapsulated State in StateTracker**
```python
class StateTracker:
    def __init__(self):
        self.previous = None
        self.current = None

    def update(self, new_state):
        self.previous = self.current  # Shift
        self.current = new_state      # Update
        return self.detect_changes()
```

**Why Better?**
- **Testable:** Create new `StateTracker()` per test
- **Thread-safe:** Each pipeline has its own tracker
- **Explicit:** State ownership is clear

### Handling Edge Cases

**1. First Frame (No Previous State)**
```python
if self.current_state is None:
    self.current_state = new_state
    return []  # No changes yet
```

**2. Round Resets (Alive Count Jumps from 0 → 5)**
```python
# Detect new round start
if self.previous_state.alive_left == 0 and self.current_state.alive_left == 5:
    return [StateChange(type='ROUND_START')]
```

**3. OCR Errors (Score Temporarily Reads Wrong)**
```python
# Smoothing: Require change to persist for 3 frames
class StateTracker:
    def __init__(self):
        self.state_buffer = deque(maxlen=3)

    def update(self, new_state):
        self.state_buffer.append(new_state)

        # Only emit change if all 3 frames agree
        if len(self.state_buffer) == 3:
            if all(s.score_left == self.state_buffer[-1].score_left for s in self.state_buffer):
                # Stable state
                return self.detect_changes()
```

**Trade-off:** Smoothing reduces false positives but adds 0.5s latency (at 6fps).

**Recommendation for MVP:** No smoothing initially. Add if OCR errors cause event spam.

---

## Extensible Event Types

### Design Goal: Add New Event Types Without Breaking Existing Code

**Strategy: Type Registry + Factory Pattern**

```python
# event_types.py
from typing import Dict, Type
from dataclasses import dataclass

@dataclass
class BaseEvent:
    """All events inherit from this"""
    match_id: str
    timestamp: float
    event_type: str

    def to_dict(self) -> Dict:
        raise NotImplementedError

# Built-in event types
@dataclass
class RoundEndEvent(BaseEvent):
    winner: str
    new_score: Tuple[int, int]

    def to_dict(self):
        return {
            'winner': self.winner,
            'new_score': self.new_score
        }

@dataclass
class KillEvent(BaseEvent):
    team: str
    count: int
    remaining_alive: int

    def to_dict(self):
        return {
            'team': self.team,
            'count': self.count,
            'remaining_alive': self.remaining_alive
        }

@dataclass
class SpikePlantedEvent(BaseEvent):
    def to_dict(self):
        return {}

# Event registry (for future extension)
EVENT_REGISTRY: Dict[str, Type[BaseEvent]] = {
    'ROUND_END': RoundEndEvent,
    'KILLS': KillEvent,
    'SPIKE_PLANTED': SpikePlantedEvent,
}

def register_event_type(event_type: str, event_class: Type[BaseEvent]):
    """Allows plugins to add new event types"""
    EVENT_REGISTRY[event_type] = event_class
```

**Adding New Event Type (Future):**
```python
# user_extensions.py
@dataclass
class UltimateUsedEvent(BaseEvent):
    team: str
    agent: str

    def to_dict(self):
        return {'team': self.team, 'agent': self.agent}

# Register it
register_event_type('ULTIMATE_USED', UltimateUsedEvent)
```

**Why This Works:**
- **Open/Closed Principle:** Open for extension (add types), closed for modification (no changes to core)
- **Type Safety:** Each event type has its own dataclass with typed fields
- **Backward Compatible:** Old event logs still parse (just ignore unknown types)

---

## Build Order (Suggested Phase Structure)

### Phase 1: State Diffing Foundation
**Build first:**
1. `StateTracker` class
2. `GameState` dataclass
3. `StateChange` dataclass
4. Unit tests for diff logic

**Validation:** Can detect score changes, kills, spike events from mock state sequences

**Why first:** Core logic with zero dependencies. Easy to test in isolation.

---

### Phase 2: Event Emission + Storage
**Build next:**
1. `Event` dataclass + schema
2. `EventEmitter` class
3. `EventStore` class (JSONL writer)
4. Integration tests (state → events → file)

**Validation:** Given state changes, produces valid JSONL event logs

**Why second:** Depends on StateTracker but not on CV pipeline. Can test with mock changes.

---

### Phase 3: Pipeline Integration
**Build next:**
1. `EventPipeline` orchestrator
2. Refactor `GameWatcher` to use pipeline
3. `MatchMetadata` dataclass
4. End-to-end test (mock frame → event log)

**Validation:** Full pipeline works with `VCTVisionEngine` (existing code unchanged)

**Why third:** Integrates all components but doesn't require new CV features yet.

---

### Phase 4: Metadata Extraction
**Build next:**
1. `MetadataExtractor` class
2. ROI definitions for team names, map
3. OCR preprocessing for text (vs digits)
4. Majority-vote validation logic

**Validation:** Can extract team names and map from sample VCT frames

**Why fourth:** Extends CV capabilities but doesn't block core event pipeline. Can use placeholder metadata if OCR fails.

---

### Phase 5: Match Session Management
**Build next:**
1. Multi-map series support (one match_id, multiple map logs)
2. Start/stop UI controls (if needed)
3. Match metadata finalization (final score, duration)

**Validation:** Can track full BO3/BO5 series with correct metadata

**Why fifth:** Builds on working pipeline. Mainly UX/coordination layer.

---

### Phase 6: Advanced Event Types (Future)
**Add later:**
1. Economy events (buy tier shifts)
2. Agent composition tracking
3. Ultimate ability detection
4. Player-level tracking (if CV supports it)

**Why last:** Extends event schema without blocking core pipeline. Can add incrementally.

---

## Scalability Considerations

### At 100 Events (Single Match)
**Approach:** Single JSONL file, load entire file into memory for analysis

**Storage:** ~10KB per match
**Performance:** Instant

---

### At 10K Events (100 Matches)
**Approach:** One file per match, query by filename (match_id)

**Storage:** ~1MB total
**Performance:** Fast (filesystem handles this easily)

**Indexing Strategy:** None needed yet. Filename contains match_id and timestamp.

---

### At 1M Events (10K Matches)
**Approach:** Hierarchical directory structure + optional SQLite index

**Directory Structure:**
```
match_logs/
  2026/
    02/
      match_001_1675893023.jsonl
      match_002_1675897654.jsonl
  2026/
    03/
      match_050_1677485923.jsonl
```

**Optional Index:**
```sql
CREATE TABLE matches (
    match_id TEXT PRIMARY KEY,
    file_path TEXT,
    start_time REAL,
    teams TEXT,
    map TEXT,
    final_score TEXT
);
```

**Query Pattern:**
```python
# Find match by team
cursor.execute("SELECT file_path FROM matches WHERE teams LIKE '%G2%'")
file_path = cursor.fetchone()[0]

# Load events
with open(file_path) as f:
    events = [json.loads(line) for line in f]
```

**Storage:** ~100MB total
**Performance:** Sub-second queries with index

**Recommendation:** Defer indexing until needed (Phase 6+). Filesystem search is fast enough for hundreds of matches.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Continuous State Snapshots (Not Event-Based)

**What goes wrong:**
```python
# BAD: Write full state every frame
while True:
    state = extract_state(frame)
    db.insert(state)  # 6 inserts per second
```

**Why bad:**
- **Storage explosion:** 21,600 records per hour (at 6fps)
- **Redundant data:** Most frames have no changes
- **Analysis complexity:** Have to diff snapshots during analysis

**Prevention:**
Only write when state **changes**. Use `StateTracker` to detect changes first.

---

### Anti-Pattern 2: Over-Engineering Event Schema Too Early

**What goes wrong:**
```python
# BAD: Design for every possible future event type upfront
class Event:
    event_type: str
    player_id: Optional[int]
    agent: Optional[str]
    weapon: Optional[str]
    position: Optional[Tuple[float, float]]
    ultimate_charge: Optional[int]
    # ... 20 more optional fields
```

**Why bad:**
- **Premature complexity:** Don't need player-level data yet
- **Maintenance burden:** Every event type checks 20 fields
- **Migration pain:** Schema changes break existing logs

**Prevention:**
- Start with **team-level events only** (score, alive count, spike)
- Use `data: Dict[str, Any]` for type-specific fields
- Add new event types as separate classes when needed

---

### Anti-Pattern 3: Tight Coupling Between CV and Event Logic

**What goes wrong:**
```python
# BAD: Event detection inside VCTVisionEngine
class VCTVisionEngine:
    def analyze(self, frame):
        state = self.extract_state(frame)

        # Embedded event detection
        if state['score_left'] > self.previous_score_left:
            self.emit_event('ROUND_END', winner='left')

        self.previous_score_left = state['score_left']
        return state
```

**Why bad:**
- **Not reusable:** Can't use `VCTVisionEngine` without event system
- **Hard to test:** Vision extraction and diffing are coupled
- **Violates SRP:** One class doing two jobs

**Prevention:**
Separate **extraction** (`VCTVisionEngine`) from **diffing** (`StateTracker`). Vision engine stays stateless.

---

### Anti-Pattern 4: Synchronous Writes Blocking Frame Processing

**What goes wrong:**
```python
# BAD: Write to disk in main loop
while True:
    frame = capture_frame()
    events = process_frame(frame)

    for event in events:
        db.execute("INSERT INTO events ...")  # Blocks here
```

**Why bad:**
- **Frame drops:** If write takes >166ms (at 6fps), frames get skipped
- **Latency spikes:** Disk I/O is unpredictable

**Prevention:**
- **Buffered writes:** Accumulate events, flush every 10 frames
- **Async I/O:** Use background thread/queue for writes
- **JSONL append:** Faster than SQL inserts

**MVP Approach:** Buffered writes are sufficient. Async can wait.

---

## Testing Strategy

### Unit Tests (Isolated Components)

**StateTracker:**
```python
def test_detect_score_change():
    tracker = StateTracker()

    # First frame
    state1 = GameState(score_left=0, score_right=0, alive_left=5, alive_right=5, spike_planted=False)
    changes = tracker.update(state1.to_dict())
    assert changes == []

    # Score increases
    state2 = GameState(score_left=1, score_right=0, alive_left=5, alive_right=5, spike_planted=False)
    changes = tracker.update(state2.to_dict())
    assert len(changes) == 1
    assert changes[0].type == 'ROUND_END'
    assert changes[0].winner == 'left'
```

**EventEmitter:**
```python
def test_emit_round_end_event():
    emitter = EventEmitter(match_id="test_match")

    change = StateChange(type='ROUND_END', winner='left', new_score=(1, 0))
    events = emitter.emit_events([change], timestamp=1234567890.0)

    assert len(events) == 1
    assert events[0].event_type == 'ROUND_END'
    assert events[0].data['winner'] == 'left'
```

**EventStore:**
```python
def test_event_store_jsonl_format(tmp_path):
    store = EventStore(storage_dir=tmp_path)

    metadata = MatchMetadata(teams=["G2", "NRG"], map="Bind", start_time=1234567890.0)
    store.start_match("test_match", metadata)

    event = Event(match_id="test_match", timestamp=1234567891.0, event_type="ROUND_END", data={"winner": "left"})
    store.append([event])

    # Read file
    log_file = list(tmp_path.glob("*.jsonl"))[0]
    with open(log_file) as f:
        lines = f.readlines()

    assert len(lines) == 2  # Metadata + event
    assert json.loads(lines[0])['type'] == 'MATCH_START'
    assert json.loads(lines[1])['event_type'] == 'ROUND_END'
```

---

### Integration Tests (Multiple Components)

**Full Pipeline:**
```python
def test_full_pipeline_with_mock_frames():
    # Mock frame sequence
    frame1 = create_mock_frame(score_left=0, score_right=0, alive_left=5, alive_right=5)
    frame2 = create_mock_frame(score_left=0, score_right=0, alive_left=3, alive_right=5)  # 2 kills
    frame3 = create_mock_frame(score_left=1, score_right=0, alive_left=5, alive_right=5)  # Round end

    metadata = MatchMetadata(teams=["Team A", "Team B"], map="Test Map", start_time=1234567890.0)
    pipeline = EventPipeline(match_id="test", metadata=metadata)

    # Process frames
    events1 = pipeline.process_frame(frame1, timestamp=1234567890.0)
    events2 = pipeline.process_frame(frame2, timestamp=1234567891.0)
    events3 = pipeline.process_frame(frame3, timestamp=1234567892.0)

    assert len(events1) == 0  # First frame, no changes
    assert len(events2) == 1  # Kill event
    assert events2[0].event_type == 'KILLS'
    assert len(events3) == 1  # Round end
    assert events3[0].event_type == 'ROUND_END'

    pipeline.end_match()

    # Verify event log
    log_files = list(Path("match_logs").glob("test_*.jsonl"))
    assert len(log_files) == 1
```

---

### End-to-End Tests (With Real Frames)

**VOD Analysis:**
```python
def test_analyze_vod_clip():
    """
    Test with a 10-second VCT VOD clip containing known events:
    - Round start (0s)
    - Spike plant (5s)
    - Round end (8s)
    """
    cap = cv2.VideoCapture("test_data/round_clip.mp4")

    metadata = MatchMetadata(teams=["G2", "NRG"], map="Bind", start_time=0)
    pipeline = EventPipeline(match_id="vod_test", metadata=metadata)

    frame_count = 0
    all_events = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_count % 10 == 0:  # 6fps
            timestamp = frame_count / 60.0
            events = pipeline.process_frame(frame, timestamp)
            all_events.extend(events)

        frame_count += 1

    pipeline.end_match()

    # Assert expected events
    event_types = [e.event_type for e in all_events]
    assert 'SPIKE_PLANTED' in event_types
    assert 'ROUND_END' in event_types
```

---

## Data Models

### Core Data Structures

```python
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any
import time

@dataclass
class GameState:
    """Represents game state at a single frame"""
    score_left: int
    score_right: int
    alive_left: int
    alive_right: int
    spike_planted: bool
    eco_left: int = 0
    eco_right: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GameState':
        return cls(
            score_left=data.get('score_left', 0),
            score_right=data.get('score_right', 0),
            alive_left=data.get('alive_left', 0),
            alive_right=data.get('alive_right', 0),
            spike_planted=data.get('spike_planted', False),
            eco_left=data.get('eco_left', 0),
            eco_right=data.get('eco_right', 0)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'score_left': self.score_left,
            'score_right': self.score_right,
            'alive_left': self.alive_left,
            'alive_right': self.alive_right,
            'spike_planted': self.spike_planted,
            'eco_left': self.eco_left,
            'eco_right': self.eco_right
        }

@dataclass
class StateChange:
    """Represents a detected change between frames"""
    type: str  # 'ROUND_END', 'KILLS', 'SPIKE_PLANTED', etc.
    data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {'type': self.type, **self.data}

@dataclass
class MatchMetadata:
    """Match session metadata"""
    teams: Tuple[str, str]
    map: str
    start_time: float
    match_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'teams': list(self.teams),
            'map': self.map,
            'start_time': self.start_time,
            'match_id': self.match_id
        }

@dataclass
class Event:
    """Timestamped event with match context"""
    match_id: str
    timestamp: float
    event_type: str
    data: Dict[str, Any]

    def to_json(self) -> str:
        import json
        return json.dumps({
            'match_id': self.match_id,
            'timestamp': self.timestamp,
            'event_type': self.event_type,
            'data': self.data
        })

    @classmethod
    def from_json(cls, json_str: str) -> 'Event':
        import json
        data = json.loads(json_str)
        return cls(
            match_id=data['match_id'],
            timestamp=data['timestamp'],
            event_type=data['event_type'],
            data=data['data']
        )
```

---

## Configuration Management

### Problem: Where Do ROIs and Thresholds Live?

**Current State:**
- `config.py` has ROIs for timer, spike, avatars
- `VCTVisionEngine` has duplicate ROI definitions
- No versioning or validation

**Recommended Structure:**
```python
# config/vct_layout_v1.py
"""
VCT Broadcast Layout Configuration
Version: 1.0 (2026 Season)
Resolution: 1920x1080
"""

LAYOUT_VERSION = "1.0"
RESOLUTION = (1920, 1080)

# ROIs: (y_start, y_end, x_start, x_end)
ROIS = {
    'score_left': (20, 90, 830, 890),
    'score_right': (20, 90, 1030, 1090),
    'timer': (20, 100, 930, 990),
    'spike': (80, 120, 940, 980),
    'team_name_left': (50, 100, 200, 400),
    'team_name_right': (50, 100, 1520, 1720),
    'map_name': (1000, 1050, 800, 1120),
}

# Sampling points for alive detection
ALIVE_DETECTION = {
    'left_sidebar_x': 260,
    'right_sidebar_x': 1660,
    'start_y': 540,
    'gap_y': 95,
    'saturation_threshold': 40,
    'value_threshold': 50,
}

# Color thresholds (HSV)
SPIKE_RED_LOWER = (0, 100, 100)
SPIKE_RED_UPPER = (10, 255, 255)

# OCR settings
TESSERACT_CMD = None  # Set to path if not in PATH
```

**Usage:**
```python
from config.vct_layout_v1 import ROIS, ALIVE_DETECTION

class VCTVisionEngine:
    def __init__(self, config_module=None):
        if config_module is None:
            from config import vct_layout_v1 as config_module

        self.rois = config_module.ROIS
        self.alive_config = config_module.ALIVE_DETECTION
```

**Why Better?**
- **Single source of truth:** One config file
- **Versioned:** Can add `vct_layout_v2.py` for new broadcast format
- **Testable:** Can inject test config in unit tests

---

## Summary: Build Order with Rationale

| Phase | What to Build | Why This Order |
|-------|---------------|----------------|
| **1. State Diffing** | `StateTracker`, `GameState`, tests | Zero dependencies, easy to test, core logic |
| **2. Event Emission** | `Event`, `EventEmitter`, `EventStore`, tests | Depends on StateTracker but not CV, can use mocks |
| **3. Pipeline Integration** | `EventPipeline`, refactor `GameWatcher` | Integrates all components, works with existing VCTVisionEngine |
| **4. Metadata Extraction** | `MetadataExtractor`, team/map OCR | Extends CV capabilities, not blocking for pipeline |
| **5. Match Session Mgmt** | Multi-map series, start/stop controls | Builds on working pipeline, mainly coordination |
| **6. Advanced Events** | Economy, agents, ultimates | Extends event schema, can add incrementally |

**Critical Path:** Phases 1-3 must be sequential. Phases 4-6 can be reordered or parallelized.

**MVP Definition:** Phases 1-3 complete = working event logger with persistent storage.

---

## Sources

This architecture is based on established patterns from:

- **Event Sourcing Pattern** (Martin Fowler) - Append-only event logs, state reconstruction
- **State Machine Pattern** - State transitions trigger events
- **Computer Vision Pipelines** - Frame extraction → processing → output separation
- **Sports Analytics Systems** - Event detection from video feeds (e.g., StatsBomb soccer analytics)
- **Python Design Patterns** - Factory pattern for event types, dataclasses for immutability

**Confidence:** HIGH - These are well-established architectural patterns with proven track records in similar domains (sports analytics, video processing, event-driven systems).

**Gaps:**
- Optimal OCR settings for team/map extraction need empirical tuning (Phase 4)
- Smoothing strategy for OCR errors (may need experimentation)
- Multi-map series coordination details (Phase 5)

These gaps are expected to be resolved during implementation of their respective phases.
