"""Tests for ReplayDetector broadcast replay suppression.

Validates that replays are detected via timer regression + unchanged score,
suppression continues until timer passes regression point or score changes,
and normal play (including new rounds) is never suppressed.
"""

from src.quality.replay_detector import ReplayDetector


class TestNormalPlayNotSuppressed:
    """Verify normal gameplay is never flagged as replay."""

    def test_normal_play_not_suppressed(self):
        """Timer counting down with unchanged score returns False."""
        detector = ReplayDetector()
        # Timer: 90 -> 89 -> 88 (normal countdown), score unchanged
        assert detector.check_frame(90, (5, 3), None, (5, 3), 1) is False
        assert detector.check_frame(89, (5, 3), 90, (5, 3), 2) is False
        assert detector.check_frame(88, (5, 3), 89, (5, 3), 3) is False


class TestReplayDetection:
    """Test replay entry conditions."""

    def test_timer_regression_with_same_score_triggers_replay(self):
        """Timer jumps backward with same score -> replay detected."""
        detector = ReplayDetector()
        # Normal frame first
        detector.check_frame(30, (5, 3), 31, (5, 3), 1)
        # Timer regresses: 30 -> 85, score unchanged
        result = detector.check_frame(85, (5, 3), 30, (5, 3), 2)
        assert result is True

    def test_timer_regression_with_score_change_not_replay(self):
        """Timer jumps with score change -> new round, not replay."""
        detector = ReplayDetector()
        # Timer goes 5 -> 100 but score changed (5,3) -> (6,3)
        result = detector.check_frame(100, (6, 3), 5, (5, 3), 1)
        assert result is False


class TestReplaySuppression:
    """Test suppression behavior once replay is detected."""

    def test_replay_suppression_continues_until_exit(self):
        """During replay, frames at or above regression point stay suppressed."""
        detector = ReplayDetector()
        # Enter replay: timer 30 -> 85, same score
        detector.check_frame(85, (5, 3), 30, (5, 3), 1)
        assert detector.is_suppressed is True

        # Subsequent frames still above regression point (30)
        assert detector.check_frame(80, (5, 3), 85, (5, 3), 2) is True
        assert detector.check_frame(70, (5, 3), 80, (5, 3), 3) is True
        assert detector.check_frame(40, (5, 3), 70, (5, 3), 4) is True

    def test_replay_exits_when_timer_passes_regression_point(self):
        """Suppression exits when timer drops below regression point."""
        detector = ReplayDetector()
        # Enter replay at regression_timer_sec=30 (previous timer was 30)
        detector.check_frame(85, (5, 3), 30, (5, 3), 1)
        assert detector.is_suppressed is True

        # Timer counting down during replay: 85, 80, 70 (all >= 30)
        detector.check_frame(80, (5, 3), 85, (5, 3), 2)
        detector.check_frame(70, (5, 3), 80, (5, 3), 3)
        assert detector.is_suppressed is True

        # Timer passes regression point: 25 < 30
        result = detector.check_frame(25, (5, 3), 70, (5, 3), 4)
        assert result is False
        assert detector.is_suppressed is False

    def test_replay_exits_on_score_change(self):
        """Score change during suppression exits replay mode."""
        detector = ReplayDetector()
        # Enter replay
        detector.check_frame(85, (5, 3), 30, (5, 3), 1)
        assert detector.is_suppressed is True

        # Score changes during replay (6, 3) != live score (5, 3)
        result = detector.check_frame(80, (6, 3), 85, (5, 3), 2)
        assert result is False
        assert detector.is_suppressed is False


class TestInvalidTimer:
    """Test behavior when OCR produces None timer values."""

    def test_invalid_timer_maintains_current_state(self):
        """None timer during normal play -> False. None during replay -> True."""
        detector = ReplayDetector()
        # Normal play: None timer -> stays not suppressed
        result = detector.check_frame(None, (5, 3), 30, (5, 3), 1)
        assert result is False

        # Enter replay
        detector.check_frame(85, (5, 3), 30, (5, 3), 2)
        assert detector.is_suppressed is True

        # None timer during replay -> stays suppressed
        result = detector.check_frame(None, (5, 3), 85, (5, 3), 3)
        assert result is True


class TestMultipleReplays:
    """Test tracking of multiple replay events."""

    def test_multiple_replays_tracked_independently(self):
        """Two separate replays increment replay_count to 2."""
        detector = ReplayDetector()

        # First replay
        detector.check_frame(85, (5, 3), 30, (5, 3), 1)
        assert detector.is_suppressed is True
        # Exit via timer passing regression point
        detector.check_frame(25, (5, 3), 85, (5, 3), 2)
        assert detector.is_suppressed is False

        # Second replay
        detector.check_frame(90, (5, 3), 40, (5, 3), 3)
        assert detector.is_suppressed is True

        metrics = detector.get_metrics()
        assert metrics["replay_count"] == 2


class TestMetrics:
    """Test replay detection metrics tracking."""

    def test_metrics_track_replay_count_and_suppressed_frames(self):
        """Metrics reflect actual replay counts and suppressed frames."""
        detector = ReplayDetector()

        # Enter replay
        detector.check_frame(85, (5, 3), 30, (5, 3), 1)  # frame 1: enter, suppressed
        # 4 more suppressed frames
        detector.check_frame(80, (5, 3), 85, (5, 3), 2)
        detector.check_frame(75, (5, 3), 80, (5, 3), 3)
        detector.check_frame(60, (5, 3), 75, (5, 3), 4)
        detector.check_frame(50, (5, 3), 60, (5, 3), 5)

        metrics = detector.get_metrics()
        assert metrics["replay_count"] == 1
        assert metrics["frames_suppressed"] == 5
        assert metrics["is_currently_suppressed"] is True


class TestReset:
    """Test reset clears all state."""

    def test_reset_clears_state(self):
        """After reset, normal frame returns False."""
        detector = ReplayDetector()
        # Enter replay
        detector.check_frame(85, (5, 3), 30, (5, 3), 1)
        assert detector.is_suppressed is True

        detector.reset()
        assert detector.is_suppressed is False

        # Normal frame after reset
        result = detector.check_frame(89, (5, 3), 90, (5, 3), 2)
        assert result is False

        metrics = detector.get_metrics()
        assert metrics["replay_count"] == 0
        assert metrics["frames_suppressed"] == 0
