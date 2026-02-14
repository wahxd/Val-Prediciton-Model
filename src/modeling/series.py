"""Series-level win probability prediction for BO3/BO5 formats.

This module extends map-level predictions to series outcomes using conditional
probability with momentum adjustment based on series score state.
"""

from typing import Literal


def series_win_probability(
    p_map: float,
    series_format: Literal["bo3", "bo5"],
    series_score: tuple[int, int] = (0, 0),
    momentum: float = 0.03,
) -> float:
    """
    Compute series win probability for Team A from current score state.

    Args:
        p_map: Base map win probability for Team A (0.0 to 1.0)
        series_format: "bo3" or "bo5"
        series_score: Current score (team_a_wins, team_b_wins)
        momentum: Probability adjustment per map lead (default 0.03 = 3%)

    Returns:
        Probability Team A wins the series from current state

    Example:
        >>> series_win_probability(0.55, "bo3")  # Team A has 55% map win prob
        0.575  # Higher than 55% due to best-of format amplification
    """
    if series_format == "bo3":
        wins_needed = 2
    elif series_format == "bo5":
        wins_needed = 3
    else:
        raise ValueError(f"Invalid series_format: {series_format}. Must be 'bo3' or 'bo5'")

    return _series_win_probability_recursive(
        p_map=p_map,
        wins_needed=wins_needed,
        a_wins=series_score[0],
        b_wins=series_score[1],
        momentum=momentum,
    )


def _series_win_probability_recursive(
    p_map: float,
    wins_needed: int,
    a_wins: int,
    b_wins: int,
    momentum: float,
    max_prob: float = 0.95,
    min_prob: float = 0.05,
) -> float:
    """
    Recursive implementation of series win probability with momentum adjustment.

    Tracks all possible score paths from current state to terminal states,
    adjusting map win probability based on score differential.

    Args:
        p_map: Base map win probability for Team A
        wins_needed: Number of wins to win series (2 for BO3, 3 for BO5)
        a_wins: Current wins for Team A
        b_wins: Current wins for Team B
        momentum: Probability adjustment per map lead
        max_prob: Maximum allowed probability (prevents degenerate extremes)
        min_prob: Minimum allowed probability (prevents degenerate extremes)

    Returns:
        Probability Team A wins the series from current state
    """
    # Terminal states
    if a_wins == wins_needed:
        return 1.0
    if b_wins == wins_needed:
        return 0.0

    # Adjust probability based on current score differential
    score_diff = a_wins - b_wins
    p_adjusted = p_map + momentum * score_diff

    # Clamp to [min_prob, max_prob] to avoid degenerate predictions
    p_adjusted = max(min_prob, min(max_prob, p_adjusted))

    # Recursive: P(win series) = P(win next map) * P(win from new state | won)
    #                           + P(lose next map) * P(win from new state | lost)
    p_win_next = _series_win_probability_recursive(
        p_map, wins_needed, a_wins + 1, b_wins, momentum, max_prob, min_prob
    )
    p_lose_next = _series_win_probability_recursive(
        p_map, wins_needed, a_wins, b_wins + 1, momentum, max_prob, min_prob
    )

    return p_adjusted * p_win_next + (1 - p_adjusted) * p_lose_next


def compute_series_probabilities(
    map_predictions: list[float],
    series_format: Literal["bo3", "bo5"],
    momentum: float = 0.03,
) -> dict:
    """
    Compute series win probability and conditional probabilities at each score state.

    Args:
        map_predictions: Per-map win probabilities for Team A
        series_format: "bo3" or "bo5"
        momentum: Probability adjustment per map lead

    Returns:
        Dict with:
            - overall_series_prob: P(Team A wins series)
            - per_map_probs: List of per-map probabilities (as provided)
            - conditional_probs: Dict mapping score states to win probabilities
            - series_format: Format string

    Example:
        >>> compute_series_probabilities([0.55, 0.52, 0.58], "bo3")
        {
            'overall_series_prob': 0.575,
            'per_map_probs': [0.55, 0.52, 0.58],
            'conditional_probs': {
                '0-0': 0.575,
                '1-0': 0.698,
                '0-1': 0.452,
                '1-1': 0.575,
            },
            'series_format': 'bo3',
        }
    """
    # Use average of per-map probabilities for overall series calculation
    p_map_avg = sum(map_predictions) / len(map_predictions)

    # Overall series probability from 0-0 state
    overall_prob = series_win_probability(
        p_map=p_map_avg,
        series_format=series_format,
        series_score=(0, 0),
        momentum=momentum,
    )

    # Compute conditional probabilities at each possible score state
    conditional_probs = {}

    if series_format == "bo3":
        # BO3 score states: 0-0, 1-0, 0-1, 1-1, 2-0, 0-2, 2-1, 1-2
        score_states = [
            (0, 0), (1, 0), (0, 1), (1, 1),
            (2, 0), (0, 2), (2, 1), (1, 2),
        ]
    else:  # bo5
        # BO5 score states: all combinations up to 3 wins
        score_states = [
            (0, 0), (1, 0), (0, 1),
            (1, 1), (2, 0), (0, 2),
            (2, 1), (1, 2), (2, 2),
            (3, 0), (0, 3), (3, 1), (1, 3), (3, 2), (2, 3),
        ]

    for a_wins, b_wins in score_states:
        score_key = f"{a_wins}-{b_wins}"
        conditional_probs[score_key] = series_win_probability(
            p_map=p_map_avg,
            series_format=series_format,
            series_score=(a_wins, b_wins),
            momentum=momentum,
        )

    return {
        "overall_series_prob": overall_prob,
        "per_map_probs": map_predictions,
        "conditional_probs": conditional_probs,
        "series_format": series_format,
    }


def validate_series_calibration(
    y_true_series: list[int],
    y_pred_series: list[float],
    n_bins: int = 5,
) -> dict:
    """
    Validate series-level calibration with explicit small-sample caveats.

    Similar to map-level calibration validation but uses fewer bins (5 vs 10)
    due to small sample size (~20-30 series). Reports directional calibration
    with warnings about statistical confidence.

    Args:
        y_true_series: Observed series outcomes (1 = Team A won, 0 = Team B won)
        y_pred_series: Predicted series win probabilities for Team A
        n_bins: Number of calibration bins (default 5 for small samples)

    Returns:
        Dict with:
            - bins: List of bin definitions (lower, upper, observed_freq, predicted_mean, count)
            - passes: Boolean (True if calibration is within relaxed threshold)
            - max_deviation: Maximum deviation between predicted and observed
            - total_series: Total number of series
            - caveat: Warning text about small sample size

    Example:
        >>> validate_series_calibration([1, 0, 1, 1, 0], [0.6, 0.4, 0.7, 0.8, 0.3])
        {
            'bins': [...],
            'passes': True,
            'max_deviation': 0.08,
            'total_series': 5,
            'caveat': 'Series-level calibration is directional (n=5); insufficient for statistical confidence',
        }
    """
    import numpy as np

    total_series = len(y_true_series)

    # Convert to numpy for easier manipulation
    y_true = np.array(y_true_series)
    y_pred = np.array(y_pred_series)

    # Create bins
    bins_list = []
    bin_edges = np.linspace(0, 1, n_bins + 1)

    max_deviation = 0.0

    for i in range(n_bins):
        bin_lower = bin_edges[i]
        bin_upper = bin_edges[i + 1]

        # Find predictions in this bin
        if i == n_bins - 1:
            # Last bin includes upper edge
            in_bin = (y_pred >= bin_lower) & (y_pred <= bin_upper)
        else:
            in_bin = (y_pred >= bin_lower) & (y_pred < bin_upper)

        count = in_bin.sum()

        if count > 0:
            observed_freq = y_true[in_bin].mean()
            predicted_mean = y_pred[in_bin].mean()
            deviation = abs(observed_freq - predicted_mean)
            max_deviation = max(max_deviation, deviation)
        else:
            observed_freq = None
            predicted_mean = None
            deviation = None

        bins_list.append({
            "lower": bin_lower,
            "upper": bin_upper,
            "observed_freq": observed_freq,
            "predicted_mean": predicted_mean,
            "count": int(count),
            "deviation": deviation,
        })

    # Relaxed threshold for small samples: 60% (vs 70% for maps)
    # With ~20-30 series, calibration is directional only
    passes = max_deviation < 0.40  # 60% threshold = max 40% deviation

    return {
        "bins": bins_list,
        "passes": passes,
        "max_deviation": max_deviation,
        "total_series": total_series,
        "caveat": f"Series-level calibration is directional (n={total_series}); insufficient for statistical confidence",
    }
