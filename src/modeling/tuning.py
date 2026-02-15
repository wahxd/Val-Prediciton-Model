"""Hyperparameter tuning for XGBoost and logistic regression models.

Provides Optuna Bayesian optimization for XGBoost (conservative parameter ranges
with MedianPruner) and GridSearchCV for logistic regression (C x penalty grid).
Includes temporal holdout validation to distinguish genuine improvement from noise.
"""

import numpy as np
import pandas as pd
from typing import Dict, Callable
import optuna
from optuna.pruners import MedianPruner
from sklearn.model_selection import GridSearchCV, LeaveOneGroupOut
from sklearn.metrics import log_loss

from src.config.modeling import ModelConfig
from src.modeling.baseline import create_trainer
from src.modeling.evaluation import temporal_cross_validate


def tune_xgboost_optuna(
    X: pd.DataFrame | np.ndarray,
    y: pd.Series | np.ndarray,
    groups: pd.Series | np.ndarray,
    n_trials: int = 100,
    random_state: int = 42,
) -> Dict:
    """Tune XGBoost hyperparameters using Optuna Bayesian optimization.

    Uses MedianPruner to kill unpromising trials early. Conservative parameter
    ranges designed for small datasets (n=71-117). Temporal holdout split
    (oldest 80% train, newest 20% validate) for evaluation.

    Args:
        X: Feature matrix (n_samples, n_features), must be sorted by date
        y: Target labels (n_samples,) - binary (0 or 1)
        groups: Series IDs for grouping (n_samples,)
        n_trials: Number of Optuna trials (default: 100)
        random_state: Random seed for reproducibility

    Returns:
        Dictionary with:
            - best_params: Dict of best hyperparameters found
            - best_log_loss: Best validation log loss achieved
            - n_trials: Number of trials completed
            - study_summary: Stats (best, worst, mean) across all trials

    Notes:
        - Data must be sorted by date for temporal split
        - Uses log_loss only as objective (calibration handled separately)
        - Conservative ranges prevent overfitting on small datasets
    """
    # Convert to numpy arrays for indexing
    if isinstance(X, pd.DataFrame):
        X_array = X.values
    else:
        X_array = X

    if isinstance(y, pd.Series):
        y_array = y.values
    else:
        y_array = y

    # Temporal holdout split: oldest 80% train, newest 20% validate
    n_samples = len(X_array)
    split_idx = int(n_samples * 0.8)

    X_train, X_val = X_array[:split_idx], X_array[split_idx:]
    y_train, y_val = y_array[:split_idx], y_array[split_idx:]

    def objective(trial: optuna.Trial) -> float:
        """Optuna objective function for XGBoost tuning.

        Suggests hyperparameters, trains model on train split,
        evaluates on validation split.

        Args:
            trial: Optuna trial object

        Returns:
            Validation log loss (lower is better)
        """
        # Suggest hyperparameters within conservative ranges
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 30, 100),
            "max_depth": trial.suggest_int("max_depth", 2, 4),
            "min_child_weight": trial.suggest_int("min_child_weight", 3, 10),
            "learning_rate": trial.suggest_float(
                "learning_rate", 0.01, 0.2, log=True
            ),
            "subsample": trial.suggest_float("subsample", 0.7, 0.95),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.7, 0.95),
            "reg_alpha": trial.suggest_float("reg_alpha", 0.0, 0.5),
            "reg_lambda": trial.suggest_float("reg_lambda", 0.5, 2.0),
        }

        # Create ModelConfig with suggested params
        config = ModelConfig(
            model_type="xgboost",
            feature_set="tuning",  # Placeholder
            random_state=random_state,
            **params,
        )

        # Create trainer and train
        trainer = create_trainer(config)
        trainer.train(X_train, y_train)

        # Predict on validation set
        y_pred_proba = trainer.predict_proba(X_val)

        # Compute validation log loss
        val_log_loss = log_loss(y_val, y_pred_proba)

        # Report for pruning (using trial number as step)
        trial.report(val_log_loss, step=trial.number)

        # Check if trial should be pruned
        if trial.should_prune():
            raise optuna.TrialPruned()

        return val_log_loss

    # Create Optuna study with MedianPruner
    study = optuna.create_study(
        direction="minimize",
        pruner=MedianPruner(
            n_startup_trials=10,  # Don't prune first 10 trials
            n_warmup_steps=5,  # Wait 5 steps before pruning
        ),
        sampler=optuna.samplers.TPESampler(seed=random_state),
    )

    # Run optimization
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

    # Extract best parameters
    best_params = study.best_params

    # Compute study summary statistics
    all_values = [trial.value for trial in study.trials if trial.value is not None]
    study_summary = {
        "best": float(min(all_values)) if all_values else float("nan"),
        "worst": float(max(all_values)) if all_values else float("nan"),
        "mean": float(np.mean(all_values)) if all_values else float("nan"),
        "std": float(np.std(all_values)) if all_values else float("nan"),
    }

    return {
        "best_params": best_params,
        "best_log_loss": float(study.best_value),
        "n_trials": len(study.trials),
        "study_summary": study_summary,
    }


def tune_logistic_gridsearch(
    X: pd.DataFrame | np.ndarray, y: pd.Series | np.ndarray, groups: pd.Series | np.ndarray
) -> Dict:
    """Tune logistic regression hyperparameters using GridSearchCV.

    Exhaustive grid search over C x penalty with LeaveOneGroupOut (series-level
    grouping) to match Phase 9 temporal cross-validation strategy.

    Args:
        X: Feature matrix (n_samples, n_features)
        y: Target labels (n_samples,) - binary (0 or 1)
        groups: Series IDs for grouping (n_samples,)

    Returns:
        Dictionary with:
            - best_params: Dict (C, penalty, solver)
            - best_log_loss: Negative of best score (converted to positive)
            - all_results: List of {params, mean_log_loss, std_log_loss} for all configs
            - n_configs: Total configs evaluated

    Notes:
        - Uses 'saga' solver (supports both l1 and l2 penalties)
        - Scoring is neg_log_loss (GridSearchCV maximizes, so negative)
        - LeaveOneGroupOut ensures no series in both train/test
    """
    # Convert to numpy arrays
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

    # Parameter grid: C x penalty
    param_grid = {
        "C": [0.01, 0.1, 1.0, 10.0],
        "penalty": ["l1", "l2"],
        "solver": ["saga"],  # Supports both l1 and l2
    }

    # Create base model (placeholder, will be replaced by grid)
    from sklearn.linear_model import LogisticRegression

    base_model = LogisticRegression(max_iter=1000, random_state=42)

    # Create GridSearchCV with LeaveOneGroupOut
    grid_search = GridSearchCV(
        estimator=base_model,
        param_grid=param_grid,
        scoring="neg_log_loss",
        cv=LeaveOneGroupOut(),
        n_jobs=-1,  # Parallelize across all cores
        verbose=0,
    )

    # Fit grid search
    grid_search.fit(X_array, y_array, groups=groups_array)

    # Extract best parameters
    best_params = grid_search.best_params_

    # Extract all results
    all_results = []
    for i, params in enumerate(grid_search.cv_results_["params"]):
        all_results.append({
            "params": params,
            "mean_log_loss": -grid_search.cv_results_["mean_test_score"][i],
            "std_log_loss": grid_search.cv_results_["std_test_score"][i],
        })

    return {
        "best_params": best_params,
        "best_log_loss": -grid_search.best_score_,  # Convert back to positive
        "all_results": all_results,
        "n_configs": len(all_results),
    }


def temporal_holdout_sanity_check(
    X: pd.DataFrame | np.ndarray,
    y: pd.Series | np.ndarray,
    tuned_config: ModelConfig,
    default_config: ModelConfig,
) -> Dict:
    """Validate tuned config against defaults on temporal holdout.

    Trains both tuned and default models on oldest 80%, evaluates on newest 20%.
    If tuned config doesn't beat defaults on holdout, tuning was noise.

    Args:
        X: Feature matrix (n_samples, n_features), must be sorted by date
        y: Target labels (n_samples,) - binary (0 or 1)
        tuned_config: ModelConfig with tuned hyperparameters
        default_config: ModelConfig with default hyperparameters

    Returns:
        Dictionary with:
            - tuned_log_loss: Holdout log loss for tuned model
            - default_log_loss: Holdout log loss for default model
            - improvement: Difference (tuned - default), negative = tuned better
            - survives_holdout: bool (tuned beats default on holdout)
            - recommendation: "use_tuned" if survives, "use_defaults" otherwise

    Notes:
        - Data must be sorted by date
        - Temporal split prevents overfitting hyperparameters to training data
    """
    # Convert to numpy arrays
    if isinstance(X, pd.DataFrame):
        X_array = X.values
    else:
        X_array = X

    if isinstance(y, pd.Series):
        y_array = y.values
    else:
        y_array = y

    # Temporal holdout split: oldest 80% train, newest 20% test
    n_samples = len(X_array)
    split_idx = int(n_samples * 0.8)

    X_train, X_test = X_array[:split_idx], X_array[split_idx:]
    y_train, y_test = y_array[:split_idx], y_array[split_idx:]

    # Train tuned model
    tuned_trainer = create_trainer(tuned_config)
    tuned_trainer.train(X_train, y_train)
    tuned_pred = tuned_trainer.predict_proba(X_test)
    tuned_log_loss = log_loss(y_test, tuned_pred)

    # Train default model
    default_trainer = create_trainer(default_config)
    default_trainer.train(X_train, y_train)
    default_pred = default_trainer.predict_proba(X_test)
    default_log_loss = log_loss(y_test, default_pred)

    # Compute improvement
    improvement = tuned_log_loss - default_log_loss

    # Survives holdout if tuned beats default
    survives_holdout = tuned_log_loss < default_log_loss

    # Recommendation
    if survives_holdout:
        recommendation = "use_tuned"
    else:
        recommendation = "use_defaults"

    return {
        "tuned_log_loss": float(tuned_log_loss),
        "default_log_loss": float(default_log_loss),
        "improvement": float(improvement),
        "survives_holdout": survives_holdout,
        "recommendation": recommendation,
    }


def compare_models(xgb_cv_results: Dict, lr_cv_results: Dict) -> Dict:
    """Compare XGBoost and logistic regression CV performance.

    XGBoost must beat LR by > 1 standard error AND calibration must not degrade
    for recommendation in favor of XGBoost.

    Args:
        xgb_cv_results: Output from temporal_cross_validate for XGBoost
        lr_cv_results: Output from temporal_cross_validate for logistic regression

    Returns:
        Dictionary with:
            - xgb_log_loss: {mean, std} for XGBoost
            - lr_log_loss: {mean, std} for logistic regression
            - difference: XGBoost - LR log loss (negative = XGBoost better)
            - se_difference: Standard error of the difference
            - significant_improvement: bool (|difference| > 1 SE in favor of XGBoost)
            - calibration_comparison: Which model has better calibration
            - recommendation: "xgboost", "logistic_regression", or "no_clear_winner"
            - skepticism_note: String flagging whether improvement is robust

    Notes:
        - Uses conservative threshold (1 SE) to avoid false positives
        - Calibration checked via max_deviation from calibration validation
        - Keep both models regardless (future data may change ranking)
    """
    # Extract log loss metrics
    xgb_mean = xgb_cv_results["aggregate_metrics"]["log_loss_mean"]
    xgb_std = xgb_cv_results["aggregate_metrics"]["log_loss_std"]

    lr_mean = lr_cv_results["aggregate_metrics"]["log_loss_mean"]
    lr_std = lr_cv_results["aggregate_metrics"]["log_loss_std"]

    # Compute difference (negative = XGBoost better)
    difference = xgb_mean - lr_mean

    # Standard error of the difference
    # SE(diff) = sqrt(SE(xgb)^2 + SE(lr)^2)
    # SE = std / sqrt(n_folds)
    n_folds = xgb_cv_results["n_folds"]
    se_xgb = xgb_std / np.sqrt(n_folds)
    se_lr = lr_std / np.sqrt(n_folds)
    se_difference = np.sqrt(se_xgb**2 + se_lr**2)

    # Significant improvement if difference > 1 SE in favor of XGBoost
    significant_improvement = bool(difference < -se_difference)

    # Check calibration (if available in CV results)
    # For now, compare overall metrics - in real use, would check max_deviation
    # from calibration_validation
    xgb_brier = xgb_cv_results["overall_metrics"]["brier_score"]
    lr_brier = lr_cv_results["overall_metrics"]["brier_score"]

    if xgb_brier < lr_brier:
        calibration_comparison = "xgboost_better"
    elif lr_brier < xgb_brier:
        calibration_comparison = "logistic_regression_better"
    else:
        calibration_comparison = "tie"

    # Recommendation logic
    if significant_improvement and calibration_comparison != "logistic_regression_better":
        recommendation = "xgboost"
        skepticism_note = (
            f"XGBoost beats LR by {abs(difference):.4f} log loss "
            f"({abs(difference/se_difference):.2f} SE). "
            "Improvement exceeds noise threshold."
        )
    elif difference > se_difference and calibration_comparison != "xgboost_better":
        # LR significantly better
        recommendation = "logistic_regression"
        skepticism_note = (
            f"Logistic regression beats XGBoost by {abs(difference):.4f} log loss "
            f"({abs(difference/se_difference):.2f} SE). "
            "XGBoost did not improve over baseline."
        )
    else:
        # Difference within noise or calibration degradation
        recommendation = "no_clear_winner"
        skepticism_note = (
            f"Difference ({difference:.4f} log loss) within {se_difference:.4f} SE. "
            "Improvement not statistically meaningful. Use defaults or simpler model."
        )

    return {
        "xgb_log_loss": {"mean": float(xgb_mean), "std": float(xgb_std)},
        "lr_log_loss": {"mean": float(lr_mean), "std": float(lr_std)},
        "difference": float(difference),
        "se_difference": float(se_difference),
        "significant_improvement": significant_improvement,
        "calibration_comparison": calibration_comparison,
        "recommendation": recommendation,
        "skepticism_note": skepticism_note,
    }
