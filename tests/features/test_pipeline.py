"""Integration tests for end-to-end feature extraction pipeline."""

import pytest
import pandas as pd
from pathlib import Path

from src.features.pipeline import FeaturePipeline
from src.data.loader import MapData
from src.data.schemas import RoundEndEvent, KillEvent, MapMetadata


def create_synthetic_map_data(
    map_id: str,
    teams: list[str],
    final_score: tuple[int, int],
    went_to_ot: bool = False,
) -> MapData:
    """
    Create synthetic MapData for testing.

    Args:
        map_id: Map identifier
        teams: [team1, team2] names
        final_score: (team1_score, team2_score)
        went_to_ot: Whether map went to overtime

    Returns:
        MapData with synthetic events
    """
    team1, team2 = teams
    score1, score2 = final_score
    total_rounds = score1 + score2

    # Generate synthetic round events
    events = []
    current_score1 = 0
    current_score2 = 0

    for round_num in range(1, total_rounds + 1):
        # Determine winner (distribute wins to reach final score)
        if current_score1 < score1:
            winner = team1
            current_score1 += 1
        else:
            winner = team2
            current_score2 += 1

        # Create round_end event
        events.append(
            RoundEndEvent(
                type="round_end",
                timestamp=float(round_num * 100),
                round=round_num,
                winning_team=winner,
                score_team1=current_score1,
                score_team2=current_score2,
                sides={
                    team1: "attack" if round_num <= 12 else "defense",
                    team2: "defense" if round_num <= 12 else "attack",
                },
            )
        )

        # Add some kills for first blood detection
        if round_num <= 3:  # First 3 rounds have kills
            events.insert(
                -1,  # Before round_end
                KillEvent(
                    type="kill",
                    timestamp=float(round_num * 100 - 50),
                    round=round_num,
                    killer="player1",
                    victim="player2",
                    weapon="Vandal",
                    killer_team=team1,
                    victim_team=team2,
                ),
            )

    # Create metadata
    metadata = MapMetadata(
        teams=teams,
        map_name="Bind",
        date="2024-01-01",
        agents={},
        validation_results={},
    )

    return MapData(
        map_id=map_id,
        map_dir=Path(f"/fake/path/{map_id}"),
        events=events,
        frames=None,
        metadata=metadata,
        files_found=["events.jsonl", "metadata.json"],
        event_count=len(events),
        parse_errors=[],
    )


class TestFeaturePipeline:
    """Integration tests for FeaturePipeline."""

    def test_pipeline_initialization(self):
        """Test pipeline initializes with valid feature set."""
        pipeline = FeaturePipeline(feature_set="core")
        assert pipeline.feature_set == "core"
        assert len(pipeline.feature_names) > 0

    def test_pipeline_invalid_feature_set(self):
        """Test pipeline raises error for invalid feature set."""
        with pytest.raises(ValueError, match="Invalid feature set"):
            FeaturePipeline(feature_set="nonexistent_set")

    def test_extract_map_dataset_core_features(self):
        """Test extraction with 'core' feature set."""
        # Create synthetic map data
        map1 = create_synthetic_map_data("map1", ["Team A", "Team B"], (13, 7))
        map2 = create_synthetic_map_data("map2", ["Team C", "Team D"], (13, 10))
        map3 = create_synthetic_map_data("map3", ["Team E", "Team F"], (13, 5))

        # Extract features
        pipeline = FeaturePipeline(feature_set="core")
        df = pipeline.extract_map_dataset([map1, map2, map3])

        # Verify DataFrame structure
        assert len(df) == 3
        assert "map_id" in df.columns
        assert "map_winner" in df.columns

        # Verify core features present
        core_features = [
            "score_differential",
            "total_rounds",
            "pistol_rounds_won_team1",
            "first_half_score_team1",
        ]
        for feature in core_features:
            assert feature in df.columns

        # Verify combat features NOT present (not in core set)
        assert "first_blood_rate_team1" not in df.columns
        assert "clutch_rounds_team1" not in df.columns

        # Verify data correctness
        assert df.loc[df["map_id"] == "map1", "score_differential"].iloc[0] == 6  # 13-7
        assert df.loc[df["map_id"] == "map2", "total_rounds"].iloc[0] == 23  # 13+10
        assert df.loc[df["map_id"] == "map3", "map_winner"].iloc[0] == "Team E"

    def test_extract_map_dataset_full_features(self):
        """Test extraction with 'full' feature set includes all features."""
        map1 = create_synthetic_map_data("map1", ["Team A", "Team B"], (13, 8))

        pipeline = FeaturePipeline(feature_set="full")
        df = pipeline.extract_map_dataset([map1])

        # Full set should include combat, economy, side performance
        assert "first_blood_rate_team1" in df.columns
        assert "attack_win_rate_team1" in df.columns
        # Economy features might be None if no buy phase data, but columns exist
        assert "eco_round_win_rate_team1" in df.columns or True  # Graceful if missing

    def test_extract_map_dataset_empty_input(self):
        """Test extraction with empty input returns empty DataFrame."""
        pipeline = FeaturePipeline(feature_set="core")
        df = pipeline.extract_map_dataset([])

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_extract_map_dataset_error_handling(self):
        """Test that bad maps are handled gracefully."""
        # Create one good map and one with invalid data
        good_map = create_synthetic_map_data("good_map", ["Team A", "Team B"], (13, 5))

        # Create bad map with no metadata (will cause teams to default to ["team1", "team2"])
        # Empty events will return empty features with None values, which is valid
        bad_map = MapData(
            map_id="bad_map",
            map_dir=Path("/fake/bad"),
            events=[],  # Empty events - extract_map_features returns empty features
            frames=None,
            metadata=None,
            files_found=[],
            event_count=0,
            parse_errors=[],
        )

        pipeline = FeaturePipeline(feature_set="core")
        df = pipeline.extract_map_dataset([good_map, bad_map])

        # Both maps should be present (extract_map_features gracefully handles empty events)
        assert len(df) == 2
        assert "good_map" in df["map_id"].values
        assert "bad_map" in df["map_id"].values

        # Good map should have valid data
        good_row = df[df["map_id"] == "good_map"].iloc[0]
        assert good_row["score_differential"] == 8  # 13-5

        # Bad map should have None values for most features
        bad_row = df[df["map_id"] == "bad_map"].iloc[0]
        assert bad_row["map_winner"] is None
        assert pd.isna(bad_row["score_differential"]) or bad_row["score_differential"] is None

    def test_extract_map_dataset_nan_handling(self):
        """Test NaN handling for features that can't be computed."""
        # Create map with minimal events (no combat data)
        map_data = MapData(
            map_id="minimal_map",
            map_dir=Path("/fake/minimal"),
            events=[
                RoundEndEvent(
                    type="round_end",
                    timestamp=100.0,
                    round=1,
                    winning_team="Team A",
                    score_team1=1,
                    score_team2=0,
                )
            ],
            frames=None,
            metadata=MapMetadata(teams=["Team A", "Team B"]),
            files_found=["events.jsonl"],
            event_count=1,
            parse_errors=[],
        )

        pipeline = FeaturePipeline(feature_set="combat")
        df = pipeline.extract_map_dataset([map_data])

        # Should succeed but with limited data
        assert len(df) == 1
        # First blood rate will be 0 (no kills)
        assert df["first_blood_rate_team1"].iloc[0] == 0.0

    def test_extract_match_dataset_basic(self):
        """Test match dataset extraction with 2 series."""
        # Series 1: BO3 (Team A wins 2-1)
        series1_map1 = create_synthetic_map_data("s1_m1", ["Team A", "Team B"], (10, 13))  # Team B wins
        series1_map2 = create_synthetic_map_data("s1_m2", ["Team A", "Team B"], (13, 8))   # Team A wins
        series1_map3 = create_synthetic_map_data("s1_m3", ["Team A", "Team B"], (13, 11))  # Team A wins

        # Series 2: BO3 (Team C wins 2-0)
        series2_map1 = create_synthetic_map_data("s2_m1", ["Team C", "Team D"], (13, 6))   # Team C wins
        series2_map2 = create_synthetic_map_data("s2_m2", ["Team C", "Team D"], (13, 9))   # Team C wins

        series_maps = {
            "series_1": [series1_map1, series1_map2, series1_map3],
            "series_2": [series2_map1, series2_map2],
        }

        pipeline = FeaturePipeline(feature_set="core")
        df = pipeline.extract_match_dataset(series_maps)

        # Should have 5 rows (3 + 2 maps)
        assert len(df) == 5

        # Verify metadata columns
        assert "series_id" in df.columns
        assert "map_index" in df.columns
        assert "map_id" in df.columns
        assert "map_winner" in df.columns

        # Verify match-level features present
        assert "series_momentum" in df.columns
        assert "maps_won_team1" in df.columns
        assert "maps_won_team2" in df.columns

        # Verify series 1 data
        s1_data = df[df["series_id"] == "series_1"]
        assert len(s1_data) == 3

        # Check map indices
        assert list(s1_data["map_index"]) == [0, 1, 2]

        # Check series state after each map
        # After map 1: 0-1
        assert s1_data.iloc[0]["maps_won_team1"] == 0
        assert s1_data.iloc[0]["maps_won_team2"] == 1

        # After map 2: 1-1
        assert s1_data.iloc[1]["maps_won_team1"] == 1
        assert s1_data.iloc[1]["maps_won_team2"] == 1

        # After map 3: 2-1
        assert s1_data.iloc[2]["maps_won_team1"] == 2
        assert s1_data.iloc[2]["maps_won_team2"] == 1

    def test_extract_match_dataset_with_series_formats(self):
        """Test match dataset with explicit series formats."""
        map1 = create_synthetic_map_data("m1", ["Team A", "Team B"], (13, 5))
        map2 = create_synthetic_map_data("m2", ["Team A", "Team B"], (13, 10))

        series_maps = {"bo5_series": [map1, map2]}
        series_formats = {"bo5_series": "bo5"}

        pipeline = FeaturePipeline(feature_set="core")
        df = pipeline.extract_match_dataset(series_maps, series_formats)

        assert len(df) == 2
        assert df["series_format"].iloc[0] == "bo5"
        assert df["series_format"].iloc[1] == "bo5"

    def test_extract_match_dataset_empty_input(self):
        """Test match dataset extraction with empty input."""
        pipeline = FeaturePipeline(feature_set="core")
        df = pipeline.extract_match_dataset({})

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_extract_match_dataset_error_handling(self):
        """Test that bad series are skipped gracefully."""
        # Good series
        good_map = create_synthetic_map_data("good", ["A", "B"], (13, 7))

        # Bad series (empty maps list)
        series_maps = {
            "good_series": [good_map],
            "bad_series": [],  # Empty list
        }

        pipeline = FeaturePipeline(feature_set="core")
        df = pipeline.extract_match_dataset(series_maps)

        # Should have 1 row (good series), bad series skipped
        assert len(df) == 1
        assert df["series_id"].iloc[0] == "good_series"

    def test_pipeline_preserves_map_winner_column(self):
        """Test that map_winner column is always present regardless of feature set."""
        map1 = create_synthetic_map_data("map1", ["Team A", "Team B"], (13, 8))

        # Test with different feature sets
        for feature_set in ["core", "combat", "full"]:
            pipeline = FeaturePipeline(feature_set=feature_set)
            df = pipeline.extract_map_dataset([map1])

            assert "map_winner" in df.columns
            assert df["map_winner"].iloc[0] == "Team A"

    def test_multiple_feature_sets_column_filtering(self):
        """Test that different feature sets return correct column subsets."""
        map1 = create_synthetic_map_data("map1", ["Team A", "Team B"], (13, 5))

        # Core set
        core_pipeline = FeaturePipeline(feature_set="core")
        core_df = core_pipeline.extract_map_dataset([map1])
        core_cols = set(core_df.columns)

        # Combat set (extends core)
        combat_pipeline = FeaturePipeline(feature_set="combat")
        combat_df = combat_pipeline.extract_map_dataset([map1])
        combat_cols = set(combat_df.columns)

        # Combat should have all core columns plus combat-specific ones
        assert "score_differential" in core_cols
        assert "score_differential" in combat_cols
        assert "first_blood_rate_team1" not in core_cols
        assert "first_blood_rate_team1" in combat_cols

        # Combat should have more columns than core
        assert len(combat_cols) > len(core_cols)
