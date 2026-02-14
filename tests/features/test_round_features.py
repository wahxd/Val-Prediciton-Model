"""Tests for round-level feature extraction."""

import pytest
from src.features.extractors.round_features import extract_round_features, RoundFeatures
from src.data.schemas import (
    RoundEndEvent,
    KillEvent,
    SpikePlantEvent,
    SpikeDefuseEvent,
    RoundStartEvent,
)


def test_extract_round_features_standard_round():
    """Test extraction from a standard round with kills, spike plant, and round end."""
    events = [
        RoundStartEvent(type="round_start", timestamp=0.0, round=1),
        KillEvent(
            type="kill",
            timestamp=10.0,
            round=1,
            killer="Player1",
            victim="Player2",
            weapon="Vandal",
            killer_team="Team A",
            victim_team="Team B",
        ),
        KillEvent(
            type="kill",
            timestamp=15.0,
            round=1,
            killer="Player3",
            victim="Player4",
            weapon="Phantom",
            killer_team="Team A",
            victim_team="Team B",
        ),
        SpikePlantEvent(type="spike_plant", timestamp=30.0, round=1),
        KillEvent(
            type="kill",
            timestamp=40.0,
            round=1,
            killer="Player5",
            victim="Player6",
            weapon="Sheriff",
            killer_team="Team B",
            victim_team="Team A",
        ),
        RoundEndEvent(
            type="round_end",
            timestamp=50.0,
            round=1,
            winning_team="Team A",
            score_team1=1,
            score_team2=0,
            sides={"Team A": "attack", "Team B": "defense"},
        ),
    ]

    features = extract_round_features(events)

    assert len(features) == 1
    rf = features[0]

    assert rf.round_number == 1
    assert rf.winning_team == "Team A"
    assert rf.score_team1 == 1
    assert rf.score_team2 == 0
    assert rf.score_differential == 1
    assert rf.spike_planted is True
    assert rf.spike_defused is False
    assert rf.kills_team1 == 2  # Team A got 2 kills
    assert rf.kills_team2 == 1  # Team B got 1 kill
    assert rf.kill_differential == 1
    assert rf.team1_side == "attack"
    assert rf.team2_side == "defense"


def test_extract_round_features_no_kills():
    """Test round with no kills (spike detonation or timeout)."""
    events = [
        RoundStartEvent(type="round_start", timestamp=0.0, round=1),
        SpikePlantEvent(type="spike_plant", timestamp=30.0, round=1),
        RoundEndEvent(
            type="round_end",
            timestamp=60.0,
            round=1,
            winning_team="Team A",
            score_team1=1,
            score_team2=0,
            sides={"Team A": "attack", "Team B": "defense"},
        ),
    ]

    features = extract_round_features(events)

    assert len(features) == 1
    rf = features[0]

    assert rf.round_number == 1
    assert rf.spike_planted is True
    assert rf.spike_defused is False
    assert rf.kills_team1 == 0
    assert rf.kills_team2 == 0
    assert rf.kill_differential == 0


def test_extract_round_features_multiple_rounds():
    """Test score progression across multiple rounds."""
    events = [
        # Round 1
        RoundEndEvent(
            type="round_end",
            timestamp=50.0,
            round=1,
            winning_team="Team A",
            score_team1=1,
            score_team2=0,
            sides={"Team A": "attack", "Team B": "defense"},
        ),
        # Round 2
        KillEvent(
            type="kill",
            timestamp=65.0,
            round=2,
            killer="Player7",
            victim="Player8",
            weapon="Operator",
            killer_team="Team B",
            victim_team="Team A",
        ),
        RoundEndEvent(
            type="round_end",
            timestamp=100.0,
            round=2,
            winning_team="Team B",
            score_team1=1,
            score_team2=1,
            sides={"Team A": "attack", "Team B": "defense"},
        ),
        # Round 3
        SpikePlantEvent(type="spike_plant", timestamp=130.0, round=3),
        SpikeDefuseEvent(type="spike_defuse", timestamp=160.0, round=3),
        RoundEndEvent(
            type="round_end",
            timestamp=170.0,
            round=3,
            winning_team="Team B",
            score_team1=1,
            score_team2=2,
            sides={"Team A": "attack", "Team B": "defense"},
        ),
    ]

    features = extract_round_features(events)

    assert len(features) == 3

    # Round 1
    assert features[0].round_number == 1
    assert features[0].score_team1 == 1
    assert features[0].score_team2 == 0
    assert features[0].score_differential == 1

    # Round 2
    assert features[1].round_number == 2
    assert features[1].score_team1 == 1
    assert features[1].score_team2 == 1
    assert features[1].score_differential == 0
    assert features[1].kills_team2 == 1

    # Round 3
    assert features[2].round_number == 3
    assert features[2].score_team1 == 1
    assert features[2].score_team2 == 2
    assert features[2].score_differential == -1
    assert features[2].spike_planted is True
    assert features[2].spike_defused is True


def test_extract_round_features_no_sides():
    """Test backward compatibility with data lacking sides field."""
    events = [
        KillEvent(
            type="kill",
            timestamp=10.0,
            round=1,
            killer="Player1",
            victim="Player2",
            weapon="Vandal",
            killer_team="Team A",
            victim_team="Team B",
        ),
        KillEvent(
            type="kill",
            timestamp=15.0,
            round=1,
            killer="Player3",
            victim="Player4",
            weapon="Phantom",
            killer_team="Team B",
            victim_team="Team A",
        ),
        RoundEndEvent(
            type="round_end",
            timestamp=50.0,
            round=1,
            winning_team="Team A",
            score_team1=1,
            score_team2=0,
            sides=None,  # Pre-Phase 6 data
        ),
    ]

    features = extract_round_features(events)

    assert len(features) == 1
    rf = features[0]

    assert rf.round_number == 1
    assert rf.team1_side is None  # No sides data
    assert rf.team2_side is None
    assert rf.kills_team1 == 1  # Should still count kills correctly
    assert rf.kills_team2 == 1


def test_extract_round_features_missing_round_end():
    """Test handling of incomplete rounds (no round_end event)."""
    events = [
        RoundStartEvent(type="round_start", timestamp=0.0, round=1),
        KillEvent(
            type="kill",
            timestamp=10.0,
            round=1,
            killer="Player1",
            victim="Player2",
            weapon="Vandal",
            killer_team="Team A",
            victim_team="Team B",
        ),
        # No round_end event
        RoundStartEvent(type="round_start", timestamp=60.0, round=2),
        RoundEndEvent(
            type="round_end",
            timestamp=110.0,
            round=2,
            winning_team="Team B",
            score_team1=0,
            score_team2=1,
            sides={"Team A": "attack", "Team B": "defense"},
        ),
    ]

    features = extract_round_features(events)

    # Round 1 should be skipped (no round_end)
    assert len(features) == 1
    assert features[0].round_number == 2
    assert features[0].winning_team == "Team B"


def test_extract_round_features_spike_defuse_without_plant():
    """Test edge case where spike_defuse exists without spike_plant (data anomaly)."""
    events = [
        SpikeDefuseEvent(type="spike_defuse", timestamp=30.0, round=1),
        RoundEndEvent(
            type="round_end",
            timestamp=50.0,
            round=1,
            winning_team="Team B",
            score_team1=0,
            score_team2=1,
            sides={"Team A": "attack", "Team B": "defense"},
        ),
    ]

    features = extract_round_features(events)

    assert len(features) == 1
    rf = features[0]

    # Should detect defuse even without plant (data quality issue)
    assert rf.spike_planted is False
    assert rf.spike_defused is True
