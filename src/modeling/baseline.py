"""Baseline model trainers: logistic regression and XGBoost.

Configuration-driven trainers that create models from ModelConfig parameters
and provide consistent training, prediction, and inspection interfaces.
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier

from src.modeling.config import ModelConfig


class BaselineTrainer:
    """Logistic regression baseline model trainer.

    Creates and trains a LogisticRegression model based on ModelConfig parameters.
    Supports coefficient extraction for analysis and interpretation.

    Attributes:
        config: ModelConfig instance with hyperparameters
        model_: Fitted LogisticRegression model (set after train() is called)
    """

    def __init__(self, config: ModelConfig):
        """Initialize trainer with configuration.

        Args:
            config: ModelConfig instance specifying hyperparameters
        """
        self.config = config
        self.model_ = None

    def model_factory(self) -> LogisticRegression:
        """Return a fresh (unfitted) model instance from config.

        Used by temporal_cross_validate to create fresh models for each fold.

        Returns:
            Fresh LogisticRegression instance with config parameters
        """
        return LogisticRegression(
            penalty=self.config.penalty,
            C=self.config.C,
            solver=self.config.solver,
            max_iter=self.config.max_iter,
            random_state=self.config.random_state,
        )

    def train(self, X: pd.DataFrame | np.ndarray, y: pd.Series | np.ndarray) -> None:
        """Fit the model on training data.

        Args:
            X: Feature matrix (n_samples, n_features)
            y: Target labels (n_samples,) - binary (0 or 1)
        """
        self.model_ = self.model_factory()
        self.model_.fit(X, y)

    def predict_proba(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        """Return probability of class 1 (team1 wins).

        Args:
            X: Feature matrix (n_samples, n_features)

        Returns:
            Probability of positive class (n_samples,)

        Raises:
            ValueError: If model hasn't been trained yet
        """
        if self.model_ is None:
            raise ValueError("Model must be trained before prediction. Call train() first.")

        # Return probability of class 1
        return self.model_.predict_proba(X)[:, 1]

    def get_coefficients(self) -> dict:
        """Return model coefficients and intercept.

        Returns:
            Dictionary with keys:
                - coef: List of feature coefficients
                - intercept: Model intercept (bias term)

        Raises:
            ValueError: If model hasn't been trained yet
        """
        if self.model_ is None:
            raise ValueError("Model must be trained before accessing coefficients. Call train() first.")

        return {
            "coef": self.model_.coef_[0].tolist(),
            "intercept": float(self.model_.intercept_[0]),
        }


class XGBoostTrainer:
    """XGBoost gradient boosting trainer with conservative regularization.

    Uses very conservative hyperparameters designed for small datasets (n=71-117).
    Provides the same interface as BaselineTrainer for compatibility with evaluation
    framework and experiment orchestration.

    Attributes:
        config: ModelConfig instance with hyperparameters
        model_: Fitted XGBClassifier model (set after train() is called)
    """

    def __init__(self, config: ModelConfig):
        """Initialize trainer with configuration.

        Args:
            config: ModelConfig instance specifying XGBoost hyperparameters
        """
        self.config = config
        self.model_ = None

    def model_factory(self) -> XGBClassifier:
        """Return a fresh (unfitted) XGBClassifier instance from config.

        Used by temporal_cross_validate to create fresh models for each fold.

        Returns:
            Fresh XGBClassifier instance with config parameters
        """
        return XGBClassifier(
            n_estimators=self.config.n_estimators,
            max_depth=self.config.max_depth,
            min_child_weight=self.config.min_child_weight,
            learning_rate=self.config.learning_rate,
            subsample=self.config.subsample,
            colsample_bytree=self.config.colsample_bytree,
            reg_alpha=self.config.reg_alpha,
            reg_lambda=self.config.reg_lambda,
            objective='binary:logistic',
            eval_metric='logloss',
            random_state=self.config.random_state,
            use_label_encoder=False,
        )

    def train(self, X: pd.DataFrame | np.ndarray, y: pd.Series | np.ndarray) -> None:
        """Fit the model on training data.

        Args:
            X: Feature matrix (n_samples, n_features)
            y: Target labels (n_samples,) - binary (0 or 1)
        """
        self.model_ = self.model_factory()
        self.model_.fit(X, y)

    def predict_proba(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        """Return probability of class 1 (team1 wins).

        Args:
            X: Feature matrix (n_samples, n_features)

        Returns:
            Probability of positive class (n_samples,)

        Raises:
            ValueError: If model hasn't been trained yet
        """
        if self.model_ is None:
            raise ValueError("Model must be trained before prediction. Call train() first.")

        # Return probability of class 1
        return self.model_.predict_proba(X)[:, 1]

    def get_feature_importances(self) -> dict:
        """Return XGBoost native feature importances.

        Returns:
            Dictionary with keys:
                - importance: List of feature importance scores (gain-based)
                - feature_names: None (feature names tracked at pipeline level)

        Raises:
            ValueError: If model hasn't been trained yet

        Notes:
            - Uses 'gain' importance (average gain across all splits using the feature)
            - Higher values indicate more important features
        """
        if self.model_ is None:
            raise ValueError("Model must be trained before accessing importances. Call train() first.")

        # Get feature importances (gain-based)
        importance_dict = self.model_.get_booster().get_score(importance_type='gain')

        # XGBoost returns dict with feature names like 'f0', 'f1', etc.
        # Convert to list aligned with feature order
        n_features = self.model_.n_features_in_
        importance_list = []
        for i in range(n_features):
            feature_key = f'f{i}'
            importance_list.append(importance_dict.get(feature_key, 0.0))

        return {
            "importance": importance_list,
            "feature_names": None,  # Feature names tracked at pipeline level
        }


def create_trainer(config: ModelConfig):
    """Factory function to create trainer based on model type.

    Args:
        config: ModelConfig instance

    Returns:
        BaselineTrainer or XGBoostTrainer based on config.model_type

    Raises:
        ValueError: If model_type is not recognized
    """
    if config.model_type == "logistic_regression":
        return BaselineTrainer(config)
    elif config.model_type == "xgboost":
        return XGBoostTrainer(config)
    else:
        raise ValueError(
            f"Unknown model_type: {config.model_type}. "
            "Must be 'logistic_regression' or 'xgboost'."
        )
