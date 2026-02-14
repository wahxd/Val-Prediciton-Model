"""Tests for feature registry loading and inheritance resolution."""

import pytest
from pathlib import Path
import tempfile
import yaml

from src.features.registry import FeatureRegistry
from src.features.config.schemas import FeatureRegistryConfig


class TestFeatureRegistry:
    """Test feature registry loading and feature resolution."""

    def test_load_default_config(self):
        """Test loading default feature_sets.yaml successfully."""
        registry = FeatureRegistry()

        # Should load without errors
        assert registry.config.version == "1.0"
        assert len(registry.config.feature_sets) > 0

        # Should have expected core sets
        set_names = registry.list_sets()
        assert "core" in set_names
        assert "combat" in set_names
        assert "side_performance" in set_names
        assert "economy" in set_names
        assert "full" in set_names

    def test_get_core_features(self):
        """Test retrieving core feature set (no inheritance)."""
        registry = FeatureRegistry()
        core_features = registry.get_feature_names("core")

        # Core should have essential features
        assert "final_score_team1" in core_features
        assert "final_score_team2" in core_features
        assert "score_differential" in core_features
        assert "pistol_rounds_won_team1" in core_features
        assert "first_half_score_team1" in core_features
        assert "max_win_streak_team1" in core_features

        # Core should NOT have combat features
        assert "first_blood_rate_team1" not in core_features
        assert "clutch_rounds_team1" not in core_features

    def test_inheritance_resolution(self):
        """Test that combat extends core correctly."""
        registry = FeatureRegistry()

        core_features = registry.get_feature_names("core")
        combat_features = registry.get_feature_names("combat")

        # Combat should have more features than core
        assert len(combat_features) > len(core_features)

        # Combat should include all core features
        for feature in core_features:
            assert feature in combat_features

        # Combat should also have its own features
        assert "first_blood_rate_team1" in combat_features
        assert "first_blood_rate_team2" in combat_features
        assert "clutch_rounds_team1" in combat_features
        assert "multi_kill_rounds_team1" in combat_features

    def test_full_set_includes_all_features(self):
        """Test that 'full' set contains all defined features."""
        registry = FeatureRegistry()

        full_features = registry.get_feature_names("full")
        economy_features = registry.get_feature_names("economy")

        # Full should have all features (extends economy which has everything)
        # Since full extends economy with no additional features, they should be equal
        assert len(full_features) >= len(economy_features)

        # Full should include features from all categories
        # Core features
        assert "final_score_team1" in full_features
        # Combat features
        assert "first_blood_rate_team1" in full_features
        # Side performance features
        assert "attack_win_rate_team1" in full_features
        # Economy features
        assert "eco_round_win_rate_team1" in full_features
        assert "avg_economy_differential" in full_features

    def test_no_duplicate_features_after_inheritance(self):
        """Test that resolved feature lists have no duplicates."""
        registry = FeatureRegistry()

        for set_name in registry.list_sets():
            features = registry.get_feature_names(set_name)
            # Check for duplicates
            assert len(features) == len(set(features)), (
                f"Feature set '{set_name}' has duplicate features"
            )

    def test_unknown_set_raises_error(self):
        """Test that unknown set name raises ValueError."""
        registry = FeatureRegistry()

        with pytest.raises(ValueError, match="Unknown feature set"):
            registry.get_feature_names("nonexistent_set")

    def test_list_sets_returns_all_defined_sets(self):
        """Test that list_sets returns all feature sets."""
        registry = FeatureRegistry()
        sets = registry.list_sets()

        # Should have at least these core sets
        assert "core" in sets
        assert "combat" in sets
        assert "side_performance" in sets
        assert "economy" in sets
        assert "full" in sets

        # Count should match config
        assert len(sets) == len(registry.config.feature_sets)

    def test_get_set_info(self):
        """Test retrieving metadata for a feature set."""
        registry = FeatureRegistry()
        info = registry.get_set_info("combat")

        # Should have metadata
        assert info["name"] == "combat"
        assert "description" in info
        assert "Combat metrics" in info["description"]
        assert info["extends"] == "core"

        # Should have resolved features
        assert "features" in info
        assert isinstance(info["features"], list)
        assert len(info["features"]) > 0

        # Should have feature count
        assert info["feature_count"] == len(info["features"])

    def test_caching_works(self):
        """Test that resolved features are cached for performance."""
        registry = FeatureRegistry()

        # First call - should resolve and cache
        features1 = registry.get_feature_names("combat")

        # Second call - should use cache (same object)
        features2 = registry.get_feature_names("combat")

        # Should return same list object (cached)
        assert features1 is features2

    def test_custom_config_path(self):
        """Test loading from custom config path."""
        # Create a minimal custom config
        custom_config = {
            "version": "1.0",
            "feature_sets": [
                {
                    "name": "minimal",
                    "description": "Minimal test set",
                    "features": ["feature_a", "feature_b"],
                }
            ],
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            yaml.dump(custom_config, f)
            temp_path = Path(f.name)

        try:
            # Load from custom path
            registry = FeatureRegistry(config_path=temp_path)

            # Should have only the minimal set
            sets = registry.list_sets()
            assert len(sets) == 1
            assert "minimal" in sets

            features = registry.get_feature_names("minimal")
            assert features == ["feature_a", "feature_b"]

        finally:
            # Clean up temp file
            temp_path.unlink()

    def test_missing_config_raises_error(self):
        """Test that missing config file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            FeatureRegistry(config_path=Path("/nonexistent/config.yaml"))

    def test_circular_inheritance_detection(self):
        """Test detection of circular inheritance."""
        # Create config with circular inheritance
        circular_config = {
            "version": "1.0",
            "feature_sets": [
                {
                    "name": "set_a",
                    "description": "Set A",
                    "extends": "set_b",
                    "features": ["feature_a"],
                },
                {
                    "name": "set_b",
                    "description": "Set B",
                    "extends": "set_a",  # Circular!
                    "features": ["feature_b"],
                },
            ],
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            yaml.dump(circular_config, f)
            temp_path = Path(f.name)

        try:
            registry = FeatureRegistry(config_path=temp_path)

            # Should detect circular inheritance when resolving
            with pytest.raises(ValueError, match="Circular inheritance"):
                registry.get_feature_names("set_a")

        finally:
            temp_path.unlink()

    def test_unknown_parent_raises_error(self):
        """Test that extending unknown parent raises ValueError."""
        invalid_config = {
            "version": "1.0",
            "feature_sets": [
                {
                    "name": "child",
                    "description": "Child set",
                    "extends": "nonexistent_parent",
                    "features": ["feature_x"],
                }
            ],
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            yaml.dump(invalid_config, f)
            temp_path = Path(f.name)

        try:
            registry = FeatureRegistry(config_path=temp_path)

            # Should fail when resolving due to unknown parent
            with pytest.raises(ValueError, match="extends unknown parent"):
                registry.get_feature_names("child")

        finally:
            temp_path.unlink()


class TestFeatureSetOrdering:
    """Test that feature ordering is preserved correctly."""

    def test_parent_features_come_first(self):
        """Test that parent features appear before child features in resolved list."""
        registry = FeatureRegistry()

        core_features = registry.get_feature_names("core")
        combat_features = registry.get_feature_names("combat")

        # First N features of combat should match core (where N = len(core))
        # This assumes no duplicates and that parent comes first
        core_len = len(core_features)
        combat_core_prefix = combat_features[:core_len]

        # All core features should be in the combat prefix (but order might vary)
        for feature in core_features:
            assert feature in combat_features[:core_len], (
                f"Core feature '{feature}' not in first {core_len} combat features"
            )

    def test_feature_order_deterministic(self):
        """Test that feature order is deterministic across multiple calls."""
        registry = FeatureRegistry()

        # Get features multiple times
        features1 = registry.get_feature_names("full")
        registry._resolved_cache.clear()  # Clear cache
        features2 = registry.get_feature_names("full")

        # Order should be identical
        assert features1 == features2
