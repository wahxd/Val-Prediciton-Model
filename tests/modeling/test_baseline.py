"""Tests for baseline model trainer."""

import numpy as np
import pytest
from sklearn.datasets import make_classification

from src.modeling.baseline import BaselineTrainer
from src.modeling.config import ModelConfig


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
