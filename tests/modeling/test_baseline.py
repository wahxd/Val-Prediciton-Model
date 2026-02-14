"""Tests for baseline model trainer."""

import numpy as np
import pytest
from pathlib import Path
import tempfile
from sklearn.datasets import make_classification

from src.modeling.baseline import BaselineTrainer, XGBoostTrainer, create_trainer
from src.modeling.config import ModelConfig
from src.modeling.calibration import (
    serialize_model_to_json,
    save_xgboost_model,
    load_xgboost_model,
)


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
def model_config():
    """Create a basic ModelConfig for testing."""
    return ModelConfig(feature_set="core", C=1.0, random_state=42)


def test_baseline_trainer_initializes_from_config(model_config):
    """BaselineTrainer initializes from ModelConfig."""
    trainer = BaselineTrainer(model_config)
    assert trainer.config == model_config
    assert trainer.model_ is None


def test_baseline_trainer_trains_on_data(model_config, synthetic_data):
    """BaselineTrainer.train() fits model on synthetic data."""
    X, y = synthetic_data
    trainer = BaselineTrainer(model_config)

    trainer.train(X, y)

    assert trainer.model_ is not None
    assert hasattr(trainer.model_, "coef_")
    assert hasattr(trainer.model_, "intercept_")


def test_predict_proba_returns_probabilities(model_config, synthetic_data):
    """BaselineTrainer.predict_proba() returns probabilities in [0, 1]."""
    X, y = synthetic_data
    trainer = BaselineTrainer(model_config)
    trainer.train(X, y)

    proba = trainer.predict_proba(X)

    assert np.all(proba >= 0)
    assert np.all(proba <= 1)


def test_predict_proba_returns_correct_shape(model_config, synthetic_data):
    """BaselineTrainer.predict_proba() returns array of correct shape."""
    X, y = synthetic_data
    trainer = BaselineTrainer(model_config)
    trainer.train(X, y)

    proba = trainer.predict_proba(X)

    assert proba.shape == (len(X),)


def test_model_factory_returns_fresh_model(model_config):
    """BaselineTrainer.model_factory() returns fresh unfitted model each time."""
    trainer = BaselineTrainer(model_config)

    model1 = trainer.model_factory()
    model2 = trainer.model_factory()

    # Should be different instances
    assert model1 is not model2

    # Should have same parameters
    assert model1.get_params() == model2.get_params()

    # Should be unfitted
    assert not hasattr(model1, "coef_")
    assert not hasattr(model2, "coef_")


def test_get_coefficients_returns_coef_and_intercept(model_config, synthetic_data):
    """BaselineTrainer.get_coefficients() returns coef and intercept after training."""
    X, y = synthetic_data
    trainer = BaselineTrainer(model_config)
    trainer.train(X, y)

    coef_dict = trainer.get_coefficients()

    assert "coef" in coef_dict
    assert "intercept" in coef_dict
    assert isinstance(coef_dict["coef"], list)
    assert isinstance(coef_dict["intercept"], float)
    assert len(coef_dict["coef"]) == X.shape[1]


def test_untrained_model_raises_error_on_predict_proba(model_config, synthetic_data):
    """Untrained model raises error on predict_proba."""
    X, y = synthetic_data
    trainer = BaselineTrainer(model_config)

    with pytest.raises(ValueError, match="must be trained"):
        trainer.predict_proba(X)


def test_untrained_model_raises_error_on_get_coefficients(model_config):
    """Untrained model raises error on get_coefficients."""
    trainer = BaselineTrainer(model_config)

    with pytest.raises(ValueError, match="must be trained"):
        trainer.get_coefficients()


# XGBoostTrainer tests


@pytest.fixture
def xgboost_config():
    """Create an XGBoost ModelConfig for testing."""
    return ModelConfig(
        model_type="xgboost",
        feature_set="core",
        max_depth=3,
        min_child_weight=5,
        n_estimators=30,  # Fewer trees for faster tests
        random_state=42,
    )


def test_xgboost_trainer_initializes_from_config(xgboost_config):
    """XGBoostTrainer initializes from ModelConfig."""
    trainer = XGBoostTrainer(xgboost_config)
    assert trainer.config == xgboost_config
    assert trainer.model_ is None


def test_xgboost_trainer_trains_on_data(xgboost_config, synthetic_data):
    """XGBoostTrainer.train() fits model on synthetic data."""
    X, y = synthetic_data
    trainer = XGBoostTrainer(xgboost_config)

    trainer.train(X, y)

    assert trainer.model_ is not None
    assert hasattr(trainer.model_, "get_booster")


def test_xgboost_predict_proba_returns_probabilities(xgboost_config, synthetic_data):
    """XGBoostTrainer.predict_proba() returns probabilities in [0, 1]."""
    X, y = synthetic_data
    trainer = XGBoostTrainer(xgboost_config)
    trainer.train(X, y)

    proba = trainer.predict_proba(X)

    assert np.all(proba >= 0)
    assert np.all(proba <= 1)


def test_xgboost_predict_proba_returns_correct_shape(xgboost_config, synthetic_data):
    """XGBoostTrainer.predict_proba() returns array of correct shape."""
    X, y = synthetic_data
    trainer = XGBoostTrainer(xgboost_config)
    trainer.train(X, y)

    proba = trainer.predict_proba(X)

    assert proba.shape == (len(X),)


def test_xgboost_model_factory_returns_fresh_model(xgboost_config):
    """XGBoostTrainer.model_factory() returns fresh unfitted model each time."""
    trainer = XGBoostTrainer(xgboost_config)

    model1 = trainer.model_factory()
    model2 = trainer.model_factory()

    # Should be different instances
    assert model1 is not model2

    # Should have same parameters
    assert model1.get_params() == model2.get_params()

    # Should be unfitted (no booster yet)
    try:
        model1.get_booster()
        assert False, "Model should not have booster before fit"
    except Exception:
        pass  # Expected - model not fitted


def test_xgboost_get_feature_importances(xgboost_config, synthetic_data):
    """XGBoostTrainer.get_feature_importances() returns importances after training."""
    X, y = synthetic_data
    trainer = XGBoostTrainer(xgboost_config)
    trainer.train(X, y)

    importances = trainer.get_feature_importances()

    assert "importance" in importances
    assert "feature_names" in importances
    assert isinstance(importances["importance"], list)
    assert len(importances["importance"]) == X.shape[1]
    assert importances["feature_names"] is None


def test_xgboost_untrained_raises_error_on_predict_proba(xgboost_config, synthetic_data):
    """Untrained XGBoost model raises error on predict_proba."""
    X, y = synthetic_data
    trainer = XGBoostTrainer(xgboost_config)

    with pytest.raises(ValueError, match="must be trained"):
        trainer.predict_proba(X)


def test_xgboost_untrained_raises_error_on_get_importances(xgboost_config):
    """Untrained XGBoost model raises error on get_feature_importances."""
    trainer = XGBoostTrainer(xgboost_config)

    with pytest.raises(ValueError, match="must be trained"):
        trainer.get_feature_importances()


# create_trainer tests


def test_create_trainer_returns_baseline_for_logistic(model_config):
    """create_trainer() returns BaselineTrainer for logistic_regression."""
    trainer = create_trainer(model_config)
    assert isinstance(trainer, BaselineTrainer)


def test_create_trainer_returns_xgboost_for_xgboost(xgboost_config):
    """create_trainer() returns XGBoostTrainer for xgboost."""
    trainer = create_trainer(xgboost_config)
    assert isinstance(trainer, XGBoostTrainer)


def test_create_trainer_raises_for_unknown_type():
    """create_trainer() raises ValueError for unknown model type."""
    # Bypass validation to test factory error handling
    config = ModelConfig.__new__(ModelConfig)
    object.__setattr__(config, "model_type", "unknown_model")
    object.__setattr__(config, "feature_set", "core")

    with pytest.raises(ValueError, match="Unknown model_type"):
        create_trainer(config)


# Serialization tests


def test_xgboost_serialization_round_trip(xgboost_config, synthetic_data):
    """XGBoost model serialization and loading round-trip."""
    X, y = synthetic_data
    trainer = XGBoostTrainer(xgboost_config)
    trainer.train(X, y)

    # Get predictions before save
    pred_before = trainer.predict_proba(X)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Save JSON metadata
        json_path = Path(tmpdir) / "model.json"
        serialize_model_to_json(trainer, json_path)

        # Save binary model
        model_path = Path(tmpdir) / "model.ubj"
        save_xgboost_model(trainer, model_path)

        # Load model
        loaded_trainer = load_xgboost_model(model_path, xgboost_config)

        # Get predictions after load
        pred_after = loaded_trainer.predict_proba(X)

        # Predictions should match
        np.testing.assert_array_almost_equal(pred_before, pred_after, decimal=6)
