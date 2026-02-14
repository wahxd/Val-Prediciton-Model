"""Tests for SHAP explainability module."""

import numpy as np
import pytest
from pathlib import Path
from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression

from src.modeling.explainability import (
    compute_shap_importance,
    plot_shap_summary,
    validate_game_mechanics_dominance,
)


@pytest.fixture
def synthetic_model_and_data():
    """Create synthetic data and trained model for SHAP testing."""
    # Create synthetic classification data
    X, y = make_classification(
        n_samples=100,
        n_features=5,
        n_informative=3,
        n_redundant=1,
        random_state=42,
    )

    # Split into train/test
    X_train, X_test = X[:80], X[80:]
    y_train, y_test = y[:80], y[80:]

    # Train logistic regression
    model = LogisticRegression(random_state=42, max_iter=1000)
    model.fit(X_train, y_train)

    feature_names = [
        "score_differential",
        "economy_tier",
        "streak_length",
        "pistol_wins",
        "attack_win_rate",
    ]

    return {
        "model": model,
        "X_train": X_train,
        "X_test": X_test,
        "y_train": y_train,
        "y_test": y_test,
        "feature_names": feature_names,
    }


def test_compute_shap_importance_returns_expected_keys(synthetic_model_and_data):
    """SHAP importance returns shap_values, feature_importance, feature_names, top_features."""
    data = synthetic_model_and_data
    result = compute_shap_importance(
        data["model"],
        data["X_train"],
        data["X_test"],
        data["feature_names"],
    )

    assert "shap_values" in result
    assert "feature_importance" in result
    assert "feature_names" in result
    assert "top_features" in result


def test_compute_shap_importance_correct_shape(synthetic_model_and_data):
    """SHAP values have shape (n_samples, n_features)."""
    data = synthetic_model_and_data
    result = compute_shap_importance(
        data["model"],
        data["X_train"],
        data["X_test"],
        data["feature_names"],
    )

    shap_values = result["shap_values"]
    assert shap_values.shape == (20, 5)  # 20 test samples, 5 features


def test_compute_shap_importance_sorted_descending(synthetic_model_and_data):
    """Feature importance dict is sorted by importance descending."""
    data = synthetic_model_and_data
    result = compute_shap_importance(
        data["model"],
        data["X_train"],
        data["X_test"],
        data["feature_names"],
    )

    importance_values = list(result["feature_importance"].values())
    assert importance_values == sorted(importance_values, reverse=True)


def test_compute_shap_importance_top_features_max_10(synthetic_model_and_data):
    """Top features list has at most 10 items."""
    data = synthetic_model_and_data
    result = compute_shap_importance(
        data["model"],
        data["X_train"],
        data["X_test"],
        data["feature_names"],
    )

    assert len(result["top_features"]) <= 10


def test_plot_shap_summary_creates_file(synthetic_model_and_data, tmp_path):
    """SHAP summary plot creates PNG file at output path."""
    data = synthetic_model_and_data
    result = compute_shap_importance(
        data["model"],
        data["X_train"],
        data["X_test"],
        data["feature_names"],
    )

    output_path = tmp_path / "shap_summary.png"
    returned_path = plot_shap_summary(
        result["shap_values"],
        data["X_test"],
        data["feature_names"],
        output_path,
    )

    assert output_path.exists()
    assert returned_path == output_path


def test_validate_game_mechanics_classifies_correctly():
    """Validate game mechanics correctly classifies features."""
    # Mix of game mechanic and non-mechanic features
    feature_importance = {
        "score_differential": 0.8,
        "economy_tier": 0.7,
        "team_name_hash": 0.6,  # NOT game mechanic
        "streak_length": 0.5,
        "pistol_wins": 0.4,
        "player_id": 0.3,  # NOT game mechanic
        "attack_win_rate": 0.25,
        "first_blood_rate": 0.2,
        "clutch_wins": 0.15,
        "overtime_wins": 0.1,
    }

    result = validate_game_mechanics_dominance(feature_importance)

    # 8 out of 10 are game mechanics (score, economy, streak, pistol, attack, first_blood, clutch, overtime)
    assert result["game_mechanic_count"] == 8
    assert result["game_mechanic_pct"] == 80.0
    assert result["passes"] is True


def test_validate_game_mechanics_passes_when_dominant():
    """Validate returns passes=True when game mechanics dominate."""
    # All game mechanic features
    feature_importance = {
        "team1_score_differential": 0.9,
        "team1_economy_tier": 0.8,
        "team1_streak_length": 0.7,
        "team1_pistol_wins": 0.6,
        "team2_attack_win_rate": 0.5,
        "team2_first_blood_rate": 0.4,
        "team2_clutch_wins": 0.3,
        "team2_multi_kill_rate": 0.2,
        "team1_buy_frequency": 0.15,
        "team2_eco_wins": 0.1,
    }

    result = validate_game_mechanics_dominance(feature_importance)

    assert result["passes"] is True
    assert result["game_mechanic_count"] == 10


def test_validate_game_mechanics_fails_when_non_mechanic_dominant():
    """Validate returns passes=False when non-game features dominate."""
    # Adversarial case: team identity features at top
    feature_importance = {
        "team_name_hash": 0.9,
        "player_id_1": 0.8,
        "player_id_2": 0.7,
        "player_id_3": 0.6,
        "region_code": 0.5,
        "score_differential": 0.4,  # Only 2 game mechanics in top 10
        "economy_tier": 0.3,
        "team_logo_hash": 0.2,
        "coach_name": 0.15,
        "org_id": 0.1,
    }

    result = validate_game_mechanics_dominance(feature_importance)

    assert result["passes"] is False
    assert result["game_mechanic_count"] < 8  # Less than 80%


def test_validate_game_mechanics_explicit_list():
    """Validate respects explicit game_mechanic_features list."""
    feature_importance = {
        "custom_feature_1": 0.9,
        "custom_feature_2": 0.8,
        "other_feature": 0.7,
        "random_feature": 0.6,
        "custom_feature_3": 0.5,
        "custom_feature_4": 0.4,
        "custom_feature_5": 0.3,
        "custom_feature_6": 0.2,
        "custom_feature_7": 0.15,
        "custom_feature_8": 0.1,
    }

    # Explicit list marking 9 of top 10 as game mechanics
    game_mechanic_features = [
        "custom_feature_1",
        "custom_feature_2",
        "custom_feature_3",
        "custom_feature_4",
        "custom_feature_5",
        "custom_feature_6",
        "custom_feature_7",
        "custom_feature_8",
        "other_feature",
    ]

    result = validate_game_mechanics_dominance(
        feature_importance,
        game_mechanic_features=game_mechanic_features,
    )

    assert result["game_mechanic_count"] == 9
    assert result["passes"] is True
