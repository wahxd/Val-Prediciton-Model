"""End-to-end feature extraction pipeline.

This module provides the main entry point for converting raw Valoscribe data
into model-ready feature DataFrames. It orchestrates all feature extraction
components and respects the feature registry for reproducible experiments.

Pipeline responsibilities:
- Load map data from Valoscribe files
- Extract features using registered extractors
- Filter columns to requested feature set
- Convert to pandas DataFrame for modeling
- Handle errors gracefully (skip bad maps, log warnings)

Example:
    >>> from src.features.pipeline import FeaturePipeline
    >>> from src.data.loader import load_all_maps
    >>>
    >>> # Load map data
    >>> results = load_all_maps(Path("D:/Git/valoscribe/data/processed"))
    >>> map_data_list = [r.data for r in results.values() if r.success]
    >>>
    >>> # Extract features
    >>> pipeline = FeaturePipeline(feature_set="combat")
    >>> df = pipeline.extract_map_dataset(map_data_list)
    >>> print(df.columns)  # Only combat features + map_id + map_winner
"""

from pathlib import Path
from typing import Any
import structlog
import pandas as pd

from src.data.loader import MapData
from src.features.registry import FeatureRegistry
from src.features.extractors.map_features import extract_map_features
from src.features.extractors.match_features import extract_match_features

logger = structlog.get_logger()


class FeaturePipeline:
    """
    End-to-end feature extraction from Valoscribe data to model-ready DataFrame.

    Extracts features from map data, filters to requested feature set, and
    produces pandas DataFrames ready for model training/inference.
    """

    def __init__(self, feature_set: str = "core", registry: FeatureRegistry | None = None):
        """
        Initialize feature extraction pipeline.

        Args:
            feature_set: Name of feature set to extract (from registry)
            registry: Optional FeatureRegistry instance (default: load from config)

        Raises:
            ValueError: If feature_set doesn't exist in registry
        """
        self.feature_set = feature_set
        self.registry = registry or FeatureRegistry()

        # Validate feature set exists and get feature list
        try:
            self.feature_names = self.registry.get_feature_names(feature_set)
        except ValueError as e:
            available_sets = ", ".join(self.registry.list_sets())
            raise ValueError(
                f"Invalid feature set '{feature_set}'. "
                f"Available sets: {available_sets}"
            ) from e

        logger.info(
            "pipeline_initialized",
            feature_set=feature_set,
            feature_count=len(self.feature_names),
        )

    def extract_map_dataset(
        self,
        map_data_list: list[MapData],
    ) -> pd.DataFrame:
        """
        Extract features from multiple maps into a DataFrame.

        Each row is one map (from team1's perspective), columns are features
        from the requested feature set plus metadata columns (map_id, map_winner).

        Args:
            map_data_list: List of MapData objects to extract features from

        Returns:
            DataFrame with columns: map_id, [feature columns], map_winner
            Empty DataFrame if all maps fail extraction

        Example:
            >>> pipeline = FeaturePipeline(feature_set="core")
            >>> df = pipeline.extract_map_dataset(map_data_list)
            >>> assert "map_id" in df.columns
            >>> assert "map_winner" in df.columns
            >>> assert "score_differential" in df.columns
        """
        if not map_data_list:
            logger.warning("extract_map_dataset_empty_input")
            return pd.DataFrame()

        feature_dicts = []
        skipped_maps = []

        for map_data in map_data_list:
            try:
                # Extract map-level features
                features = extract_map_features(
                    events=map_data.events,
                    map_id=map_data.map_id,
                    teams=map_data.metadata.teams if map_data.metadata else ["team1", "team2"],
                )

                # Add map_id as metadata
                features["map_id"] = map_data.map_id

                feature_dicts.append(features)

            except Exception as e:
                # Log warning and skip this map
                logger.warning(
                    "map_feature_extraction_failed",
                    map_id=map_data.map_id,
                    error=str(e),
                )
                skipped_maps.append(map_data.map_id)

        if not feature_dicts:
            logger.error(
                "extract_map_dataset_all_failed",
                total_maps=len(map_data_list),
                skipped=len(skipped_maps),
            )
            return pd.DataFrame()

        # Convert to DataFrame
        df = pd.DataFrame(feature_dicts)

        # Filter to requested feature set + metadata columns
        metadata_columns = ["map_id", "map_winner"]
        selected_columns = metadata_columns + [
            col for col in self.feature_names if col in df.columns
        ]

        # Check for missing features
        missing_features = set(self.feature_names) - set(df.columns)
        if missing_features:
            logger.warning(
                "missing_features",
                feature_set=self.feature_set,
                missing=list(missing_features),
            )

        # Select columns (missing features will be absent, that's OK)
        available_columns = [col for col in selected_columns if col in df.columns]
        df = df[available_columns]

        logger.info(
            "extract_map_dataset_complete",
            total_maps=len(map_data_list),
            successful=len(feature_dicts),
            skipped=len(skipped_maps),
            rows=len(df),
            columns=len(df.columns),
        )

        if skipped_maps:
            logger.debug("skipped_maps", map_ids=skipped_maps)

        return df

    def extract_match_dataset(
        self,
        series_maps: dict[str, list[MapData]],
        series_formats: dict[str, str] | None = None,
    ) -> pd.DataFrame:
        """
        Extract features for match/series prediction.

        Each row is one map within a series, includes both map-level and
        match-level features (series momentum, aggregate stats, etc.).

        Args:
            series_maps: Dict mapping series_id -> list of MapData (in order)
            series_formats: Optional dict mapping series_id -> format ("bo3"/"bo5")
                Defaults to "bo3" for all series

        Returns:
            DataFrame with columns: series_id, map_index, map_id, [features], map_winner
            Empty DataFrame if all series fail extraction

        Example:
            >>> series_maps = {
            ...     "series_1": [map1_data, map2_data, map3_data],
            ...     "series_2": [map4_data, map5_data],
            ... }
            >>> pipeline = FeaturePipeline(feature_set="full")
            >>> df = pipeline.extract_match_dataset(series_maps)
            >>> assert "series_momentum" in df.columns
        """
        if not series_maps:
            logger.warning("extract_match_dataset_empty_input")
            return pd.DataFrame()

        if series_formats is None:
            series_formats = {}

        all_rows = []
        skipped_series = []

        for series_id, maps_list in series_maps.items():
            if not maps_list:
                logger.warning("empty_series", series_id=series_id)
                skipped_series.append(series_id)
                continue

            try:
                # Extract map features for each map in series
                map_feature_dicts = []
                for i, map_data in enumerate(maps_list):
                    try:
                        features = extract_map_features(
                            events=map_data.events,
                            map_id=map_data.map_id,
                            teams=map_data.metadata.teams if map_data.metadata else ["team1", "team2"],
                        )
                        features["map_id"] = map_data.map_id
                        features["map_index"] = i  # Position in series (0, 1, 2, ...)
                        map_feature_dicts.append(features)

                    except Exception as e:
                        logger.warning(
                            "map_extraction_failed_in_series",
                            series_id=series_id,
                            map_id=map_data.map_id,
                            error=str(e),
                        )
                        # Skip this map but continue with series

                if not map_feature_dicts:
                    logger.warning("no_valid_maps_in_series", series_id=series_id)
                    skipped_series.append(series_id)
                    continue

                # Extract match-level features for each completed map prefix
                # (e.g., after map 1, after map 2, after map 3)
                series_format = series_formats.get(series_id, "bo3")

                for i in range(len(map_feature_dicts)):
                    # Features for predicting outcome of map i+1 (or series after map i)
                    # Use maps 0..i as context
                    completed_maps = map_feature_dicts[:i+1]

                    # Extract match features from completed maps so far
                    match_features = extract_match_features(
                        map_features_list=completed_maps,
                        series_format=series_format,
                    )

                    # Combine map-level and match-level features
                    row = {
                        "series_id": series_id,
                        **map_feature_dicts[i],  # Map-level features for this map
                        **match_features,  # Match-level features from series context
                    }

                    all_rows.append(row)

            except Exception as e:
                logger.warning(
                    "series_extraction_failed",
                    series_id=series_id,
                    error=str(e),
                )
                skipped_series.append(series_id)

        if not all_rows:
            logger.error(
                "extract_match_dataset_all_failed",
                total_series=len(series_maps),
                skipped=len(skipped_series),
            )
            return pd.DataFrame()

        # Convert to DataFrame
        df = pd.DataFrame(all_rows)

        # Filter to requested feature set + metadata columns
        # Match dataset includes both map-level and match-level features
        metadata_columns = ["series_id", "map_index", "map_id", "map_winner"]

        # Get all feature names (both map-level and match-level)
        # For now, include all columns that aren't metadata
        # In future, we could have separate feature sets for match-level features
        selected_columns = metadata_columns + [
            col for col in df.columns
            if col not in metadata_columns
        ]

        df = df[selected_columns]

        logger.info(
            "extract_match_dataset_complete",
            total_series=len(series_maps),
            successful=len(series_maps) - len(skipped_series),
            skipped=len(skipped_series),
            rows=len(df),
            columns=len(df.columns),
        )

        if skipped_series:
            logger.debug("skipped_series", series_ids=skipped_series)

        return df
