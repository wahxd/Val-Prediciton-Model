"""Feature configuration module.

This module contains YAML-based feature set definitions and Pydantic schemas
for validation. Feature sets enable reproducible experiments by naming groups
of features (e.g., "core", "economy_extended") so model training can reference
set names instead of hardcoded feature lists.
"""

from src.features.config.schemas import FeatureSetDefinition, FeatureRegistryConfig

__all__ = ["FeatureSetDefinition", "FeatureRegistryConfig"]
