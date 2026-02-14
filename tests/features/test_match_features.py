"""Tests for match-level series feature extraction."""

import pytest
from src.features.extractors.match_features import extract_match_features


class TestMatchFeatureExtraction:
    """Test match/series-level feature aggregation."""

    def test_bo3_team1_wins_2_1_comeback(self):
        """Test BO3 where team1 loses map 1, then wins maps 2 and 3 (comeback)."""
        # Map 1: Team2 wins 13-10 (team1 score_differential = -3)
        map1 = {
            "score_differential": -3,
            "went_to_overtime": False,
            "first_blood_rate_team1": 0.45,
            "attack_win_rate_team1": 0.42,
            "defense_win_rate_team1": 0.38,
            "pistol_rounds_won_team1": 1,
        }

        # Map 2: Team1 wins 13-8 (score_differential = +5)
        map2 = {
            "score_differential": 5,
            "went_to_overtime": False,
            "first_blood_rate_team1": 0.55,
            "attack_win_rate_team1": 0.60,
            "defense_win_rate_team1": 0.58,
            "pistol_rounds_won_team1": 2,
        }

        # Map 3: Team1 wins 13-11 (score_differential = +2)
        map3 = {
            "score_differential": 2,
            "went_to_overtime": False,
            "first_blood_rate_team1": 0.50,
            "attack_win_rate_team1": 0.52,
            "defense_win_rate_team1": 0.50,
            "pistol_rounds_won_team1": 1,
        }

        features = extract_match_features([map1, map2, map3], series_format="bo3")

        # Series state
        assert features["maps_won_team1"] == 2
        assert features["maps_won_team2"] == 1
        assert features["maps_played"] == 3
        assert features["series_score_differential"] == 1
        assert features["series_format"] == "bo3"

        # Series momentum
        assert features["avg_map_score_diff"] == pytest.approx(((-3) + 5 + 2) / 3)
        assert features["maps_to_overtime_count"] == 0
        assert features["maps_to_overtime_pct"] == 0.0
        assert features["comeback_indicator"] is True  # Team1 came back from 0-1 deficit
        assert features["prev_map_score_diff"] == 2  # Map 3
        assert features["prev_map_went_ot"] is False
        assert features["series_momentum"] == 2  # Team1 won last 2 maps

        # Aggregated statistics
        assert features["avg_first_blood_rate"] == pytest.approx(0.50)
        assert features["avg_attack_win_rate"] == pytest.approx((0.42 + 0.60 + 0.52) / 3)
        assert features["avg_defense_win_rate"] == pytest.approx((0.38 + 0.58 + 0.50) / 3)
        assert features["pistol_round_win_pct"] == pytest.approx(4 / 6)  # 4 won out of 6 total

    def test_bo3_team1_wins_2_0_dominant(self):
        """Test BO3 where team1 wins 2-0 (dominant performance)."""
        # Map 1: Team1 wins 13-5
        map1 = {
            "score_differential": 8,
            "went_to_overtime": False,
            "first_blood_rate_team1": 0.65,
            "attack_win_rate_team1": 0.70,
            "defense_win_rate_team1": 0.75,
            "pistol_rounds_won_team1": 2,
        }

        # Map 2: Team1 wins 13-7
        map2 = {
            "score_differential": 6,
            "went_to_overtime": False,
            "first_blood_rate_team1": 0.60,
            "attack_win_rate_team1": 0.65,
            "defense_win_rate_team1": 0.62,
            "pistol_rounds_won_team1": 2,
        }

        features = extract_match_features([map1, map2], series_format="bo3")

        # Series state
        assert features["maps_won_team1"] == 2
        assert features["maps_won_team2"] == 0
        assert features["maps_played"] == 2
        assert features["series_score_differential"] == 2
        assert features["series_format"] == "bo3"

        # Series momentum
        assert features["avg_map_score_diff"] == pytest.approx(7.0)
        assert features["maps_to_overtime_count"] == 0
        assert features["comeback_indicator"] is False  # No comeback needed
        assert features["prev_map_score_diff"] == 6
        assert features["series_momentum"] == 2  # Team1 won both maps

        # Aggregated statistics
        assert features["avg_first_blood_rate"] == pytest.approx(0.625)
        assert features["pistol_round_win_pct"] == 1.0  # 4/4 pistol rounds won

    def test_first_map_context(self):
        """Test features for first map of series (no prior maps)."""
        # Map 1 only
        map1 = {
            "score_differential": 3,
            "went_to_overtime": False,
            "first_blood_rate_team1": 0.52,
            "attack_win_rate_team1": 0.50,
            "defense_win_rate_team1": 0.55,
            "pistol_rounds_won_team1": 1,
        }

        features = extract_match_features([map1], series_format="bo3")

        # Series state
        assert features["maps_won_team1"] == 1
        assert features["maps_won_team2"] == 0
        assert features["maps_played"] == 1

        # Series momentum
        assert features["comeback_indicator"] is False  # Can't comeback on first map
        assert features["prev_map_score_diff"] == 3  # Current (first) map
        assert features["series_momentum"] == 1  # Team1 won 1 map

    def test_series_with_overtime_maps(self):
        """Test series with multiple OT maps."""
        # Map 1: Team1 wins in OT (14-12)
        map1 = {
            "score_differential": 2,
            "went_to_overtime": True,
            "first_blood_rate_team1": 0.48,
            "attack_win_rate_team1": 0.50,
            "defense_win_rate_team1": 0.52,
            "pistol_rounds_won_team1": 1,
        }

        # Map 2: Team2 wins in regulation (13-9)
        map2 = {
            "score_differential": -4,
            "went_to_overtime": False,
            "first_blood_rate_team1": 0.40,
            "attack_win_rate_team1": 0.42,
            "defense_win_rate_team1": 0.38,
            "pistol_rounds_won_team1": 0,
        }

        # Map 3: Team1 wins in OT (15-13)
        map3 = {
            "score_differential": 2,
            "went_to_overtime": True,
            "first_blood_rate_team1": 0.52,
            "attack_win_rate_team1": 0.51,
            "defense_win_rate_team1": 0.50,
            "pistol_rounds_won_team1": 2,
        }

        features = extract_match_features([map1, map2, map3], series_format="bo3")

        # Overtime tracking
        assert features["maps_to_overtime_count"] == 2
        assert features["maps_to_overtime_pct"] == pytest.approx(2 / 3)

        # Series state
        assert features["maps_won_team1"] == 2
        assert features["maps_won_team2"] == 1

        # Momentum (last map won by team1)
        assert features["series_momentum"] == 1
        assert features["prev_map_went_ot"] is True

    def test_bo1_single_map(self):
        """Test BO1 scenario (single map, all series features should be minimal)."""
        map1 = {
            "score_differential": 5,
            "went_to_overtime": False,
            "first_blood_rate_team1": 0.55,
            "attack_win_rate_team1": 0.58,
            "defense_win_rate_team1": 0.60,
            "pistol_rounds_won_team1": 2,
        }

        features = extract_match_features([map1], series_format="bo3")

        # Series features are limited for single map
        assert features["maps_played"] == 1
        assert features["maps_won_team1"] == 1
        assert features["series_momentum"] == 1
        assert features["comeback_indicator"] is False
        assert features["maps_to_overtime_count"] == 0

    def test_empty_map_list(self):
        """Test graceful handling of empty map list."""
        features = extract_match_features([], series_format="bo3")

        # Should return default/empty features
        assert features["maps_played"] == 0
        assert features["maps_won_team1"] == 0
        assert features["maps_won_team2"] == 0
        assert features["series_score_differential"] == 0
        assert features["avg_first_blood_rate"] is None
        assert features["series_momentum"] == 0

    def test_invalid_series_format(self):
        """Test that invalid series format raises ValueError."""
        map1 = {"score_differential": 5, "went_to_overtime": False}

        with pytest.raises(ValueError, match="Invalid series_format"):
            extract_match_features([map1], series_format="bo7")

    def test_missing_optional_features(self):
        """Test graceful handling when optional features are missing from map data."""
        # Map with minimal features (no combat/side stats)
        map1 = {
            "score_differential": 3,
            "went_to_overtime": False,
        }

        map2 = {
            "score_differential": -2,
            "went_to_overtime": False,
        }

        features = extract_match_features([map1, map2], series_format="bo3")

        # Basic features should work
        assert features["maps_won_team1"] == 1
        assert features["maps_won_team2"] == 1
        assert features["avg_map_score_diff"] == pytest.approx(0.5)

        # Optional features should be None or 0
        assert features["avg_first_blood_rate"] is None
        assert features["avg_attack_win_rate"] is None
        assert features["pistol_round_win_pct"] == 0.0

    def test_bo5_series(self):
        """Test BO5 series format tracking."""
        # 5-map series
        maps = [
            {"score_differential": 5, "went_to_overtime": False},
            {"score_differential": -3, "went_to_overtime": False},
            {"score_differential": 2, "went_to_overtime": True},
            {"score_differential": -1, "went_to_overtime": False},
            {"score_differential": 4, "went_to_overtime": False},
        ]

        features = extract_match_features(maps, series_format="bo5")

        assert features["series_format"] == "bo5"
        assert features["maps_played"] == 5
        assert features["maps_won_team1"] == 3  # Maps 1, 3, 5
        assert features["maps_won_team2"] == 2
        assert features["series_score_differential"] == 1
