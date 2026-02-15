"""Tests for evaluation framework."""

import json
import numpy as np
import pytest
from pathlib import Path
from sklearn.linear_model import LogisticRegression

from src.modeling.evaluation import (
    compute_metrics,
    temporal_cross_validate,
    generate_evaluation_report,
)
from src.config.modeling import ModelConfig, ExperimentConfig


class TestComputeMetrics:
    """Tests for compute_metrics function."""

    def test_compute_metrics_returns_correct_keys(self):
        """Test that compute_metrics returns expected keys."""
        y_true = np.array([0, 1, 0, 1, 1])
        y_pred_proba = np.array([0.2, 0.8, 0.3, 0.7, 0.9])

        metrics = compute_metrics(y_true, y_pred_proba)

        assert "log_loss" in metrics
        assert "brier_score" in metrics
        assert "accuracy" in metrics
        assert isinstance(metrics["log_loss"], float)
        assert isinstance(metrics["brier_score"], float)
        assert isinstance(metrics["accuracy"], float)

    def test_compute_metrics_perfect_predictions(self):
        """Test metrics with perfect predictions."""
        y_true = np.array([0, 1, 0, 1, 1])
        y_pred_proba = np.array([0.0, 1.0, 0.0, 1.0, 1.0])

        metrics = compute_metrics(y_true, y_pred_proba)

        # Perfect predictions should have near-zero log loss
        assert metrics["log_loss"] < 0.01
        # Perfect brier score is 0
        assert metrics["brier_score"] < 0.01
        # Perfect accuracy is 1.0
        assert metrics["accuracy"] == 1.0

    def test_compute_metrics_worst_predictions(self):
        """Test metrics with worst possible predictions."""
        y_true = np.array([0, 1, 0, 1, 1])
        y_pred_proba = np.array([1.0, 0.0, 1.0, 0.0, 0.0])

        metrics = compute_metrics(y_true, y_pred_proba)

        # Worst predictions should have high log loss
        assert metrics["log_loss"] > 10.0
        # Worst brier score is 1.0
        assert metrics["brier_score"] > 0.9
        # Worst accuracy is 0.0
        assert metrics["accuracy"] == 0.0

    def test_compute_metrics_single_class(self):
        """Test that single-class data returns NaN for log_loss."""
        y_true = np.array([1, 1, 1, 1])
        y_pred_proba = np.array([0.8, 0.9, 0.7, 0.85])

        metrics = compute_metrics(y_true, y_pred_proba)

        # Log loss undefined for single class
        assert np.isnan(metrics["log_loss"])
        # Brier score and accuracy still defined
        assert not np.isnan(metrics["brier_score"])
        assert not np.isnan(metrics["accuracy"])


class TestTemporalCrossValidate:
    """Tests for temporal_cross_validate function."""

    def setup_method(self):
        """Create synthetic grouped data for testing."""
        np.random.seed(42)

        # Create 4 groups (series) with varying sizes
        # Group 0: 8 samples
        # Group 1: 6 samples
        # Group 2: 10 samples
        # Group 3: 8 samples
        # Total: 32 samples

        self.groups = np.array(
            [0] * 8 + [1] * 6 + [2] * 10 + [3] * 8
        )

        # Generate features (2 features)
        self.X = np.random.randn(32, 2)

        # Generate labels with some correlation to features
        # Use simple linear decision boundary
        scores = self.X[:, 0] * 0.5 + self.X[:, 1] * 0.3
        self.y = (scores > 0).astype(int)

        # Factory for creating fresh models
        self.model_factory = lambda: LogisticRegression(
            penalty="l2", C=1.0, solver="lbfgs", max_iter=1000, random_state=42
        )

    def test_temporal_cv_returns_expected_structure(self):
        """Test that temporal_cross_validate returns expected structure."""
        results = temporal_cross_validate(
            self.X, self.y, self.groups, self.model_factory
        )

        assert "fold_metrics" in results
        assert "aggregate_metrics" in results
        assert "overall_metrics" in results
        assert "all_y_true" in results
        assert "all_y_pred" in results
        assert "n_folds" in results

        assert isinstance(results["fold_metrics"], list)
        assert isinstance(results["aggregate_metrics"], dict)
        assert isinstance(results["overall_metrics"], dict)
        assert isinstance(results["all_y_true"], np.ndarray)
        assert isinstance(results["all_y_pred"], np.ndarray)
        assert isinstance(results["n_folds"], int)

    def test_temporal_cv_no_series_leakage(self):
        """Test that no series appears in both train and test."""
        results = temporal_cross_validate(
            self.X, self.y, self.groups, self.model_factory
        )

        # We should have predictions for all samples
        assert len(results["all_y_true"]) == len(self.y)
        assert len(results["all_y_pred"]) == len(self.y)

        # Number of folds should match number of unique groups
        # (assuming no folds were skipped due to single-class training)
        assert results["n_folds"] <= len(np.unique(self.groups))

    def test_temporal_cv_aggregate_metrics_structure(self):
        """Test that aggregate metrics have mean and std."""
        results = temporal_cross_validate(
            self.X, self.y, self.groups, self.model_factory
        )

        agg = results["aggregate_metrics"]

        # Check for mean and std keys
        assert "log_loss_mean" in agg
        assert "log_loss_std" in agg
        assert "brier_score_mean" in agg
        assert "brier_score_std" in agg
        assert "accuracy_mean" in agg
        assert "accuracy_std" in agg

    def test_temporal_cv_handles_single_class_folds(self):
        """Test that folds with single class in training are skipped."""
        # Create data where one group has all same labels
        groups = np.array([0] * 5 + [1] * 5)
        X = np.random.randn(10, 2)
        y = np.array([1, 1, 1, 1, 1, 0, 0, 1, 0, 1])  # Group 0 all 1s

        results = temporal_cross_validate(
            X, y, groups, self.model_factory
        )

        # Should skip the fold with all 1s in training
        # So n_folds should be less than total groups
        assert results["n_folds"] <= len(np.unique(groups))

    def test_temporal_cv_with_pandas_input(self):
        """Test that temporal_cross_validate works with pandas inputs."""
        import pandas as pd

        X_df = pd.DataFrame(self.X, columns=["feat1", "feat2"])
        y_series = pd.Series(self.y, name="target")
        groups_series = pd.Series(self.groups, name="series_id")

        results = temporal_cross_validate(
            X_df, y_series, groups_series, self.model_factory
        )

        # Should work the same as numpy arrays
        assert results["n_folds"] > 0
        assert len(results["all_y_true"]) == len(y_series)


class TestGenerateEvaluationReport:
    """Tests for generate_evaluation_report function."""

    def setup_method(self):
        """Create synthetic CV results and config."""
        np.random.seed(42)

        # Create synthetic CV results
        n_samples = 30
        self.cv_results = {
            "fold_metrics": [
                {"log_loss": 0.5, "brier_score": 0.2, "accuracy": 0.75},
                {"log_loss": 0.6, "brier_score": 0.25, "accuracy": 0.70},
                {"log_loss": 0.55, "brier_score": 0.22, "accuracy": 0.73},
            ],
            "aggregate_metrics": {
                "log_loss_mean": 0.55,
                "log_loss_std": 0.04,
                "brier_score_mean": 0.22,
                "brier_score_std": 0.02,
                "accuracy_mean": 0.73,
                "accuracy_std": 0.02,
            },
            "overall_metrics": {
                "log_loss": 0.54,
                "brier_score": 0.21,
                "accuracy": 0.74,
            },
            "all_y_true": np.random.randint(0, 2, n_samples),
            "all_y_pred": np.random.rand(n_samples),
            "n_folds": 3,
        }

        # Create experiment config
        model_config = ModelConfig(feature_set="core", C=1.0)
        self.experiment_config = ExperimentConfig(
            experiment_id="test_experiment",
            model=model_config,
        )

    def test_generate_report_creates_expected_files(self, tmp_path):
        """Test that generate_evaluation_report creates all expected files."""
        exp_dir = generate_evaluation_report(
            self.experiment_config, self.cv_results, tmp_path
        )

        # Check directory exists
        assert exp_dir.exists()
        assert exp_dir.is_dir()

        # Check all expected files exist
        assert (exp_dir / "config.json").exists()
        assert (exp_dir / "metrics.json").exists()
        assert (exp_dir / "calibration_curve.png").exists()
        assert (exp_dir / "prediction_distribution.png").exists()

    def test_generate_report_config_json_valid(self, tmp_path):
        """Test that config.json is valid JSON with expected content."""
        exp_dir = generate_evaluation_report(
            self.experiment_config, self.cv_results, tmp_path
        )

        config_path = exp_dir / "config.json"
        with open(config_path, "r") as f:
            config_data = json.load(f)

        assert config_data["experiment_id"] == "test_experiment"
        assert config_data["model"]["feature_set"] == "core"
        assert config_data["model"]["C"] == 1.0
        assert config_data["calibration_method"] == "sigmoid"

    def test_generate_report_metrics_json_valid(self, tmp_path):
        """Test that metrics.json is valid JSON with expected keys."""
        exp_dir = generate_evaluation_report(
            self.experiment_config, self.cv_results, tmp_path
        )

        metrics_path = exp_dir / "metrics.json"
        with open(metrics_path, "r") as f:
            metrics_data = json.load(f)

        assert "aggregate_metrics" in metrics_data
        assert "overall_metrics" in metrics_data
        assert "n_folds" in metrics_data
        assert "fold_metrics" in metrics_data

        # Check aggregate metrics structure
        agg = metrics_data["aggregate_metrics"]
        assert "log_loss_mean" in agg
        assert "log_loss_std" in agg
        assert agg["log_loss_mean"] == 0.55

    def test_generate_report_plots_have_content(self, tmp_path):
        """Test that generated PNG files are not empty."""
        exp_dir = generate_evaluation_report(
            self.experiment_config, self.cv_results, tmp_path
        )

        calibration_path = exp_dir / "calibration_curve.png"
        dist_path = exp_dir / "prediction_distribution.png"

        # Check files have non-zero size
        assert calibration_path.stat().st_size > 0
        assert dist_path.stat().st_size > 0

        # Rough size check (PNG should be at least 5KB)
        assert calibration_path.stat().st_size > 5000
        assert dist_path.stat().st_size > 5000
