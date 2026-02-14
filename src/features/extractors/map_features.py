"""Map-level feature aggregation from round-level and combat features.

This module aggregates round-level features into a single feature vector per team per map.
These map-level features are what the prediction model trains on.

Feature categories:
- Score features: final scores, differentials, overtime status
- Pistol round features: outcomes of R1 and R13
- Half features: first half vs second half performance
- Momentum features: win/loss streaks, comebacks
- Combat features: first blood rates, clutch rounds, multi-kills
- Side performance: attack/defense win rates
- Economy features: eco round win rates, economy differentials
"""

from typing import Any
from collections import defaultdict

from src.data.schemas import ValoscribeEvent, RoundEndEvent
from src.features.extractors.round_features import extract_round_features
from src.features.extractors.combat import (
    extract_first_bloods,
    extract_clutch_rounds,
    extract_multi_kills,
    extract_side_performance,
)
from src.features.economy import EconomyTracker


def extract_map_features(
    events: list[ValoscribeEvent],
    map_id: str,
    teams: list[str],  # [team1, team2]
) -> dict[str, Any]:
    """
    Extract map-level features from Valoscribe events.

    Aggregates round-level data into a single feature dict. All features are from
    team1's perspective (team2 features are the inverse/complement).

    This is a LOCKED decision: no team identity features, purely game mechanics.

    Args:
        events: List of all events for a single map
        map_id: Map identifier (for debugging/logging)
        teams: Two-element list [team1, team2] - team name order matters for consistency

    Returns:
        Dictionary mapping feature_name -> value. Values are int, float, bool, or str.
        Returns None for features that can't be computed due to missing data.

    Example:
        >>> events = load_events("map_123/events.jsonl")
        >>> features = extract_map_features(events, "map_123", ["Team A", "Team B"])
        >>> print(f"Final score: {features['final_score_team1']}-{features['final_score_team2']}")
        >>> print(f"First blood rate: {features['first_blood_rate_team1']:.2%}")
    """
    if len(teams) != 2:
        raise ValueError(f"Expected 2 teams, got {len(teams)}: {teams}")

    team1_name = teams[0]
    team2_name = teams[1]

    # Initialize feature dict
    features: dict[str, Any] = {}

    # Extract round-level features first
    round_features = extract_round_features(events)

    if not round_features:
        # No valid rounds found - return minimal features with None values
        return _empty_features()

    # Get the final round to extract score features
    final_round = round_features[-1]

    # === SCORE FEATURES ===
    features["final_score_team1"] = final_round.score_team1
    features["final_score_team2"] = final_round.score_team2
    features["score_differential"] = final_round.score_differential
    features["total_rounds"] = len(round_features)
    features["went_to_overtime"] = features["total_rounds"] > 24

    # Determine map winner
    if final_round.score_team1 > final_round.score_team2:
        features["map_winner"] = team1_name
    else:
        features["map_winner"] = team2_name

    # === PISTOL ROUND FEATURES ===
    pistol_r1 = next((rf for rf in round_features if rf.round_number == 1), None)
    pistol_r13 = next((rf for rf in round_features if rf.round_number == 13), None)

    features["pistol_round1_winner"] = pistol_r1.winning_team if pistol_r1 else None
    features["pistol_round2_winner"] = pistol_r13.winning_team if pistol_r13 else None

    pistol_rounds_won_team1 = 0
    if pistol_r1 and pistol_r1.winning_team == team1_name:
        pistol_rounds_won_team1 += 1
    if pistol_r13 and pistol_r13.winning_team == team1_name:
        pistol_rounds_won_team1 += 1
    features["pistol_rounds_won_team1"] = pistol_rounds_won_team1

    # === HALF FEATURES ===
    first_half_rounds = [rf for rf in round_features if rf.round_number <= 12]
    second_half_rounds = [rf for rf in round_features if rf.round_number >= 13]

    features["first_half_score_team1"] = sum(
        1 for rf in first_half_rounds if rf.winning_team == team1_name
    )
    features["first_half_score_team2"] = sum(
        1 for rf in first_half_rounds if rf.winning_team == team2_name
    )
    features["second_half_score_team1"] = sum(
        1 for rf in second_half_rounds if rf.winning_team == team1_name
    )
    features["second_half_score_team2"] = sum(
        1 for rf in second_half_rounds if rf.winning_team == team2_name
    )

    # === MOMENTUM FEATURES ===
    # Calculate win/loss streaks
    team1_streaks = _calculate_streaks(round_features, team1_name)
    team2_streaks = _calculate_streaks(round_features, team2_name)

    features["max_win_streak_team1"] = team1_streaks["max_win_streak"]
    features["max_win_streak_team2"] = team2_streaks["max_win_streak"]
    features["max_loss_streak_team1"] = team1_streaks["max_loss_streak"]
    features["max_loss_streak_team2"] = team2_streaks["max_loss_streak"]

    # Comeback detection: team that was behind at halftime won
    halftime_leader = None
    if features["first_half_score_team1"] > features["first_half_score_team2"]:
        halftime_leader = team1_name
    elif features["first_half_score_team2"] > features["first_half_score_team1"]:
        halftime_leader = team2_name

    features["comeback_from_behind"] = False
    if halftime_leader is not None:
        map_winner = features["map_winner"]
        features["comeback_from_behind"] = halftime_leader != map_winner

    # === COMBAT FEATURES ===
    first_bloods = extract_first_bloods(events)
    clutch_rounds = extract_clutch_rounds(events)
    multi_kills = extract_multi_kills(events)

    # First blood rates
    total_rounds_with_fb = len(first_bloods)
    team1_first_bloods = sum(
        1 for fb in first_bloods.values() if fb.killer_team == team1_name
    )
    team2_first_bloods = sum(
        1 for fb in first_bloods.values() if fb.killer_team == team2_name
    )

    features["first_blood_rate_team1"] = (
        team1_first_bloods / total_rounds_with_fb if total_rounds_with_fb > 0 else 0.0
    )
    features["first_blood_rate_team2"] = (
        team2_first_bloods / total_rounds_with_fb if total_rounds_with_fb > 0 else 0.0
    )

    # Clutch rounds
    features["clutch_rounds_team1"] = sum(
        1 for cr in clutch_rounds if cr.clutch_team == team1_name
    )
    features["clutch_rounds_team2"] = sum(
        1 for cr in clutch_rounds if cr.clutch_team == team2_name
    )

    # Multi-kill rounds (rounds with at least one multi-kill)
    team1_multi_kill_rounds = set(
        mk.round_number for mk in multi_kills if mk.player_team == team1_name
    )
    team2_multi_kill_rounds = set(
        mk.round_number for mk in multi_kills if mk.player_team == team2_name
    )

    features["multi_kill_rounds_team1"] = len(team1_multi_kill_rounds)
    features["multi_kill_rounds_team2"] = len(team2_multi_kill_rounds)

    # === SIDE PERFORMANCE FEATURES ===
    side_perf = extract_side_performance(events)

    features["attack_win_rate_team1"] = side_perf.team1_attack_win_rate
    features["defense_win_rate_team1"] = side_perf.team1_defense_win_rate
    features["attack_win_rate_team2"] = side_perf.team2_attack_win_rate
    features["defense_win_rate_team2"] = side_perf.team2_defense_win_rate

    # === ECONOMY FEATURES ===
    # Track economy with EconomyTracker
    economy_tracker = EconomyTracker(events)
    economy_rounds = economy_tracker.reconstruct()

    if economy_rounds:
        # Eco round win rates
        team1_eco_rounds = [
            er for er in economy_rounds if er.team1_tier == "eco"
        ]
        team2_eco_rounds = [
            er for er in economy_rounds if er.team2_tier == "eco"
        ]

        # Match eco rounds with round outcomes
        team1_eco_wins = 0
        for eco_round in team1_eco_rounds:
            round_result = next(
                (rf for rf in round_features if rf.round_number == eco_round.round_number),
                None,
            )
            if round_result and round_result.winning_team == team1_name:
                team1_eco_wins += 1

        team2_eco_wins = 0
        for eco_round in team2_eco_rounds:
            round_result = next(
                (rf for rf in round_features if rf.round_number == eco_round.round_number),
                None,
            )
            if round_result and round_result.winning_team == team2_name:
                team2_eco_wins += 1

        features["eco_round_win_rate_team1"] = (
            team1_eco_wins / len(team1_eco_rounds) if team1_eco_rounds else 0.0
        )
        features["eco_round_win_rate_team2"] = (
            team2_eco_wins / len(team2_eco_rounds) if team2_eco_rounds else 0.0
        )

        # Average economy differential
        economy_differentials = [
            (er.team1_credits - er.team2_credits) / 5  # Per-player differential
            for er in economy_rounds
        ]
        features["avg_economy_differential"] = (
            sum(economy_differentials) / len(economy_differentials)
            if economy_differentials
            else 0.0
        )

        # Force buy rounds (buy when on eco-level credits)
        # This is approximate - force buys would be detected by comparing tier to actual credits
        # For now, use a simplified heuristic: count rounds where team had eco credits but didn't eco
        features["force_buy_rounds_team1"] = 0  # Placeholder - needs buy phase data
        features["force_buy_rounds_team2"] = 0  # Placeholder - needs buy phase data

        # Full buy rounds and eco rounds
        features["full_buy_rounds_team1"] = sum(
            1 for er in economy_rounds if er.team1_tier == "full_buy"
        )
        features["eco_rounds_team1"] = len(team1_eco_rounds)

    else:
        # No economy data available - set all economy features to None or 0
        features["eco_round_win_rate_team1"] = None
        features["eco_round_win_rate_team2"] = None
        features["avg_economy_differential"] = None
        features["force_buy_rounds_team1"] = None
        features["force_buy_rounds_team2"] = None
        features["full_buy_rounds_team1"] = None
        features["eco_rounds_team1"] = None

    return features


def _calculate_streaks(round_features: list, team_name: str) -> dict[str, int]:
    """
    Calculate max win and loss streaks for a team.

    Args:
        round_features: List of RoundFeatures
        team_name: Name of team to calculate streaks for

    Returns:
        Dict with max_win_streak and max_loss_streak
    """
    max_win_streak = 0
    max_loss_streak = 0
    current_win_streak = 0
    current_loss_streak = 0

    for rf in round_features:
        if rf.winning_team == team_name:
            # Win
            current_win_streak += 1
            current_loss_streak = 0
            max_win_streak = max(max_win_streak, current_win_streak)
        else:
            # Loss
            current_loss_streak += 1
            current_win_streak = 0
            max_loss_streak = max(max_loss_streak, current_loss_streak)

    return {
        "max_win_streak": max_win_streak,
        "max_loss_streak": max_loss_streak,
    }


def _empty_features() -> dict[str, Any]:
    """
    Return empty feature dict with None values for all features.

    Used when no valid rounds are found in the data.
    """
    return {
        # Score features
        "final_score_team1": None,
        "final_score_team2": None,
        "score_differential": None,
        "total_rounds": None,
        "went_to_overtime": None,
        "map_winner": None,
        # Pistol features
        "pistol_round1_winner": None,
        "pistol_round2_winner": None,
        "pistol_rounds_won_team1": None,
        # Half features
        "first_half_score_team1": None,
        "first_half_score_team2": None,
        "second_half_score_team1": None,
        "second_half_score_team2": None,
        # Momentum features
        "max_win_streak_team1": None,
        "max_win_streak_team2": None,
        "max_loss_streak_team1": None,
        "max_loss_streak_team2": None,
        "comeback_from_behind": None,
        # Combat features
        "first_blood_rate_team1": None,
        "first_blood_rate_team2": None,
        "clutch_rounds_team1": None,
        "clutch_rounds_team2": None,
        "multi_kill_rounds_team1": None,
        "multi_kill_rounds_team2": None,
        # Side performance features
        "attack_win_rate_team1": None,
        "defense_win_rate_team1": None,
        "attack_win_rate_team2": None,
        "defense_win_rate_team2": None,
        # Economy features
        "eco_round_win_rate_team1": None,
        "eco_round_win_rate_team2": None,
        "avg_economy_differential": None,
        "force_buy_rounds_team1": None,
        "force_buy_rounds_team2": None,
        "full_buy_rounds_team1": None,
        "eco_rounds_team1": None,
    }
