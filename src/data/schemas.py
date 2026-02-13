"""Pydantic models for Valoscribe data formats."""

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict


# Configuration for all models: preserve unknown fields during discovery phase
MODEL_CONFIG = ConfigDict(extra='allow')


class ValoscribeEvent(BaseModel):
    """Base event model - preserves all fields via extra='allow'."""

    type: str
    timestamp: float
    round: int

    model_config = MODEL_CONFIG


class KillEvent(ValoscribeEvent):
    """Kill event with known fields."""

    type: Literal["kill"]
    killer: str
    victim: str
    weapon: str
    killer_team: str
    victim_team: str


class RoundStartEvent(ValoscribeEvent):
    """Round start event."""

    type: Literal["round_start"]
    sides: dict[str, str] | None = None  # Phase 6 addition: {"Team A": "attack", "Team B": "defense"}


class RoundEndEvent(ValoscribeEvent):
    """Round end event with scores."""

    type: Literal["round_end"]
    winning_team: str
    score_team1: int
    score_team2: int
    sides: dict[str, str] | None = None  # Phase 6 addition: side tracking


class SpikePlantEvent(ValoscribeEvent):
    """Spike plant event."""

    type: Literal["spike_plant"]


class SpikeDefuseEvent(ValoscribeEvent):
    """Spike defuse event."""

    type: Literal["spike_defuse"]


class BuyPhaseEvent(ValoscribeEvent):
    """Buy phase loadout event (Phase 6 addition)."""

    type: Literal["buy_phase"]
    team1_credits: int | None = None
    team2_credits: int | None = None
    team1_loadout_type: str | None = None  # full_buy | half_buy | eco | force_buy | unknown
    team2_loadout_type: str | None = None


class UltUsageEvent(ValoscribeEvent):
    """Ultimate usage event (Phase 6 addition)."""

    type: Literal["ult_usage"]
    player: str | None = None
    player_index: int | None = None
    agent: str | None = None


class TimeoutEvent(ValoscribeEvent):
    """Timeout event (Phase 6 addition)."""

    type: Literal["timeout"]
    team: str


class MapMetadata(BaseModel):
    """Map-level metadata from Valoscribe."""

    teams: list[str] = []
    map_name: str = ""
    date: str = ""
    agents: dict[str, Any] = {}
    validation_results: dict[str, Any] = {}

    model_config = MODEL_CONFIG


# Event type mapping for dispatch
EVENT_TYPE_MAP: dict[str, type[ValoscribeEvent]] = {
    "kill": KillEvent,
    "round_start": RoundStartEvent,
    "round_end": RoundEndEvent,
    "spike_plant": SpikePlantEvent,
    "spike_defuse": SpikeDefuseEvent,
    "buy_phase": BuyPhaseEvent,
    "ult_usage": UltUsageEvent,
    "timeout": TimeoutEvent,
}


def parse_event(raw_json: str) -> ValoscribeEvent:
    """
    Parse a raw JSON string into the appropriate event type.

    First parses as base ValoscribeEvent to get the type field,
    then dispatches to specific subclass. Unknown types return
    base ValoscribeEvent (preserving all fields via extra='allow').

    Args:
        raw_json: JSON string representing a single event

    Returns:
        ValoscribeEvent or subclass instance

    Raises:
        ValidationError: If JSON is invalid or required fields missing
    """
    # Parse as base model first to get type
    base_event = ValoscribeEvent.model_validate_json(raw_json)

    # Dispatch to specific type if known
    event_class = EVENT_TYPE_MAP.get(base_event.type, ValoscribeEvent)

    # Re-parse with specific class
    return event_class.model_validate_json(raw_json)
