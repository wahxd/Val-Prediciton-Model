"""Tests for model calibration and serialization."""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest
from sklearn.datasets import make_classification
from sklearn.calibration import CalibratedClassifierCV

from src.modeling.baseline import BaselineTrainer
from src.modeling.calibration import (
    create_calibrated_model,
    serialize_model_to_json,
    load_model_from_json,
)
from src.config.modeling import ModelConfig


@pytest.fixture
def synthetic_data():
    """Generate synthetic classification data for testing."""
    X, y = make_classification(
        n_samples=100,
        n_features=5,
        n_informative=3,
        n_redundant=1,
        n_repeated=0,
        n_classes=2,
        random_state=42,
    )
    return X, y


@pytest.fixture
def trained_trainer(synthetic_data):
    """Create and train a BaselineTrainer."""
    X, y = synthetic_data
    config = ModelConfig(feature_set="core", C=1.0, random_state=42)
    trainer = BaselineTrainer(config)
    trainer.train(X, y)
    return trainer


def test_create_calibrated_model_wraps_in_calibratedclassifiercv(trained_trainer):
    """create_calibrated_model wraps model in CalibratedClassifierCV."""
    calibrated = create_calibrated_model(
        trained_trainer.model_, method="sigmoid", cv=5
    )

    assert isinstance(calibrated, CalibratedClassifierCV)
    assert calibrated.method == "sigmoid"
    assert calibrated.cv == 5
    assert calibrated.ensemble is True


def test_calibrated_model_produces_probabilities(trained_trainer, synthetic_data):
    """Calibrated model produces probabilities in [0, 1]."""
    X, y = synthetic_data
    calibrated = create_calibrated_model(
        trained_trainer.model_, method="sigmoid", cv=5
    )
    calibrated.fit(X, y)

    proba = calibrated.predict_proba(X)[:, 1]

    assert np.all(proba >= 0)
    assert np.all(proba <= 1)


def test_serialize_model_to_json_creates_valid_file(trained_trainer):
    """serialize_model_to_json creates valid JSON file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "model.json"

        serialize_model_to_json(trained_trainer, filepath)

        assert filepath.exists()
        with open(filepath, "r") as f:
            data = json.load(f)
            assert isinstance(data, dict)


def test_serialize_model_contains_expected_keys(trained_trainer):
    """JSON file contains expected keys (model_type, config, coefficients, metadata)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "model.json"

        serialize_model_to_json(trained_trainer, filepath)

        with open(filepath, "r") as f:
            data = json.load(f)

        # Top-level keys
        assert "model_type" in data
        assert "config" in data
        assert "coefficients" in data
        assert "metadata" in data

        # model_type
        assert data["model_type"] == "logistic_regression"

        # coefficients structure
        assert "coef" in data["coefficients"]
        assert "intercept" in data["coefficients"]
        assert "feature_names" in data["coefficients"]
        assert "classes" in data["coefficients"]

        # metadata structure
        assert "serialized_at" in data["metadata"]
        assert "sklearn_version" in data["metadata"]


def test_load_model_from_json_reconstructs_model(trained_trainer):
    """load_model_from_json reconstructs model."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "model.json"

        serialize_model_to_json(trained_trainer, filepath)
        loaded_trainer, metadata = load_model_from_json(filepath)

        assert isinstance(loaded_trainer, BaselineTrainer)
        assert loaded_trainer.model_ is not None
        assert isinstance(metadata, dict)
        assert "serialized_at" in metadata
        assert "sklearn_version" in metadata


def test_round_trip_serialization_preserves_predictions(trained_trainer, synthetic_data):
    """Round-trip serialization: train → serialize → load → predict produces same results."""
    X, y = synthetic_data

    # Original predictions
    original_proba = trained_trainer.predict_proba(X)

    # Serialize and load
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "model.json"

        serialize_model_to_json(trained_trainer, filepath)
        loaded_trainer, _ = load_model_from_json(filepath)

        loaded_proba = loaded_trainer.predict_proba(X)

    # Predictions should match (within float tolerance)
    assert np.allclose(original_proba, loaded_proba)


def test_loaded_model_predictions_match_original(trained_trainer, synthetic_data):
    """Loaded model predictions match original predictions (np.allclose)."""
    X, y = synthetic_data

    original_proba = trained_trainer.predict_proba(X)

    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "model.json"

        serialize_model_to_json(trained_trainer, filepath)
        loaded_trainer, _ = load_model_from_json(filepath)

        loaded_proba = loaded_trainer.predict_proba(X)

    # Exact match (within float precision)
    assert np.allclose(original_proba, loaded_proba, rtol=1e-10, atol=1e-12)


def test_serialize_untrained_model_raises_error():
    """Serializing untrained model raises error."""
    config = ModelConfig(feature_set="core", C=1.0, random_state=42)
    trainer = BaselineTrainer(config)

    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "model.json"

        with pytest.raises(ValueError, match="must be fitted"):
            serialize_model_to_json(trainer, filepath)


def test_load_invalid_model_type_raises_error():
    """Loading JSON with invalid model_type raises error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "invalid.json"

        # Write invalid JSON
        with open(filepath, "w") as f:
            json.dump({"model_type": "xgboost", "config": {}, "coefficients": {}, "metadata": {}}, f)

        with pytest.raises(ValueError, match="Unsupported model_type"):
            load_model_from_json(filepath)
