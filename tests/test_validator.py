"""Tests for StateValidator data quality enforcement.

Validates that the validator rejects low OCR confidence, out-of-range values,
malformed timers, and incoherent state transitions (alive increase mid-round,
score decrease within a half).
"""

from src.state.models import GameState
from src.state.validator import StateValidator


def _make_raw_state(**overrides) -> dict:
    """Create a raw state dict with sensible defaults for validation."""
    defaults = {
        "score_left": 5,
        "score_right": 3,
        "alive_left": 5,
        "alive_right": 5,
        "timer": "1:30",
        "spike_planted": False,
        "frame_number": 100,
        "timestamp": 1000.0,
    }
    defaults.update(overrides)
    return defaults


def _make_confidence(**overrides) -> dict[str, float]:
    """Create OCR confidence dict with all fields at 0.9 by default."""
    defaults = {
        "timer": 0.9,
        "score_left": 0.9,
        "score_right": 0.9,
        "alive_left": 0.9,
        "alive_right": 0.9,
    }
    defaults.update(overrides)
    return defaults


class TestValidateFrame:
    """Test validate_frame() accepts valid data and rejects invalid data."""

    def test_valid_frame_passes(self):
        validator = StateValidator()
        result = validator.validate_frame(
            _make_raw_state(), _make_confidence()
        )
        assert result is not None
        assert isinstance(result, GameState)
        assert result.score_left == 5
        assert result.timer == "1:30"

    def test_low_confidence_timer_rejects_frame(self):
        validator = StateValidator()
        result = validator.validate_frame(
            _make_raw_state(), _make_confidence(timer=0.5)
        )
        assert result is None

    def test_low_confidence_score_rejects_frame(self):
        validator = StateValidator()
        result = validator.validate_frame(
            _make_raw_state(), _make_confidence(score_left=0.6)
        )
        assert result is None

    def test_alive_count_above_5_rejects(self):
        validator = StateValidator()
        result = validator.validate_frame(
            _make_raw_state(alive_left=6), _make_confidence()
        )
        assert result is None

    def test_alive_count_negative_rejects(self):
        validator = StateValidator()
        result = validator.validate_frame(
            _make_raw_state(alive_left=-1), _make_confidence()
        )
        assert result is None

    def test_score_above_13_rejects(self):
        validator = StateValidator()
        result = validator.validate_frame(
            _make_raw_state(score_left=14), _make_confidence()
        )
        assert result is None

    def test_malformed_timer_rejects(self):
        validator = StateValidator()
        result = validator.validate_frame(
            _make_raw_state(timer="abc"), _make_confidence()
        )
        assert result is None


class TestCheckCoherence:
    """Test check_coherence() state transition rules."""

    def test_coherence_alive_increase_mid_round_warns(self):
        validator = StateValidator()
        # Set up: first state with alive_left=3, mark round as active
        first_state = GameState(
            score_left=5, score_right=3, alive_left=3, alive_right=4,
            timer="0:45", spike_planted=False, frame_number=100,
            timestamp=1000.0,
            ocr_confidence={"timer": 0.9, "score_left": 0.9, "score_right": 0.9,
                            "alive_left": 0.9, "alive_right": 0.9},
        )
        validator.check_coherence(first_state)
        validator.in_round = True  # Ensure we're in a round

        # Now alive_left increases from 3 to 4 mid-round (impossible)
        second_state = GameState(
            score_left=5, score_right=3, alive_left=4, alive_right=4,
            timer="0:40", spike_planted=False, frame_number=101,
            timestamp=1000.167,
            ocr_confidence={"timer": 0.9, "score_left": 0.9, "score_right": 0.9,
                            "alive_left": 0.9, "alive_right": 0.9},
        )
        is_coherent, warnings = validator.check_coherence(second_state)
        assert is_coherent is False
        assert len(warnings) >= 1
        assert "QUAL-02" in warnings[0]

    def test_coherence_score_decrease_warns(self):
        validator = StateValidator()
        first_state = GameState(
            score_left=5, score_right=3, alive_left=5, alive_right=5,
            timer="1:30", spike_planted=False, frame_number=100,
            timestamp=1000.0,
            ocr_confidence={"timer": 0.9, "score_left": 0.9, "score_right": 0.9,
                            "alive_left": 0.9, "alive_right": 0.9},
        )
        validator.check_coherence(first_state)

        # Score decreases (impossible in a match)
        second_state = GameState(
            score_left=4, score_right=3, alive_left=5, alive_right=5,
            timer="1:25", spike_planted=False, frame_number=101,
            timestamp=1000.167,
            ocr_confidence={"timer": 0.9, "score_left": 0.9, "score_right": 0.9,
                            "alive_left": 0.9, "alive_right": 0.9},
        )
        is_coherent, warnings = validator.check_coherence(second_state)
        assert is_coherent is False
        assert any("QUAL-03" in w for w in warnings)

    def test_coherence_round_start_allows_alive_reset(self):
        """After round end, alive going from 2 to 5 is OK (new round)."""
        validator = StateValidator()
        # End of a round: low alive, low timer
        end_state = GameState(
            score_left=5, score_right=3, alive_left=2, alive_right=0,
            timer="0:10", spike_planted=False, frame_number=100,
            timestamp=1000.0,
            ocr_confidence={"timer": 0.9, "score_left": 0.9, "score_right": 0.9,
                            "alive_left": 0.9, "alive_right": 0.9},
        )
        validator.check_coherence(end_state)
        validator.in_round = True

        # New round: score changed (6-3), both alive reset to 5, high timer
        # The check_coherence detects round start via 5v5 + timer > 90
        new_round_state = GameState(
            score_left=6, score_right=3, alive_left=5, alive_right=5,
            timer="1:40", spike_planted=False, frame_number=200,
            timestamp=1010.0,
            ocr_confidence={"timer": 0.9, "score_left": 0.9, "score_right": 0.9,
                            "alive_left": 0.9, "alive_right": 0.9},
        )
        is_coherent, warnings = validator.check_coherence(new_round_state)
        assert is_coherent is True
        assert warnings == []


class TestConsecutiveFailures:
    """Test consecutive failure tracking and warning thresholds."""

    def test_consecutive_failures_tracking(self):
        validator = StateValidator()
        # Submit 11 invalid frames (malformed timer)
        for i in range(11):
            validator.validate_frame(
                _make_raw_state(timer="abc", frame_number=i),
                _make_confidence(),
            )
        assert validator.consecutive_failures == 11
        assert validator.should_warn() is True

    def test_consecutive_failures_reset_on_valid(self):
        validator = StateValidator()
        # Submit 5 invalid frames
        for i in range(5):
            validator.validate_frame(
                _make_raw_state(timer="abc", frame_number=i),
                _make_confidence(),
            )
        assert validator.consecutive_failures == 5

        # Submit 1 valid frame
        result = validator.validate_frame(
            _make_raw_state(frame_number=10), _make_confidence()
        )
        assert result is not None
        assert validator.consecutive_failures == 0

    def test_should_warn_false_below_threshold(self):
        validator = StateValidator()
        for i in range(9):
            validator.validate_frame(
                _make_raw_state(timer="abc", frame_number=i),
                _make_confidence(),
            )
        assert validator.should_warn() is False

    def test_should_warn_true_at_threshold(self):
        validator = StateValidator()
        for i in range(10):
            validator.validate_frame(
                _make_raw_state(timer="abc", frame_number=i),
                _make_confidence(),
            )
        assert validator.should_warn() is True
