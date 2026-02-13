"""Tests for Pydantic schema validation and parsing."""

import json
import pytest
from pathlib import Path
from pydantic import ValidationError

from src.data.schemas import (
    ValoscribeEvent,
    KillEvent,
    RoundEndEvent,
    MapMetadata,
    parse_event,
    EVENT_TYPE_MAP,
)
from src.data.config import DataPipelineConfig, get_config


# Fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_parse_kill_event():
    """Parse a kill event JSON and verify all fields populated."""
    kill_json = '{"type": "kill", "timestamp": 15.3, "round": 1, "killer": "Player1", "victim": "Player6", "weapon": "Vandal", "killer_team": "Team_A", "victim_team": "Team_B"}'

    event = parse_event(kill_json)

    assert isinstance(event, KillEvent)
    assert event.type == "kill"
    assert event.timestamp == 15.3
    assert event.round == 1
    assert event.killer == "Player1"
    assert event.victim == "Player6"
    assert event.weapon == "Vandal"
    assert event.killer_team == "Team_A"
    assert event.victim_team == "Team_B"


def test_parse_round_end_event():
    """Parse round_end event and verify scores and winning_team."""
    round_end_json = '{"type": "round_end", "timestamp": 52.0, "round": 1, "winning_team": "Team_B", "score_team1": 0, "score_team2": 1}'

    event = parse_event(round_end_json)

    assert isinstance(event, RoundEndEvent)
    assert event.type == "round_end"
    assert event.winning_team == "Team_B"
    assert event.score_team1 == 0
    assert event.score_team2 == 1


def test_parse_unknown_event_type():
    """Parse event with unknown type, verify it returns base ValoscribeEvent with all fields preserved."""
    unknown_json = '{"type": "ability_use", "timestamp": 30.0, "round": 2, "agent": "Sova", "ability": "Recon Bolt"}'

    event = parse_event(unknown_json)

    # Should return base ValoscribeEvent, not a subclass
    assert type(event) == ValoscribeEvent
    assert event.type == "ability_use"
    assert event.timestamp == 30.0
    assert event.round == 2

    # Extra fields should be preserved in model_extra
    assert event.model_extra is not None
    assert event.model_extra.get("agent") == "Sova"
    assert event.model_extra.get("ability") == "Recon Bolt"


def test_extra_fields_preserved():
    """Parse kill event with extra field, verify extra field accessible via model_extra."""
    kill_with_extra = '{"type": "kill", "timestamp": 15.3, "round": 1, "killer": "Player1", "victim": "Player6", "weapon": "Vandal", "killer_team": "Team_A", "victim_team": "Team_B", "headshot": true}'

    event = parse_event(kill_with_extra)

    assert isinstance(event, KillEvent)
    # Extra field preserved
    assert event.model_extra is not None
    assert event.model_extra.get("headshot") is True


def test_invalid_event_raises():
    """Parse garbage JSON, verify ValidationError raised."""
    invalid_json = '{"not_a_valid": "event"}'

    with pytest.raises(ValidationError) as exc_info:
        parse_event(invalid_json)

    # Check that required fields are mentioned in error
    errors = exc_info.value.errors()
    error_fields = {e['loc'][0] for e in errors}
    assert 'type' in error_fields or 'timestamp' in error_fields or 'round' in error_fields


def test_map_metadata_parse():
    """Parse sample_metadata.json fixture and verify fields."""
    metadata_path = FIXTURES_DIR / "sample_metadata.json"
    with open(metadata_path, 'r') as f:
        metadata_json = f.read()

    metadata = MapMetadata.model_validate_json(metadata_json)

    assert metadata.teams == ["Team_A", "Team_B"]
    assert metadata.map_name == "Ascent"
    assert metadata.date == "2025-01-15"
    assert "Team_A" in metadata.agents
    assert metadata.validation_results.get("status") == "pass"

    # Extra field preserved
    assert metadata.model_extra is not None
    assert metadata.model_extra.get("unexpected_field") == "This field tests extra='allow' preservation"


def test_map_metadata_partial():
    """Parse metadata missing optional fields, verify it still parses with defaults."""
    partial_json = '{"teams": ["Team_C", "Team_D"]}'

    metadata = MapMetadata.model_validate_json(partial_json)

    assert metadata.teams == ["Team_C", "Team_D"]
    assert metadata.map_name == ""  # Default
    assert metadata.date == ""  # Default
    assert metadata.agents == {}  # Default
    assert metadata.validation_results == {}  # Default


def test_config_loads_from_env(monkeypatch, tmp_path):
    """Use monkeypatch to set VALOSCRIBE_DATA_DIR env var, verify DataPipelineConfig loads it."""
    # Create a temporary directory to use as data dir
    test_data_dir = tmp_path / "valoscribe_data"
    test_data_dir.mkdir()

    # Set environment variable
    monkeypatch.setenv("VALOSCRIBE_DATA_DIR", str(test_data_dir))

    config = DataPipelineConfig()

    assert config.valoscribe_data_dir == test_data_dir
    assert config.audit_output_dir == Path("data/audit")  # Default
    assert config.log_level == "INFO"  # Default


def test_config_override(tmp_path):
    """Verify get_config(data_dir_override=...) overrides env var."""
    override_dir = tmp_path / "override_data"
    override_dir.mkdir()

    config = get_config(data_dir_override=override_dir)

    assert config.valoscribe_data_dir == override_dir


def test_event_type_map_completeness():
    """Verify EVENT_TYPE_MAP contains all expected event types."""
    expected_types = {"kill", "round_start", "round_end", "spike_plant", "spike_defuse"}

    assert set(EVENT_TYPE_MAP.keys()) == expected_types
    assert len(EVENT_TYPE_MAP) == 5
