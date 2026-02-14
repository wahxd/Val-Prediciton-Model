"""Tests for combat and side performance feature extraction."""

import pytest
from src.features.extractors.combat import (
    extract_first_bloods,
    extract_clutch_rounds,
    extract_multi_kills,
    extract_side_performance,
    compute_anti_eco_stats,
    FirstBlood,
    ClutchRound,
    MultiKill,
    SidePerformance,
    AntiEcoStats,
)
from src.data.schemas import (
    KillEvent,
    RoundEndEvent,
    RoundStartEvent,
)


def test_extract_first_bloods():
    """Test first blood identification with timestamp ordering."""
    events = [
        KillEvent(
            type="kill",
            timestamp=15.0,
            round=1,
            killer="Player2",
            victim="Player3",
            weapon="Phantom",
            killer_team="Team A",
            victim_team="Team B",
        ),
        KillEvent(
            type="kill",
            timestamp=10.0,  # Earlier timestamp - this is first blood
            round=1,
            killer="Player1",
            victim="Player4",
            weapon="Vandal",
            killer_team="Team A",
            victim_team="Team B",
        ),
        KillEvent(
            type="kill",
            timestamp=20.0,
            round=2,
            killer="Player5",
            victim="Player6",
            weapon="Sheriff",
            killer_team="Team B",
            victim_team="Team A",
        ),
    ]

    first_bloods = extract_first_bloods(events)

    assert len(first_bloods) == 2

    # Round 1 first blood
    assert 1 in first_bloods
    fb1 = first_bloods[1]
    assert fb1.killer == "Player1"  # Earliest timestamp
    assert fb1.killer_team == "Team A"
    assert fb1.victim == "Player4"
    assert fb1.timestamp == 10.0

    # Round 2 first blood
    assert 2 in first_bloods
    fb2 = first_bloods[2]
    assert fb2.killer == "Player5"
    assert fb2.timestamp == 20.0


def test_extract_first_bloods_no_kills():
    """Test first bloods when a round has no kills."""
    events = [
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

    first_bloods = extract_first_bloods(events)

    # No kills = no first bloods
    assert len(first_bloods) == 0


def test_extract_clutch_rounds_1v2():
    """Test clutch detection in a 1v2 scenario."""
    events = [
        KillEvent(
            type="kill",
            timestamp=10.0,
            round=1,
            killer="ClutchPlayer",
            victim="Opponent1",
            weapon="Vandal",
            killer_team="Team A",
            victim_team="Team B",
        ),
        KillEvent(
            type="kill",
            timestamp=15.0,
            round=1,
            killer="ClutchPlayer",
            victim="Opponent2",
            weapon="Vandal",
            killer_team="Team A",
            victim_team="Team B",
        ),
        RoundEndEvent(
            type="round_end",
            timestamp=20.0,
            round=1,
            winning_team="Team A",
            score_team1=1,
            score_team2=0,
            sides={"Team A": "attack", "Team B": "defense"},
        ),
    ]

    clutches = extract_clutch_rounds(events)

    assert len(clutches) == 1
    clutch = clutches[0]
    assert clutch.round_number == 1
    assert clutch.clutch_player == "ClutchPlayer"
    assert clutch.clutch_team == "Team A"
    assert clutch.opponents_remaining == 2


def test_extract_clutch_rounds_1v3():
    """Test clutch detection in a 1v3 scenario."""
    events = [
        KillEvent(
            type="kill",
            timestamp=10.0,
            round=1,
            killer="Hero",
            victim="Enemy1",
            weapon="Operator",
            killer_team="Team B",
            victim_team="Team A",
        ),
        KillEvent(
            type="kill",
            timestamp=12.0,
            round=1,
            killer="Hero",
            victim="Enemy2",
            weapon="Operator",
            killer_team="Team B",
            victim_team="Team A",
        ),
        KillEvent(
            type="kill",
            timestamp=14.0,
            round=1,
            killer="Hero",
            victim="Enemy3",
            weapon="Operator",
            killer_team="Team B",
            victim_team="Team A",
        ),
        RoundEndEvent(
            type="round_end",
            timestamp=20.0,
            round=1,
            winning_team="Team B",
            score_team1=0,
            score_team2=1,
            sides={"Team A": "attack", "Team B": "defense"},
        ),
    ]

    clutches = extract_clutch_rounds(events)

    assert len(clutches) == 1
    clutch = clutches[0]
    assert clutch.clutch_player == "Hero"
    assert clutch.opponents_remaining == 3


def test_extract_clutch_rounds_team_effort():
    """Test that team efforts (multiple players getting kills) are not clutches."""
    events = [
        KillEvent(
            type="kill",
            timestamp=10.0,
            round=1,
            killer="Player1",
            victim="Enemy1",
            weapon="Vandal",
            killer_team="Team A",
            victim_team="Team B",
        ),
        KillEvent(
            type="kill",
            timestamp=12.0,
            round=1,
            killer="Player2",  # Different player
            victim="Enemy2",
            weapon="Phantom",
            killer_team="Team A",
            victim_team="Team B",
        ),
        RoundEndEvent(
            type="round_end",
            timestamp=20.0,
            round=1,
            winning_team="Team A",
            score_team1=1,
            score_team2=0,
            sides={"Team A": "attack", "Team B": "defense"},
        ),
    ]

    clutches = extract_clutch_rounds(events)

    # Not a clutch - multiple players contributed
    assert len(clutches) == 0


def test_extract_multi_kills_double():
    """Test detection of double kill (2 kills within 10s)."""
    events = [
        KillEvent(
            type="kill",
            timestamp=10.0,
            round=1,
            killer="Fragger",
            victim="Enemy1",
            weapon="Phantom",
            killer_team="Team A",
            victim_team="Team B",
        ),
        KillEvent(
            type="kill",
            timestamp=12.5,  # 2.5s later - within window
            round=1,
            killer="Fragger",
            victim="Enemy2",
            weapon="Phantom",
            killer_team="Team A",
            victim_team="Team B",
        ),
    ]

    multi_kills = extract_multi_kills(events)

    assert len(multi_kills) == 1
    mk = multi_kills[0]
    assert mk.player == "Fragger"
    assert mk.player_team == "Team A"
    assert mk.kill_count == 2
    assert mk.time_window == 2.5


def test_extract_multi_kills_triple():
    """Test detection of triple kill."""
    events = [
        KillEvent(
            type="kill",
            timestamp=10.0,
            round=1,
            killer="Ace",
            victim="E1",
            weapon="Vandal",
            killer_team="Team B",
            victim_team="Team A",
        ),
        KillEvent(
            type="kill",
            timestamp=11.0,
            round=1,
            killer="Ace",
            victim="E2",
            weapon="Vandal",
            killer_team="Team B",
            victim_team="Team A",
        ),
        KillEvent(
            type="kill",
            timestamp=13.0,
            round=1,
            killer="Ace",
            victim="E3",
            weapon="Vandal",
            killer_team="Team B",
            victim_team="Team A",
        ),
    ]

    multi_kills = extract_multi_kills(events)

    assert len(multi_kills) == 1
    mk = multi_kills[0]
    assert mk.kill_count == 3
    assert mk.time_window == 3.0


def test_extract_multi_kills_outside_window():
    """Test that kills outside 10s window are not counted as multi-kill."""
    events = [
        KillEvent(
            type="kill",
            timestamp=10.0,
            round=1,
            killer="Slow",
            victim="E1",
            weapon="Operator",
            killer_team="Team A",
            victim_team="Team B",
        ),
        KillEvent(
            type="kill",
            timestamp=25.0,  # 15s later - outside window
            round=1,
            killer="Slow",
            victim="E2",
            weapon="Operator",
            killer_team="Team A",
            victim_team="Team B",
        ),
    ]

    multi_kills = extract_multi_kills(events)

    # No multi-kill - kills too far apart
    assert len(multi_kills) == 0


def test_extract_side_performance_with_sides():
    """Test side performance with explicit sides data."""
    events = [
        # Round 1: Team A attack, wins
        RoundEndEvent(
            type="round_end",
            timestamp=50.0,
            round=1,
            winning_team="Team A",
            score_team1=1,
            score_team2=0,
            sides={"Team A": "attack", "Team B": "defense"},
        ),
        # Round 2: Team A attack, wins
        RoundEndEvent(
            type="round_end",
            timestamp=100.0,
            round=2,
            winning_team="Team A",
            score_team1=2,
            score_team2=0,
            sides={"Team A": "attack", "Team B": "defense"},
        ),
        # Round 3: Team A attack, loses
        RoundEndEvent(
            type="round_end",
            timestamp=150.0,
            round=3,
            winning_team="Team B",
            score_team1=2,
            score_team2=1,
            sides={"Team A": "attack", "Team B": "defense"},
        ),
        # Round 4: Team A defense, Team B wins
        RoundEndEvent(
            type="round_end",
            timestamp=200.0,
            round=4,
            winning_team="Team B",
            score_team1=2,
            score_team2=2,
            sides={"Team A": "defense", "Team B": "attack"},
        ),
    ]

    perf = extract_side_performance(events)

    # Team A: 2/3 attack wins, 0/1 defense wins
    assert perf.team1_attack_rounds == 3
    assert perf.team1_attack_wins == 2
    assert perf.team1_defense_rounds == 1
    assert perf.team1_defense_wins == 0

    # Team B: 1/1 attack wins, 1/3 defense wins
    assert perf.team2_attack_rounds == 1
    assert perf.team2_attack_wins == 1
    assert perf.team2_defense_rounds == 3
    assert perf.team2_defense_wins == 1

    # Win rates
    assert perf.team1_attack_win_rate == pytest.approx(2 / 3)
    assert perf.team1_defense_win_rate == 0.0
    assert perf.team2_attack_win_rate == 1.0
    assert perf.team2_defense_win_rate == pytest.approx(1 / 3)


def test_extract_side_performance_no_sides():
    """Test side performance inference when sides field is missing."""
    events = [
        # Round 1-3: inferred as Team A attack
        RoundEndEvent(
            type="round_end",
            timestamp=50.0,
            round=1,
            winning_team="Team A",
            score_team1=1,
            score_team2=0,
            sides=None,
        ),
        RoundEndEvent(
            type="round_end",
            timestamp=100.0,
            round=2,
            winning_team="Team B",
            score_team1=1,
            score_team2=1,
            sides=None,
        ),
        # Round 13+: inferred as halftime swap (Team A defense)
        RoundEndEvent(
            type="round_end",
            timestamp=600.0,
            round=13,
            winning_team="Team A",
            score_team1=7,
            score_team2=6,
            sides=None,
        ),
    ]

    perf = extract_side_performance(events)

    # Should have inferred sides based on round numbers
    assert perf.team1_attack_rounds == 2  # Rounds 1-2
    assert perf.team1_defense_rounds == 1  # Round 13


def test_compute_anti_eco_stats_no_economy_data():
    """Test anti-eco stats when economy data is not available."""
    events = [
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

    stats = compute_anti_eco_stats(events, economy_tiers=None)

    # Should gracefully return zeros
    assert stats.team1_anti_eco_wins == 0
    assert stats.team1_anti_eco_rounds == 0
    assert stats.team2_anti_eco_wins == 0
    assert stats.team2_anti_eco_rounds == 0
    assert stats.team1_conversion_rate == 0.0
    assert stats.team2_conversion_rate == 0.0


def test_side_performance_zero_division():
    """Test that win rate properties handle zero rounds correctly."""
    perf = SidePerformance(
        team1_attack_wins=0,
        team1_attack_rounds=0,
        team1_defense_wins=0,
        team1_defense_rounds=0,
        team2_attack_wins=0,
        team2_attack_rounds=0,
        team2_defense_wins=0,
        team2_defense_rounds=0,
    )

    # Should return 0.0 instead of raising ZeroDivisionError
    assert perf.team1_attack_win_rate == 0.0
    assert perf.team1_defense_win_rate == 0.0
    assert perf.team2_attack_win_rate == 0.0
    assert perf.team2_defense_win_rate == 0.0
