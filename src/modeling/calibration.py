"""Model calibration and serialization utilities.

Provides CalibratedClassifierCV wrapper for Platt scaling and JSON-based model
serialization for long-term archival (avoiding pickle fragility).
"""

import json
from datetime import datetime, UTC
from pathlib import Path

import numpy as np
import sklearn
import xgboost
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression

from src.modeling.baseline import BaselineTrainer, XGBoostTrainer
from src.modeling.config import ModelConfig


def create_calibrated_model(
    base_model: LogisticRegression,
    method: str = "sigmoid",
    cv: int = 5,
) -> CalibratedClassifierCV:
    """Wrap a base model in CalibratedClassifierCV with Platt scaling.

    Args:
        base_model: Fitted or unfitted LogisticRegression model
        method: Calibration method ("sigmoid" for Platt scaling, "isotonic")
        cv: Number of CV folds for internal calibration CV

    Returns:
        CalibratedClassifierCV wrapper (unfitted, must call fit())

    Notes:
        - Uses ensemble=True to average predictions from internal CV folds
        - For betting applications, sigmoid (Platt scaling) is recommended
    """
    return CalibratedClassifierCV(
        estimator=base_model,
        method=method,
        cv=cv,
        ensemble=True,
    )


def serialize_model_to_json(trainer: BaselineTrainer | XGBoostTrainer, filepath: Path) -> None:
    """Save model config and metadata to JSON file.

    For LogisticRegression: Serializes coefficients + metadata (JSON-only, no binary).
    For XGBoost: Serializes config + feature importances as JSON. Use save_xgboost_model()
    for full binary model (XGBoost's native format).

    Serializes as JSON rather than pickle for:
        - Long-term stability (version independence)
        - Human readability
        - Cross-platform compatibility

    Args:
        trainer: Trained BaselineTrainer or XGBoostTrainer instance
        filepath: Output JSON file path

    Raises:
        ValueError: If trainer model hasn't been trained yet

    JSON Structure for logistic_regression:
        {
            "model_type": "logistic_regression",
            "config": {... ModelConfig as dict ...},
            "coefficients": {
                "coef": [[...float values...]],
                "intercept": [...float values...],
                "feature_names": null,
                "classes": [0, 1]
            },
            "metadata": {
                "serialized_at": "ISO timestamp",
                "sklearn_version": "x.y.z"
            }
        }

    JSON Structure for xgboost:
        {
            "model_type": "xgboost",
            "config": {... ModelConfig as dict ...},
            "feature_importances": {
                "importance": [...float values...],
                "feature_names": null
            },
            "metadata": {
                "serialized_at": "ISO timestamp",
                "xgboost_version": "x.y.z",
                "note": "Full model saved separately via save_xgboost_model()"
            }
        }
    """
    if trainer.model_ is None:
        raise ValueError("Trainer model must be fitted before serialization")

    # Handle based on trainer type
    if isinstance(trainer, BaselineTrainer):
        # Extract coefficients
        coef = trainer.model_.coef_.tolist()
        intercept = trainer.model_.intercept_.tolist()
        classes = trainer.model_.classes_.tolist()

        # Build JSON structure
        data = {
            "model_type": "logistic_regression",
            "config": trainer.config.model_dump(),
            "coefficients": {
                "coef": coef,
                "intercept": intercept,
                "feature_names": None,  # Feature names tracked at pipeline level
                "classes": classes,
            },
            "metadata": {
                "serialized_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "sklearn_version": sklearn.__version__,
            },
        }

    elif isinstance(trainer, XGBoostTrainer):
        # Extract feature importances
        importances = trainer.get_feature_importances()

        # Build JSON structure
        data = {
            "model_type": "xgboost",
            "config": trainer.config.model_dump(),
            "feature_importances": importances,
            "metadata": {
                "serialized_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "xgboost_version": xgboost.__version__,
                "note": "Full model saved separately via save_xgboost_model()",
            },
        }

    else:
        raise ValueError(f"Unsupported trainer type: {type(trainer)}")

    # Write to file
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


def save_xgboost_model(trainer: XGBoostTrainer, filepath: Path) -> None:
    """Save XGBoost model to binary file using XGBoost's native format.

    This saves the full trained model (trees, splits, weights) in XGBoost's
    portable binary format. Use alongside serialize_model_to_json() for complete
    model archival (JSON for metadata, binary for model weights).

    Args:
        trainer: Trained XGBoostTrainer instance
        filepath: Output file path (typically .ubj or .json extension)

    Raises:
        ValueError: If trainer model hasn't been trained yet

    Notes:
        - Uses XGBoost's save_model() which supports multiple formats
        - .ubj (Universal Binary JSON) is recommended for portability
        - More portable than pickle, works across XGBoost versions
    """
    if trainer.model_ is None:
        raise ValueError("Trainer model must be fitted before saving")

    filepath.parent.mkdir(parents=True, exist_ok=True)
    trainer.model_.save_model(filepath)


def load_xgboost_model(filepath: Path, config: ModelConfig) -> XGBoostTrainer:
    """Load XGBoost model from binary file.

    Args:
        filepath: Path to model file created by save_xgboost_model()
        config: ModelConfig with same parameters used during training

    Returns:
        XGBoostTrainer with loaded model ready for prediction

    Raises:
        FileNotFoundError: If filepath doesn't exist

    Notes:
        - Loaded model is ready for prediction (no fit() needed)
        - Config must match original training config (not validated)
    """
    trainer = XGBoostTrainer(config)
    trainer.model_ = trainer.model_factory()
    trainer.model_.load_model(filepath)

    return trainer


def load_model_from_json(filepath: Path) -> tuple[BaselineTrainer, dict]:
    """Load logistic regression model from JSON file.

    Reconstructs LogisticRegression by setting coef_ and intercept_ directly,
    bypassing the fit() process.

    For XGBoost models, this function raises an error directing to load_xgboost_model().

    Args:
        filepath: Path to JSON file created by serialize_model_to_json()

    Returns:
        Tuple of (trainer_with_fitted_model, metadata_dict)

    Raises:
        ValueError: If JSON structure is invalid, model_type is xgboost, or unsupported

    Notes:
        - Loaded model is ready for prediction (no fit() needed)
        - Metadata includes original sklearn version and serialization timestamp
        - For XGBoost: Use load_xgboost_model() with binary model file instead
    """
    with open(filepath, "r") as f:
        data = json.load(f)

    # Validate model type
    model_type = data.get("model_type")

    if model_type == "xgboost":
        raise ValueError(
            "XGBoost models cannot be fully loaded from JSON (only metadata). "
            "Use load_xgboost_model() to load the binary model file created by save_xgboost_model()."
        )

    if model_type != "logistic_regression":
        raise ValueError(
            f"Unsupported model_type: {model_type}. "
            "Only 'logistic_regression' is supported by load_model_from_json()."
        )

    # Reconstruct config
    config = ModelConfig(**data["config"])

    # Create trainer
    trainer = BaselineTrainer(config)

    # Reconstruct model manually
    model = LogisticRegression(
        penalty=config.penalty,
        C=config.C,
        solver=config.solver,
        max_iter=config.max_iter,
        random_state=config.random_state,
    )

    # Set coefficients and intercept directly (bypass fit)
    model.coef_ = np.array(data["coefficients"]["coef"])
    model.intercept_ = np.array(data["coefficients"]["intercept"])
    model.classes_ = np.array(data["coefficients"]["classes"])

    # Mark as fitted (sklearn checks this attribute)
    model.n_features_in_ = model.coef_.shape[1]

    # Store in trainer
    trainer.model_ = model

    return trainer, data["metadata"]
