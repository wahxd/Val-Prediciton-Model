"""Tests for series-level win probability prediction (BO3/BO5)."""

import pytest
import numpy as np
from src.modeling.series import (
    series_win_probability,
    compute_series_probabilities,
    validate_series_calibration,
)


class TestBO3BasicTests:
    """Basic tests for BO3 series win probability."""

    def test_bo3_symmetric_with_no_momentum(self):
        """P(series) with p_map=0.5 and momentum=0 should be exactly 0.5."""
        p_series = series_win_probability(0.5, "bo3", momentum=0.0)
        assert abs(p_series - 0.5) < 0.001  # Within rounding error

    def test_bo3_amplifies_advantage(self):
        """P(series) with p_map=0.6 should be > 0.6 (amplification)."""
        p_series = series_win_probability(0.6, "bo3")
        assert p_series > 0.6

    def test_bo3_amplifies_disadvantage(self):
        """P(series) with p_map=0.4 should be < 0.4 (inverse amplification)."""
        p_series = series_win_probability(0.4, "bo3")
        assert p_series < 0.4

    def test_bo3_momentum_increases_probability_when_leading(self):
        """P(series) from score (1,0) should be > P(series) from (0,0)."""
        p_from_0_0 = series_win_probability(0.55, "bo3", series_score=(0, 0))
        p_from_1_0 = series_win_probability(0.55, "bo3", series_score=(1, 0))
        assert p_from_1_0 > p_from_0_0

    def test_bo3_momentum_decreases_probability_when_trailing(self):
        """P(series) from score (0,1) should be < P(series) from (0,0)."""
        p_from_0_0 = series_win_probability(0.55, "bo3", series_score=(0, 0))
        p_from_0_1 = series_win_probability(0.55, "bo3", series_score=(0, 1))
        assert p_from_0_1 < p_from_0_0


class TestBO5BasicTests:
    """Basic tests for BO5 series win probability."""

    def test_bo5_symmetric_with_no_momentum(self):
        """P(series) with p_map=0.5 and momentum=0 should be exactly 0.5."""
        p_series = series_win_probability(0.5, "bo5", momentum=0.0)
        assert abs(p_series - 0.5) < 0.001

    def test_bo5_amplifies_more_than_bo3(self):
        """BO5 amplifies advantage more than BO3 for p_map > 0.5."""
        p_bo3 = series_win_probability(0.55, "bo3")
        p_bo5 = series_win_probability(0.55, "bo5")
        assert p_bo5 > p_bo3

    def test_bo5_amplifies_disadvantage_more_than_bo3(self):
        """BO5 amplifies disadvantage more than BO3 for p_map < 0.5."""
        p_bo3 = series_win_probability(0.45, "bo3")
        p_bo5 = series_win_probability(0.45, "bo5")
        assert p_bo5 < p_bo3

    def test_bo5_terminal_state_win(self):
        """P(series) from terminal score state (3,0) = 1.0."""
        p_series = series_win_probability(0.55, "bo5", series_score=(3, 0))
        assert abs(p_series - 1.0) < 0.001

    def test_bo5_terminal_state_loss(self):
        """P(series) from terminal score state (0,3) = 0.0."""
        p_series = series_win_probability(0.55, "bo5", series_score=(0, 3))
        assert abs(p_series - 0.0) < 0.001


class TestBO3TerminalStates:
    """Test terminal states for BO3."""

    def test_bo3_terminal_state_2_0_win(self):
        """P(series) from (2,0) = 1.0."""
        p_series = series_win_probability(0.55, "bo3", series_score=(2, 0))
        assert abs(p_series - 1.0) < 0.001

    def test_bo3_terminal_state_0_2_loss(self):
        """P(series) from (0,2) = 0.0."""
        p_series = series_win_probability(0.55, "bo3", series_score=(0, 2))
        assert abs(p_series - 0.0) < 0.001


class TestMomentumAdjustment:
    """Tests for momentum adjustment behavior."""

    def test_positive_momentum_increases_probability_with_lead(self):
        """With positive momentum, winning team's probability increases more."""
        # No momentum
        p_no_momentum = series_win_probability(0.55, "bo3", series_score=(1, 0), momentum=0.0)

        # With momentum
        p_with_momentum = series_win_probability(0.55, "bo3", series_score=(1, 0), momentum=0.03)

        assert p_with_momentum > p_no_momentum

    def test_zero_momentum_behaves_consistently(self):
        """With zero momentum, results match pure binomial distribution."""
        # This is validated by symmetry test above
        p_series = series_win_probability(0.5, "bo3", momentum=0.0)
        assert abs(p_series - 0.5) < 0.001

    def test_momentum_doesnt_push_outside_bounds(self):
        """Momentum doesn't push probabilities outside [0.0, 1.0] range."""
        # Even with large momentum and strong advantage (from neutral state)
        p_series = series_win_probability(0.8, "bo3", series_score=(0, 0), momentum=0.10)
        assert 0.0 <= p_series <= 1.0

        # Even with large momentum and strong disadvantage (from neutral state)
        p_series = series_win_probability(0.2, "bo3", series_score=(0, 0), momentum=0.10)
        assert 0.0 <= p_series <= 1.0

        # Individual map probabilities are clamped to [0.05, 0.95]
        # but series probabilities can approach 0 or 1 when combining multiple maps

    def test_large_momentum_still_produces_valid_probabilities(self):
        """Large momentum (0.10) still produces valid probabilities."""
        p_series = series_win_probability(0.55, "bo3", momentum=0.10)
        assert 0.0 <= p_series <= 1.0


class TestEdgeCases:
    """Edge case tests for series probability."""

    def test_p_map_zero(self):
        """p_map = 0.0 -> series prob = 0.0 (or very close)."""
        p_series = series_win_probability(0.0, "bo3")
        assert p_series < 0.1  # Should be very low (clamped to min_prob=0.05)

    def test_p_map_one(self):
        """p_map = 1.0 -> series prob = 1.0 (or very close)."""
        p_series = series_win_probability(1.0, "bo3")
        assert p_series > 0.9  # Should be very high (clamped to max_prob=0.95)

    def test_invalid_series_format(self):
        """Invalid series format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid series_format"):
            series_win_probability(0.55, "bo7")


class TestComputeSeriesProbabilities:
    """Tests for compute_series_probabilities function."""

    def test_uniform_per_map_probs(self):
        """With uniform per-map probs, overall matches single-map calculation."""
        map_predictions = [0.55, 0.55, 0.55]
        result = compute_series_probabilities(map_predictions, "bo3")

        # Overall should match single-map calculation with p=0.55
        expected = series_win_probability(0.55, "bo3")
        assert abs(result["overall_series_prob"] - expected) < 0.001

    def test_varying_per_map_probs_uses_average(self):
        """With varying per-map probs, uses average correctly."""
        map_predictions = [0.50, 0.55, 0.60]  # Average = 0.55
        result = compute_series_probabilities(map_predictions, "bo3")

        expected = series_win_probability(0.55, "bo3")
        assert abs(result["overall_series_prob"] - expected) < 0.001

    def test_returns_conditional_probabilities_bo3(self):
        """Returns conditional probabilities at score states for BO3."""
        map_predictions = [0.55]
        result = compute_series_probabilities(map_predictions, "bo3")

        # Check that conditional_probs contains expected score states
        assert "0-0" in result["conditional_probs"]
        assert "1-0" in result["conditional_probs"]
        assert "0-1" in result["conditional_probs"]
        assert "1-1" in result["conditional_probs"]

        # 0-0 should match overall
        assert abs(result["conditional_probs"]["0-0"] - result["overall_series_prob"]) < 0.001

    def test_returns_conditional_probabilities_bo5(self):
        """Returns conditional probabilities at score states for BO5."""
        map_predictions = [0.55]
        result = compute_series_probabilities(map_predictions, "bo5")

        # Check that conditional_probs contains BO5 score states
        assert "0-0" in result["conditional_probs"]
        assert "2-1" in result["conditional_probs"]
        assert "2-2" in result["conditional_probs"]

    def test_returns_correct_structure(self):
        """Returns correct dictionary structure."""
        map_predictions = [0.55, 0.52]
        result = compute_series_probabilities(map_predictions, "bo3")

        assert "overall_series_prob" in result
        assert "per_map_probs" in result
        assert "conditional_probs" in result
        assert "series_format" in result

        assert result["per_map_probs"] == map_predictions
        assert result["series_format"] == "bo3"


class TestSeriesCalibration:
    """Tests for series-level calibration validation."""

    def test_perfect_calibration_passes(self):
        """validate_series_calibration with perfect calibration -> passes."""
        # Perfect calibration: predicted = observed
        y_true = [1, 1, 1, 1, 1, 0, 0, 0, 0, 0]
        y_pred = [0.55] * 5 + [0.45] * 5  # 5 wins at 0.55, 5 losses at 0.45

        result = validate_series_calibration(y_true, y_pred)

        # With 5 series in each bin, this should be well-calibrated
        assert result["passes"] is True
        assert result["total_series"] == 10

    def test_small_sample_includes_caveat(self):
        """validate_series_calibration with small sample -> includes caveat text."""
        y_true = [1, 0, 1, 1, 0]
        y_pred = [0.6, 0.4, 0.7, 0.8, 0.3]

        result = validate_series_calibration(y_true, y_pred)

        assert "caveat" in result
        assert "directional" in result["caveat"]
        assert "n=5" in result["caveat"]

    def test_returns_correct_structure(self):
        """validate_series_calibration returns correct structure."""
        y_true = [1, 0, 1, 1, 0]
        y_pred = [0.6, 0.4, 0.7, 0.8, 0.3]

        result = validate_series_calibration(y_true, y_pred)

        assert "bins" in result
        assert "passes" in result
        assert "max_deviation" in result
        assert "total_series" in result
        assert "caveat" in result

        assert isinstance(result["bins"], list)
        # passes can be Python bool or numpy.bool_
        assert isinstance(result["passes"], (bool, np.bool_))
        assert isinstance(result["max_deviation"], (float, int, np.floating))
        assert isinstance(result["total_series"], int)

    def test_bins_contain_correct_fields(self):
        """Calibration bins contain correct fields."""
        y_true = [1, 0, 1, 1, 0]
        y_pred = [0.6, 0.4, 0.7, 0.8, 0.3]

        result = validate_series_calibration(y_true, y_pred, n_bins=3)

        for bin_data in result["bins"]:
            assert "lower" in bin_data
            assert "upper" in bin_data
            assert "observed_freq" in bin_data
            assert "predicted_mean" in bin_data
            assert "count" in bin_data
            assert "deviation" in bin_data


class TestProbabilityBounds:
    """Test that all probabilities stay within valid bounds."""

    def test_bo3_probabilities_always_valid(self):
        """All BO3 probabilities are in [0.0, 1.0]."""
        for p_map in [0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0]:
            for score in [(0, 0), (1, 0), (0, 1), (1, 1)]:
                p_series = series_win_probability(0.55, "bo3", series_score=score)
                assert 0.0 <= p_series <= 1.0

    def test_bo5_probabilities_always_valid(self):
        """All BO5 probabilities are in [0.0, 1.0]."""
        for p_map in [0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0]:
            for score in [(0, 0), (1, 0), (0, 1), (2, 1), (1, 2)]:
                p_series = series_win_probability(0.55, "bo5", series_score=score)
                assert 0.0 <= p_series <= 1.0

    def test_extreme_momentum_doesnt_break_bounds(self):
        """Extreme momentum values don't push probabilities outside [0.0, 1.0]."""
        # Very large momentum
        p_series = series_win_probability(0.55, "bo3", series_score=(1, 0), momentum=0.50)
        assert 0.0 <= p_series <= 1.0

        # Negative momentum (hypothetically)
        p_series = series_win_probability(0.55, "bo3", series_score=(1, 0), momentum=-0.10)
        assert 0.0 <= p_series <= 1.0
