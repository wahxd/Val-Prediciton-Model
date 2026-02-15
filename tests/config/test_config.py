"""Tests for model configuration schemas."""

import pytest
from pathlib import Path
from pydantic import ValidationError

from src.config.modeling import ModelConfig, ExperimentConfig


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

    def test_xgboost_config_defaults(self):
        """Test XGBoost config uses correct defaults."""
        config = ModelConfig(model_type="xgboost", feature_set="core")

        assert config.model_type == "xgboost"
        assert config.max_depth == 3
        assert config.min_child_weight == 5
        assert config.n_estimators == 50
        assert config.learning_rate == 0.1
        assert config.subsample == 0.8
        assert config.colsample_bytree == 0.8
        assert config.reg_alpha == 0.1
        assert config.reg_lambda == 1.0

    def test_xgboost_config_all_params(self):
        """Test XGBoost config accepts all XGBoost parameters."""
        config = ModelConfig(
            model_type="xgboost",
            feature_set="combat",
            max_depth=4,
            min_child_weight=7,
            n_estimators=80,
            learning_rate=0.15,
            subsample=0.85,
            colsample_bytree=0.9,
            reg_alpha=0.3,
            reg_lambda=1.5,
            random_state=123,
        )

        assert config.max_depth == 4
        assert config.min_child_weight == 7
        assert config.n_estimators == 80
        assert config.learning_rate == 0.15
        assert config.subsample == 0.85
        assert config.colsample_bytree == 0.9
        assert config.reg_alpha == 0.3
        assert config.reg_lambda == 1.5
        assert config.random_state == 123

    def test_xgboost_max_depth_validation(self):
        """Test max_depth range validation (2-4)."""
        # Valid values
        ModelConfig(model_type="xgboost", feature_set="core", max_depth=2)
        ModelConfig(model_type="xgboost", feature_set="core", max_depth=4)

        # Invalid: too low
        with pytest.raises(ValidationError) as exc_info:
            ModelConfig(model_type="xgboost", feature_set="core", max_depth=1)
        assert "max_depth" in str(exc_info.value)

        # Invalid: too high
        with pytest.raises(ValidationError) as exc_info:
            ModelConfig(model_type="xgboost", feature_set="core", max_depth=5)
        assert "max_depth" in str(exc_info.value)

    def test_xgboost_min_child_weight_validation(self):
        """Test min_child_weight range validation (3-10)."""
        # Valid values
        ModelConfig(model_type="xgboost", feature_set="core", min_child_weight=3)
        ModelConfig(model_type="xgboost", feature_set="core", min_child_weight=10)

        # Invalid: too low
        with pytest.raises(ValidationError) as exc_info:
            ModelConfig(model_type="xgboost", feature_set="core", min_child_weight=2)
        assert "min_child_weight" in str(exc_info.value)

        # Invalid: too high
        with pytest.raises(ValidationError) as exc_info:
            ModelConfig(model_type="xgboost", feature_set="core", min_child_weight=11)
        assert "min_child_weight" in str(exc_info.value)

    def test_xgboost_n_estimators_validation(self):
        """Test n_estimators range validation (30-100)."""
        # Valid values
        ModelConfig(model_type="xgboost", feature_set="core", n_estimators=30)
        ModelConfig(model_type="xgboost", feature_set="core", n_estimators=100)

        # Invalid: too low
        with pytest.raises(ValidationError) as exc_info:
            ModelConfig(model_type="xgboost", feature_set="core", n_estimators=29)
        assert "n_estimators" in str(exc_info.value)

        # Invalid: too high
        with pytest.raises(ValidationError) as exc_info:
            ModelConfig(model_type="xgboost", feature_set="core", n_estimators=101)
        assert "n_estimators" in str(exc_info.value)

    def test_xgboost_learning_rate_validation(self):
        """Test learning_rate range validation (0.01-0.2)."""
        # Valid values
        ModelConfig(model_type="xgboost", feature_set="core", learning_rate=0.01)
        ModelConfig(model_type="xgboost", feature_set="core", learning_rate=0.2)

        # Invalid: too low
        with pytest.raises(ValidationError) as exc_info:
            ModelConfig(model_type="xgboost", feature_set="core", learning_rate=0.005)
        assert "learning_rate" in str(exc_info.value)

        # Invalid: too high
        with pytest.raises(ValidationError) as exc_info:
            ModelConfig(model_type="xgboost", feature_set="core", learning_rate=0.25)
        assert "learning_rate" in str(exc_info.value)

    def test_penalty_l1_with_saga_solver(self):
        """Test penalty='l1' is accepted with solver='saga'."""
        config = ModelConfig(
            model_type="logistic_regression",
            feature_set="core",
            penalty="l1",
            solver="saga",
        )

        assert config.penalty == "l1"
        assert config.solver == "saga"

    def test_penalty_validation(self):
        """Test penalty validation allows l1 and l2."""
        # Valid values
        ModelConfig(feature_set="core", penalty="l1", solver="saga")
        ModelConfig(feature_set="core", penalty="l2")

        # Invalid value
        with pytest.raises(ValidationError) as exc_info:
            ModelConfig(feature_set="core", penalty="elasticnet")
        assert "penalty" in str(exc_info.value)


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
