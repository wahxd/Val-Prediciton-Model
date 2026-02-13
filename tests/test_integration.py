"""Integration tests for the full event detection pipeline.

Tests the complete flow: raw frames -> StateTracker (debounce) -> detect_changes ->
EventEmitter -> typed events. Validates round simulation, replay suppression,
and flicker prevention through the actual component chain.
"""

from src.events.emitter import EventEmitter
from src.events.schemas import (
    KillEvent,
    RoundEndEvent,
    RoundStartEvent,
    SpikePlantEvent,
)
from src.quality.replay_detector import ReplayDetector, timer_str_to_seconds
from src.state.models import GameState
from src.state.tracker import StateTracker


_frame_counter = 0


def make_state(**overrides) -> GameState:
    """Create a GameState with sensible defaults for integration tests."""
    global _frame_counter
    _frame_counter += 1
    defaults = {
        "score_left": 5,
        "score_right": 3,
        "alive_left": 5,
        "alive_right": 5,
        "timer": "1:30",
        "spike_planted": False,
        "frame_number": _frame_counter,
        "timestamp": 1000.0 + _frame_counter * 0.167,
        "ocr_confidence": {
            "timer": 0.9, "score_left": 0.9, "score_right": 0.9,
            "alive_left": 0.9, "alive_right": 0.9,
        },
    }
    defaults.update(overrides)
    return GameState(**defaults)


def setup_function():
    """Reset frame counter before each test."""
    global _frame_counter
    _frame_counter = 0


class TestFullPipelineRoundSimulation:
    """Test complete round simulation through the real pipeline."""

    def test_full_pipeline_round_simulation(self):
        """Feed frames through StateTracker -> detect_changes -> EventEmitter
        and verify correct event sequence for a full round."""
        tracker = StateTracker()
        emitter = EventEmitter()
        all_events = []

        # --- Phase 1: Round start (timer transition low -> high, 5v5) ---
        # We need a confirmed_state first with a low timer
        # Feed 3 frames with low timer to establish baseline
        for _ in range(3):
            tracker.update(make_state(timer="0:05"))
        changes = tracker.detect_changes()
        # First consensus sets baseline, no changes yet

        # Now feed 3 frames with high timer (round start transition)
        for _ in range(3):
            tracker.update(make_state(timer="1:40"))
        changes = tracker.detect_changes()

        if changes and tracker.confirmed_state:
            # Build previous state from the old confirmed (low timer)
            prev_state = GameState(
                score_left=5, score_right=3, alive_left=5, alive_right=5,
                timer="0:05", spike_planted=False, frame_number=0,
                timestamp=999.0,
                ocr_confidence={"timer": 0.9, "score_left": 0.9,
                                "score_right": 0.9, "alive_left": 0.9,
                                "alive_right": 0.9},
            )
            events = emitter.emit_events(changes, tracker.confirmed_state, prev_state)
            all_events.extend(events)

        round_starts = [e for e in all_events if isinstance(e, RoundStartEvent)]
        assert len(round_starts) == 1, f"Expected 1 RoundStartEvent, got {len(round_starts)}"

        # --- Phase 2: First kill (alive_left drops to 4) ---
        for _ in range(3):
            tracker.update(make_state(timer="1:20", alive_left=4))
        changes = tracker.detect_changes()

        if changes and tracker.confirmed_state:
            prev_state = GameState(
                score_left=5, score_right=3, alive_left=5, alive_right=5,
                timer="1:40", spike_planted=False, frame_number=0,
                timestamp=999.0,
                ocr_confidence={"timer": 0.9, "score_left": 0.9,
                                "score_right": 0.9, "alive_left": 0.9,
                                "alive_right": 0.9},
            )
            events = emitter.emit_events(changes, tracker.confirmed_state, prev_state)
            all_events.extend(events)

        kill_events = [e for e in all_events if isinstance(e, KillEvent)]
        assert len(kill_events) >= 1

        # --- Phase 3: Spike plant ---
        for _ in range(3):
            tracker.update(make_state(timer="0:55", alive_left=4, spike_planted=True))
        changes = tracker.detect_changes()

        if changes and tracker.confirmed_state:
            prev_state = GameState(
                score_left=5, score_right=3, alive_left=4, alive_right=5,
                timer="1:20", spike_planted=False, frame_number=0,
                timestamp=999.0,
                ocr_confidence={"timer": 0.9, "score_left": 0.9,
                                "score_right": 0.9, "alive_left": 0.9,
                                "alive_right": 0.9},
            )
            events = emitter.emit_events(changes, tracker.confirmed_state, prev_state)
            all_events.extend(events)

        spike_events = [e for e in all_events if isinstance(e, SpikePlantEvent)]
        assert len(spike_events) == 1

        # --- Phase 4: Round end (score_right increases) ---
        for _ in range(3):
            tracker.update(make_state(
                timer="0:30", alive_left=0, alive_right=2,
                spike_planted=False, score_right=4,
            ))
        changes = tracker.detect_changes()

        if changes and tracker.confirmed_state:
            prev_state = GameState(
                score_left=5, score_right=3, alive_left=4, alive_right=5,
                timer="0:55", spike_planted=True, frame_number=0,
                timestamp=999.0,
                ocr_confidence={"timer": 0.9, "score_left": 0.9,
                                "score_right": 0.9, "alive_left": 0.9,
                                "alive_right": 0.9},
            )
            events = emitter.emit_events(changes, tracker.confirmed_state, prev_state)
            all_events.extend(events)

        round_ends = [e for e in all_events if isinstance(e, RoundEndEvent)]
        assert len(round_ends) == 1
        assert round_ends[0].winner == "right"

        # Verify event order
        event_types = [type(e).__name__ for e in all_events]
        # RoundStartEvent should come before KillEvent
        if "RoundStartEvent" in event_types and "KillEvent" in event_types:
            assert event_types.index("RoundStartEvent") < event_types.index("KillEvent")
        # KillEvent should come before SpikePlantEvent
        if "KillEvent" in event_types and "SpikePlantEvent" in event_types:
            assert event_types.index("KillEvent") < event_types.index("SpikePlantEvent")

        # Verify every event has full state snapshot
        for event in all_events:
            assert hasattr(event, "score_left")
            assert hasattr(event, "score_right")
            assert hasattr(event, "alive_left")
            assert hasattr(event, "alive_right")
            assert hasattr(event, "game_time")


class TestPipelineReplaySuppression:
    """Test that replay detection suppresses events in the pipeline."""

    def test_pipeline_replay_suppression(self):
        """When ReplayDetector detects replay, EventEmitter should not be called."""
        tracker = StateTracker()
        emitter = EventEmitter()
        detector = ReplayDetector()
        all_events = []

        # Establish baseline: 3 frames with timer counting down
        for _ in range(3):
            tracker.update(make_state(timer="0:30"))
        tracker.detect_changes()  # Sets confirmed_state

        # Now simulate replay: timer jumps from 30 -> 85, same score
        for _ in range(3):
            tracker.update(make_state(timer="1:25"))
        changes = tracker.detect_changes()

        # Check replay detection
        current_timer = timer_str_to_seconds("1:25")
        previous_timer = timer_str_to_seconds("0:30")
        is_replay = detector.check_frame(
            current_timer, (5, 3), previous_timer, (5, 3), 10
        )
        assert is_replay is True

        # Because replay is detected, we should NOT feed events to emitter
        if not is_replay and changes and tracker.confirmed_state:
            events = emitter.emit_events(changes, tracker.confirmed_state,
                                         make_state(timer="0:30"))
            all_events.extend(events)

        # No events should be emitted due to replay suppression
        assert len(all_events) == 0

        # After replay exits (timer passes regression point), events resume
        detector.check_frame(25, (5, 3), current_timer, (5, 3), 11)
        assert detector.is_suppressed is False


class TestPipelineDebounce:
    """Test that 3-frame consensus prevents flicker events."""

    def test_pipeline_debounce_prevents_flicker(self):
        """Flickering alive_left values prevent false kill events."""
        tracker = StateTracker()
        emitter = EventEmitter()

        # Establish baseline: 3 frames with alive_left=5
        for _ in range(3):
            tracker.update(make_state(alive_left=5))
        tracker.detect_changes()  # Sets confirmed_state

        # Flicker: 2 frames with alive_left=4, then 1 frame back to 5
        tracker.update(make_state(alive_left=4))
        tracker.update(make_state(alive_left=4))
        tracker.update(make_state(alive_left=5))  # Flicker back

        changes = tracker.detect_changes()
        # No consensus on alive_left (4, 4, 5) - should NOT include alive_left
        assert "alive_left" not in changes

        # Now 2 more frames with alive_left=4 (buffer: 4, 5, 4) -- still no consensus
        tracker.update(make_state(alive_left=4))
        changes = tracker.detect_changes()
        assert "alive_left" not in changes

        # Only after 3 consistent frames of alive_left=4 should it trigger
        tracker.update(make_state(alive_left=4))
        tracker.update(make_state(alive_left=4))
        changes = tracker.detect_changes()
        # Now buffer is (4, 4, 4) -> consensus
        assert "alive_left" in changes
        assert changes["alive_left"] == (5, 4)
