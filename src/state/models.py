"""GameState frozen dataclass for representing a single frame's game state.

All event detection depends on validated, immutable state snapshots.
GameState rejects invalid values at construction time via field validators.
"""

from __future__ import annotations

import re
from typing import Optional

from pydantic import field_validator
from pydantic.dataclasses import dataclass as pydantic_dataclass


@pydantic_dataclass(frozen=True)
class GameState:
    """Immutable snapshot of game state from a single frame.

    Fields are validated at construction: scores must be 0-13, alive counts
    must be 0-5, and timer must match M:SS or MM:SS format. Invalid values
    raise ValidationError, ensuring only valid states enter the pipeline.
    """

    score_left: int
    score_right: int
    alive_left: int
    alive_right: int
    timer: str
    spike_planted: bool
    frame_number: int
    timestamp: float
    ocr_confidence: dict[str, float]

    @field_validator("score_left", "score_right")
    @classmethod
    def score_in_range(cls, v: int) -> int:
        """Score must be between 0 and 13 (max rounds in regulation + OT)."""
        if not 0 <= v <= 13:
            raise ValueError(f"Score must be 0-13, got {v}")
        return v

    @field_validator("alive_left", "alive_right")
    @classmethod
    def alive_in_range(cls, v: int) -> int:
        """Alive count must be between 0 and 5 (team size)."""
        if not 0 <= v <= 5:
            raise ValueError(f"Alive count must be 0-5, got {v}")
        return v

    @field_validator("timer")
    @classmethod
    def timer_format(cls, v: str) -> str:
        """Timer must match M:SS or MM:SS format."""
        if not re.match(r"^\d{1,2}:\d{2}$", v):
            raise ValueError(f"Timer must match M:SS or MM:SS format, got '{v}'")
        return v

    def timer_to_seconds(self) -> Optional[int]:
        """Convert timer string to total seconds.

        Returns:
            Integer seconds (e.g., '1:30' -> 90), or None if format is invalid.
        """
        match = re.match(r"^(\d{1,2}):(\d{2})$", self.timer)
        if not match:
            return None
        minutes = int(match.group(1))
        seconds = int(match.group(2))
        return minutes * 60 + seconds
