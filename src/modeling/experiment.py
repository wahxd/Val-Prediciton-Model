"""End-to-end experiment runner with baseline comparisons.

Orchestrates full experiment pipeline: train, validate, calibrate, explain, report.
Provides unified entry point that ties together all modeling components.
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import log_loss, brier_score_loss, accuracy_score
from sklearn.calibration import calibration_curve

from src.modeling.config import ExperimentConfig
from src.modeling.baseline import BaselineTrainer
from src.modeling.evaluation import temporal_cross_validate, generate_evaluation_report
from src.modeling.explainability import compute_shap_importance, plot_shap_summary, validate_game_mechanics_dominance
from src.modeling.calibration import serialize_model_to_json


def compute_naive_baselines(y_true: np.ndarray | pd.Series) -> dict:
    """Compute naive baseline predictions for comparison.

    Provides two baselines:
    1. Naive prior: always predict 0.5 (log loss should be ~0.693)
    2. Majority class: always predict the majority class probability

    Args:
        y_true: True binary labels (0 or 1)

    Returns:
        Dictionary with "naive_prior" and "majority_class" sub-dicts,
        each containing "log_loss", "brier_score", "accuracy"

    Notes:
        - Naive prior log loss is ln(2) ≈ 0.693 for balanced classes
        - Majority class uses max(mean, 1-mean) as constant prediction
    """
    # Convert to numpy array
    if isinstance(y_true, pd.Series):
        y_true_array = y_true.values
    else:
        y_true_array = y_true

    n_samples = len(y_true_array)

    # Naive prior baseline: always predict 0.5
    naive_prior_pred = np.full(n_samples, 0.5)
    naive_prior_metrics = {
        "log_loss": log_loss(y_true_array, naive_prior_pred),
        "brier_score": brier_score_loss(y_true_array, naive_prior_pred),
        "accuracy": accuracy_score(y_true_array, (naive_prior_pred > 0.5).astype(int)),
    }

    # Majority class baseline: always predict majority class probability
    class_mean = y_true_array.mean()
    majority_prob = max(class_mean, 1 - class_mean)
    majority_class_pred = np.full(n_samples, majority_prob)
    majority_class_metrics = {
        "log_loss": log_loss(y_true_array, majority_class_pred),
        "brier_score": brier_score_loss(y_true_array, majority_class_pred),
        "accuracy": accuracy_score(y_true_array, (majority_class_pred > 0.5).astype(int)),
    }

    return {
        "naive_prior": naive_prior_metrics,
        "majority_class": majority_class_metrics,
    }


def validate_calibration(
    y_true: np.ndarray | pd.Series,
    y_pred_proba: np.ndarray | pd.Series,
    n_bins: int = 10,
    tolerance: float = 0.10,
) -> dict:
    """Validate calibration by checking bin-level deviation.

    For each bin in the calibration curve, checks whether the deviation between
    predicted and observed probability is within tolerance.

    Args:
        y_true: True binary labels (0 or 1)
        y_pred_proba: Predicted probabilities for positive class
        n_bins: Number of bins for calibration curve
        tolerance: Maximum allowed deviation (default 0.10 = 10%)

    Returns:
        Dictionary with:
            - bins: list of dicts with "predicted", "observed", "deviation", "within_tolerance" per bin
            - bins_within_tolerance: count of bins within tolerance
            - total_bins: total number of bins with samples
            - tolerance: the tolerance value used
            - passes: True if >= 70% of bins are within tolerance
            - max_deviation: largest absolute deviation across bins

    Notes:
        - Uses uniform binning strategy
        - Bins with no samples are excluded from counts
        - 70% threshold relaxed for small datasets (vs 80-90% for large datasets)
    """
    # Convert to numpy arrays
    if isinstance(y_true, pd.Series):
        y_true_array = y_true.values
    else:
        y_true_array = y_true

    if isinstance(y_pred_proba, pd.Series):
        y_pred_proba_array = y_pred_proba.values
    else:
        y_pred_proba_array = y_pred_proba

    # Compute calibration curve
    fraction_of_positives, mean_predicted_value = calibration_curve(
        y_true_array, y_pred_proba_array, n_bins=n_bins, strategy='uniform'
    )

    # Analyze each bin
    bins = []
    bins_within_tolerance = 0
    max_deviation = 0.0

    for predicted, observed in zip(mean_predicted_value, fraction_of_positives):
        deviation = abs(observed - predicted)
        within_tolerance = deviation <= tolerance

        if within_tolerance:
            bins_within_tolerance += 1

        max_deviation = max(max_deviation, deviation)

        bins.append({
            "predicted": float(predicted),
            "observed": float(observed),
            "deviation": float(deviation),
            "within_tolerance": bool(within_tolerance),
        })

    total_bins = len(bins)

    # Check if passes (>= 70% of bins within tolerance)
    if total_bins > 0:
        pct_within_tolerance = (bins_within_tolerance / total_bins) * 100
        passes = pct_within_tolerance >= 70.0
    else:
        # No bins (too few samples) - cannot validate
        pct_within_tolerance = 0.0
        passes = False

    return {
        "bins": bins,
        "bins_within_tolerance": bins_within_tolerance,
        "total_bins": total_bins,
        "tolerance": tolerance,
        "passes": passes,
        "max_deviation": max_deviation,
        "pct_within_tolerance": pct_within_tolerance,
    }


def run_experiment(
    config: ExperimentConfig,
    X: pd.DataFrame | np.ndarray,
    y: pd.Series | np.ndarray,
    groups: pd.Series | np.ndarray,
    feature_names: list[str],
) -> dict:
    """Run complete end-to-end experiment from config to evaluation report.

    Orchestrates the full modeling workflow:
    1. Train model with temporal cross-validation
    2. Compute naive baselines for comparison
    3. Train final model on full dataset (for SHAP and serialization)
    4. Compute SHAP feature importance
    5. Validate game mechanics dominance
    6. Validate calibration
    7. Generate evaluation report (JSON + plots)
    8. Serialize model to JSON

    Args:
        config: ExperimentConfig with model parameters and output directory
        X: Feature matrix (n_samples, n_features)
        y: Target labels (n_samples,) - binary (0 or 1)
        groups: Series IDs for grouping (n_samples,) - each unique ID is one series
        feature_names: List of feature names in column order

    Returns:
        Comprehensive results dictionary with:
            - experiment_id: Experiment identifier
            - cv_results: Output from temporal_cross_validate
            - naive_baselines: Baseline metrics (naive_prior, majority_class)
            - beats_naive_prior: True if model log_loss < naive_prior log_loss
            - beats_majority_class: True if model log_loss < majority_class log_loss
            - shap_analysis: SHAP importance analysis results
            - game_mechanics_validation: Game mechanics dominance check
            - calibration_validation: Calibration bin-level validation
            - experiment_dir: Path to experiment output directory

    Notes:
        - All outputs saved to config.output_dir / config.experiment_id
        - Creates: config.json, metrics.json, model.json, calibration_curve.png,
          prediction_distribution.png, feature_importance.png
    """
    # 1. Create baseline trainer from config
    trainer = BaselineTrainer(config.model)

    # 2. Run temporal cross-validation
    cv_results = temporal_cross_validate(
        X=X,
        y=y,
        groups=groups,
        model_factory=trainer.model_factory,
        calibration_method=config.calibration_method,
        calibration_cv=config.calibration_cv,
    )

    # 3. Compute naive baselines
    naive_baselines = compute_naive_baselines(y)

    # 4. Compare model to baselines
    model_log_loss = cv_results["overall_metrics"]["log_loss"]
    beats_naive_prior = model_log_loss < naive_baselines["naive_prior"]["log_loss"]
    beats_majority_class = model_log_loss < naive_baselines["majority_class"]["log_loss"]

    # 5. Train final model on full dataset (for SHAP and serialization)
    trainer.train(X, y)

    # 6. Compute SHAP importance (use first 80% as train, last 20% as test for explainer)
    n_samples = len(X) if isinstance(X, np.ndarray) else len(X.values)
    split_idx = int(n_samples * 0.8)

    if isinstance(X, pd.DataFrame):
        X_shap_train = X.iloc[:split_idx]
        X_shap_test = X.iloc[split_idx:]
    else:
        X_shap_train = X[:split_idx]
        X_shap_test = X[split_idx:]

    shap_analysis = compute_shap_importance(
        trainer.model_,
        X_shap_train,
        X_shap_test,
        feature_names,
    )

    # 7. Validate game mechanics dominance
    game_mechanics_validation = validate_game_mechanics_dominance(
        shap_analysis["feature_importance"]
    )

    # 8. Validate calibration from CV predictions
    calibration_validation = validate_calibration(
        cv_results["all_y_true"],
        cv_results["all_y_pred"],
    )

    # 9. Generate evaluation report (creates experiment directory)
    experiment_dir = generate_evaluation_report(
        config,
        cv_results,
        config.output_dir,
    )

    # 10. Add baseline metrics to saved metrics.json
    metrics_path = experiment_dir / "metrics.json"
    with open(metrics_path, "r") as f:
        metrics_data = json.load(f)

    metrics_data["naive_baselines"] = naive_baselines
    metrics_data["beats_naive_prior"] = beats_naive_prior
    metrics_data["beats_majority_class"] = beats_majority_class
    metrics_data["calibration_validation"] = {
        "passes": calibration_validation["passes"],
        "bins_within_tolerance": calibration_validation["bins_within_tolerance"],
        "total_bins": calibration_validation["total_bins"],
        "max_deviation": calibration_validation["max_deviation"],
    }
    metrics_data["game_mechanics_validation"] = {
        "passes": game_mechanics_validation["passes"],
        "game_mechanic_count": game_mechanics_validation["game_mechanic_count"],
        "game_mechanic_pct": game_mechanics_validation["game_mechanic_pct"],
        "top_10_features": game_mechanics_validation["top_10_features"],
    }

    with open(metrics_path, "w") as f:
        json.dump(metrics_data, f, indent=2)

    # 11. Generate SHAP plot
    shap_plot_path = experiment_dir / "feature_importance.png"
    plot_shap_summary(
        shap_analysis["shap_values"],
        X_shap_test,
        feature_names,
        shap_plot_path,
    )

    # 12. Serialize model to JSON
    model_path = experiment_dir / "model.json"
    serialize_model_to_json(trainer, model_path)

    # 13. Return comprehensive results
    return {
        "experiment_id": config.experiment_id,
        "cv_results": cv_results,
        "naive_baselines": naive_baselines,
        "beats_naive_prior": beats_naive_prior,
        "beats_majority_class": beats_majority_class,
        "shap_analysis": shap_analysis,
        "game_mechanics_validation": game_mechanics_validation,
        "calibration_validation": calibration_validation,
        "experiment_dir": experiment_dir,
    }
