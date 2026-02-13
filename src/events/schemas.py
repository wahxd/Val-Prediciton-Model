"""Frozen Pydantic dataclasses for all VCT match event types.

Every event includes a full game state snapshot (score, alive counts, timer,
spike status) so each event is a self-contained historical fact that can be
analyzed independently without needing surrounding context.
"""

from __future__ import annotations

import dataclasses
from typing import Literal

from pydantic.dataclasses import dataclass as pydantic_dataclass


@pydantic_dataclass(frozen=True, kw_only=True)
class BaseEvent:
    """Base event containing common fields and full game state snapshot.

    All events inherit these fields ensuring every logged event carries
    the complete game state at the moment it occurred.

    All fields are keyword-only to avoid ordering issues with inheritance
    and to enforce explicit construction of events.
    """

    event_type: str
    timestamp: float  # Wall clock time (time.time())
    frame_number: int
    game_time: str  # Round timer OCR value, e.g. "1:23"
    game_time_seconds: int  # Timer converted to seconds for sorting

    # Full state snapshot - every event includes these
    score_left: int
    score_right: int
    alive_left: int
    alive_right: int
    spike_planted: bool


@pydantic_dataclass(frozen=True, kw_only=True)
class KillEvent(BaseEvent):
    """A player was eliminated. Tracks which team lost a player."""

    event_type: Literal["kill"] = "kill"
    team: Literal["left", "right"]  # Which team lost a player
    alive_before: int
    alive_after: int


@pydantic_dataclass(frozen=True, kw_only=True)
class RoundEndEvent(BaseEvent):
    """A round concluded. Includes winner and inferred win condition."""

    event_type: Literal["round_end"] = "round_end"
    winner: Literal["left", "right"]
    win_condition: Literal[
        "elimination", "spike_detonate", "spike_defuse", "timeout"
    ]
    final_score_left: int
    final_score_right: int


@pydantic_dataclass(frozen=True, kw_only=True)
class RoundStartEvent(BaseEvent):
    """A new round began. round_number = score_left + score_right + 1."""

    event_type: Literal["round_start"] = "round_start"
    round_number: int  # score_left + score_right + 1


@pydantic_dataclass(frozen=True, kw_only=True)
class SpikePlantEvent(BaseEvent):
    """The spike was planted. Includes round timer at plant moment."""

    event_type: Literal["spike_plant"] = "spike_plant"
    plant_time_seconds: int  # Timer at plant moment


@pydantic_dataclass(frozen=True, kw_only=True)
class SpikeDefuseEvent(BaseEvent):
    """The spike was defused. Includes round timer at defuse moment."""

    event_type: Literal["spike_defuse"] = "spike_defuse"
    defuse_time_seconds: int  # Timer at defuse moment


@pydantic_dataclass(frozen=True, kw_only=True)
class SpikeDetonateEvent(BaseEvent):
    """The spike detonated (exploded)."""

    event_type: Literal["spike_detonate"] = "spike_detonate"


@pydantic_dataclass(frozen=True, kw_only=True)
class TimeoutEvent(BaseEvent):
    """A tactical timeout was called. Team attribution for momentum analysis."""

    event_type: Literal["timeout"] = "timeout"
    team: Literal["left", "right"]  # Which team called timeout


def event_to_dict(event: BaseEvent) -> dict:
    """Convert a frozen event dataclass to a serializable dictionary.

    Uses dataclasses.asdict() for reliable conversion. This will be used
    by the JSONL store in Phase 2 for event persistence.
    """
    return dataclasses.asdict(event)


__all__ = [
    "BaseEvent",
    "KillEvent",
    "RoundEndEvent",
    "RoundStartEvent",
    "SpikePlantEvent",
    "SpikeDefuseEvent",
    "SpikeDetonateEvent",
    "TimeoutEvent",
    "event_to_dict",
]
