"""Configuration schemas for model experiments.

Pydantic models for type-safe, validated, and immutable experiment configuration.
All experiments are defined via these schemas to ensure reproducibility.
"""

from pathlib import Path
from pydantic import BaseModel, Field, field_validator, ConfigDict


class ModelConfig(BaseModel):
    """Configuration for model training.

    Attributes:
        model_type: Type of model ("logistic_regression" or "xgboost")
        feature_set: Name of feature set from FeatureRegistry (e.g., "core", "combat")
        C: Inverse regularization strength for logistic regression (larger = less regularization)
        solver: Optimization solver for logistic regression
        max_iter: Maximum iterations for solver convergence
        random_state: Random seed for reproducibility
    """

    model_type: str = Field(
        default="logistic_regression",
        description="Model type: 'logistic_regression' or 'xgboost'",
    )
    feature_set: str = Field(
        ..., description="Feature set name from registry (e.g., 'core', 'combat')"
    )
    C: float = Field(
        default=1.0,
        gt=0,
        description="Inverse regularization strength (larger C = less regularization)",
    )
    solver: str = Field(
        default="lbfgs", description="Solver for logistic regression"
    )
    max_iter: int = Field(
        default=1000, ge=100, description="Maximum solver iterations"
    )
    random_state: int = Field(default=42, description="Random seed")

    model_config = ConfigDict(frozen=True)

    @field_validator("model_type")
    @classmethod
    def validate_model_type(cls, v: str) -> str:
        """Validate model type is supported."""
        allowed = {"logistic_regression", "xgboost"}
        if v not in allowed:
            raise ValueError(
                f"model_type must be one of {allowed}, got '{v}'"
            )
        return v

    @field_validator("solver")
    @classmethod
    def validate_solver(cls, v: str) -> str:
        """Validate solver is supported by sklearn LogisticRegression."""
        allowed = {"lbfgs", "newton-cg", "sag", "saga"}
        if v not in allowed:
            raise ValueError(
                f"solver must be one of {allowed}, got '{v}'"
            )
        return v


class ExperimentConfig(BaseModel):
    """Full experiment configuration.

    Attributes:
        experiment_id: Unique identifier for this experiment run
        model: Model configuration (hyperparameters, feature set)
        calibration_method: Calibration method ("sigmoid" or "isotonic")
        calibration_cv: Number of CV folds for CalibratedClassifierCV internal CV
        cv_strategy: Cross-validation strategy (currently only "leave_one_series_out")
        output_dir: Directory for experiment outputs (metrics, plots, models)
    """

    experiment_id: str = Field(
        ..., min_length=1, description="Unique experiment identifier"
    )
    model: ModelConfig = Field(..., description="Model configuration")
    calibration_method: str = Field(
        default="sigmoid", description="Calibration method (sigmoid or isotonic)"
    )
    calibration_cv: int = Field(
        default=5,
        ge=2,
        description="CV folds for internal calibration (CalibratedClassifierCV)",
    )
    cv_strategy: str = Field(
        default="leave_one_series_out",
        description="Cross-validation strategy",
    )
    output_dir: Path = Field(
        default=Path("experiments"), description="Output directory for experiments"
    )

    model_config = ConfigDict(frozen=True)

    @field_validator("calibration_method")
    @classmethod
    def validate_calibration_method(cls, v: str) -> str:
        """Validate calibration method is supported."""
        allowed = {"sigmoid", "isotonic"}
        if v not in allowed:
            raise ValueError(
                f"calibration_method must be one of {allowed}, got '{v}'"
            )
        return v

    def to_json(self) -> dict:
        """Convert to JSON-serializable dict.

        Returns:
            Dictionary suitable for JSON serialization
        """
        data = self.model_dump()
        # Convert Path to string for JSON serialization
        data["output_dir"] = str(data["output_dir"])
        return data
