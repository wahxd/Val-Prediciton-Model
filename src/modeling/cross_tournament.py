"""Cross-tournament validation and recency weighting.

Provides leave-one-tournament-out diagnostic for detecting meta shifts,
tournament-level recency weighting, three-variant model comparison
(Champions-only, mixed, recency-weighted), and structured investigation reports.
"""

import numpy as np
from typing import Dict, List, Callable, Optional
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.metrics import log_loss, accuracy_score
from scipy import stats

from src.modeling.thesis_validation import compare_feature_importance_across_groups


def leave_one_tournament_out_cv(
    X: np.ndarray,
    y: np.ndarray,
    tournament_ids: np.ndarray,
    model_factory: Callable,
    feature_names: Optional[List[str]] = None
) -> dict:
    """Leave-one-tournament-out cross-validation for meta shift detection.

    Uses LeaveOneGroupOut with tournament_ids as groups. For each fold,
    trains on all-but-one tournament and tests on the held-out tournament.

    This is a DIAGNOSTIC only (not primary validation). Primary CV uses
    series_id grouping (LeaveOneGroupOut by series) to prevent series leakage.

    Args:
        X: Feature matrix (n_samples, n_features)
        y: Target labels (n_samples,) - binary (0 or 1)
        tournament_ids: Tournament IDs for grouping (n_samples,)
        model_factory: Callable that returns fresh sklearn estimator
        feature_names: Optional list of feature names for SHAP importance

    Returns:
        Dict containing:
            - per_tournament_results: list of {tournament, log_loss, accuracy, n_samples, shap_importance}
            - overall_log_loss: log loss on concatenated predictions
            - accuracy_range: max - min accuracy across tournaments
            - meta_shift_detected: bool (accuracy_range > 0.10 per CONTEXT)
            - worst_tournament: name and metrics of worst-performing fold
    """
    # Check if we have at least 2 tournaments
    unique_tournaments = np.unique(tournament_ids)
    if len(unique_tournaments) < 2:
        # Can't do LOTO with single tournament - return empty results
        return {
            "per_tournament_results": [],
            "overall_log_loss": float("nan"),
            "accuracy_range": 0.0,
            "meta_shift_detected": False,
            "worst_tournament": None,
        }

    logo = LeaveOneGroupOut()
    results = []
    all_y_true = []
    all_y_pred = []

    for train_idx, test_idx in logo.split(X, y, groups=tournament_ids):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        # Get tournament name for this fold
        test_tournament = tournament_ids[test_idx][0]  # All same in test fold

        # Check if training data has both classes
        if len(np.unique(y_train)) < 2:
            # Skip this fold - can't train on single class
            continue

        # Train model
        model = model_factory()
        model.fit(X_train, y_train)

        # Predict probabilities
        y_pred_proba = model.predict_proba(X_test)[:, 1]

        # Compute metrics
        fold_metrics = {
            "tournament": str(test_tournament),
            "log_loss": float(log_loss(y_test, y_pred_proba)),
            "accuracy": float(accuracy_score(y_test, (y_pred_proba > 0.5).astype(int))),
            "n_samples": int(len(y_test)),
        }

        # Compute SHAP importance if feature_names provided
        if feature_names is not None:
            try:
                import shap
                # Use TreeExplainer if model supports it, otherwise LinearExplainer
                if hasattr(model, "feature_importances_"):
                    explainer = shap.TreeExplainer(model)
                else:
                    explainer = shap.LinearExplainer(model, X_train)

                shap_values = explainer.shap_values(X_test)
                if isinstance(shap_values, list):
                    shap_values = shap_values[1]  # Binary classification - use positive class

                # Compute mean absolute SHAP per feature
                feature_importance = {}
                for i, name in enumerate(feature_names):
                    feature_importance[name] = float(np.abs(shap_values[:, i]).mean())

                fold_metrics["shap_importance"] = feature_importance
            except Exception:
                # SHAP computation failed - skip it
                fold_metrics["shap_importance"] = None

        results.append(fold_metrics)
        all_y_true.extend(y_test)
        all_y_pred.extend(y_pred_proba)

    # Convert to numpy arrays
    all_y_true = np.array(all_y_true)
    all_y_pred = np.array(all_y_pred)

    # Compute overall metrics
    overall_log_loss = float(log_loss(all_y_true, all_y_pred))

    # Compute accuracy range
    accuracies = [r["accuracy"] for r in results]
    if len(accuracies) > 0:
        accuracy_range = float(max(accuracies) - min(accuracies))
    else:
        accuracy_range = 0.0

    # Meta shift detected if accuracy range > 10pp
    meta_shift_detected = bool(accuracy_range > 0.10)

    # Find worst tournament (highest log loss)
    if len(results) > 0:
        worst_tournament_result = max(results, key=lambda r: r["log_loss"])
        worst_tournament = {
            "tournament": worst_tournament_result["tournament"],
            "log_loss": worst_tournament_result["log_loss"],
            "accuracy": worst_tournament_result["accuracy"],
            "n_samples": worst_tournament_result["n_samples"],
        }
    else:
        worst_tournament = None

    return {
        "per_tournament_results": results,
        "overall_log_loss": overall_log_loss,
        "accuracy_range": accuracy_range,
        "meta_shift_detected": meta_shift_detected,
        "worst_tournament": worst_tournament,
    }


def compute_recency_weights(
    tournament_ids: np.ndarray,
    tournament_order: List[str]
) -> np.ndarray:
    """Compute tournament-level recency weights.

    Assigns weights based on tournament position in chronological order:
    - Most recent: 1.0
    - One back: 0.7
    - Two back: 0.5
    - Three+ back: 0.3

    For <= 5 tournaments, uses fixed weights per CONTEXT.
    For > 5 tournaments, evolve to exponential decay (future-proof).

    Args:
        tournament_ids: Array of tournament IDs (one per sample)
        tournament_order: List of tournament names from oldest to newest

    Returns:
        Array of per-sample weights (each sample gets its tournament's weight)
    """
    # Fixed weights for <= 5 tournaments
    if len(tournament_order) <= 5:
        # Assign weights based on position from end
        tournament_weights = {}
        for i, tournament_name in enumerate(tournament_order):
            # Position from end (0 = most recent)
            position_from_end = len(tournament_order) - 1 - i

            if position_from_end == 0:
                weight = 1.0
            elif position_from_end == 1:
                weight = 0.7
            elif position_from_end == 2:
                weight = 0.5
            else:  # 3+
                weight = 0.3

            tournament_weights[tournament_name] = weight
    else:
        # Exponential decay for > 5 tournaments (future-proof)
        # Decay rate chosen so 5th tournament back ~ 0.3
        decay_rate = 0.15
        tournament_weights = {}
        for i, tournament_name in enumerate(tournament_order):
            position_from_end = len(tournament_order) - 1 - i
            weight = np.exp(-decay_rate * position_from_end)
            tournament_weights[tournament_name] = weight

    # Map per-sample weights
    sample_weights = np.array([
        tournament_weights.get(str(tid), 1.0)
        for tid in tournament_ids
    ])

    return sample_weights


def compare_training_strategies(
    X: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    tournament_ids: np.ndarray,
    tournament_order: List[str],
    model_factory: Callable,
    feature_names: Optional[List[str]] = None
) -> dict:
    """Compare three training strategies on same temporal CV.

    Strategies:
    1. Champions-only: Train only on first tournament in tournament_order
    2. Mixed (all pooled): Train on all samples equally weighted
    3. Recency-weighted: Train on all samples with tournament-level weights

    All strategies evaluated using the same test folds (leave-one-group-out by series).

    Args:
        X: Feature matrix
        y: Target labels
        groups: Series IDs for CV grouping
        tournament_ids: Tournament IDs for each sample
        tournament_order: List of tournament names from oldest to newest
        model_factory: Callable that returns fresh sklearn estimator
        feature_names: Optional list of feature names

    Returns:
        Dict with:
            - champions_only: {log_loss, accuracy}
            - mixed: {log_loss, accuracy}
            - recency_weighted: {log_loss, accuracy}
            - best_strategy: name of strategy with lowest log_loss
            - comparison_table: formatted comparison
    """
    logo = LeaveOneGroupOut()

    # Strategy 1: Champions-only (first tournament)
    if len(tournament_order) > 0:
        first_tournament = tournament_order[0]
        champions_mask = tournament_ids == first_tournament

        champions_y_true = []
        champions_y_pred = []

        for train_idx, test_idx in logo.split(X, y, groups=groups):
            # Filter training data to only first tournament
            champions_train_mask = np.isin(train_idx, np.where(champions_mask)[0])
            if not np.any(champions_train_mask):
                # No champions data in this fold - skip
                continue

            champions_train_idx = train_idx[champions_train_mask]
            X_train = X[champions_train_idx]
            y_train = y[champions_train_idx]
            X_test = X[test_idx]
            y_test = y[test_idx]

            # Check if training data has both classes
            if len(np.unique(y_train)) < 2:
                continue

            # Train model
            model = model_factory()
            model.fit(X_train, y_train)

            # Predict
            y_pred_proba = model.predict_proba(X_test)[:, 1]

            champions_y_true.extend(y_test)
            champions_y_pred.extend(y_pred_proba)

        if len(champions_y_true) > 0:
            champions_y_true = np.array(champions_y_true)
            champions_y_pred = np.array(champions_y_pred)

            champions_only = {
                "log_loss": float(log_loss(champions_y_true, champions_y_pred)),
                "accuracy": float(accuracy_score(champions_y_true, (champions_y_pred > 0.5).astype(int))),
            }
        else:
            champions_only = {
                "log_loss": float("nan"),
                "accuracy": float("nan"),
            }
    else:
        champions_only = {
            "log_loss": float("nan"),
            "accuracy": float("nan"),
        }

    # Strategy 2: Mixed (all pooled)
    mixed_y_true = []
    mixed_y_pred = []

    for train_idx, test_idx in logo.split(X, y, groups=groups):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        # Check if training data has both classes
        if len(np.unique(y_train)) < 2:
            continue

        # Train model (no weights)
        model = model_factory()
        model.fit(X_train, y_train)

        # Predict
        y_pred_proba = model.predict_proba(X_test)[:, 1]

        mixed_y_true.extend(y_test)
        mixed_y_pred.extend(y_pred_proba)

    mixed_y_true = np.array(mixed_y_true)
    mixed_y_pred = np.array(mixed_y_pred)

    mixed = {
        "log_loss": float(log_loss(mixed_y_true, mixed_y_pred)),
        "accuracy": float(accuracy_score(mixed_y_true, (mixed_y_pred > 0.5).astype(int))),
    }

    # Strategy 3: Recency-weighted
    recency_y_true = []
    recency_y_pred = []
    recency_weights = compute_recency_weights(tournament_ids, tournament_order)

    for train_idx, test_idx in logo.split(X, y, groups=groups):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        sample_weights_train = recency_weights[train_idx]

        # Check if training data has both classes
        if len(np.unique(y_train)) < 2:
            continue

        # Train model with sample weights
        model = model_factory()
        model.fit(X_train, y_train, sample_weight=sample_weights_train)

        # Predict
        y_pred_proba = model.predict_proba(X_test)[:, 1]

        recency_y_true.extend(y_test)
        recency_y_pred.extend(y_pred_proba)

    recency_y_true = np.array(recency_y_true)
    recency_y_pred = np.array(recency_y_pred)

    recency_weighted = {
        "log_loss": float(log_loss(recency_y_true, recency_y_pred)),
        "accuracy": float(accuracy_score(recency_y_true, (recency_y_pred > 0.5).astype(int))),
    }

    # Determine best strategy (lowest log_loss)
    strategies = {
        "champions_only": champions_only["log_loss"],
        "mixed": mixed["log_loss"],
        "recency_weighted": recency_weighted["log_loss"],
    }

    # Filter out NaN values
    valid_strategies = {k: v for k, v in strategies.items() if not np.isnan(v)}

    if len(valid_strategies) > 0:
        best_strategy = min(valid_strategies, key=valid_strategies.get)
    else:
        best_strategy = "none"

    # Format comparison table
    comparison_table = {
        "champions_only": champions_only,
        "mixed": mixed,
        "recency_weighted": recency_weighted,
    }

    return {
        "champions_only": champions_only,
        "mixed": mixed,
        "recency_weighted": recency_weighted,
        "best_strategy": best_strategy,
        "comparison_table": comparison_table,
    }


def generate_cross_tournament_report(
    loto_results: dict,
    strategy_comparison: dict,
    stability_results: Optional[dict] = None
) -> dict:
    """Generate cross-tournament diagnostic report.

    Structured per CONTEXT:
    1. Statistical reality check: Is accuracy drop beyond CV noise?
    2. Feature shift diagnosis: SHAP comparison via thesis_validation
    3. Thesis validation: Does hierarchy hold across tournaments?
    4. Trading implication: Stable features, recommended retrain frequency

    If no meta shift detected (accuracy_range < 10pp), reports "No meta shift detected".

    Args:
        loto_results: Output from leave_one_tournament_out_cv()
        strategy_comparison: Output from compare_training_strategies()
        stability_results: Optional output from thesis_validation.compare_feature_importance_across_groups()

    Returns:
        JSON-serializable dict with structured report
    """
    # Section 1: Statistical reality check
    accuracy_range = loto_results["accuracy_range"]
    meta_shift_detected = loto_results["meta_shift_detected"]

    if not meta_shift_detected:
        # No meta shift - short report
        return {
            "meta_shift_detected": False,
            "summary": "No meta shift detected - model generalizes well across tournaments",
            "accuracy_range": accuracy_range,
            "statistical_check": {
                "accuracy_range": accuracy_range,
                "threshold": 0.10,
                "interpretation": "Accuracy drop within acceptable range (< 10pp)"
            },
            "best_training_strategy": strategy_comparison["best_strategy"],
            "recommendation": "Mixed temporal training recommended (default)"
        }

    # Meta shift detected - full investigation
    per_tournament = loto_results["per_tournament_results"]
    accuracies = [r["accuracy"] for r in per_tournament]
    log_losses = [r["log_loss"] for r in per_tournament]

    # Compute confidence intervals
    accuracy_mean = float(np.mean(accuracies))
    accuracy_std = float(np.std(accuracies))
    accuracy_ci = stats.t.interval(
        0.95,
        len(accuracies) - 1,
        loc=accuracy_mean,
        scale=accuracy_std / np.sqrt(len(accuracies))
    )

    statistical_check = {
        "accuracy_range": accuracy_range,
        "accuracy_mean": accuracy_mean,
        "accuracy_std": accuracy_std,
        "accuracy_95ci": [float(accuracy_ci[0]), float(accuracy_ci[1])],
        "threshold": 0.10,
        "interpretation": (
            f"Accuracy drop ({accuracy_range:.3f}) exceeds 10pp threshold - "
            "indicates potential meta shift between tournaments"
        )
    }

    # Section 2: Feature shift diagnosis
    if stability_results is not None:
        feature_shift = {
            "avg_overlap": stability_results["avg_overlap"],
            "stable_features": stability_results["stable_features"],
            "unstable_features": stability_results["unstable_features"],
            "interpretation": (
                f"Feature importance overlap: {stability_results['avg_overlap']:.1f}%. "
                f"{len(stability_results['stable_features'])} stable features, "
                f"{len(stability_results['unstable_features'])} unstable features."
            )
        }
    else:
        feature_shift = {
            "avg_overlap": None,
            "stable_features": [],
            "unstable_features": [],
            "interpretation": "No SHAP feature importance data available for comparison"
        }

    # Section 3: Thesis validation (hierarchy check across tournaments)
    thesis_validation = {
        "available": stability_results is not None,
        "interpretation": (
            "Check if Side×Map > Pistol > Economy hierarchy holds across tournaments. "
            "Use thesis_validation.validate_thesis_hierarchy() on per-tournament SHAP."
        )
    }

    # Section 4: Trading implication
    if stability_results is not None:
        trading_implication = {
            "stable_features": stability_results["trading_implications"]["stable"],
            "unstable_features": stability_results["trading_implications"]["unstable"],
            "recommended_strategy": strategy_comparison["best_strategy"],
            "retrain_frequency": (
                "Recommend retraining when new tournament data available - "
                "meta shifts detected between tournaments"
            )
        }
    else:
        trading_implication = {
            "stable_features": "Unknown - no cross-tournament SHAP data",
            "unstable_features": "Unknown - no cross-tournament SHAP data",
            "recommended_strategy": strategy_comparison["best_strategy"],
            "retrain_frequency": (
                "Recommend retraining per tournament - accuracy variance high"
            )
        }

    return {
        "meta_shift_detected": True,
        "summary": f"Meta shift detected - accuracy range {accuracy_range:.3f} exceeds 10pp threshold",
        "worst_tournament": loto_results["worst_tournament"],
        "statistical_check": statistical_check,
        "feature_shift": feature_shift,
        "thesis_validation": thesis_validation,
        "trading_implication": trading_implication,
        "strategy_comparison": strategy_comparison["comparison_table"],
    }
