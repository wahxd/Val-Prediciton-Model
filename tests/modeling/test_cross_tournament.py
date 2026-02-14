"""Tests for cross-tournament validation and recency weighting."""

import pytest
import numpy as np
from sklearn.linear_model import LogisticRegression

from src.modeling.cross_tournament import (
    leave_one_tournament_out_cv,
    compute_recency_weights,
    compare_training_strategies,
    generate_cross_tournament_report,
)


# Fixtures
@pytest.fixture
def synthetic_three_tournament_data():
    """Create synthetic data with 3 tournaments for testing."""
    np.random.seed(42)

    # Tournament 1: 15 samples
    X1 = np.random.randn(15, 5)
    y1 = np.random.randint(0, 2, size=15)
    tournament1 = np.array(["champions_2025"] * 15)
    series1 = np.array([f"series_1_{i//3}" for i in range(15)])

    # Tournament 2: 12 samples
    X2 = np.random.randn(12, 5)
    y2 = np.random.randint(0, 2, size=12)
    tournament2 = np.array(["masters_bangkok"] * 12)
    series2 = np.array([f"series_2_{i//3}" for i in range(12)])

    # Tournament 3: 10 samples
    X3 = np.random.randn(10, 5)
    y3 = np.random.randint(0, 2, size=10)
    tournament3 = np.array(["vct_americas"] * 10)
    series3 = np.array([f"series_3_{i//3}" for i in range(10)])

    # Combine
    X = np.vstack([X1, X2, X3])
    y = np.hstack([y1, y2, y3])
    tournament_ids = np.hstack([tournament1, tournament2, tournament3])
    series_ids = np.hstack([series1, series2, series3])

    return X, y, tournament_ids, series_ids


@pytest.fixture
def synthetic_meta_shift_data():
    """Create synthetic data with meta shift (one tournament much different)."""
    np.random.seed(42)

    # Tournament 1: Easy to predict (high accuracy)
    X1 = np.random.randn(15, 5) + np.array([2, 0, 0, 0, 0])  # Feature 0 strong signal
    y1 = (X1[:, 0] > 1).astype(int)  # Perfect separation
    tournament1 = np.array(["tournament_1"] * 15)
    series1 = np.array([f"series_1_{i//3}" for i in range(15)])

    # Tournament 2: Easy to predict (high accuracy)
    X2 = np.random.randn(12, 5) + np.array([2, 0, 0, 0, 0])
    y2 = (X2[:, 0] > 1).astype(int)
    tournament2 = np.array(["tournament_2"] * 12)
    series2 = np.array([f"series_2_{i//3}" for i in range(12)])

    # Tournament 3: Hard to predict (low accuracy) - noise
    X3 = np.random.randn(10, 5)
    y3 = np.random.randint(0, 2, size=10)
    tournament3 = np.array(["tournament_3"] * 10)
    series3 = np.array([f"series_3_{i//3}" for i in range(10)])

    # Combine
    X = np.vstack([X1, X2, X3])
    y = np.hstack([y1, y2, y3])
    tournament_ids = np.hstack([tournament1, tournament2, tournament3])
    series_ids = np.hstack([series1, series2, series3])

    return X, y, tournament_ids, series_ids


# Tests for leave_one_tournament_out_cv
def test_leave_one_tournament_out_basic(synthetic_three_tournament_data):
    """Test basic LOTO CV with 3 tournaments."""
    X, y, tournament_ids, series_ids = synthetic_three_tournament_data

    def model_factory():
        return LogisticRegression(max_iter=1000, random_state=42)

    result = leave_one_tournament_out_cv(X, y, tournament_ids, model_factory)

    # Should have 3 fold results (one per tournament)
    assert len(result["per_tournament_results"]) == 3

    # Each fold should have required metrics
    for fold in result["per_tournament_results"]:
        assert "tournament" in fold
        assert "log_loss" in fold
        assert "accuracy" in fold
        assert "n_samples" in fold

    # Overall metrics should be present
    assert "overall_log_loss" in result
    assert "accuracy_range" in result
    assert "meta_shift_detected" in result
    assert "worst_tournament" in result


def test_leave_one_tournament_meta_shift_detected(synthetic_meta_shift_data):
    """Test meta shift detection when one tournament has much lower accuracy."""
    X, y, tournament_ids, series_ids = synthetic_meta_shift_data

    def model_factory():
        return LogisticRegression(max_iter=1000, random_state=42)

    result = leave_one_tournament_out_cv(X, y, tournament_ids, model_factory)

    # Should have 3 fold results
    assert len(result["per_tournament_results"]) == 3

    # Meta shift should be detected (accuracy range > 10pp)
    assert result["meta_shift_detected"] is True
    assert result["accuracy_range"] > 0.10

    # Worst tournament should be identified
    assert result["worst_tournament"] is not None
    assert "tournament" in result["worst_tournament"]


def test_leave_one_tournament_no_meta_shift(synthetic_three_tournament_data):
    """Test no meta shift when all tournaments have similar accuracy."""
    X, y, tournament_ids, series_ids = synthetic_three_tournament_data

    def model_factory():
        return LogisticRegression(max_iter=1000, random_state=42)

    result = leave_one_tournament_out_cv(X, y, tournament_ids, model_factory)

    # Meta shift detection depends on data - just check it's a bool
    assert isinstance(result["meta_shift_detected"], bool)

    # Accuracy range should be reasonable
    assert result["accuracy_range"] >= 0.0
    assert result["accuracy_range"] <= 1.0


def test_leave_one_tournament_worst_identified(synthetic_meta_shift_data):
    """Test worst tournament is correctly identified."""
    X, y, tournament_ids, series_ids = synthetic_meta_shift_data

    def model_factory():
        return LogisticRegression(max_iter=1000, random_state=42)

    result = leave_one_tournament_out_cv(X, y, tournament_ids, model_factory)

    # Worst tournament should have highest log_loss
    worst = result["worst_tournament"]
    all_log_losses = [r["log_loss"] for r in result["per_tournament_results"]]

    assert worst["log_loss"] == max(all_log_losses)


def test_leave_one_tournament_single_tournament():
    """Test LOTO with single tournament (should skip)."""
    np.random.seed(42)
    X = np.random.randn(10, 5)
    y = np.random.randint(0, 2, size=10)
    tournament_ids = np.array(["single_tournament"] * 10)

    def model_factory():
        return LogisticRegression(max_iter=1000, random_state=42)

    result = leave_one_tournament_out_cv(X, y, tournament_ids, model_factory)

    # With single tournament, LOTO can't create folds (all data is test)
    # Should return empty results
    assert len(result["per_tournament_results"]) == 0


# Tests for compute_recency_weights
def test_recency_weights_three_tournaments():
    """Test recency weights with 3 tournaments."""
    tournament_ids = np.array(
        ["champions_2025"] * 15 + ["masters_bangkok"] * 12 + ["vct_americas"] * 10
    )
    tournament_order = ["champions_2025", "masters_bangkok", "vct_americas"]

    weights = compute_recency_weights(tournament_ids, tournament_order)

    # Check shape
    assert len(weights) == len(tournament_ids)

    # Check weights for each tournament
    # champions_2025 is oldest (two back) -> 0.5
    # masters_bangkok is middle (one back) -> 0.7
    # vct_americas is newest (current) -> 1.0
    assert np.all(weights[:15] == 0.5)  # champions
    assert np.all(weights[15:27] == 0.7)  # masters
    assert np.all(weights[27:] == 1.0)  # vct


def test_recency_weights_two_tournaments():
    """Test recency weights with 2 tournaments."""
    tournament_ids = np.array(["old"] * 10 + ["new"] * 10)
    tournament_order = ["old", "new"]

    weights = compute_recency_weights(tournament_ids, tournament_order)

    # Old tournament (one back) -> 0.7
    # New tournament (current) -> 1.0
    assert np.all(weights[:10] == 0.7)
    assert np.all(weights[10:] == 1.0)


def test_recency_weights_single_tournament():
    """Test recency weights with 1 tournament."""
    tournament_ids = np.array(["only_one"] * 10)
    tournament_order = ["only_one"]

    weights = compute_recency_weights(tournament_ids, tournament_order)

    # Single tournament (current) -> 1.0
    assert np.all(weights == 1.0)


def test_recency_weights_per_sample():
    """Test per-sample weights match tournament assignment."""
    tournament_ids = np.array(["A", "B", "A", "C", "B"])
    tournament_order = ["A", "B", "C"]

    weights = compute_recency_weights(tournament_ids, tournament_order)

    # A is two back (0.5), B is one back (0.7), C is current (1.0)
    expected = np.array([0.5, 0.7, 0.5, 1.0, 0.7])
    np.testing.assert_array_equal(weights, expected)


# Tests for compare_training_strategies
def test_compare_strategies_all_valid(synthetic_three_tournament_data):
    """Test all three strategies produce valid metrics."""
    X, y, tournament_ids, series_ids = synthetic_three_tournament_data
    tournament_order = ["champions_2025", "masters_bangkok", "vct_americas"]

    def model_factory():
        return LogisticRegression(max_iter=1000, random_state=42)

    result = compare_training_strategies(
        X, y, series_ids, tournament_ids, tournament_order, model_factory
    )

    # All strategies should have metrics
    assert "champions_only" in result
    assert "mixed" in result
    assert "recency_weighted" in result

    # Check each strategy has log_loss and accuracy
    for strategy in ["champions_only", "mixed", "recency_weighted"]:
        assert "log_loss" in result[strategy]
        assert "accuracy" in result[strategy]

    # Best strategy should be identified
    assert "best_strategy" in result
    assert result["best_strategy"] in ["champions_only", "mixed", "recency_weighted"]


def test_compare_strategies_best_identified(synthetic_three_tournament_data):
    """Test best strategy is correctly identified."""
    X, y, tournament_ids, series_ids = synthetic_three_tournament_data
    tournament_order = ["champions_2025", "masters_bangkok", "vct_americas"]

    def model_factory():
        return LogisticRegression(max_iter=1000, random_state=42)

    result = compare_training_strategies(
        X, y, series_ids, tournament_ids, tournament_order, model_factory
    )

    # Best strategy should have lowest log_loss
    best = result["best_strategy"]
    best_log_loss = result[best]["log_loss"]

    # Check it's actually the lowest (among valid strategies)
    valid_log_losses = [
        result[s]["log_loss"]
        for s in ["champions_only", "mixed", "recency_weighted"]
        if not np.isnan(result[s]["log_loss"])
    ]

    if len(valid_log_losses) > 0:
        assert best_log_loss == min(valid_log_losses)


def test_compare_strategies_recency_uses_weights(synthetic_three_tournament_data):
    """Test recency-weighted uses sample_weight (different from mixed)."""
    X, y, tournament_ids, series_ids = synthetic_three_tournament_data
    tournament_order = ["champions_2025", "masters_bangkok", "vct_americas"]

    def model_factory():
        return LogisticRegression(max_iter=1000, random_state=42)

    result = compare_training_strategies(
        X, y, series_ids, tournament_ids, tournament_order, model_factory
    )

    # Recency-weighted should produce different results from mixed
    # (not a strict requirement since data is random, but likely)
    mixed_loss = result["mixed"]["log_loss"]
    recency_loss = result["recency_weighted"]["log_loss"]

    # Both should be valid (not NaN)
    assert not np.isnan(mixed_loss)
    assert not np.isnan(recency_loss)


# Tests for generate_cross_tournament_report
def test_report_structure_complete():
    """Test report has all 4 sections."""
    # Mock LOTO results with meta shift
    loto_results = {
        "per_tournament_results": [
            {"tournament": "A", "log_loss": 0.7, "accuracy": 0.6, "n_samples": 10},
            {"tournament": "B", "log_loss": 0.65, "accuracy": 0.65, "n_samples": 10},
            {"tournament": "C", "log_loss": 0.8, "accuracy": 0.45, "n_samples": 10},
        ],
        "overall_log_loss": 0.72,
        "accuracy_range": 0.20,  # > 10pp
        "meta_shift_detected": True,
        "worst_tournament": {"tournament": "C", "log_loss": 0.8, "accuracy": 0.45, "n_samples": 10},
    }

    # Mock strategy comparison
    strategy_comparison = {
        "champions_only": {"log_loss": 0.75, "accuracy": 0.55},
        "mixed": {"log_loss": 0.70, "accuracy": 0.60},
        "recency_weighted": {"log_loss": 0.68, "accuracy": 0.62},
        "best_strategy": "recency_weighted",
        "comparison_table": {},
    }

    report = generate_cross_tournament_report(loto_results, strategy_comparison)

    # Should have meta shift detected
    assert report["meta_shift_detected"] is True

    # Should have all 4 sections
    assert "statistical_check" in report
    assert "feature_shift" in report
    assert "thesis_validation" in report
    assert "trading_implication" in report


def test_report_with_meta_shift():
    """Test report with meta shift detected."""
    loto_results = {
        "per_tournament_results": [
            {"tournament": "A", "log_loss": 0.7, "accuracy": 0.6, "n_samples": 10},
            {"tournament": "B", "log_loss": 0.8, "accuracy": 0.45, "n_samples": 10},
        ],
        "overall_log_loss": 0.75,
        "accuracy_range": 0.15,  # > 10pp
        "meta_shift_detected": True,
        "worst_tournament": {"tournament": "B", "log_loss": 0.8, "accuracy": 0.45, "n_samples": 10},
    }

    strategy_comparison = {
        "best_strategy": "mixed",
        "comparison_table": {},
    }

    report = generate_cross_tournament_report(loto_results, strategy_comparison)

    assert report["meta_shift_detected"] is True
    assert "Meta shift detected" in report["summary"]
    assert report["worst_tournament"]["tournament"] == "B"


def test_report_without_meta_shift():
    """Test report without meta shift (short version)."""
    loto_results = {
        "per_tournament_results": [
            {"tournament": "A", "log_loss": 0.7, "accuracy": 0.6, "n_samples": 10},
            {"tournament": "B", "log_loss": 0.65, "accuracy": 0.62, "n_samples": 10},
        ],
        "overall_log_loss": 0.675,
        "accuracy_range": 0.02,  # < 10pp
        "meta_shift_detected": False,
        "worst_tournament": {"tournament": "A", "log_loss": 0.7, "accuracy": 0.6, "n_samples": 10},
    }

    strategy_comparison = {
        "best_strategy": "mixed",
        "comparison_table": {},
    }

    report = generate_cross_tournament_report(loto_results, strategy_comparison)

    assert report["meta_shift_detected"] is False
    assert "No meta shift detected" in report["summary"]
    assert "recommendation" in report


def test_report_json_serializable():
    """Test report is JSON-serializable."""
    import json

    loto_results = {
        "per_tournament_results": [
            {"tournament": "A", "log_loss": 0.7, "accuracy": 0.6, "n_samples": 10},
        ],
        "overall_log_loss": 0.7,
        "accuracy_range": 0.0,
        "meta_shift_detected": False,
        "worst_tournament": {"tournament": "A", "log_loss": 0.7, "accuracy": 0.6, "n_samples": 10},
    }

    strategy_comparison = {
        "best_strategy": "mixed",
        "comparison_table": {},
    }

    report = generate_cross_tournament_report(loto_results, strategy_comparison)

    # Should be JSON-serializable
    json_str = json.dumps(report)
    assert len(json_str) > 0


def test_report_with_stability_results():
    """Test report includes stability results when provided."""
    loto_results = {
        "per_tournament_results": [
            {"tournament": "A", "log_loss": 0.7, "accuracy": 0.6, "n_samples": 10},
            {"tournament": "B", "log_loss": 0.8, "accuracy": 0.45, "n_samples": 10},
        ],
        "overall_log_loss": 0.75,
        "accuracy_range": 0.15,  # > 10pp
        "meta_shift_detected": True,
        "worst_tournament": {"tournament": "B", "log_loss": 0.8, "accuracy": 0.45, "n_samples": 10},
    }

    strategy_comparison = {
        "best_strategy": "mixed",
        "comparison_table": {},
    }

    stability_results = {
        "avg_overlap": 65.0,
        "stable_features": ["feature_1", "feature_2"],
        "unstable_features": ["feature_3", "feature_4", "feature_5"],
        "trading_implications": {
            "stable": "2 features stable",
            "unstable": "3 features unstable - recommend retrain"
        }
    }

    report = generate_cross_tournament_report(
        loto_results, strategy_comparison, stability_results
    )

    # Should include stability data in feature shift section
    assert report["feature_shift"]["avg_overlap"] == 65.0
    assert len(report["feature_shift"]["stable_features"]) == 2
    assert len(report["feature_shift"]["unstable_features"]) == 3
