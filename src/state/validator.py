"""StateValidator for data quality enforcement on OCR-extracted game state.

Rejects frames with OCR confidence below 0.7, impossible game values
(alive > 5, score > 13, malformed timers), and incoherent state transitions
(alive count increases mid-round, score decreases within a half).

Per user decision: invalid values are discarded and frame is skipped (return None),
NOT auto-corrected.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from .models import GameState

logger = logging.getLogger(__name__)

# Fields that must be present and valid for a frame to be accepted
CRITICAL_FIELDS: tuple[str, ...] = (
    "score_left",
    "score_right",
    "alive_left",
    "alive_right",
    "timer",
)


class StateValidator:
    """Validates OCR-extracted game state for quality and coherence.

    Enforces three layers of validation:
    1. OCR confidence threshold (0.7 per field)
    2. Range/format checks (alive 0-5, score 0-13, timer M:SS)
    3. Coherence rules (alive monotonicity within rounds, score monotonicity within halves)
    """

    def __init__(self) -> None:
        self.min_ocr_confidence: float = 0.7
        self.last_valid_state: Optional[GameState] = None
        self.in_round: bool = False
        self.consecutive_failures: int = 0
        self.failure_threshold_warn: int = 10
        self.failure_threshold_pause: int = 180  # 30 seconds at 6fps

    def validate_frame(
        self,
        raw_state: dict,
        ocr_confidence: dict[str, float],
    ) -> Optional[GameState]:
        """Validate a raw OCR frame and construct a GameState if valid.

        Takes raw extracted values (from VCTVisionEngine output) and per-field
        OCR confidence scores. Returns a valid GameState or None if the frame
        should be skipped.

        Args:
            raw_state: Dict with keys: score_left, score_right, alive_left,
                alive_right, timer, spike_planted, frame_number, timestamp.
            ocr_confidence: Dict mapping field name to confidence float (0.0-1.0).

        Returns:
            A validated GameState, or None if the frame should be discarded.
        """
        # Step 1: Check OCR confidence for critical fields
        for field in CRITICAL_FIELDS:
            confidence = ocr_confidence.get(field, 0.0)
            if confidence < self.min_ocr_confidence:
                logger.debug(
                    "Frame %s: field '%s' confidence %.2f < %.2f threshold, skipping",
                    raw_state.get("frame_number", "?"),
                    field,
                    confidence,
                    self.min_ocr_confidence,
                )
                self.consecutive_failures += 1
                return None

        # Step 2: Validate ranges
        try:
            alive_left = int(raw_state.get("alive_left", -1))
            alive_right = int(raw_state.get("alive_right", -1))
            score_left = int(raw_state.get("score_left", -1))
            score_right = int(raw_state.get("score_right", -1))
        except (ValueError, TypeError):
            self.consecutive_failures += 1
            return None

        if not (0 <= alive_left <= 5):
            logger.debug("Invalid alive_left: %s", alive_left)
            self.consecutive_failures += 1
            return None

        if not (0 <= alive_right <= 5):
            logger.debug("Invalid alive_right: %s", alive_right)
            self.consecutive_failures += 1
            return None

        if not (0 <= score_left <= 13):
            logger.debug("Invalid score_left: %s", score_left)
            self.consecutive_failures += 1
            return None

        if not (0 <= score_right <= 13):
            logger.debug("Invalid score_right: %s", score_right)
            self.consecutive_failures += 1
            return None

        timer = str(raw_state.get("timer", ""))
        if not re.match(r"^\d{1,2}:\d{2}$", timer):
            logger.debug("Invalid timer format: '%s'", timer)
            self.consecutive_failures += 1
            return None

        # Step 3: Construct GameState (Pydantic validators provide additional safety)
        try:
            game_state = GameState(
                score_left=score_left,
                score_right=score_right,
                alive_left=alive_left,
                alive_right=alive_right,
                timer=timer,
                spike_planted=bool(raw_state.get("spike_planted", False)),
                frame_number=int(raw_state.get("frame_number", 0)),
                timestamp=float(raw_state.get("timestamp", 0.0)),
                ocr_confidence=ocr_confidence,
            )
        except Exception:
            logger.debug("GameState construction failed for frame %s", raw_state.get("frame_number", "?"))
            self.consecutive_failures += 1
            return None

        # Valid frame: reset failure counter
        self.consecutive_failures = 0
        return game_state

    def check_coherence(
        self, new_state: GameState
    ) -> tuple[bool, list[str]]:
        """Validate state transitions against game logic rules.

        Checks:
        - QUAL-02: Alive counts must not increase mid-round (unless new round started)
        - QUAL-03: Score must not decrease within a match half

        Also detects round starts (both alive counts return to 5 with timer > 1:30).

        Args:
            new_state: The new GameState to check against previous state.

        Returns:
            Tuple of (is_coherent, warnings) where is_coherent is False if
            any rule is violated, and warnings lists all detected issues.
        """
        warnings: list[str] = []

        if self.last_valid_state is None:
            self.last_valid_state = new_state
            # Detect initial round start
            new_seconds = new_state.timer_to_seconds()
            if (
                new_state.alive_left == 5
                and new_state.alive_right == 5
                and new_seconds is not None
                and new_seconds > 90
            ):
                self.in_round = True
            return True, []

        last = self.last_valid_state

        # Detect round start: both alive counts at 5 and timer high (> 1:30 = 90s)
        new_seconds = new_state.timer_to_seconds()
        if (
            new_state.alive_left == 5
            and new_state.alive_right == 5
            and new_seconds is not None
            and new_seconds > 90
        ):
            self.in_round = True
            self.last_valid_state = new_state
            return True, []

        # Check if score changed (indicates new round, alive reset is expected)
        score_changed = (
            new_state.score_left != last.score_left
            or new_state.score_right != last.score_right
        )

        # QUAL-02: Alive counts must not increase mid-round
        if self.in_round and not score_changed:
            if new_state.alive_left > last.alive_left:
                warnings.append(
                    f"QUAL-02: alive_left increased mid-round "
                    f"({last.alive_left} -> {new_state.alive_left})"
                )
            if new_state.alive_right > last.alive_right:
                warnings.append(
                    f"QUAL-02: alive_right increased mid-round "
                    f"({last.alive_right} -> {new_state.alive_right})"
                )

        # QUAL-03: Score must not decrease within a match half
        if new_state.score_left < last.score_left:
            warnings.append(
                f"QUAL-03: score_left decreased "
                f"({last.score_left} -> {new_state.score_left})"
            )
        if new_state.score_right < last.score_right:
            warnings.append(
                f"QUAL-03: score_right decreased "
                f"({last.score_right} -> {new_state.score_right})"
            )

        is_coherent = len(warnings) == 0

        if is_coherent:
            self.last_valid_state = new_state

        return is_coherent, warnings

    def should_warn(self) -> bool:
        """Check if consecutive failures have reached the warning threshold.

        Returns:
            True if consecutive_failures >= 10 (failure_threshold_warn).
        """
        return self.consecutive_failures >= self.failure_threshold_warn

    def should_pause(self) -> bool:
        """Check if consecutive failures have reached the pause threshold.

        Returns:
            True if consecutive_failures >= 180 (failure_threshold_pause,
            representing ~30 seconds at 6fps).
        """
        return self.consecutive_failures >= self.failure_threshold_pause

    def mark_round_start(self) -> None:
        """Reset round tracking for a new round.

        Sets in_round to True and updates last_valid_state alive counts
        to 5 (full team) if a valid state exists.
        """
        self.in_round = True
        if self.last_valid_state is not None:
            # Create updated state with alive counts reset to 5
            self.last_valid_state = GameState(
                score_left=self.last_valid_state.score_left,
                score_right=self.last_valid_state.score_right,
                alive_left=5,
                alive_right=5,
                timer=self.last_valid_state.timer,
                spike_planted=self.last_valid_state.spike_planted,
                frame_number=self.last_valid_state.frame_number,
                timestamp=self.last_valid_state.timestamp,
                ocr_confidence=self.last_valid_state.ocr_confidence,
            )

    def mark_round_end(self) -> None:
        """Mark the current round as ended."""
        self.in_round = False
