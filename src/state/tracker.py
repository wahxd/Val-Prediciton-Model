"""StateTracker with 3-frame consensus debouncing for stable state detection.

Without debouncing, OCR flicker creates event storms -- the tracker requires
3 consecutive frames to agree on a field value before confirming the change.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Optional

from .models import GameState

# Fields tracked for consensus and change detection
TRACKED_FIELDS: tuple[str, ...] = (
    "score_left",
    "score_right",
    "alive_left",
    "alive_right",
    "timer",
    "spike_planted",
)


class StateTracker:
    """Tracks game state with 3-frame consensus debouncing.

    Uses a ring buffer (deque with maxlen=3) to store recent frames.
    A field value is only considered stable when all 3 frames in the
    buffer agree on it. State changes are detected by comparing stable
    fields against the last confirmed state.
    """

    def __init__(self) -> None:
        self.history: deque[GameState] = deque(maxlen=3)
        self.confirmed_state: Optional[GameState] = None

    def update(self, state: GameState) -> None:
        """Append a new frame's state to the history ring buffer.

        Args:
            state: Validated GameState from the current frame.
        """
        self.history.append(state)

    def has_consensus(self, field: str) -> bool:
        """Check if all 3 frames in history agree on a field's value.

        Args:
            field: Name of a GameState field to check.

        Returns:
            True only if history has exactly 3 frames and all share the
            same value for the given field. False if fewer than 3 frames
            or values disagree.
        """
        if len(self.history) < 3:
            return False

        values = [getattr(state, field) for state in self.history]
        return values[0] == values[1] == values[2]

    def get_stable_fields(self) -> dict[str, Any]:
        """Return dict of field->value for fields with 3-frame consensus.

        Only tracked fields (score, alive, timer, spike_planted) are checked.

        Returns:
            Dict of field name to stable value. Empty dict if fewer than
            3 frames in history or no fields have consensus.
        """
        if len(self.history) < 3:
            return {}

        stable: dict[str, Any] = {}
        for field in TRACKED_FIELDS:
            if self.has_consensus(field):
                stable[field] = getattr(self.history[-1], field)
        return stable

    def detect_changes(self) -> dict[str, tuple[Any, Any]]:
        """Compare stable fields against confirmed state and detect changes.

        When stable fields are detected, the confirmed state is updated to
        reflect the new consensus values (using the latest history entry as
        the base for non-tracked fields like frame_number and timestamp).

        Returns:
            Dict of field -> (old_value, new_value) for changed fields.
            Empty dict if no confirmed state yet or no changes detected.
        """
        stable = self.get_stable_fields()
        if not stable:
            return {}

        changes: dict[str, tuple[Any, Any]] = {}

        if self.confirmed_state is None:
            # First time we have stable fields -- set as baseline,
            # but don't report changes (nothing to compare against).
            latest = self.history[-1]
            # Build confirmed state using stable field values and
            # metadata from the latest frame.
            confirmed_kwargs: dict[str, Any] = {
                "score_left": stable.get("score_left", latest.score_left),
                "score_right": stable.get("score_right", latest.score_right),
                "alive_left": stable.get("alive_left", latest.alive_left),
                "alive_right": stable.get("alive_right", latest.alive_right),
                "timer": stable.get("timer", latest.timer),
                "spike_planted": stable.get("spike_planted", latest.spike_planted),
                "frame_number": latest.frame_number,
                "timestamp": latest.timestamp,
                "ocr_confidence": latest.ocr_confidence,
            }
            self.confirmed_state = GameState(**confirmed_kwargs)
            return {}

        # Compare stable fields against confirmed state
        for field, new_value in stable.items():
            old_value = getattr(self.confirmed_state, field)
            if old_value != new_value:
                changes[field] = (old_value, new_value)

        # Update confirmed state if any changes detected
        if changes:
            latest = self.history[-1]
            confirmed_kwargs = {
                "score_left": stable.get("score_left", self.confirmed_state.score_left),
                "score_right": stable.get("score_right", self.confirmed_state.score_right),
                "alive_left": stable.get("alive_left", self.confirmed_state.alive_left),
                "alive_right": stable.get("alive_right", self.confirmed_state.alive_right),
                "timer": stable.get("timer", self.confirmed_state.timer),
                "spike_planted": stable.get(
                    "spike_planted", self.confirmed_state.spike_planted
                ),
                "frame_number": latest.frame_number,
                "timestamp": latest.timestamp,
                "ocr_confidence": latest.ocr_confidence,
            }
            self.confirmed_state = GameState(**confirmed_kwargs)

        return changes

    def reset(self) -> None:
        """Clear history and confirmed state (used at round boundaries)."""
        self.history.clear()
        self.confirmed_state = None
