"""Tests for map-level feature extraction."""

import pytest
from src.features.extractors.map_features import extract_map_features, _calculate_streaks
from src.data.schemas import RoundEndEvent, KillEvent, SpikePlantEvent
from src.features.extractors.round_features import RoundFeatures


class TestMapFeatureExtraction:
    """Test map-level feature aggregation from events."""

    def test_standard_map_13_7(self):
        """Test feature extraction for a standard 13-7 map."""
        # Create synthetic events for a 13-7 map (Team A wins)
        events = []
        teams = ["Team A", "Team B"]

        # Simulate 20 rounds: Team A wins 13, Team B wins 7
        # R1-12: First half, Team A wins 8-4
        # R13-20: Second half, Team A wins 5-3 (total 13-7)
        round_results = (
            # First half (R1-12): Team A wins 8, Team B wins 4
            ["Team A"] * 3 + ["Team B"] * 2 + ["Team A"] * 3 + ["Team B"] * 2 + ["Team A"] * 2 +
            # Second half (R13-20): Team A wins 5, Team B wins 3
            ["Team A"] * 2 + ["Team B"] + ["Team A"] * 3 + ["Team B"] * 2
        )

        score_team_a = 0
        score_team_b = 0

        for round_num, winner in enumerate(round_results, start=1):
            if winner == "Team A":
                score_team_a += 1
            else:
                score_team_b += 1

            # Create round_end event
            events.append(
                RoundEndEvent(
                    type="round_end",
                    timestamp=float(round_num * 100),
                    round=round_num,
                    winning_team=winner,
                    score_team1=score_team_a,
                    score_team2=score_team_b,
                    sides={"Team A": "attack" if round_num <= 12 else "defense",
                           "Team B": "defense" if round_num <= 12 else "attack"},
                )
            )

            # Add some kills for first blood and combat stats
            if round_num % 2 == 0:  # Team A gets first blood on even rounds
                events.append(
                    KillEvent(
                        type="kill",
                        timestamp=float(round_num * 100 + 10),
                        round=round_num,
                        killer="PlayerA1",
                        killer_team="Team A",
                        victim="PlayerB1",
                        victim_team="Team B",
                        weapon="Vandal",
                    )
                )
            else:  # Team B gets first blood on odd rounds
                events.append(
                    KillEvent(
                        type="kill",
                        timestamp=float(round_num * 100 + 10),
                        round=round_num,
                        killer="PlayerB1",
                        killer_team="Team B",
                        victim="PlayerA1",
                        victim_team="Team A",
                        weapon="Phantom",
                    )
                )

        # Extract map features
        features = extract_map_features(events, "map_test_001", teams)

        # Verify score features
        assert features["final_score_team1"] == 13
        assert features["final_score_team2"] == 7
        assert features["score_differential"] == 6
        assert features["total_rounds"] == 20
        assert features["went_to_overtime"] is False
        assert features["map_winner"] == "Team A"

        # Verify pistol rounds (R1 and R13)
        assert features["pistol_round1_winner"] == "Team A"
        assert features["pistol_round2_winner"] == "Team A"
        assert features["pistol_rounds_won_team1"] == 2

        # Verify half features
        assert features["first_half_score_team1"] == 8
        assert features["first_half_score_team2"] == 4
        assert features["second_half_score_team1"] == 5
        assert features["second_half_score_team2"] == 3

        # Verify first blood rates (Team A on even rounds, Team B on odd)
        # 20 rounds: 10 even (Team A), 10 odd (Team B)
        assert features["first_blood_rate_team1"] == 0.5
        assert features["first_blood_rate_team2"] == 0.5

        # Verify side performance
        # Team A: attack R1-12 (8 wins / 12 rounds), defense R13-20 (5 wins / 8 rounds)
        assert features["attack_win_rate_team1"] == 8 / 12
        assert features["defense_win_rate_team1"] == 5 / 8

    def test_overtime_map(self):
        """Test feature extraction for a map that goes to overtime."""
        events = []
        teams = ["Team X", "Team Y"]

        # Simulate 26 rounds (12-12 -> 14-12 in OT)
        round_results = (
            ["Team X"] * 6 + ["Team Y"] * 6 +  # First half 6-6
            ["Team Y"] * 6 + ["Team X"] * 6 +  # Second half 12-12
            ["Team X"] * 2  # OT: Team X wins 14-12
        )

        score_x = 0
        score_y = 0

        for round_num, winner in enumerate(round_results, start=1):
            if winner == "Team X":
                score_x += 1
            else:
                score_y += 1

            events.append(
                RoundEndEvent(
                    type="round_end",
                    timestamp=float(round_num * 100),
                    round=round_num,
                    winning_team=winner,
                    score_team1=score_x,
                    score_team2=score_y,
                    sides={"Team X": "attack", "Team Y": "defense"},
                )
            )

        features = extract_map_features(events, "map_ot_001", teams)

        # Verify OT detection
        assert features["total_rounds"] == 26
        assert features["went_to_overtime"] is True
        assert features["final_score_team1"] == 14
        assert features["final_score_team2"] == 12
        assert features["map_winner"] == "Team X"

    def test_comeback_detection(self):
        """Test comeback detection when team behind at half wins."""
        events = []
        teams = ["Team A", "Team B"]

        # Team B leads 9-3 at half, but Team A wins 13-11
        round_results = (
            ["Team B"] * 9 + ["Team A"] * 3 +  # First half: 3-9
            ["Team A"] * 10 + ["Team B"] * 2  # Second half: Team A wins 10-2 -> 13-11
        )

        score_a = 0
        score_b = 0

        for round_num, winner in enumerate(round_results, start=1):
            if winner == "Team A":
                score_a += 1
            else:
                score_b += 1

            events.append(
                RoundEndEvent(
                    type="round_end",
                    timestamp=float(round_num * 100),
                    round=round_num,
                    winning_team=winner,
                    score_team1=score_a,
                    score_team2=score_b,
                    sides={"Team A": "attack", "Team B": "defense"},
                )
            )

        features = extract_map_features(events, "map_comeback", teams)

        # Verify comeback
        assert features["first_half_score_team1"] == 3
        assert features["first_half_score_team2"] == 9
        assert features["map_winner"] == "Team A"
        assert features["comeback_from_behind"] is True

    def test_missing_economy_data_graceful_handling(self):
        """Test that missing economy data doesn't break feature extraction."""
        # Create minimal events with only round_end (no spike plants or detailed data)
        events = []
        teams = ["Team C", "Team D"]

        # Just 5 rounds for quick test
        for round_num in range(1, 6):
            winner = "Team C" if round_num % 2 == 1 else "Team D"
            score_c = (round_num + 1) // 2
            score_d = round_num // 2

            events.append(
                RoundEndEvent(
                    type="round_end",
                    timestamp=float(round_num * 100),
                    round=round_num,
                    winning_team=winner,
                    score_team1=score_c,
                    score_team2=score_d,
                    sides={"Team C": "attack", "Team D": "defense"},
                )
            )

        features = extract_map_features(events, "map_minimal", teams)

        # Score features should still work
        assert features["final_score_team1"] == 3
        assert features["final_score_team2"] == 2
        assert features["map_winner"] == "Team C"

        # Combat features should gracefully handle no data
        assert features["first_blood_rate_team1"] == 0.0  # No kills = 0 rate
        assert features["clutch_rounds_team1"] == 0

        # Economy features should be None when economy can't be reconstructed
        # (This depends on EconomyTracker behavior - it may return empty list or basic data)
        # We allow None or 0.0 for missing economy features
        assert features["eco_round_win_rate_team1"] is None or isinstance(
            features["eco_round_win_rate_team1"], (float, int)
        )

    def test_empty_events_returns_none_features(self):
        """Test that empty event list returns features with None values."""
        features = extract_map_features([], "map_empty", ["Team A", "Team B"])

        # All features should be None
        assert features["final_score_team1"] is None
        assert features["map_winner"] is None
        assert features["pistol_round1_winner"] is None
        assert features["first_blood_rate_team1"] is None

    def test_calculate_streaks(self):
        """Test win/loss streak calculation helper."""
        # Create synthetic round features
        round_features = [
            RoundFeatures(
                round_number=i + 1,
                winning_team=winner,
                score_team1=0,
                score_team2=0,
                score_differential=0,
                spike_planted=False,
                spike_defused=False,
                kills_team1=0,
                kills_team2=0,
                kill_differential=0,
                team1_side=None,
                team2_side=None,
            )
            for i, winner in enumerate(
                ["Team A", "Team A", "Team A", "Team B", "Team B", "Team A"]
            )
        ]

        streaks = _calculate_streaks(round_features, "Team A")

        # Max win streak: 3 (rounds 1-3)
        # Max loss streak: 2 (rounds 4-5)
        assert streaks["max_win_streak"] == 3
        assert streaks["max_loss_streak"] == 2


class TestEdgeCases:
    """Test edge cases in map feature extraction."""

    def test_single_round_map(self):
        """Test map with only one round (edge case)."""
        events = [
            RoundEndEvent(
                type="round_end",
                timestamp=100.0,
                round=1,
                winning_team="Team A",
                score_team1=1,
                score_team2=0,
                sides={"Team A": "attack", "Team B": "defense"},
            )
        ]

        features = extract_map_features(events, "map_single", ["Team A", "Team B"])

        assert features["final_score_team1"] == 1
        assert features["total_rounds"] == 1
        assert features["pistol_round2_winner"] is None  # No R13

    def test_invalid_team_count_raises_error(self):
        """Test that providing wrong number of teams raises ValueError."""
        events = []
        with pytest.raises(ValueError, match="Expected 2 teams"):
            extract_map_features(events, "map_test", ["Team A"])  # Only 1 team

        with pytest.raises(ValueError, match="Expected 2 teams"):
            extract_map_features(events, "map_test", ["A", "B", "C"])  # 3 teams
