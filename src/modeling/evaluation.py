"""Evaluation framework for model experiments.

Provides temporal cross-validation with series-level grouping, metrics computation,
and evaluation report generation (JSON + plots).
"""

import json
from pathlib import Path
from typing import Callable
import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for headless environments
import matplotlib.pyplot as plt
from sklearn.metrics import log_loss, brier_score_loss, accuracy_score
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.calibration import CalibratedClassifierCV, calibration_curve


def compute_metrics(y_true: np.ndarray, y_pred_proba: np.ndarray) -> dict:
    """Compute evaluation metrics for binary classification.

    Args:
        y_true: True binary labels (0 or 1)
        y_pred_proba: Predicted probabilities for positive class

    Returns:
        Dictionary with keys:
            - log_loss: Log loss (lower is better, 0.693 is random)
            - brier_score: Brier score (MSE of probabilities)
            - accuracy: Accuracy at 0.5 threshold

    Notes:
        - If y_true contains only one class, log_loss is undefined (returns NaN)
        - Accuracy uses 0.5 threshold (y_pred_proba > 0.5 → class 1)
    """
    # Handle single-class case
    if len(np.unique(y_true)) == 1:
        return {
            "log_loss": float("nan"),
            "brier_score": brier_score_loss(y_true, y_pred_proba),
            "accuracy": accuracy_score(y_true, (y_pred_proba > 0.5).astype(int)),
        }

    return {
        "log_loss": log_loss(y_true, y_pred_proba),
        "brier_score": brier_score_loss(y_true, y_pred_proba),
        "accuracy": accuracy_score(y_true, (y_pred_proba > 0.5).astype(int)),
    }


def temporal_cross_validate(
    X: pd.DataFrame | np.ndarray,
    y: pd.Series | np.ndarray,
    groups: pd.Series | np.ndarray,
    model_factory: Callable,
    calibration_method: str = "sigmoid",
    calibration_cv: int = 5,
) -> dict:
    """Perform temporal cross-validation with leave-one-series-out strategy.

    Uses LeaveOneGroupOut to ensure no series appears in both train and test sets,
    preventing data leakage from series-level correlation (maps within same BO3/BO5).

    Args:
        X: Feature matrix (n_samples, n_features)
        y: Target labels (n_samples,) - binary (0 or 1)
        groups: Series IDs for grouping (n_samples,) - each unique ID is one series
        model_factory: Callable that returns a fresh sklearn estimator
        calibration_method: "sigmoid" (Platt scaling) or "isotonic"
        calibration_cv: Number of CV folds for CalibratedClassifierCV internal CV

    Returns:
        Dictionary with:
            - fold_metrics: List of per-fold metric dicts
            - aggregate_metrics: Mean and std of fold metrics
            - overall_metrics: Metrics computed on concatenated predictions
            - all_y_true: Concatenated true labels across all folds
            - all_y_pred: Concatenated predicted probabilities across all folds
            - n_folds: Number of folds completed

    Notes:
        - Folds with only one class in training are skipped (CalibratedClassifierCV requires both)
        - If calibration_cv exceeds min class count, it's reduced automatically
    """
    logo = LeaveOneGroupOut()
    fold_metrics = []
    all_y_true = []
    all_y_pred = []

    # Convert to numpy arrays for indexing
    if isinstance(X, pd.DataFrame):
        X_array = X.values
    else:
        X_array = X

    if isinstance(y, pd.Series):
        y_array = y.values
    else:
        y_array = y

    if isinstance(groups, pd.Series):
        groups_array = groups.values
    else:
        groups_array = groups

    fold_idx = 0
    for train_idx, test_idx in logo.split(X_array, y_array, groups=groups_array):
        X_train, X_test = X_array[train_idx], X_array[test_idx]
        y_train, y_test = y_array[train_idx], y_array[test_idx]

        # Check if training data has both classes
        unique_classes = np.unique(y_train)
        if len(unique_classes) < 2:
            warnings.warn(
                f"Fold {fold_idx}: Only one class in training set, skipping fold"
            )
            fold_idx += 1
            continue

        # Check if calibration_cv exceeds min class count
        min_class_count = min(np.sum(y_train == 0), np.sum(y_train == 1))
        effective_cal_cv = min(calibration_cv, min_class_count)

        if effective_cal_cv < calibration_cv:
            warnings.warn(
                f"Fold {fold_idx}: Reducing calibration_cv from {calibration_cv} "
                f"to {effective_cal_cv} (min class count)"
            )

        # Create fresh model and wrap in calibration
        base_model = model_factory()
        calibrated_model = CalibratedClassifierCV(
            estimator=base_model,
            method=calibration_method,
            cv=effective_cal_cv,
            ensemble=True,
        )

        # Train
        calibrated_model.fit(X_train, y_train)

        # Predict probabilities
        y_pred_proba = calibrated_model.predict_proba(X_test)[:, 1]

        # Compute fold metrics
        fold_result = compute_metrics(y_test, y_pred_proba)
        fold_metrics.append(fold_result)

        # Store predictions
        all_y_true.extend(y_test)
        all_y_pred.extend(y_pred_proba)

        fold_idx += 1

    # Convert to numpy arrays
    all_y_true = np.array(all_y_true)
    all_y_pred = np.array(all_y_pred)

    # Aggregate fold metrics
    aggregate_metrics = {}
    for metric_name in ["log_loss", "brier_score", "accuracy"]:
        values = [f[metric_name] for f in fold_metrics if not np.isnan(f[metric_name])]
        if len(values) > 0:
            aggregate_metrics[f"{metric_name}_mean"] = np.mean(values)
            aggregate_metrics[f"{metric_name}_std"] = np.std(values)
        else:
            aggregate_metrics[f"{metric_name}_mean"] = float("nan")
            aggregate_metrics[f"{metric_name}_std"] = float("nan")

    # Overall metrics (on concatenated predictions)
    overall_metrics = compute_metrics(all_y_true, all_y_pred)

    return {
        "fold_metrics": fold_metrics,
        "aggregate_metrics": aggregate_metrics,
        "overall_metrics": overall_metrics,
        "all_y_true": all_y_true,
        "all_y_pred": all_y_pred,
        "n_folds": len(fold_metrics),
    }


def generate_evaluation_report(
    experiment_config,
    cv_results: dict,
    output_dir: Path,
) -> Path:
    """Generate evaluation report with JSON metrics and plots.

    Creates experiment directory with:
        - config.json: Experiment configuration
        - metrics.json: Aggregate, overall, and per-fold metrics
        - calibration_curve.png: Reliability diagram
        - prediction_distribution.png: Histogram of predicted probabilities

    Args:
        experiment_config: ExperimentConfig object
        cv_results: Output from temporal_cross_validate()
        output_dir: Base directory for experiments

    Returns:
        Path to experiment directory

    Notes:
        - Plots are saved at 150 DPI
        - Uses plt.close() to avoid memory leaks
    """
    exp_dir = output_dir / experiment_config.experiment_id
    exp_dir.mkdir(parents=True, exist_ok=True)

    # Save config
    config_path = exp_dir / "config.json"
    with open(config_path, "w") as f:
        json.dump(experiment_config.to_json(), f, indent=2)

    # Save metrics
    metrics_data = {
        "aggregate_metrics": cv_results["aggregate_metrics"],
        "overall_metrics": cv_results["overall_metrics"],
        "n_folds": cv_results["n_folds"],
        "fold_metrics": cv_results["fold_metrics"],
    }
    metrics_path = exp_dir / "metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics_data, f, indent=2)

    # Generate calibration curve
    y_true = cv_results["all_y_true"]
    y_pred = cv_results["all_y_pred"]

    prob_true, prob_pred = calibration_curve(
        y_true, y_pred, n_bins=10, strategy="uniform"
    )

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot([0, 1], [0, 1], "k--", linewidth=2, label="Perfect calibration")
    ax.plot(prob_pred, prob_true, marker="o", markersize=8, label="Model calibration")
    ax.set_xlabel("Mean predicted probability", fontsize=12)
    ax.set_ylabel("Fraction of positives", fontsize=12)
    ax.set_title("Calibration Curve (Reliability Diagram)", fontsize=14)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_xlim([0, 1])
    ax.set_ylim([0, 1])

    calibration_path = exp_dir / "calibration_curve.png"
    fig.savefig(calibration_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    # Generate prediction distribution
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.hist(y_pred, bins=20, edgecolor="black", alpha=0.7)
    ax.axvline(x=0.5, color="red", linestyle="--", linewidth=2, label="Threshold (0.5)")
    ax.set_xlabel("Predicted probability", fontsize=12)
    ax.set_ylabel("Count", fontsize=12)
    ax.set_title("Prediction Distribution", fontsize=14)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3, axis="y")

    dist_path = exp_dir / "prediction_distribution.png"
    fig.savefig(dist_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return exp_dir
