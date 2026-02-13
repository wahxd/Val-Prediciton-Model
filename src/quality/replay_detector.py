"""Replay detection for VCT broadcast footage.

Broadcast replays inject phantom duplicate events that corrupt training data.
The ReplayDetector identifies replay segments by detecting timer regression
(timer jumps backward in time) combined with unchanged score (ruling out
new rounds which also show timer jumps).

Detection logic (per user decision - both conditions required):
- Timer regresses (current_timer > previous_timer, since timer counts DOWN)
- Score is unchanged (if score changed, it is a new round, not a replay)

Suppression continues until the timer progresses forward past the point
where regression was first detected, or until the score changes (new round).
"""

from __future__ import annotations

import re
from typing import Optional


def timer_str_to_seconds(timer: str) -> Optional[int]:
    """Convert a timer string in "M:SS" or "MM:SS" format to integer seconds.

    Returns None if the format is invalid. This is a shared utility used by
    both ReplayDetector and the StateTracker.

    Examples:
        >>> timer_str_to_seconds("1:23")
        83
        >>> timer_str_to_seconds("0:05")
        5
        >>> timer_str_to_seconds("12:00")
        720
        >>> timer_str_to_seconds("invalid")  # Returns None
    """
    if not isinstance(timer, str):
        return None

    match = re.fullmatch(r"(\d{1,2}):(\d{2})", timer.strip())
    if match is None:
        return None

    minutes = int(match.group(1))
    seconds = int(match.group(2))

    if seconds >= 60:
        return None

    return minutes * 60 + seconds


class ReplayDetector:
    """Detects broadcast replay segments and suppresses events during them.

    Replays are identified when:
    1. The round timer regresses (jumps to a higher value, since it counts down)
    2. The score has NOT changed (ruling out new rounds)

    Both conditions must be true simultaneously (per user decision).

    Suppression continues until:
    - The timer progresses past the regression point (live footage caught up), OR
    - The score changes (new round started during replay)

    Usage:
        detector = ReplayDetector()
        for frame in frames:
            suppressed = detector.check_frame(
                current_timer_sec=timer,
                current_score=(score_l, score_r),
                previous_timer_sec=prev_timer,
                previous_score=(prev_score_l, prev_score_r),
                frame_number=frame_num,
            )
            if not suppressed:
                # Process events from this frame
                ...
    """

    def __init__(self) -> None:
        self._is_suppressed: bool = False
        self._regression_timer_sec: Optional[int] = None
        self._last_live_score: tuple[int, int] = (0, 0)
        self._suppression_start_frame: Optional[int] = None
        self._frames_suppressed: int = 0
        self._replay_count: int = 0

    @property
    def is_suppressed(self) -> bool:
        """Whether events are currently being suppressed due to replay."""
        return self._is_suppressed

    def check_frame(
        self,
        current_timer_sec: Optional[int],
        current_score: tuple[int, int],
        previous_timer_sec: Optional[int],
        previous_score: tuple[int, int],
        frame_number: int,
    ) -> bool:
        """Check whether this frame is part of a replay and should be suppressed.

        Returns True if events from this frame should be suppressed (replay
        detected or ongoing). Returns False for normal live play.

        Args:
            current_timer_sec: Current frame's round timer in seconds, or None
                if OCR failed.
            current_score: Current frame's score as (left, right).
            previous_timer_sec: Previous frame's round timer in seconds, or None
                if OCR failed.
            previous_score: Previous frame's score as (left, right).
            frame_number: Current frame number (for metrics tracking).

        Returns:
            True if frame should be suppressed (replay), False if live.
        """
        # Rule 1: If either timer is None (invalid OCR), maintain current state.
        # Don't change suppression mode on bad data.
        if current_timer_sec is None or previous_timer_sec is None:
            if self._is_suppressed:
                self._frames_suppressed += 1
            return self._is_suppressed

        # Rule 4: While suppressed, exit if score changes (new round started)
        if self._is_suppressed and current_score != self._last_live_score:
            self._is_suppressed = False
            self._regression_timer_sec = None
            self._suppression_start_frame = None
            return False

        # Rule 3: While suppressed, check exit condition:
        # Timer has progressed forward past the regression point
        if (
            self._is_suppressed
            and self._regression_timer_sec is not None
            and current_timer_sec < self._regression_timer_sec
        ):
            self._is_suppressed = False
            self._regression_timer_sec = None
            self._suppression_start_frame = None
            return False

        # Rule 2: Detect NEW replay:
        # Timer went backward (current > previous since timer counts DOWN)
        # AND score didn't change (not a new round)
        if (
            not self._is_suppressed
            and current_timer_sec > previous_timer_sec
            and current_score == previous_score
        ):
            self._is_suppressed = True
            self._regression_timer_sec = previous_timer_sec
            self._last_live_score = previous_score
            self._suppression_start_frame = frame_number
            self._replay_count += 1

        # Rule 5: If suppressed, increment frames_suppressed
        if self._is_suppressed:
            self._frames_suppressed += 1

        # Rule 6: Return suppression state
        return self._is_suppressed

    def reset(self) -> None:
        """Clear all state. Used at match start."""
        self._is_suppressed = False
        self._regression_timer_sec = None
        self._last_live_score = (0, 0)
        self._suppression_start_frame = None
        self._frames_suppressed = 0
        self._replay_count = 0

    def get_metrics(self) -> dict:
        """Return replay detection metrics.

        Returns:
            Dictionary with:
                - replay_count: Number of replay segments detected
                - frames_suppressed: Total frames suppressed across all replays
                - is_currently_suppressed: Whether currently in a replay
        """
        return {
            "replay_count": self._replay_count,
            "frames_suppressed": self._frames_suppressed,
            "is_currently_suppressed": self._is_suppressed,
        }
