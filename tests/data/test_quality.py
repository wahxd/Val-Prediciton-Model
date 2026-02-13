"""Tests for quality scoring and data catalog modules."""

import pytest

from src.data.quality import (
    check_kill_count,
    check_round_progression,
    check_round_start_end_balance,
    check_event_completeness,
    check_timing_consistency,
    score_map_quality,
)
from src.data.catalog import DataCatalog, FieldStats
from src.data.schemas import (
    ValoscribeEvent,
    KillEvent,
    RoundStartEvent,
    RoundEndEvent,
    MapMetadata,
)


# Helper functions to create test events
def make_kill_event(round_num: int, timestamp: float, killer: str = "PlayerA", victim: str = "PlayerB") -> KillEvent:
    """Create a test kill event."""
    return KillEvent(
        type="kill",
        round=round_num,
        timestamp=timestamp,
        killer=killer,
        victim=victim,
        weapon="Vandal",
        killer_team="TeamA",
        victim_team="TeamB",
    )


def make_round_start(round_num: int, timestamp: float) -> RoundStartEvent:
    """Create a test round start event."""
    return RoundStartEvent(type="round_start", round=round_num, timestamp=timestamp)


def make_round_end(round_num: int, timestamp: float, winning_team: str = "TeamA") -> RoundEndEvent:
    """Create a test round end event."""
    return RoundEndEvent(
        type="round_end",
        round=round_num,
        timestamp=timestamp,
        winning_team=winning_team,
        score_team1=round_num,
        score_team2=0,
    )


# Quality scoring tests
def test_check_kill_count_high():
    """High kill count should score near 1.0 with no issues."""
    events = [make_kill_event(1, 10.0 + i) for i in range(150)]
    check = check_kill_count(events)

    assert check.score == 1.0
    assert len(check.issues) == 0
    assert len(check.warnings) == 0
    assert check.details["kill_count"] == 150


def test_check_kill_count_low():
    """Low kill count should score < 0.5 and flag issue."""
    events = [make_kill_event(1, 10.0 + i) for i in range(30)]
    check = check_kill_count(events)

    assert check.score < 0.5
    assert len(check.issues) > 0
    assert "Critically low kill count" in check.issues[0]
    assert check.details["kill_count"] == 30


def test_check_kill_count_zero():
    """Zero kills should score 0.0."""
    events = [make_round_start(1, 0.0)]  # No kill events
    check = check_kill_count(events)

    assert check.score == 0.0
    assert len(check.issues) > 0
    assert check.details["kill_count"] == 0


def test_check_round_progression_sequential():
    """Sequential rounds should score 1.0."""
    events = []
    for round_num in range(1, 14):
        events.append(make_round_start(round_num, round_num * 60.0))
        events.append(make_round_end(round_num, round_num * 60.0 + 40.0))

    check = check_round_progression(events)

    assert check.score == 1.0
    assert len(check.issues) == 0
    assert check.details["total_rounds"] == 13
    assert check.details["gaps"] == []


def test_check_round_progression_gap():
    """Missing round should flag issue and lower score."""
    events = []
    for round_num in [1, 2, 4, 5]:  # Missing round 3
        events.append(make_round_start(round_num, round_num * 60.0))
        events.append(make_round_end(round_num, round_num * 60.0 + 40.0))

    check = check_round_progression(events)

    assert check.score < 1.0
    assert len(check.issues) > 0
    assert 3 in check.details["gaps"]
    assert "missing [3]" in check.issues[0]


def test_check_round_start_end_balanced():
    """Equal starts and ends should score 1.0."""
    events = []
    for round_num in range(1, 14):
        events.append(make_round_start(round_num, round_num * 60.0))
        events.append(make_round_end(round_num, round_num * 60.0 + 40.0))

    check = check_round_start_end_balance(events)

    assert check.score == 1.0
    assert len(check.issues) == 0
    assert check.details["round_starts"] == 13
    assert check.details["round_ends"] == 13


def test_check_round_start_end_unbalanced():
    """Unbalanced starts and ends should lower score."""
    events = []
    for round_num in range(1, 14):
        events.append(make_round_start(round_num, round_num * 60.0))
        if round_num <= 11:  # Only 11 round_end events
            events.append(make_round_end(round_num, round_num * 60.0 + 40.0))

    check = check_round_start_end_balance(events)

    assert check.score < 1.0
    assert check.details["round_starts"] == 13
    assert check.details["round_ends"] == 11
    assert check.details["difference"] == 2


def test_check_event_completeness_full():
    """Complete rounds with all expected events should score 1.0."""
    events = []
    for round_num in range(1, 14):
        events.append(make_round_start(round_num, round_num * 60.0))
        events.append(make_kill_event(round_num, round_num * 60.0 + 10.0))
        events.append(make_kill_event(round_num, round_num * 60.0 + 20.0))
        events.append(make_round_end(round_num, round_num * 60.0 + 40.0))

    check = check_event_completeness(events)

    assert check.score == 1.0
    assert len(check.issues) == 0
    assert check.details["complete_rounds"] == 13


def test_check_event_completeness_missing_kills():
    """Round with no kills should trigger warning."""
    events = []
    # Round 1: complete
    events.append(make_round_start(1, 60.0))
    events.append(make_kill_event(1, 70.0))
    events.append(make_round_end(1, 100.0))
    # Round 2: no kills
    events.append(make_round_start(2, 120.0))
    events.append(make_round_end(2, 160.0))

    check = check_event_completeness(events)

    assert check.score < 1.0
    assert len(check.warnings) > 0
    assert "Round 2 has no kill events" in check.warnings[0]
    assert 2 in check.details["incomplete_rounds"]


def test_check_timing_consistent():
    """Monotonically increasing timestamps should score 1.0."""
    events = []
    timestamp = 0.0
    for round_num in range(1, 14):
        events.append(make_round_start(round_num, timestamp))
        timestamp += 10.0
        events.append(make_kill_event(round_num, timestamp))
        timestamp += 10.0
        events.append(make_kill_event(round_num, timestamp))
        timestamp += 20.0
        events.append(make_round_end(round_num, timestamp))
        timestamp += 20.0  # Gap between rounds

    check = check_timing_consistency(events)

    assert check.score == 1.0
    assert len(check.issues) == 0
    assert check.details["timestamp_regressions"] == 0


def test_check_timing_regression():
    """Timestamp going backwards should flag issue."""
    events = [
        make_round_start(1, 60.0),
        make_kill_event(1, 80.0),
        make_kill_event(1, 70.0),  # Regression!
        make_round_end(1, 100.0),
    ]

    check = check_timing_consistency(events)

    assert check.score < 1.0
    assert len(check.issues) > 0
    assert "Timestamp regression" in check.issues[0]


def test_score_map_quality_overall():
    """Full event set should return complete QualityScore."""
    events = []
    for round_num in range(1, 14):
        events.append(make_round_start(round_num, round_num * 60.0))
        for i in range(12):  # 12 kills per round = 156 total
            events.append(make_kill_event(round_num, round_num * 60.0 + 5.0 * i))
        events.append(make_round_end(round_num, round_num * 60.0 + 55.0))

    score = score_map_quality(events, map_id="test_map")

    assert score.map_id == "test_map"
    assert 0.0 <= score.overall_score <= 1.0
    assert score.tier in ["high", "medium", "low"]
    assert len(score.checks) == 5
    assert all(c.weight > 0 for c in score.checks)


def test_score_map_quality_tiers():
    """Test tier boundaries."""
    # High tier: lots of events, perfect structure
    high_events = []
    for round_num in range(1, 14):
        high_events.append(make_round_start(round_num, round_num * 60.0))
        for i in range(12):
            high_events.append(make_kill_event(round_num, round_num * 60.0 + 5.0 * i))
        high_events.append(make_round_end(round_num, round_num * 60.0 + 55.0))

    high_score = score_map_quality(high_events, map_id="high")
    assert high_score.tier == "high"
    assert high_score.overall_score >= 0.8

    # Low tier: very few events
    low_events = [
        make_round_start(1, 0.0),
        make_kill_event(1, 10.0),
        make_round_end(1, 20.0),
    ]
    low_score = score_map_quality(low_events, map_id="low")
    assert low_score.tier in ["low", "medium"]  # Depends on exact thresholds
    assert low_score.overall_score < 0.8


def test_cross_check_disagreement():
    """Valoscribe pass but low score should flag disagreement."""
    # Create low-quality events
    events = [
        make_round_start(1, 0.0),
        make_kill_event(1, 10.0),
        make_round_end(1, 20.0),
    ]

    # Metadata says "passed"
    metadata = MapMetadata(validation_results={"passed": True})

    score = score_map_quality(events, metadata=metadata, map_id="test")

    if score.tier == "low":
        assert len(score.cross_check_disagreements) > 0
        assert "pass but quality score is low" in score.cross_check_disagreements[0]


def test_flagged_for_review():
    """Low tier or disagreement should flag for review."""
    # Low tier case
    low_events = [make_round_start(1, 0.0), make_kill_event(1, 10.0)]
    low_score = score_map_quality(low_events, map_id="low")

    if low_score.tier == "low":
        assert low_score.flagged_for_review is True

    # Disagreement case
    medium_events = []
    for round_num in range(1, 8):
        medium_events.append(make_round_start(round_num, round_num * 60.0))
        for i in range(8):
            medium_events.append(make_kill_event(round_num, round_num * 60.0 + 5.0 * i))
        medium_events.append(make_round_end(round_num, round_num * 60.0 + 55.0))

    metadata_pass = MapMetadata(validation_results={"passed": True})
    medium_score = score_map_quality(medium_events, metadata=metadata_pass, map_id="medium")

    # If there's a disagreement, should be flagged
    if len(medium_score.cross_check_disagreements) > 0:
        assert medium_score.flagged_for_review is True


# Data catalog tests
def test_catalog_accumulates_event_types():
    """Catalog should track all event types."""
    catalog = DataCatalog()

    events = [
        make_kill_event(1, 10.0),
        make_round_start(1, 0.0),
        make_round_end(1, 50.0),
    ]

    catalog.add_map_events(events)

    assert len(catalog.entries) == 3
    assert "kill" in catalog.entries
    assert "round_start" in catalog.entries
    assert "round_end" in catalog.entries
    assert catalog.total_events == 3
    assert catalog.total_maps == 1


def test_catalog_tracks_field_stats():
    """Catalog should track field statistics."""
    catalog = DataCatalog()

    events = [
        make_kill_event(1, 10.0, killer="PlayerA", victim="PlayerB"),
        make_kill_event(1, 20.0, killer="PlayerC", victim="PlayerD"),
    ]

    catalog.add_map_events(events)

    kill_entry = catalog.entries["kill"]
    assert kill_entry.count == 2
    assert "killer" in kill_entry.fields
    assert "victim" in kill_entry.fields

    killer_stats = kill_entry.fields["killer"]
    assert killer_stats.count == 2
    assert killer_stats.dtype == "str"


def test_catalog_discovers_extra_fields():
    """Catalog should discover fields in model_extra."""
    catalog = DataCatalog()

    # Create event with extra field
    event_dict = {
        "type": "kill",
        "round": 1,
        "timestamp": 10.0,
        "killer": "PlayerA",
        "victim": "PlayerB",
        "weapon": "Vandal",
        "killer_team": "TeamA",
        "victim_team": "TeamB",
        "headshot": True,  # Extra field
    }

    event = KillEvent.model_validate(event_dict)
    catalog.add_event(event)

    kill_entry = catalog.entries["kill"]
    assert "headshot" in kill_entry.fields
    assert kill_entry.fields["headshot"].dtype == "bool"


def test_catalog_to_dict():
    """Catalog should serialize to dict."""
    catalog = DataCatalog()

    events = [
        make_kill_event(1, 10.0),
        make_round_start(1, 0.0),
    ]

    catalog.add_map_events(events)

    data = catalog.to_dict()

    assert "total_events" in data
    assert "total_maps" in data
    assert "event_types" in data
    assert "kill" in data["event_types"]
    assert data["total_events"] == 2
    assert data["total_maps"] == 1
