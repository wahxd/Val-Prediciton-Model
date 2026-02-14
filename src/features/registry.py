"""Feature registry for loading and resolving named feature sets.

The registry loads YAML-based feature set definitions and resolves composable
inheritance. This enables reproducible experiments by referencing feature set
names (e.g., "core", "economy") instead of hardcoded feature lists.

Example:
    >>> from src.features.registry import FeatureRegistry
    >>> registry = FeatureRegistry()
    >>> features = registry.get_feature_names("combat")
    >>> print(f"Combat set has {len(features)} features")
    >>> print(features[:5])  # First 5 features
"""

from pathlib import Path
import yaml

from src.features.config.schemas import FeatureRegistryConfig, FeatureSetDefinition


class FeatureRegistry:
    """
    Registry for loading and resolving feature sets from YAML config.

    Handles composable inheritance where sets can extend other sets,
    combining features while avoiding duplicates.
    """

    def __init__(self, config_path: Path | None = None):
        """
        Initialize registry from YAML config file.

        Args:
            config_path: Path to feature_sets.yaml. If None, uses default
                location at src/features/config/feature_sets.yaml

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If YAML is invalid or doesn't match schema
        """
        if config_path is None:
            # Default to src/features/config/feature_sets.yaml
            config_path = (
                Path(__file__).parent / "config" / "feature_sets.yaml"
            )

        if not config_path.exists():
            raise FileNotFoundError(f"Feature config not found: {config_path}")

        # Load and validate YAML
        with open(config_path, "r", encoding="utf-8") as f:
            raw_config = yaml.safe_load(f)

        # Validate with Pydantic
        self.config = FeatureRegistryConfig(**raw_config)

        # Build lookup dict for fast access
        self._sets: dict[str, FeatureSetDefinition] = {
            fs.name: fs for fs in self.config.feature_sets
        }

        # Cache for resolved feature lists (post-inheritance)
        self._resolved_cache: dict[str, list[str]] = {}

    def get_feature_names(self, set_name: str) -> list[str]:
        """
        Get ordered list of feature names for a given set.

        Resolves inheritance if the set extends another set. Features from
        parent sets are included first, then child set features. Duplicates
        are automatically removed while preserving order.

        Args:
            set_name: Name of feature set (e.g., "core", "combat", "full")

        Returns:
            Ordered list of feature names

        Raises:
            ValueError: If set_name doesn't exist

        Example:
            >>> registry = FeatureRegistry()
            >>> core_features = registry.get_feature_names("core")
            >>> combat_features = registry.get_feature_names("combat")
            >>> len(combat_features) > len(core_features)  # combat extends core
            True
        """
        # Check cache first
        if set_name in self._resolved_cache:
            return self._resolved_cache[set_name]

        # Validate set exists
        if set_name not in self._sets:
            available = ", ".join(self._sets.keys())
            raise ValueError(
                f"Unknown feature set '{set_name}'. Available sets: {available}"
            )

        # Resolve inheritance recursively
        features = self._resolve_features(set_name)

        # Cache result
        self._resolved_cache[set_name] = features

        return features

    def _resolve_features(self, set_name: str, visited: set[str] | None = None) -> list[str]:
        """
        Recursively resolve features for a set, including inherited features.

        Args:
            set_name: Name of feature set to resolve
            visited: Set of already-visited set names (for cycle detection)

        Returns:
            Ordered list of feature names with inheritance resolved

        Raises:
            ValueError: If circular inheritance detected
        """
        if visited is None:
            visited = set()

        # Detect circular inheritance
        if set_name in visited:
            raise ValueError(
                f"Circular inheritance detected in feature set '{set_name}'"
            )

        visited.add(set_name)

        feature_set = self._sets[set_name]

        # Base case: no parent
        if feature_set.extends is None:
            return feature_set.features.copy()

        # Recursive case: resolve parent first
        parent_name = feature_set.extends

        if parent_name not in self._sets:
            raise ValueError(
                f"Feature set '{set_name}' extends unknown parent '{parent_name}'"
            )

        parent_features = self._resolve_features(parent_name, visited)

        # Combine: parent features + this set's features
        # Use dict.fromkeys() to remove duplicates while preserving order
        combined = list(dict.fromkeys(parent_features + feature_set.features))

        return combined

    def list_sets(self) -> list[str]:
        """
        Get list of all available feature set names.

        Returns:
            List of feature set names in definition order

        Example:
            >>> registry = FeatureRegistry()
            >>> sets = registry.list_sets()
            >>> "core" in sets
            True
            >>> "full" in sets
            True
        """
        return [fs.name for fs in self.config.feature_sets]

    def get_set_info(self, set_name: str) -> dict[str, any]:
        """
        Get metadata and resolved features for a feature set.

        Args:
            set_name: Name of feature set

        Returns:
            Dictionary with name, description, extends, and resolved features

        Raises:
            ValueError: If set_name doesn't exist

        Example:
            >>> registry = FeatureRegistry()
            >>> info = registry.get_set_info("combat")
            >>> print(info["description"])
            Combat metrics (first blood, clutches, multi-kills) on top of core
            >>> len(info["features"])  # Includes core + combat features
            23
        """
        if set_name not in self._sets:
            available = ", ".join(self._sets.keys())
            raise ValueError(
                f"Unknown feature set '{set_name}'. Available sets: {available}"
            )

        feature_set = self._sets[set_name]
        resolved_features = self.get_feature_names(set_name)

        return {
            "name": feature_set.name,
            "description": feature_set.description,
            "extends": feature_set.extends,
            "features": resolved_features,
            "feature_count": len(resolved_features),
        }
