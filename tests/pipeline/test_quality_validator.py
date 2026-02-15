"""Tests for QualityValidator pipeline integration."""

import json
from pathlib import Path

import pytest

from src.pipeline.quality_validator import QualityValidator, validate_map_output


def create_fixture_events(output_dir: Path, num_rounds: int = 13):
    """Create realistic events.jsonl for testing."""
    events = []
    for r in range(1, num_rounds + 1):
        # Round start
        events.append({"type": "round_start", "timestamp": r * 120.0, "round": r})

        # 10 kills per round
        for k in range(10):
            events.append({
                "type": "kill",
                "timestamp": r * 120.0 + k * 5,
                "round": r,
                "killer": f"Player{k % 5}",
                "victim": f"Player{(k + 5) % 10}",
                "weapon": "Vandal",
                "killer_team": "Team A",
                "victim_team": "Team B",
            })

        # Round end
        events.append({
            "type": "round_end",
            "timestamp": r * 120.0 + 60,
            "round": r,
            "winning_team": "Team A",
            "score_team1": min(r, 13),
            "score_team2": max(0, r - 13)
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "events.jsonl", "w", encoding='utf-8') as f:
        for event in events:
            f.write(json.dumps(event) + "\n")

    metadata = {
        "teams": ["Team A", "Team B"],
        "map_name": "Haven",
        "date": "2024-06-15",
        "agents": {},
        "validation_results": {}
    }
    with open(output_dir / "metadata.json", "w", encoding='utf-8') as f:
        json.dump(metadata, f)


def test_validate_complete_output(tmp_path):
    """Validate complete output with events and metadata."""
    output_dir = tmp_path / "map_123"
    create_fixture_events(output_dir, num_rounds=13)

    result = validate_map_output(output_dir, "map_123")

    # Check structure
    assert isinstance(result, dict)
    assert "overall_score" in result
    assert "tier" in result
    assert "checks" in result
    assert "total_events" in result
    assert "total_rounds" in result

    # Check values
    assert result["overall_score"] > 0.5  # Should be decent quality
    assert result["tier"] in ("high", "medium")
    assert result["total_events"] > 0
    assert result["total_rounds"] == 13

    # Check all 5 quality checks are present
    expected_checks = ["kill_count", "round_progression", "round_start_end_balance",
                      "event_completeness", "timing_consistency"]
    for check_name in expected_checks:
        assert check_name in result["checks"]
        assert "score" in result["checks"][check_name]
        assert "issues" in result["checks"][check_name]
        assert "warnings" in result["checks"][check_name]


def test_validate_missing_events(tmp_path):
    """Validate output dir with only metadata (no events.jsonl)."""
    output_dir = tmp_path / "map_456"
    output_dir.mkdir(parents=True)

    metadata = {
        "teams": ["Team A", "Team B"],
        "map_name": "Bind",
        "date": "2024-06-15",
        "agents": {},
        "validation_results": {}
    }
    with open(output_dir / "metadata.json", "w", encoding='utf-8') as f:
        json.dump(metadata, f)

    result = validate_map_output(output_dir, "map_456")

    assert result["overall_score"] == 0.0
    assert result["tier"] == "low"
    assert result["flagged_for_review"] is True
    assert "No events found in output" in result["all_issues"]
    assert result["total_events"] == 0
    assert result["total_rounds"] == 0


def test_validate_empty_events(tmp_path):
    """Validate output with empty events.jsonl (0 lines)."""
    output_dir = tmp_path / "map_789"
    output_dir.mkdir(parents=True)

    # Create empty events file
    with open(output_dir / "events.jsonl", "w", encoding='utf-8') as f:
        pass

    result = validate_map_output(output_dir, "map_789")

    assert result["overall_score"] == 0.0
    assert result["tier"] == "low"
    assert result["flagged_for_review"] is True
    assert result["total_events"] == 0


def test_validate_missing_metadata(tmp_path):
    """Validate output with events but no metadata.json."""
    output_dir = tmp_path / "map_101"
    output_dir.mkdir(parents=True)

    # Create events without metadata
    events = [
        {"type": "round_start", "timestamp": 0.0, "round": 1},
        {"type": "kill", "timestamp": 5.0, "round": 1, "killer": "P1", "victim": "P2",
         "weapon": "Vandal", "killer_team": "Team A", "victim_team": "Team B"},
        {"type": "round_end", "timestamp": 60.0, "round": 1, "winning_team": "Team A",
         "score_team1": 1, "score_team2": 0},
    ]
    with open(output_dir / "events.jsonl", "w", encoding='utf-8') as f:
        for event in events:
            f.write(json.dumps(event) + "\n")

    result = validate_map_output(output_dir, "map_101")

    # Should still run quality checks with metadata=None
    assert isinstance(result, dict)
    assert result["total_events"] == 3
    assert result["total_rounds"] == 1
    assert "checks" in result


def test_validate_output_dir_not_found(tmp_path):
    """Validate non-existent output directory."""
    output_dir = tmp_path / "nonexistent_map"

    result = validate_map_output(output_dir, "nonexistent_map")

    assert result["overall_score"] == 0.0
    assert result["tier"] == "low"
    assert result["flagged_for_review"] is True
    assert "No events found in output" in result["all_issues"]


def test_quality_validator_class(tmp_path):
    """Test QualityValidator class wrapper."""
    base_dir = tmp_path / "processed"
    base_dir.mkdir()

    map_id = "test_map_123"
    map_dir = base_dir / map_id
    create_fixture_events(map_dir, num_rounds=20)

    validator = QualityValidator(base_dir)
    result = validator.validate(map_id)

    assert isinstance(result, dict)
    assert result["overall_score"] > 0.5
    assert result["total_rounds"] == 20
    assert result["total_events"] > 0


def test_metrics_serializable(tmp_path):
    """Verify returned metrics dict is JSON-serializable."""
    output_dir = tmp_path / "map_serial"
    create_fixture_events(output_dir, num_rounds=13)

    result = validate_map_output(output_dir, "map_serial")

    # Should not raise
    json_str = json.dumps(result)
    assert isinstance(json_str, str)

    # Should round-trip correctly
    parsed = json.loads(json_str)
    assert parsed["overall_score"] == result["overall_score"]
    assert parsed["tier"] == result["tier"]


def test_validate_malformed_events(tmp_path):
    """Validate output with some malformed events (should skip them gracefully)."""
    output_dir = tmp_path / "map_malformed"
    output_dir.mkdir(parents=True)

    events = [
        {"type": "round_start", "timestamp": 0.0, "round": 1},
        {"type": "kill", "timestamp": 5.0},  # Missing required fields
        "invalid json line",  # Not valid JSON
        {"type": "round_end", "timestamp": 60.0, "round": 1, "winning_team": "Team A",
         "score_team1": 1, "score_team2": 0},
    ]

    with open(output_dir / "events.jsonl", "w", encoding='utf-8') as f:
        for event in events:
            if isinstance(event, dict):
                f.write(json.dumps(event) + "\n")
            else:
                f.write(event + "\n")

    result = validate_map_output(output_dir, "map_malformed")

    # Should process valid events and skip invalid ones
    assert isinstance(result, dict)
    # Should have at least round_start and round_end (2 valid events)
    assert result["total_events"] >= 2
