"""Match-level series feature aggregation for BO3/BO5 prediction.

This module aggregates per-map features into match/series-level features for
predicting the outcome of BO3 or BO5 series. It combines map-level statistics
with series momentum indicators (score differentials, overtime patterns, etc.).

Feature categories:
- Series state: maps won, score differential, format
- Series momentum: consecutive wins, comeback indicators, OT patterns
- Aggregated map statistics: average performance across completed maps
"""

from typing import Any


def extract_match_features(
    map_features_list: list[dict[str, Any]],  # Feature dicts from extract_map_features, ordered by map sequence
    series_format: str = "bo3",  # "bo3" or "bo5"
) -> dict[str, Any]:
    """
    Extract match/series-level features from completed maps.

    Aggregates per-map features and computes series momentum indicators.
    All features are from team1's perspective (team order must be consistent
    across all maps in the series).

    Args:
        map_features_list: List of map feature dicts from extract_map_features(),
            ordered by map sequence (map 1, map 2, map 3, etc.)
        series_format: "bo3" or "bo5"

    Returns:
        Dictionary mapping feature_name -> value. Values are int, float, bool, str, or None.

    Example:
        >>> map1_features = extract_map_features(map1_events, "map1", ["T1", "T2"])
        >>> map2_features = extract_map_features(map2_events, "map2", ["T1", "T2"])
        >>> series_features = extract_match_features([map1_features, map2_features], "bo3")
        >>> print(f"Series score: {series_features['maps_won_team1']}-{series_features['maps_won_team2']}")
    """
    if not map_features_list:
        return _empty_match_features()

    # Validate series format
    if series_format not in ("bo3", "bo5"):
        raise ValueError(f"Invalid series_format: {series_format}. Must be 'bo3' or 'bo5'")

    features: dict[str, Any] = {}

    # === SERIES STATE FEATURES ===
    maps_played = len(map_features_list)
    maps_won_team1 = sum(
        1 for m in map_features_list
        if m.get("score_differential", 0) > 0  # Positive differential = team1 won
    )
    maps_won_team2 = maps_played - maps_won_team1

    features["maps_won_team1"] = maps_won_team1
    features["maps_won_team2"] = maps_won_team2
    features["maps_played"] = maps_played
    features["series_score_differential"] = maps_won_team1 - maps_won_team2
    features["series_format"] = series_format

    # === SERIES MOMENTUM FEATURES ===
    # Average map score differential
    score_diffs = [m.get("score_differential", 0) for m in map_features_list]
    features["avg_map_score_diff"] = (
        sum(score_diffs) / len(score_diffs) if score_diffs else 0.0
    )

    # Overtime tracking
    ot_maps = [m for m in map_features_list if m.get("went_to_overtime", False)]
    features["maps_to_overtime_count"] = len(ot_maps)
    features["maps_to_overtime_pct"] = (
        len(ot_maps) / maps_played if maps_played > 0 else 0.0
    )

    # Comeback indicator: team1 was down in series but came back to win a map
    comeback = False
    team1_deficit = False
    for i, map_feat in enumerate(map_features_list):
        # Calculate score before this map
        prior_maps = map_features_list[:i]
        if prior_maps:
            prior_team1_wins = sum(
                1 for m in prior_maps if m.get("score_differential", 0) > 0
            )
            prior_team2_wins = i - prior_team1_wins

            # Check if team1 was behind before this map
            if prior_team2_wins > prior_team1_wins:
                team1_deficit = True

            # Check if team1 won this map while in deficit
            if team1_deficit and map_feat.get("score_differential", 0) > 0:
                comeback = True
                break

    features["comeback_indicator"] = comeback

    # Previous map features (for predicting next map in series)
    if maps_played >= 1:
        prev_map = map_features_list[-1]
        features["prev_map_score_diff"] = prev_map.get("score_differential", None)
        features["prev_map_went_ot"] = prev_map.get("went_to_overtime", None)
    else:
        features["prev_map_score_diff"] = None
        features["prev_map_went_ot"] = None

    # Series momentum: consecutive map wins for current leader
    # +N = team1 won last N maps, -N = team2 won last N maps, 0 = series tied or first map
    momentum = 0
    if maps_played >= 1:
        # Walk backwards from most recent map
        current_streak = 0
        last_winner = None

        for map_feat in reversed(map_features_list):
            map_diff = map_feat.get("score_differential", 0)
            if map_diff > 0:
                winner = 1  # team1
            elif map_diff < 0:
                winner = 2  # team2
            else:
                # Tie (shouldn't happen in Valorant, but handle gracefully)
                break

            if last_winner is None:
                last_winner = winner
                current_streak = 1
            elif winner == last_winner:
                current_streak += 1
            else:
                break

        # Convert to signed momentum (positive = team1 momentum)
        if last_winner == 1:
            momentum = current_streak
        elif last_winner == 2:
            momentum = -current_streak

    features["series_momentum"] = momentum

    # === AGGREGATED MAP STATISTICS ===
    # Average first blood rate
    fb_rates = [
        m.get("first_blood_rate_team1", None)
        for m in map_features_list
        if m.get("first_blood_rate_team1") is not None
    ]
    features["avg_first_blood_rate"] = (
        sum(fb_rates) / len(fb_rates) if fb_rates else None
    )

    # Average attack/defense win rates
    attack_rates = [
        m.get("attack_win_rate_team1", None)
        for m in map_features_list
        if m.get("attack_win_rate_team1") is not None
    ]
    defense_rates = [
        m.get("defense_win_rate_team1", None)
        for m in map_features_list
        if m.get("defense_win_rate_team1") is not None
    ]

    features["avg_attack_win_rate"] = (
        sum(attack_rates) / len(attack_rates) if attack_rates else None
    )
    features["avg_defense_win_rate"] = (
        sum(defense_rates) / len(defense_rates) if defense_rates else None
    )

    # Pistol round win percentage across all maps
    pistol_wins = 0
    total_pistol_rounds = 0
    for map_feat in map_features_list:
        pistol_count = map_feat.get("pistol_rounds_won_team1", None)
        if pistol_count is not None:
            pistol_wins += pistol_count
            total_pistol_rounds += 2  # R1 and R13

    features["pistol_round_win_pct"] = (
        pistol_wins / total_pistol_rounds if total_pistol_rounds > 0 else 0.0
    )

    return features


def _empty_match_features() -> dict[str, Any]:
    """
    Return empty feature dict with None/default values.

    Used when map_features_list is empty or invalid.
    """
    return {
        # Series state
        "maps_won_team1": 0,
        "maps_won_team2": 0,
        "maps_played": 0,
        "series_score_differential": 0,
        "series_format": None,
        # Series momentum
        "avg_map_score_diff": 0.0,
        "maps_to_overtime_count": 0,
        "maps_to_overtime_pct": 0.0,
        "comeback_indicator": False,
        "prev_map_score_diff": None,
        "prev_map_went_ot": None,
        "series_momentum": 0,
        # Aggregated statistics
        "avg_first_blood_rate": None,
        "avg_attack_win_rate": None,
        "avg_defense_win_rate": None,
        "pistol_round_win_pct": 0.0,
    }
