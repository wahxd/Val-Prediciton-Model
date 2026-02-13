"""EventEmitter: transforms validated state changes into typed event objects.

The core logic bridge between "state changed" and "game event happened."
Maps state diffs to event types, infers win conditions from round event
history, detects round starts via timer transitions (not thresholds), and
detects tactical timeouts as explicit events with team attribution.

Pipeline position: state -> validation -> debounce -> replay check -> emit -> metrics
"""

from __future__ import annotations

from collections import deque
from typing import Any, Literal, Optional

from src.events.schemas import (
    BaseEvent,
    KillEvent,
    RoundEndEvent,
    RoundStartEvent,
    SpikeDefuseEvent,
    SpikeDetonateEvent,
    SpikePlantEvent,
    TimeoutEvent,
)
from src.quality.replay_detector import timer_str_to_seconds
from src.state.models import GameState

# Threshold for frozen-timer frames before emitting a timeout event.
# At ~6fps capture rate, 5 frames is approximately 0.8 seconds of freeze.
TIMEOUT_FREEZE_THRESHOLD: int = 5

# Timer thresholds for transition-based round start detection.
# Previous timer must be below LOW and current must be at or above HIGH.
ROUND_START_TIMER_LOW: int = 30
ROUND_START_TIMER_HIGH: int = 80

# Timer threshold (seconds) below which spike un-plant is treated as detonation.
SPIKE_DETONATE_TIMER_THRESHOLD: int = 5


class EventEmitter:
    """Converts validated state changes into typed event objects.

    Tracks round-level event history for win condition inference, detects
    round starts via timer transitions, and emits timeout events when the
    game timer freezes mid-round.

    Usage:
        emitter = EventEmitter()
        changes = tracker.detect_changes()
        events = emitter.emit_events(changes, current_state, previous_state)
        for event in events:
            # Process or store event
            ...
    """

    def __init__(self) -> None:
        self.recent_events: deque[BaseEvent] = deque(maxlen=20)
        self.current_round_events: list[BaseEvent] = []
        self.last_spike_state: bool = False
        self.last_timer_seconds: Optional[int] = None
        self.timeout_detected: bool = False
        self._timeout_freeze_count: int = 0

    def emit_events(
        self,
        changes: dict[str, tuple[Any, Any]],
        current_state: GameState,
        previous_state: GameState,
    ) -> list[BaseEvent]:
        """Transform state changes into typed event objects.

        Takes the changes dict from StateTracker.detect_changes(), plus current
        and previous GameState. Returns a list of events to emit.

        Processing order matters:
        1. Round start (clears round state)
        2. Timeout detection (mid-round timer freeze)
        3. Kills (alive count decreases)
        4. Spike transitions (plant/defuse/detonate)
        5. Round end (score increase, uses accumulated round events for win condition)

        Args:
            changes: Dict of field -> (old_value, new_value) from StateTracker.
            current_state: The current validated GameState.
            previous_state: The previous validated GameState.

        Returns:
            List of typed event objects emitted for this state transition.
        """
        events: list[BaseEvent] = []
        base_data = self._build_base_data(current_state)

        # Convert timers to seconds for transition checks
        current_timer_seconds = timer_str_to_seconds(current_state.timer)
        previous_timer_seconds = timer_str_to_seconds(previous_state.timer)

        # --- 1. Check for round start (TRANSITION-BASED) ---
        round_started = self._check_round_start(
            current_state, current_timer_seconds, previous_timer_seconds, base_data, events
        )

        # --- 2. Check for tactical timeout ---
        self._check_timeout(
            current_state, current_timer_seconds, previous_timer_seconds,
            changes, base_data, events,
        )

        # --- 3. Check for kills ---
        if "alive_left" in changes:
            old_alive, new_alive = changes["alive_left"]
            if new_alive < old_alive:
                events.append(
                    KillEvent(
                        **base_data,
                        team="left",
                        alive_before=old_alive,
                        alive_after=new_alive,
                    )
                )

        if "alive_right" in changes:
            old_alive, new_alive = changes["alive_right"]
            if new_alive < old_alive:
                events.append(
                    KillEvent(
                        **base_data,
                        team="right",
                        alive_before=old_alive,
                        alive_after=new_alive,
                    )
                )

        # --- 4. Check for spike transitions ---
        if "spike_planted" in changes:
            old_spike, new_spike = changes["spike_planted"]
            if not old_spike and new_spike:
                # False -> True: spike planted
                plant_time = current_timer_seconds if current_timer_seconds is not None else 0
                events.append(
                    SpikePlantEvent(**base_data, plant_time_seconds=plant_time)
                )
            elif old_spike and not new_spike:
                # True -> False: defuse or detonate
                timer_sec = current_timer_seconds if current_timer_seconds is not None else 0
                if timer_sec < SPIKE_DETONATE_TIMER_THRESHOLD:
                    events.append(SpikeDetonateEvent(**base_data))
                else:
                    events.append(
                        SpikeDefuseEvent(**base_data, defuse_time_seconds=timer_sec)
                    )

        # --- 5. Check for round end ---
        if "score_left" in changes or "score_right" in changes:
            winner: Literal["left", "right"]
            if "score_left" in changes:
                old_score, new_score = changes["score_left"]
                if new_score > old_score:
                    winner = "left"
                else:
                    # Score decreased -- should not happen, but handle gracefully
                    winner = "left"
            else:
                winner = "right"

            # If both scores changed (very rare), prefer the one that increased
            if "score_left" in changes and "score_right" in changes:
                left_old, left_new = changes["score_left"]
                right_old, right_new = changes["score_right"]
                if left_new > left_old:
                    winner = "left"
                elif right_new > right_old:
                    winner = "right"

            # Include events emitted this frame in round history for win condition
            all_round_events = self.current_round_events + events
            win_condition = self._infer_win_condition(all_round_events, current_state)

            events.append(
                RoundEndEvent(
                    **base_data,
                    winner=winner,
                    win_condition=win_condition,
                    final_score_left=current_state.score_left,
                    final_score_right=current_state.score_right,
                )
            )

        # --- 6. Track state ---
        self.last_spike_state = current_state.spike_planted
        if current_timer_seconds is not None:
            self.last_timer_seconds = current_timer_seconds

        for event in events:
            self.recent_events.append(event)
            self.current_round_events.append(event)

        return events

    def _check_round_start(
        self,
        current_state: GameState,
        current_timer_seconds: Optional[int],
        previous_timer_seconds: Optional[int],
        base_data: dict[str, Any],
        events: list[BaseEvent],
    ) -> bool:
        """Detect round start via timer transition from low to high + 5v5.

        Round start is detected when the timer TRANSITIONS from a low value
        (< 30s) to a high value (>= 80s), AND both teams have full alive
        counts (5v5). This transition-based approach prevents false positives
        from mid-round high timer values or replay footage.

        Returns True if a round start was detected.
        """
        if current_timer_seconds is None:
            return False

        full_teams = current_state.alive_left == 5 and current_state.alive_right == 5

        if not full_teams:
            return False

        # Check transition from previous_state timer
        prev_transition = (
            previous_timer_seconds is not None
            and previous_timer_seconds < ROUND_START_TIMER_LOW
            and current_timer_seconds >= ROUND_START_TIMER_HIGH
        )

        # Fallback: check transition from tracked last_timer_seconds
        tracked_transition = (
            self.last_timer_seconds is not None
            and self.last_timer_seconds < ROUND_START_TIMER_LOW
            and current_timer_seconds >= ROUND_START_TIMER_HIGH
        )

        if prev_transition or tracked_transition:
            round_number = current_state.score_left + current_state.score_right + 1
            events.append(
                RoundStartEvent(**base_data, round_number=round_number)
            )
            self.current_round_events = []
            self.last_spike_state = False
            self.timeout_detected = False
            self._timeout_freeze_count = 0
            return True

        return False

    def _check_timeout(
        self,
        current_state: GameState,
        current_timer_seconds: Optional[int],
        previous_timer_seconds: Optional[int],
        changes: dict[str, tuple[Any, Any]],
        base_data: dict[str, Any],
        events: list[BaseEvent],
    ) -> None:
        """Detect tactical timeout via frozen timer mid-round.

        A timeout is detected when the game timer stays frozen for multiple
        consecutive frames while the round is active (both teams have alive
        players and no score change). Team attribution is based on which team
        is losing the round (fewer alive players or lower score).
        """
        if current_timer_seconds is None or previous_timer_seconds is None:
            return

        score_changed = "score_left" in changes or "score_right" in changes
        round_active = (
            current_state.alive_left > 0
            and current_state.alive_right > 0
            and not score_changed
        )

        timer_frozen = current_timer_seconds == previous_timer_seconds

        if timer_frozen and round_active:
            self._timeout_freeze_count += 1

            if (
                self._timeout_freeze_count >= TIMEOUT_FREEZE_THRESHOLD
                and not self.timeout_detected
            ):
                team = self._determine_timeout_team(current_state)
                events.append(TimeoutEvent(**base_data, team=team))
                self.timeout_detected = True
        else:
            # Timer is moving again -- reset freeze counter
            if self._timeout_freeze_count > 0 and not timer_frozen:
                self._timeout_freeze_count = 0
                self.timeout_detected = False

    def _build_base_data(self, state: GameState) -> dict[str, Any]:
        """Extract common event fields from a GameState.

        Returns a dict suitable for unpacking into any event constructor
        via **base_data.
        """
        timer_seconds = timer_str_to_seconds(state.timer)
        return {
            "timestamp": state.timestamp,
            "frame_number": state.frame_number,
            "game_time": state.timer,
            "game_time_seconds": timer_seconds if timer_seconds is not None else 0,
            "score_left": state.score_left,
            "score_right": state.score_right,
            "alive_left": state.alive_left,
            "alive_right": state.alive_right,
            "spike_planted": state.spike_planted,
        }

    def _infer_win_condition(
        self,
        round_events: list[BaseEvent],
        current_state: GameState,
    ) -> Literal["elimination", "spike_detonate", "spike_defuse", "timeout"]:
        """Determine win condition from accumulated round event history.

        Priority order:
        1. SpikeDetonateEvent present -> spike_detonate
        2. SpikeDefuseEvent present -> spike_defuse
        3. Any team has 0 alive -> elimination
        4. Default -> timeout (timer ran out)
        """
        for event in round_events:
            if isinstance(event, SpikeDetonateEvent):
                return "spike_detonate"

        for event in round_events:
            if isinstance(event, SpikeDefuseEvent):
                return "spike_defuse"

        if current_state.alive_left == 0 or current_state.alive_right == 0:
            return "elimination"

        return "timeout"

    def _determine_timeout_team(
        self, current_state: GameState
    ) -> Literal["left", "right"]:
        """Attribute tactical timeout to a team.

        Heuristic: the team losing the round (fewer alive players) is more
        likely to call a timeout. If alive counts are equal, the team with
        the lower score is used. If both are equal, defaults to "left".
        """
        if current_state.alive_left < current_state.alive_right:
            return "left"
        elif current_state.alive_right < current_state.alive_left:
            return "right"

        # Alive counts equal -- fall back to score
        if current_state.score_left < current_state.score_right:
            return "left"
        elif current_state.score_right < current_state.score_left:
            return "right"

        return "left"

    def reset(self) -> None:
        """Clear all state for a new match."""
        self.recent_events.clear()
        self.current_round_events.clear()
        self.last_spike_state = False
        self.last_timer_seconds = None
        self.timeout_detected = False
        self._timeout_freeze_count = 0
