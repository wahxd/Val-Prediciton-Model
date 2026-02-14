"""Model calibration and serialization utilities.

Provides CalibratedClassifierCV wrapper for Platt scaling and JSON-based model
serialization for long-term archival (avoiding pickle fragility).
"""

import json
from datetime import datetime, UTC
from pathlib import Path

import numpy as np
import sklearn
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression

from src.modeling.baseline import BaselineTrainer
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


def serialize_model_to_json(trainer: BaselineTrainer, filepath: Path) -> None:
    """Save model coefficients and config to JSON file.

    Serializes model as coefficients + metadata rather than pickle for:
        - Long-term stability (sklearn version independence)
        - Human readability
        - Cross-platform compatibility

    Args:
        trainer: Trained BaselineTrainer instance
        filepath: Output JSON file path

    Raises:
        ValueError: If trainer model hasn't been trained yet

    JSON Structure:
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
    """
    if trainer.model_ is None:
        raise ValueError("Trainer model must be fitted before serialization")

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

    # Write to file
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


def load_model_from_json(filepath: Path) -> tuple[BaselineTrainer, dict]:
    """Load model from JSON file.

    Reconstructs LogisticRegression by setting coef_ and intercept_ directly,
    bypassing the fit() process.

    Args:
        filepath: Path to JSON file created by serialize_model_to_json()

    Returns:
        Tuple of (trainer_with_fitted_model, metadata_dict)

    Raises:
        ValueError: If JSON structure is invalid or model_type unsupported

    Notes:
        - Loaded model is ready for prediction (no fit() needed)
        - Metadata includes original sklearn version and serialization timestamp
    """
    with open(filepath, "r") as f:
        data = json.load(f)

    # Validate model type
    if data.get("model_type") != "logistic_regression":
        raise ValueError(
            f"Unsupported model_type: {data.get('model_type')}. "
            "Only 'logistic_regression' is supported."
        )

    # Reconstruct config
    config = ModelConfig(**data["config"])

    # Create trainer
    trainer = BaselineTrainer(config)

    # Reconstruct model manually
    model = LogisticRegression(
        penalty='l2',
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
