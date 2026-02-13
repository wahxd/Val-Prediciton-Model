"""Tests for StateTracker 3-frame consensus debouncing.

Validates that the tracker requires 3 consecutive frames to agree before
confirming any field value, preventing OCR flicker from generating event storms.
"""

from src.state.models import GameState
from src.state.tracker import StateTracker, TRACKED_FIELDS

# Auto-incrementing counters for unique frame_number and timestamp
_frame_counter = 0


def make_state(**overrides) -> GameState:
    """Create a GameState with sensible defaults, overriding any field.

    Defaults: score 5-3, alive 5-5, timer "1:30", spike False,
    auto-incrementing frame_number and timestamp, all OCR confidence 0.9.
    """
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
            "timer": 0.9,
            "score_left": 0.9,
            "score_right": 0.9,
            "alive_left": 0.9,
            "alive_right": 0.9,
        },
    }
    defaults.update(overrides)
    return GameState(**defaults)


def setup_function():
    """Reset frame counter before each test."""
    global _frame_counter
    _frame_counter = 0


class TestGetStableFields:
    """Test get_stable_fields() consensus requirements."""

    def test_empty_tracker_returns_no_stable_fields(self):
        tracker = StateTracker()
        assert tracker.get_stable_fields() == {}

    def test_one_frame_returns_no_stable_fields(self):
        tracker = StateTracker()
        tracker.update(make_state())
        assert tracker.get_stable_fields() == {}

    def test_two_frames_returns_no_stable_fields(self):
        tracker = StateTracker()
        tracker.update(make_state())
        tracker.update(make_state())
        assert tracker.get_stable_fields() == {}

    def test_three_identical_frames_returns_all_stable(self):
        tracker = StateTracker()
        tracker.update(make_state())
        tracker.update(make_state())
        tracker.update(make_state())

        stable = tracker.get_stable_fields()
        assert len(stable) == len(TRACKED_FIELDS)
        assert stable["score_left"] == 5
        assert stable["score_right"] == 3
        assert stable["alive_left"] == 5
        assert stable["alive_right"] == 5
        assert stable["timer"] == "1:30"
        assert stable["spike_planted"] is False

    def test_three_frames_with_one_different_field_excludes_it(self):
        tracker = StateTracker()
        tracker.update(make_state(alive_left=5))
        tracker.update(make_state(alive_left=4))
        tracker.update(make_state(alive_left=4))

        stable = tracker.get_stable_fields()
        # alive_left has no consensus (5, 4, 4)
        assert "alive_left" not in stable
        # Other fields should still have consensus
        assert "score_left" in stable
        assert "score_right" in stable
        assert "timer" in stable


class TestDetectChanges:
    """Test detect_changes() state diff detection."""

    def test_detect_changes_returns_diffs(self):
        tracker = StateTracker()
        # Establish baseline: 3 frames to get confirmed_state
        for _ in range(3):
            tracker.update(make_state())
        tracker.detect_changes()  # Sets confirmed_state (first consensus)

        # Now change score_right to 4 for 3 frames
        for _ in range(3):
            tracker.update(make_state(score_right=4))

        changes = tracker.detect_changes()
        assert "score_right" in changes
        assert changes["score_right"] == (3, 4)

    def test_detect_changes_empty_when_no_change(self):
        tracker = StateTracker()
        # Establish baseline
        for _ in range(3):
            tracker.update(make_state())
        tracker.detect_changes()  # Sets confirmed_state

        # Same values for 3 more frames
        for _ in range(3):
            tracker.update(make_state())

        changes = tracker.detect_changes()
        assert changes == {}

    def test_detect_changes_first_consensus_sets_baseline_no_changes(self):
        tracker = StateTracker()
        for _ in range(3):
            tracker.update(make_state())

        # First detect_changes() should set confirmed_state but return empty
        changes = tracker.detect_changes()
        assert changes == {}
        assert tracker.confirmed_state is not None


class TestRingBuffer:
    """Test deque(maxlen=3) eviction behavior."""

    def test_ring_buffer_evicts_oldest(self):
        tracker = StateTracker()
        # Frame 1 has alive_left=5
        tracker.update(make_state(alive_left=5))
        # Frames 2-4 have alive_left=4
        tracker.update(make_state(alive_left=4))
        tracker.update(make_state(alive_left=4))
        tracker.update(make_state(alive_left=4))

        # After 4 frames, oldest (alive_left=5) is evicted
        # Buffer has 3 frames all with alive_left=4
        stable = tracker.get_stable_fields()
        assert stable["alive_left"] == 4


class TestReset:
    """Test reset() clears all state."""

    def test_reset_clears_everything(self):
        tracker = StateTracker()
        for _ in range(3):
            tracker.update(make_state())
        assert tracker.get_stable_fields() != {}

        tracker.reset()
        assert tracker.get_stable_fields() == {}
        assert tracker.confirmed_state is None
        assert len(tracker.history) == 0
