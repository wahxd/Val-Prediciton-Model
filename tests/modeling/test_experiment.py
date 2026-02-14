"""Tests for end-to-end experiment runner."""

import numpy as np
import pytest
from pathlib import Path
from sklearn.datasets import make_classification

from src.modeling.config import ModelConfig, ExperimentConfig
from src.modeling.experiment import (
    compute_naive_baselines,
    validate_calibration,
    run_experiment,
)


@pytest.fixture
def synthetic_experiment_data():
    """Create synthetic data for experiment testing."""
    # Create synthetic classification data
    X, y = make_classification(
        n_samples=80,
        n_features=5,
        n_informative=3,
        n_redundant=1,
        random_state=42,
    )

    # Create 4 synthetic groups (series_ids)
    groups = np.array([0]*20 + [1]*20 + [2]*20 + [3]*20)

    feature_names = [
        "score_diff",
        "economy_diff",
        "pistol_wins",
        "first_blood_rate",
        "streak_length",
    ]

    return {
        "X": X,
        "y": y,
        "groups": groups,
        "feature_names": feature_names,
    }


def test_compute_naive_baselines_returns_correct_structure():
    """Naive baselines returns dict with naive_prior and majority_class sub-dicts."""
    y = np.array([0, 1, 0, 1, 1, 1, 0, 0, 1, 0])
    result = compute_naive_baselines(y)

    assert "naive_prior" in result
    assert "majority_class" in result

    # Each baseline should have metrics
    for baseline_name in ["naive_prior", "majority_class"]:
        baseline = result[baseline_name]
        assert "log_loss" in baseline
        assert "brier_score" in baseline
        assert "accuracy" in baseline


def test_compute_naive_baselines_naive_prior_log_loss_is_0_693():
    """Naive prior (always 0.5) log loss is approximately 0.693 (ln(2))."""
    # Balanced dataset
    y = np.array([0, 1, 0, 1, 0, 1, 0, 1, 0, 1])
    result = compute_naive_baselines(y)

    # ln(2) ≈ 0.6931471805599453
    assert abs(result["naive_prior"]["log_loss"] - 0.693) < 0.001


def test_compute_naive_baselines_majority_class():
    """Majority class baseline uses max(mean, 1-mean) as probability."""
    # 70% class 1, 30% class 0
    y = np.array([1, 1, 1, 1, 1, 1, 1, 0, 0, 0])
    result = compute_naive_baselines(y)

    # Majority prob should be 0.7, log_loss should be lower than naive prior
    majority_log_loss = result["majority_class"]["log_loss"]
    naive_prior_log_loss = result["naive_prior"]["log_loss"]

    # Majority class should beat naive prior on imbalanced data
    assert majority_log_loss < naive_prior_log_loss


def test_validate_calibration_returns_expected_structure():
    """Calibration validation returns bins, passes, and summary fields."""
    y_true = np.array([0, 1, 0, 1, 1, 1, 0, 0, 1, 0] * 5)  # 50 samples
    y_pred = np.array([0.2, 0.8, 0.3, 0.7, 0.9, 0.6, 0.1, 0.4, 0.85, 0.15] * 5)

    result = validate_calibration(y_true, y_pred, n_bins=5, tolerance=0.15)

    assert "bins" in result
    assert "bins_within_tolerance" in result
    assert "total_bins" in result
    assert "tolerance" in result
    assert "passes" in result
    assert "max_deviation" in result


def test_validate_calibration_passes_for_well_calibrated():
    """Well-calibrated predictions pass validation."""
    # Create perfectly calibrated synthetic data
    np.random.seed(42)
    n_samples = 100

    # Generate predictions uniformly
    y_pred = np.random.uniform(0, 1, n_samples)

    # Generate labels such that P(y=1) = y_pred (perfect calibration)
    y_true = (np.random.uniform(0, 1, n_samples) < y_pred).astype(int)

    result = validate_calibration(y_true, y_pred, n_bins=5, tolerance=0.20)

    # With perfect calibration and 20% tolerance, should pass
    # (note: some randomness, but should generally pass)
    assert result["passes"] is True or result["bins_within_tolerance"] >= result["total_bins"] * 0.6


def test_validate_calibration_fails_for_poorly_calibrated():
    """Poorly calibrated predictions fail validation."""
    # All predictions at 0.1, but half are actually positive
    y_true = np.array([0, 1, 0, 1, 0, 1, 0, 1, 0, 1] * 10)  # 50% positive
    y_pred = np.full(100, 0.1)  # Predict 10% positive (poor calibration)

    result = validate_calibration(y_true, y_pred, n_bins=5, tolerance=0.10)

    # Large deviation between 0.1 predicted and ~0.5 observed
    assert result["max_deviation"] > 0.3
    # Should fail with strict 10% tolerance
    assert result["passes"] is False


def test_validate_calibration_bin_structure():
    """Each bin has predicted, observed, deviation, within_tolerance fields."""
    y_true = np.array([0, 1, 0, 1, 1, 1, 0, 0, 1, 0] * 5)
    y_pred = np.array([0.2, 0.8, 0.3, 0.7, 0.9, 0.6, 0.1, 0.4, 0.85, 0.15] * 5)

    result = validate_calibration(y_true, y_pred, n_bins=5, tolerance=0.15)

    for bin_data in result["bins"]:
        assert "predicted" in bin_data
        assert "observed" in bin_data
        assert "deviation" in bin_data
        assert "within_tolerance" in bin_data
        assert isinstance(bin_data["within_tolerance"], bool)


def test_run_experiment_completes_end_to_end(synthetic_experiment_data, tmp_path):
    """Experiment runs end-to-end on synthetic data."""
    data = synthetic_experiment_data

    config = ExperimentConfig(
        experiment_id="test_experiment",
        model=ModelConfig(feature_set="core", C=1.0),
        output_dir=tmp_path,
    )

    result = run_experiment(
        config,
        data["X"],
        data["y"],
        data["groups"],
        data["feature_names"],
    )

    # Check result structure
    assert result["experiment_id"] == "test_experiment"
    assert "cv_results" in result
    assert "naive_baselines" in result
    assert "beats_naive_prior" in result
    assert "beats_majority_class" in result
    assert "shap_analysis" in result
    assert "game_mechanics_validation" in result
    assert "calibration_validation" in result
    assert "experiment_dir" in result


def test_run_experiment_creates_expected_files(synthetic_experiment_data, tmp_path):
    """Experiment creates all expected output files."""
    data = synthetic_experiment_data

    config = ExperimentConfig(
        experiment_id="test_experiment_files",
        model=ModelConfig(feature_set="core", C=1.0),
        output_dir=tmp_path,
    )

    result = run_experiment(
        config,
        data["X"],
        data["y"],
        data["groups"],
        data["feature_names"],
    )

    exp_dir = result["experiment_dir"]

    # Check all expected files exist
    assert (exp_dir / "config.json").exists()
    assert (exp_dir / "metrics.json").exists()
    assert (exp_dir / "model.json").exists()
    assert (exp_dir / "calibration_curve.png").exists()
    assert (exp_dir / "prediction_distribution.png").exists()
    assert (exp_dir / "feature_importance.png").exists()


def test_run_experiment_result_has_beats_naive_prior_key(synthetic_experiment_data, tmp_path):
    """Experiment result includes beats_naive_prior comparison."""
    data = synthetic_experiment_data

    config = ExperimentConfig(
        experiment_id="test_beats_naive",
        model=ModelConfig(feature_set="core", C=1.0),
        output_dir=tmp_path,
    )

    result = run_experiment(
        config,
        data["X"],
        data["y"],
        data["groups"],
        data["feature_names"],
    )

    assert "beats_naive_prior" in result
    assert isinstance(result["beats_naive_prior"], bool)

    # With informative features, should beat naive baseline
    assert result["beats_naive_prior"] is True


def test_run_experiment_result_has_shap_analysis(synthetic_experiment_data, tmp_path):
    """Experiment result includes SHAP analysis."""
    data = synthetic_experiment_data

    config = ExperimentConfig(
        experiment_id="test_shap",
        model=ModelConfig(feature_set="core", C=1.0),
        output_dir=tmp_path,
    )

    result = run_experiment(
        config,
        data["X"],
        data["y"],
        data["groups"],
        data["feature_names"],
    )

    assert "shap_analysis" in result
    shap = result["shap_analysis"]

    assert "shap_values" in shap
    assert "feature_importance" in shap
    assert "feature_names" in shap
    assert "top_features" in shap


def test_run_experiment_result_has_calibration_validation(synthetic_experiment_data, tmp_path):
    """Experiment result includes calibration validation."""
    data = synthetic_experiment_data

    config = ExperimentConfig(
        experiment_id="test_calibration",
        model=ModelConfig(feature_set="core", C=1.0),
        output_dir=tmp_path,
    )

    result = run_experiment(
        config,
        data["X"],
        data["y"],
        data["groups"],
        data["feature_names"],
    )

    assert "calibration_validation" in result
    cal = result["calibration_validation"]

    assert "bins" in cal
    assert "passes" in cal
    assert "total_bins" in cal


def test_run_experiment_beats_baselines_on_informative_data(synthetic_experiment_data, tmp_path):
    """Model beats both naive baselines on informative synthetic data."""
    data = synthetic_experiment_data

    config = ExperimentConfig(
        experiment_id="test_beats_baselines",
        model=ModelConfig(feature_set="core", C=1.0),
        output_dir=tmp_path,
    )

    result = run_experiment(
        config,
        data["X"],
        data["y"],
        data["groups"],
        data["feature_names"],
    )

    # With n_informative=3, model should learn signal
    assert result["beats_naive_prior"] is True
    assert result["beats_majority_class"] is True

    # Model log loss should be meaningfully better
    model_log_loss = result["cv_results"]["overall_metrics"]["log_loss"]
    naive_log_loss = result["naive_baselines"]["naive_prior"]["log_loss"]
    assert model_log_loss < naive_log_loss * 0.95  # At least 5% improvement
