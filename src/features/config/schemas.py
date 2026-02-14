"""Pydantic models for feature registry configuration validation."""

from pydantic import BaseModel, Field


class FeatureSetDefinition(BaseModel):
    """
    Definition of a named feature set.

    Feature sets support composable inheritance via the 'extends' field.
    When a set extends another, it inherits all features from the parent
    and adds its own (duplicates are removed automatically).

    Attributes:
        name: Unique identifier for this feature set
        description: Human-readable description of the set's purpose
        extends: Optional parent set name to inherit features from
        features: List of feature names in this set (added on top of parent)

    Example:
        # Base set
        core:
          name: core
          description: Basic score and round features
          features:
            - final_score_team1
            - final_score_team2
            - pistol_rounds_won_team1

        # Extended set
        combat:
          name: combat
          description: Combat metrics on top of core
          extends: core
          features:
            - first_blood_rate_team1
            - clutch_rounds_team1
    """

    name: str = Field(..., description="Unique feature set identifier")
    description: str = Field(..., description="Purpose and contents of this set")
    extends: str | None = Field(
        None, description="Parent feature set name (for inheritance)"
    )
    features: list[str] = Field(
        default_factory=list, description="Feature names in this set"
    )


class FeatureRegistryConfig(BaseModel):
    """
    Root configuration for feature registry.

    Contains metadata and list of all feature set definitions.

    Attributes:
        version: Config format version (for future compatibility)
        feature_sets: List of all defined feature sets
    """

    version: str = Field(default="1.0", description="Config format version")
    feature_sets: list[FeatureSetDefinition] = Field(
        ..., description="All feature set definitions"
    )
