"""Tests for data loader."""

import json
from pathlib import Path

import pandas as pd
import pytest

from src.data.loader import (
    LoadResult,
    MapData,
    discover_maps,
    get_map_index,
    load_all_maps,
    load_events,
    load_frames,
    load_map,
    load_metadata,
)
from src.data.schemas import (
    KillEvent,
    RoundEndEvent,
    RoundStartEvent,
    SpikeDefuseEvent,
    SpikePlantEvent,
    ValoscribeEvent,
)


# Test fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def create_test_map(
    tmp_path: Path,
    map_id: str,
    events: bool = True,
    frames: bool = True,
    metadata: bool = True,
) -> Path:
    """Helper to create a test map directory with fixture files.

    Args:
        tmp_path: pytest tmp_path fixture
        map_id: Map directory name
        events: Include events.jsonl
        frames: Include frames.csv
        metadata: Include metadata.json

    Returns:
        Path to created map directory
    """
    map_dir = tmp_path / map_id
    map_dir.mkdir()

    if events:
        src_events = FIXTURES_DIR / "sample_events.jsonl"
        dst_events = map_dir / "events.jsonl"
        dst_events.write_text(src_events.read_text())

    if frames:
        src_frames = FIXTURES_DIR / "sample_frames.csv"
        dst_frames = map_dir / "frames.csv"
        dst_frames.write_text(src_frames.read_text())

    if metadata:
        src_metadata = FIXTURES_DIR / "sample_metadata.json"
        dst_metadata = map_dir / "metadata.json"
        dst_metadata.write_text(src_metadata.read_text())

    return map_dir


def test_discover_maps_finds_directories(tmp_path):
    """Test that discover_maps finds all map directories."""
    # Create 3 test map directories
    create_test_map(tmp_path, "map_001")
    create_test_map(tmp_path, "map_002")
    create_test_map(tmp_path, "map_003")

    # Create a file (should be ignored)
    (tmp_path / "readme.txt").write_text("test")

    # Discover maps
    maps = discover_maps(tmp_path)

    # Should find all 3 directories, sorted
    assert len(maps) == 3
    assert list(maps.keys()) == ["map_001", "map_002", "map_003"]
    assert all(isinstance(p, Path) for p in maps.values())
    assert all(p.is_dir() for p in maps.values())


def test_discover_maps_empty_dir(tmp_path):
    """Test that discover_maps returns empty dict for empty directory."""
    maps = discover_maps(tmp_path)
    assert maps == {}


def test_discover_maps_nonexistent_dir(tmp_path):
    """Test that discover_maps raises FileNotFoundError for nonexistent directory."""
    nonexistent = tmp_path / "does_not_exist"

    with pytest.raises(FileNotFoundError) as exc_info:
        discover_maps(nonexistent)

    assert "not found" in str(exc_info.value).lower()
    assert str(nonexistent) in str(exc_info.value)


def test_load_events_parses_all_types(tmp_path):
    """Test that load_events parses all event types correctly."""
    map_dir = create_test_map(tmp_path, "test_map")
    events_file = map_dir / "events.jsonl"

    events, parse_errors = load_events(events_file)

    # Should have 11 events from sample_events.jsonl
    assert len(events) == 11
    assert len(parse_errors) == 0

    # Check specific event types are parsed to correct subclasses
    assert isinstance(events[0], RoundStartEvent)
    assert events[0].type == "round_start"
    assert events[0].round == 1

    assert isinstance(events[1], KillEvent)
    assert events[1].type == "kill"
    assert events[1].killer == "Player1"
    assert events[1].victim == "Player6"
    assert events[1].weapon == "Vandal"

    assert isinstance(events[3], SpikePlantEvent)
    assert events[3].type == "spike_plant"

    assert isinstance(events[8], SpikeDefuseEvent)
    assert events[8].type == "spike_defuse"

    assert isinstance(events[5], RoundEndEvent)
    assert events[5].type == "round_end"
    assert events[5].winning_team == "Team_B"


def test_load_events_continues_on_error(tmp_path):
    """Test that load_events continues parsing after encountering invalid lines."""
    # Create JSONL with 5 valid lines and 1 invalid line
    events_file = tmp_path / "events_with_error.jsonl"
    events_file.write_text(
        '{"type": "round_start", "timestamp": 0.5, "round": 1}\n'
        '{"type": "kill", "timestamp": 15.3, "round": 1, "killer": "P1", "victim": "P2", "weapon": "Vandal", "killer_team": "A", "victim_team": "B"}\n'
        '{"type": "round_start", "timestamp": 30.0, "round": 2}\n'
        '{invalid json here}\n'  # Invalid JSON
        '{"type": "round_start", "timestamp": 45.0, "round": 3}\n'
        '{"type": "round_start", "timestamp": 60.0, "round": 4}\n'
    )

    events, parse_errors = load_events(events_file)

    # Should have 5 valid events
    assert len(events) == 5

    # Should have 1 parse error
    assert len(parse_errors) == 1
    assert parse_errors[0]["line"] == 4
    assert "invalid json here" in parse_errors[0]["raw"].lower()


def test_load_events_preserves_extra_fields(tmp_path):
    """Test that events with extra fields preserve them in model_extra."""
    # Create JSONL with event containing extra fields
    events_file = tmp_path / "events_extra.jsonl"
    events_file.write_text(
        '{"type": "kill", "timestamp": 15.3, "round": 1, "killer": "P1", "victim": "P2", '
        '"weapon": "Vandal", "killer_team": "A", "victim_team": "B", '
        '"headshot": true, "wallbang": false, "custom_field": "test"}\n'
    )

    events, parse_errors = load_events(events_file)

    assert len(events) == 1
    assert len(parse_errors) == 0

    # Extra fields should be preserved (Pydantic extra='allow')
    event = events[0]
    # Known fields accessible directly
    assert event.killer == "P1"

    # Extra fields accessible via model_extra
    # Note: headshot is in sample data so might be recognized or extra
    # custom_field definitely should be extra
    if hasattr(event, "model_extra"):
        # Pydantic v2 stores in model_extra
        assert "custom_field" in event.model_extra or hasattr(event, "custom_field")


def test_load_frames_returns_dataframe(tmp_path):
    """Test that load_frames returns a DataFrame with expected shape."""
    map_dir = create_test_map(tmp_path, "test_map")
    frames_file = map_dir / "frames.csv"

    df = load_frames(frames_file)

    # Should be a DataFrame
    assert isinstance(df, pd.DataFrame)

    # Should have 5 rows from sample_frames.csv (header + 5 data rows)
    assert len(df) == 5

    # Should have expected columns
    assert "timestamp" in df.columns
    assert "team1_alive" in df.columns


def test_load_metadata_parses_fields(tmp_path):
    """Test that load_metadata parses fields correctly."""
    map_dir = create_test_map(tmp_path, "test_map")
    metadata_file = map_dir / "metadata.json"

    metadata = load_metadata(metadata_file)

    # Check fields from sample_metadata.json
    assert isinstance(metadata.teams, list)
    assert len(metadata.teams) == 2
    assert isinstance(metadata.map_name, str)
    assert metadata.map_name  # Should be non-empty


def test_load_map_all_files(tmp_path):
    """Test load_map with all three files present."""
    map_dir = create_test_map(tmp_path, "test_map", events=True, frames=True, metadata=True)

    map_data = load_map(map_dir)

    assert isinstance(map_data, MapData)
    assert map_data.map_id == "test_map"
    assert map_data.map_dir == map_dir
    assert len(map_data.events) == 11  # From sample_events.jsonl
    assert map_data.frames is not None
    assert isinstance(map_data.frames, pd.DataFrame)
    assert map_data.metadata is not None
    assert map_data.event_count == 11
    assert set(map_data.files_found) == {"events.jsonl", "frames.csv", "metadata.json"}
    assert len(map_data.parse_errors) == 0


def test_load_map_missing_frames(tmp_path):
    """Test load_map with only events.jsonl and metadata.json."""
    map_dir = create_test_map(tmp_path, "test_map", events=True, frames=False, metadata=True)

    map_data = load_map(map_dir)

    assert map_data.map_id == "test_map"
    assert len(map_data.events) == 11
    assert map_data.frames is None  # Missing
    assert map_data.metadata is not None
    assert set(map_data.files_found) == {"events.jsonl", "metadata.json"}


def test_load_map_missing_events_raises(tmp_path):
    """Test load_map raises ValueError when events.jsonl is missing."""
    map_dir = create_test_map(tmp_path, "test_map", events=False, frames=True, metadata=True)

    with pytest.raises(ValueError) as exc_info:
        load_map(map_dir)

    assert "required" in str(exc_info.value).lower()
    assert "events.jsonl" in str(exc_info.value).lower()


def test_load_all_maps_continue_on_error(tmp_path):
    """Test load_all_maps continues when one map fails."""
    # Create 3 maps: 2 valid, 1 with missing events.jsonl
    create_test_map(tmp_path, "map_001", events=True, frames=True, metadata=True)
    create_test_map(tmp_path, "map_002", events=False, frames=True, metadata=True)  # Invalid
    create_test_map(tmp_path, "map_003", events=True, frames=True, metadata=True)

    results = load_all_maps(tmp_path)

    # Should have 3 results
    assert len(results) == 3

    # Check successes
    assert results["map_001"].success is True
    assert results["map_001"].data is not None
    assert results["map_003"].success is True
    assert results["map_003"].data is not None

    # Check failure
    assert results["map_002"].success is False
    assert results["map_002"].data is None
    assert results["map_002"].error is not None
    assert "events.jsonl" in results["map_002"].error.lower()
    assert results["map_002"].error_phase == "events"


def test_get_map_index_extracts_summary(tmp_path):
    """Test get_map_index extracts summary info from load results."""
    # Create 2 test maps
    create_test_map(tmp_path, "map_001", events=True, frames=True, metadata=True)
    create_test_map(tmp_path, "map_002", events=True, frames=False, metadata=True)

    # Load maps
    results = load_all_maps(tmp_path)

    # Get index
    index = get_map_index(results)

    # Should have 2 entries
    assert len(index) == 2

    # Check first entry
    entry = index[0]
    assert entry["map_id"] == "map_001"
    assert isinstance(entry["teams"], list)
    assert isinstance(entry["map_name"], str)
    assert isinstance(entry["date"], str)
    assert entry["event_count"] == 11
    assert "events.jsonl" in entry["files_found"]

    # Second entry should also be present
    assert index[1]["map_id"] == "map_002"


def test_get_map_index_handles_missing_metadata(tmp_path):
    """Test get_map_index handles maps with missing metadata gracefully."""
    # Create map without metadata
    create_test_map(tmp_path, "map_no_meta", events=True, frames=True, metadata=False)

    results = load_all_maps(tmp_path)
    index = get_map_index(results)

    assert len(index) == 1
    entry = index[0]

    # Should have "unknown" placeholders for missing metadata fields
    assert entry["map_id"] == "map_no_meta"
    assert entry["teams"] == ["unknown", "unknown"]
    assert entry["map_name"] == "unknown"
    assert entry["date"] == "unknown"
    assert entry["event_count"] == 11  # Events still loaded
    assert "metadata.json" not in entry["files_found"]


def test_load_all_maps_filters_to_specific_maps(tmp_path):
    """Test load_all_maps can filter to specific map_ids."""
    # Create 3 maps
    create_test_map(tmp_path, "map_001")
    create_test_map(tmp_path, "map_002")
    create_test_map(tmp_path, "map_003")

    # Load only map_001 and map_003
    results = load_all_maps(tmp_path, map_ids=["map_001", "map_003"])

    # Should only have 2 results
    assert len(results) == 2
    assert "map_001" in results
    assert "map_003" in results
    assert "map_002" not in results
