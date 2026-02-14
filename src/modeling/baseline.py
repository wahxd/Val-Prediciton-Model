"""Baseline logistic regression model trainer.

Configuration-driven trainer that creates LogisticRegression models from ModelConfig
parameters and provides training, prediction, and coefficient extraction.
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

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
        self._base_model = LogisticRegression(
            penalty='l2',
            C=config.C,
            solver=config.solver,
            max_iter=config.max_iter,
            random_state=config.random_state,
        )
        self.model_ = None

    def model_factory(self) -> LogisticRegression:
        """Return a fresh (unfitted) model instance from config.

        Used by temporal_cross_validate to create fresh models for each fold.

        Returns:
            Fresh LogisticRegression instance with config parameters
        """
        return LogisticRegression(
            penalty='l2',
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
