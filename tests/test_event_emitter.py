"""Tests for EventEmitter state-to-event mapping.

Validates that the emitter correctly transforms state diffs into typed events,
including kill events, round end with win condition inference, spike transitions,
transition-based round start detection, and timeout events with team attribution.
"""

from src.events.emitter import EventEmitter
from src.events.schemas import (
    KillEvent,
    RoundEndEvent,
    RoundStartEvent,
    SpikeDefuseEvent,
    SpikeDetonateEvent,
    SpikePlantEvent,
    TimeoutEvent,
)
from src.state.models import GameState


_frame_counter = 0


def make_state(**overrides) -> GameState:
    """Create a GameState with sensible defaults for emitter tests."""
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


class TestKillEvents:
    """Test kill event emission on alive count decreases."""

    def test_kill_event_on_alive_decrease(self):
        emitter = EventEmitter()
        prev = make_state(alive_left=4)
        curr = make_state(alive_left=3)
        changes = {"alive_left": (4, 3)}

        events = emitter.emit_events(changes, curr, prev)
        kill_events = [e for e in events if isinstance(e, KillEvent)]
        assert len(kill_events) == 1
        assert kill_events[0].team == "left"
        assert kill_events[0].alive_before == 4
        assert kill_events[0].alive_after == 3

    def test_kill_event_right_team(self):
        emitter = EventEmitter()
        prev = make_state(alive_right=5)
        curr = make_state(alive_right=4)
        changes = {"alive_right": (5, 4)}

        events = emitter.emit_events(changes, curr, prev)
        kill_events = [e for e in events if isinstance(e, KillEvent)]
        assert len(kill_events) == 1
        assert kill_events[0].team == "right"

    def test_double_kill_same_frame(self):
        """alive_left 4 -> 2 emits 1 KillEvent (team-level granularity)."""
        emitter = EventEmitter()
        prev = make_state(alive_left=4)
        curr = make_state(alive_left=2)
        changes = {"alive_left": (4, 2)}

        events = emitter.emit_events(changes, curr, prev)
        kill_events = [e for e in events if isinstance(e, KillEvent)]
        assert len(kill_events) == 1
        assert kill_events[0].alive_before == 4
        assert kill_events[0].alive_after == 2


class TestRoundEndEvents:
    """Test round end detection on score increase."""

    def test_round_end_on_score_increase_left(self):
        emitter = EventEmitter()
        prev = make_state(score_left=5, alive_right=0)
        curr = make_state(score_left=6, alive_right=0)
        changes = {"score_left": (5, 6)}

        events = emitter.emit_events(changes, curr, prev)
        round_end_events = [e for e in events if isinstance(e, RoundEndEvent)]
        assert len(round_end_events) == 1
        assert round_end_events[0].winner == "left"
        assert round_end_events[0].win_condition == "elimination"

    def test_round_end_on_score_increase_right(self):
        emitter = EventEmitter()
        prev = make_state(score_right=3)
        curr = make_state(score_right=4)
        changes = {"score_right": (3, 4)}

        events = emitter.emit_events(changes, curr, prev)
        round_end_events = [e for e in events if isinstance(e, RoundEndEvent)]
        assert len(round_end_events) == 1
        assert round_end_events[0].winner == "right"


class TestSpikeEvents:
    """Test spike plant, defuse, and detonate events."""

    def test_spike_plant_event(self):
        emitter = EventEmitter()
        prev = make_state(spike_planted=False, timer="1:05")
        curr = make_state(spike_planted=True, timer="1:05")
        changes = {"spike_planted": (False, True)}

        events = emitter.emit_events(changes, curr, prev)
        spike_events = [e for e in events if isinstance(e, SpikePlantEvent)]
        assert len(spike_events) == 1
        assert spike_events[0].plant_time_seconds == 65  # 1:05 = 65s

    def test_spike_defuse_event(self):
        """spike True -> False with timer > 5s (above detonate threshold) -> defuse."""
        emitter = EventEmitter()
        prev = make_state(spike_planted=True, timer="0:25")
        curr = make_state(spike_planted=False, timer="0:25")
        changes = {"spike_planted": (True, False)}

        events = emitter.emit_events(changes, curr, prev)
        defuse_events = [e for e in events if isinstance(e, SpikeDefuseEvent)]
        assert len(defuse_events) == 1
        assert defuse_events[0].defuse_time_seconds == 25

    def test_spike_detonate_event(self):
        """spike True -> False with timer < 5s -> detonate."""
        emitter = EventEmitter()
        prev = make_state(spike_planted=True, timer="0:03")
        curr = make_state(spike_planted=False, timer="0:03")
        changes = {"spike_planted": (True, False)}

        events = emitter.emit_events(changes, curr, prev)
        detonate_events = [e for e in events if isinstance(e, SpikeDetonateEvent)]
        assert len(detonate_events) == 1


class TestRoundStartTransition:
    """Test transition-based round start detection.

    Round start requires timer TRANSITION from low (<30s) to high (>=80s)
    plus 5v5 alive counts. A high timer alone must NOT trigger it.
    """

    def test_round_start_requires_timer_transition_not_just_threshold(self):
        """Both frames have high timer + 5v5 -> NO RoundStartEvent."""
        emitter = EventEmitter()
        prev = make_state(timer="1:25")  # 85s
        curr = make_state(timer="1:23")  # 83s
        changes = {}

        events = emitter.emit_events(changes, curr, prev)
        round_start_events = [e for e in events if isinstance(e, RoundStartEvent)]
        assert len(round_start_events) == 0

    def test_round_start_on_timer_transition_low_to_high(self):
        """Timer transitions from <30s to >=80s with 5v5 -> RoundStartEvent."""
        emitter = EventEmitter()
        prev = make_state(timer="0:05")  # 5s (low)
        curr = make_state(timer="1:40")  # 100s (high)
        changes = {}

        events = emitter.emit_events(changes, curr, prev)
        round_start_events = [e for e in events if isinstance(e, RoundStartEvent)]
        assert len(round_start_events) == 1
        assert round_start_events[0].round_number == 9  # 5+3+1

    def test_round_start_transition_without_5v5_does_not_trigger(self):
        """Timer transitions low->high but not 5v5 -> NO RoundStartEvent."""
        emitter = EventEmitter()
        prev = make_state(timer="0:05", alive_left=3, alive_right=4)
        curr = make_state(timer="1:40", alive_left=3, alive_right=4)
        changes = {}

        events = emitter.emit_events(changes, curr, prev)
        round_start_events = [e for e in events if isinstance(e, RoundStartEvent)]
        assert len(round_start_events) == 0


class TestTimeoutEvents:
    """Test tactical timeout detection via frozen timer."""

    def test_timeout_event_emitted_on_timer_freeze(self):
        """Timer frozen 5+ frames mid-round -> TimeoutEvent."""
        emitter = EventEmitter()
        # Feed 5 frames with identical frozen timer, both teams alive
        for i in range(5):
            prev = make_state(timer="0:45", alive_left=3, alive_right=4)
            curr = make_state(timer="0:45", alive_left=3, alive_right=4)
            events = emitter.emit_events({}, curr, prev)

        timeout_events = [e for e in events if isinstance(e, TimeoutEvent)]
        assert len(timeout_events) == 1

    def test_timeout_event_team_attribution_fewer_alive(self):
        """Team with fewer alive players is attributed the timeout."""
        emitter = EventEmitter()
        # Left has 2 alive, right has 4 -> left attributed
        for i in range(5):
            prev = make_state(timer="0:45", alive_left=2, alive_right=4)
            curr = make_state(timer="0:45", alive_left=2, alive_right=4)
            events = emitter.emit_events({}, curr, prev)

        timeout_events = [e for e in events if isinstance(e, TimeoutEvent)]
        assert len(timeout_events) == 1
        assert timeout_events[0].team == "left"

    def test_timeout_event_not_emitted_between_rounds(self):
        """Timer frozen but alive=0 on one side -> no timeout."""
        emitter = EventEmitter()
        for i in range(6):
            prev = make_state(timer="0:00", alive_left=0, alive_right=3)
            curr = make_state(timer="0:00", alive_left=0, alive_right=3)
            events = emitter.emit_events({}, curr, prev)

        timeout_events = [e for e in events if isinstance(e, TimeoutEvent)]
        assert len(timeout_events) == 0


class TestEventStateSnapshot:
    """Test that events include full game state snapshot."""

    def test_events_include_full_state_snapshot(self):
        """Every event has score, alive, timer, spike fields populated."""
        emitter = EventEmitter()
        prev = make_state(alive_left=4, score_left=5, score_right=3)
        curr = make_state(alive_left=3, score_left=5, score_right=3)
        changes = {"alive_left": (4, 3)}

        events = emitter.emit_events(changes, curr, prev)
        assert len(events) >= 1
        event = events[0]
        assert event.score_left == 5
        assert event.score_right == 3
        assert event.alive_left == 3
        assert event.alive_right == 5
        assert event.game_time == "1:30"
        assert event.spike_planted is False
        assert event.frame_number > 0
        assert event.timestamp > 0


class TestNoChanges:
    """Test behavior with empty changes."""

    def test_no_events_on_no_changes(self):
        emitter = EventEmitter()
        prev = make_state()
        curr = make_state()
        events = emitter.emit_events({}, curr, prev)
        assert events == []


class TestMultipleEvents:
    """Test multiple events emitted in the same frame."""

    def test_multiple_events_same_frame(self):
        """Alive decrease AND score increase -> both KillEvent and RoundEndEvent."""
        emitter = EventEmitter()
        prev = make_state(alive_left=1, alive_right=1, score_right=3)
        curr = make_state(alive_left=1, alive_right=0, score_right=4)
        changes = {
            "alive_right": (1, 0),
            "score_right": (3, 4),
        }

        events = emitter.emit_events(changes, curr, prev)
        event_types = {type(e) for e in events}
        assert KillEvent in event_types
        assert RoundEndEvent in event_types


class TestReset:
    """Test reset clears internal state."""

    def test_reset_clears_round_events(self):
        emitter = EventEmitter()
        # Emit some events
        prev = make_state(alive_left=4)
        curr = make_state(alive_left=3)
        emitter.emit_events({"alive_left": (4, 3)}, curr, prev)
        assert len(emitter.current_round_events) > 0

        emitter.reset()
        assert len(emitter.current_round_events) == 0
        assert len(emitter.recent_events) == 0
        assert emitter.last_timer_seconds is None
        assert emitter.timeout_detected is False
