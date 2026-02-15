"""Tests for hyperparameter tuning functions."""

import numpy as np
import pytest
from sklearn.datasets import make_classification

from src.config.modeling import ModelConfig
from src.modeling.tuning import (
    tune_xgboost_optuna,
    tune_logistic_gridsearch,
    temporal_holdout_sanity_check,
    compare_models,
)


@pytest.fixture
def synthetic_tuning_data():
    """Create synthetic data for tuning tests."""
    # Small dataset for fast testing
    X, y = make_classification(
        n_samples=30,
        n_features=5,
        n_informative=3,
        n_redundant=1,
        random_state=42,
    )

    # Create 3 synthetic groups
    groups = np.array([0]*10 + [1]*10 + [2]*10)

    return {"X": X, "y": y, "groups": groups}


def test_tune_xgboost_optuna_returns_valid_structure(synthetic_tuning_data):
    """Optuna tuning returns best_params, best_log_loss, n_trials, study_summary."""
    data = synthetic_tuning_data

    result = tune_xgboost_optuna(
        data["X"],
        data["y"],
        data["groups"],
        n_trials=5,  # Small for speed
        random_state=42,
    )

    # Check structure
    assert "best_params" in result
    assert "best_log_loss" in result
    assert "n_trials" in result
    assert "study_summary" in result

    # Check best_params has required keys
    assert "n_estimators" in result["best_params"]
    assert "max_depth" in result["best_params"]
    assert "min_child_weight" in result["best_params"]
    assert "learning_rate" in result["best_params"]

    # Check types
    assert isinstance(result["best_log_loss"], float)
    assert isinstance(result["n_trials"], int)
    assert result["n_trials"] <= 5  # May be less due to pruning


def test_tune_xgboost_optuna_params_within_constraints(synthetic_tuning_data):
    """Optuna suggests params within conservative constraints."""
    data = synthetic_tuning_data

    result = tune_xgboost_optuna(
        data["X"],
        data["y"],
        data["groups"],
        n_trials=5,
        random_state=42,
    )

    params = result["best_params"]

    # Check constraints
    assert 30 <= params["n_estimators"] <= 100
    assert 2 <= params["max_depth"] <= 4
    assert 3 <= params["min_child_weight"] <= 10
    assert 0.01 <= params["learning_rate"] <= 0.2
    assert 0.7 <= params["subsample"] <= 0.95
    assert 0.7 <= params["colsample_bytree"] <= 0.95


def test_tune_xgboost_optuna_study_summary_has_stats(synthetic_tuning_data):
    """Study summary contains best, worst, mean, std."""
    data = synthetic_tuning_data

    result = tune_xgboost_optuna(
        data["X"],
        data["y"],
        data["groups"],
        n_trials=5,
        random_state=42,
    )

    summary = result["study_summary"]

    assert "best" in summary
    assert "worst" in summary
    assert "mean" in summary
    assert "std" in summary

    # Best should be same as best_log_loss
    assert abs(summary["best"] - result["best_log_loss"]) < 1e-6


def test_tune_logistic_gridsearch_returns_valid_structure(synthetic_tuning_data):
    """GridSearchCV tuning returns best_params, best_log_loss, all_results, n_configs."""
    data = synthetic_tuning_data

    result = tune_logistic_gridsearch(
        data["X"],
        data["y"],
        data["groups"],
    )

    # Check structure
    assert "best_params" in result
    assert "best_log_loss" in result
    assert "all_results" in result
    assert "n_configs" in result

    # Check best_params
    assert "C" in result["best_params"]
    assert "penalty" in result["best_params"]
    assert "solver" in result["best_params"]

    # Check types
    assert isinstance(result["best_log_loss"], float)
    assert isinstance(result["n_configs"], int)
    assert result["n_configs"] == 8  # 4 C values × 2 penalties


def test_tune_logistic_gridsearch_all_results_has_expected_configs(synthetic_tuning_data):
    """GridSearchCV evaluates all expected configs."""
    data = synthetic_tuning_data

    result = tune_logistic_gridsearch(
        data["X"],
        data["y"],
        data["groups"],
    )

    all_results = result["all_results"]

    # Should have 8 configs (4 C × 2 penalty)
    assert len(all_results) == 8

    # Each config has params, mean_log_loss, std_log_loss
    for config in all_results:
        assert "params" in config
        assert "mean_log_loss" in config
        assert "std_log_loss" in config


def test_temporal_holdout_sanity_check_returns_valid_structure(synthetic_tuning_data):
    """Temporal holdout validation returns expected fields."""
    data = synthetic_tuning_data

    # Create tuned and default configs
    tuned_config = ModelConfig(
        model_type="logistic_regression",
        feature_set="test",
        C=10.0,
        penalty="l1",
        solver="saga",
    )

    default_config = ModelConfig(
        model_type="logistic_regression",
        feature_set="test",
        C=1.0,
        penalty="l2",
    )

    result = temporal_holdout_sanity_check(
        data["X"],
        data["y"],
        tuned_config,
        default_config,
    )

    # Check structure
    assert "tuned_log_loss" in result
    assert "default_log_loss" in result
    assert "improvement" in result
    assert "survives_holdout" in result
    assert "recommendation" in result

    # Check types
    assert isinstance(result["tuned_log_loss"], float)
    assert isinstance(result["default_log_loss"], float)
    assert isinstance(result["survives_holdout"], bool)
    assert result["recommendation"] in ["use_tuned", "use_defaults"]


def test_temporal_holdout_sanity_check_improvement_calculation(synthetic_tuning_data):
    """Improvement is tuned - default (negative = tuned better)."""
    data = synthetic_tuning_data

    tuned_config = ModelConfig(
        model_type="logistic_regression",
        feature_set="test",
        C=10.0,
    )

    default_config = ModelConfig(
        model_type="logistic_regression",
        feature_set="test",
        C=1.0,
    )

    result = temporal_holdout_sanity_check(
        data["X"],
        data["y"],
        tuned_config,
        default_config,
    )

    # Improvement should match difference
    expected_improvement = result["tuned_log_loss"] - result["default_log_loss"]
    assert abs(result["improvement"] - expected_improvement) < 1e-6

    # survives_holdout should match (tuned < default)
    expected_survives = result["tuned_log_loss"] < result["default_log_loss"]
    assert result["survives_holdout"] == expected_survives


def test_compare_models_returns_valid_structure():
    """Model comparison returns expected fields."""
    # Mock CV results
    xgb_cv = {
        "aggregate_metrics": {
            "log_loss_mean": 0.60,
            "log_loss_std": 0.05,
        },
        "overall_metrics": {
            "brier_score": 0.20,
        },
        "n_folds": 5,
    }

    lr_cv = {
        "aggregate_metrics": {
            "log_loss_mean": 0.65,
            "log_loss_std": 0.04,
        },
        "overall_metrics": {
            "brier_score": 0.22,
        },
        "n_folds": 5,
    }

    result = compare_models(xgb_cv, lr_cv)

    # Check structure
    assert "xgb_log_loss" in result
    assert "lr_log_loss" in result
    assert "difference" in result
    assert "se_difference" in result
    assert "significant_improvement" in result
    assert "calibration_comparison" in result
    assert "recommendation" in result
    assert "skepticism_note" in result


def test_compare_models_significant_improvement_logic():
    """Significant improvement requires difference > 1 SE."""
    # Case 1: XGBoost significantly better (difference > 1 SE)
    xgb_cv = {
        "aggregate_metrics": {
            "log_loss_mean": 0.55,
            "log_loss_std": 0.05,
        },
        "overall_metrics": {
            "brier_score": 0.20,
        },
        "n_folds": 5,
    }

    lr_cv = {
        "aggregate_metrics": {
            "log_loss_mean": 0.65,
            "log_loss_std": 0.04,
        },
        "overall_metrics": {
            "brier_score": 0.22,
        },
        "n_folds": 5,
    }

    result = compare_models(xgb_cv, lr_cv)

    # Difference should be negative (XGBoost better)
    assert result["difference"] < 0

    # SE calculation: SE = std / sqrt(n_folds)
    se_xgb = 0.05 / np.sqrt(5)
    se_lr = 0.04 / np.sqrt(5)
    expected_se = np.sqrt(se_xgb**2 + se_lr**2)
    assert abs(result["se_difference"] - expected_se) < 1e-6

    # With large difference (0.10), should be significant
    assert result["significant_improvement"] is True
    assert result["recommendation"] == "xgboost"


def test_compare_models_no_clear_winner_when_within_noise():
    """No clear winner when difference within 1 SE."""
    # XGBoost barely better, within noise
    xgb_cv = {
        "aggregate_metrics": {
            "log_loss_mean": 0.649,
            "log_loss_std": 0.05,
        },
        "overall_metrics": {
            "brier_score": 0.21,
        },
        "n_folds": 5,
    }

    lr_cv = {
        "aggregate_metrics": {
            "log_loss_mean": 0.650,
            "log_loss_std": 0.05,
        },
        "overall_metrics": {
            "brier_score": 0.21,
        },
        "n_folds": 5,
    }

    result = compare_models(xgb_cv, lr_cv)

    # Difference tiny
    assert abs(result["difference"]) < 0.01

    # Not significant
    assert result["significant_improvement"] is False
    assert result["recommendation"] == "no_clear_winner"


def test_compare_models_calibration_comparison():
    """Calibration comparison uses Brier score."""
    # XGBoost better log loss AND calibration
    xgb_cv = {
        "aggregate_metrics": {
            "log_loss_mean": 0.55,
            "log_loss_std": 0.05,
        },
        "overall_metrics": {
            "brier_score": 0.18,  # Better calibration
        },
        "n_folds": 5,
    }

    lr_cv = {
        "aggregate_metrics": {
            "log_loss_mean": 0.65,
            "log_loss_std": 0.04,
        },
        "overall_metrics": {
            "brier_score": 0.22,  # Worse calibration
        },
        "n_folds": 5,
    }

    result = compare_models(xgb_cv, lr_cv)

    assert result["calibration_comparison"] == "xgboost_better"
    assert result["recommendation"] == "xgboost"
