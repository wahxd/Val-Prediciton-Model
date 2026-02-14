"""Tests for model configuration schemas."""

import pytest
from pathlib import Path
from pydantic import ValidationError

from src.modeling.config import ModelConfig, ExperimentConfig


class TestModelConfig:
    """Tests for ModelConfig validation."""

    def test_valid_config_defaults(self):
        """Test creating ModelConfig with defaults."""
        config = ModelConfig(feature_set="core")

        assert config.model_type == "logistic_regression"
        assert config.feature_set == "core"
        assert config.C == 1.0
        assert config.solver == "lbfgs"
        assert config.max_iter == 1000
        assert config.random_state == 42

    def test_valid_config_all_params(self):
        """Test creating ModelConfig with all parameters specified."""
        config = ModelConfig(
            model_type="xgboost",
            feature_set="combat",
            C=10.0,
            solver="saga",
            max_iter=2000,
            random_state=123,
        )

        assert config.model_type == "xgboost"
        assert config.feature_set == "combat"
        assert config.C == 10.0
        assert config.solver == "saga"
        assert config.max_iter == 2000
        assert config.random_state == 123

    def test_invalid_model_type(self):
        """Test invalid model_type raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ModelConfig(model_type="random_forest", feature_set="core")

        assert "model_type" in str(exc_info.value)

    def test_invalid_solver(self):
        """Test invalid solver raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ModelConfig(feature_set="core", solver="adam")

        assert "solver" in str(exc_info.value)

    def test_invalid_c_negative(self):
        """Test negative C raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ModelConfig(feature_set="core", C=-1.0)

        assert "C" in str(exc_info.value)

    def test_invalid_c_zero(self):
        """Test zero C raises ValidationError (must be > 0)."""
        with pytest.raises(ValidationError) as exc_info:
            ModelConfig(feature_set="core", C=0.0)

        assert "C" in str(exc_info.value)

    def test_invalid_max_iter_too_low(self):
        """Test max_iter < 100 raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ModelConfig(feature_set="core", max_iter=50)

        assert "max_iter" in str(exc_info.value)

    def test_config_immutable(self):
        """Test config is immutable (frozen=True)."""
        config = ModelConfig(feature_set="core")

        with pytest.raises(ValidationError):
            config.C = 10.0


class TestExperimentConfig:
    """Tests for ExperimentConfig validation."""

    def test_valid_config(self):
        """Test creating valid ExperimentConfig."""
        model_config = ModelConfig(feature_set="core")
        exp_config = ExperimentConfig(
            experiment_id="baseline_001", model=model_config
        )

        assert exp_config.experiment_id == "baseline_001"
        assert exp_config.model.feature_set == "core"
        assert exp_config.calibration_method == "sigmoid"
        assert exp_config.calibration_cv == 5
        assert exp_config.cv_strategy == "leave_one_series_out"
        assert exp_config.output_dir == Path("experiments")

    def test_to_json_serialization(self):
        """Test to_json() produces serializable dict."""
        model_config = ModelConfig(feature_set="combat", C=5.0)
        exp_config = ExperimentConfig(
            experiment_id="test_001",
            model=model_config,
            calibration_method="isotonic",
            output_dir=Path("custom/path"),
        )

        json_data = exp_config.to_json()

        assert isinstance(json_data, dict)
        assert json_data["experiment_id"] == "test_001"
        assert json_data["model"]["feature_set"] == "combat"
        assert json_data["model"]["C"] == 5.0
        assert json_data["calibration_method"] == "isotonic"
        # Path should be converted to string (platform-agnostic check)
        assert isinstance(json_data["output_dir"], str)
        assert "custom" in json_data["output_dir"]
        assert "path" in json_data["output_dir"]

    def test_invalid_calibration_method(self):
        """Test invalid calibration_method raises ValidationError."""
        model_config = ModelConfig(feature_set="core")

        with pytest.raises(ValidationError) as exc_info:
            ExperimentConfig(
                experiment_id="test",
                model=model_config,
                calibration_method="platt",  # Should be "sigmoid" not "platt"
            )

        assert "calibration_method" in str(exc_info.value)

    def test_invalid_calibration_cv_too_low(self):
        """Test calibration_cv < 2 raises ValidationError."""
        model_config = ModelConfig(feature_set="core")

        with pytest.raises(ValidationError) as exc_info:
            ExperimentConfig(
                experiment_id="test", model=model_config, calibration_cv=1
            )

        assert "calibration_cv" in str(exc_info.value)

    def test_empty_experiment_id(self):
        """Test empty experiment_id raises ValidationError."""
        model_config = ModelConfig(feature_set="core")

        with pytest.raises(ValidationError) as exc_info:
            ExperimentConfig(experiment_id="", model=model_config)

        assert "experiment_id" in str(exc_info.value)

    def test_config_immutable(self):
        """Test experiment config is immutable (frozen=True)."""
        model_config = ModelConfig(feature_set="core")
        exp_config = ExperimentConfig(
            experiment_id="test", model=model_config
        )

        with pytest.raises(ValidationError):
            exp_config.calibration_method = "isotonic"
