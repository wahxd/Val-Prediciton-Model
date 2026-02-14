"""Round-level feature extraction from Valoscribe events.

This module extracts per-round features that capture game state at the round level:
- Score progression and differentials
- Spike plant/defuse events
- Kill counts and differentials
- Side tracking (attack/defense)

These features serve as building blocks for map-level aggregation.
"""

from dataclasses import dataclass
from collections import defaultdict

from src.data.schemas import ValoscribeEvent, RoundEndEvent, KillEvent, SpikePlantEvent, SpikeDefuseEvent


@dataclass
class RoundFeatures:
    """Per-round feature set extracted from events."""

    round_number: int
    winning_team: str
    score_team1: int  # Cumulative after round
    score_team2: int  # Cumulative after round
    score_differential: int  # team1 - team2 (positive = team1 leading)
    spike_planted: bool
    spike_defused: bool
    kills_team1: int  # Kills by team1 this round
    kills_team2: int  # Kills by team2 this round
    kill_differential: int  # team1_kills - team2_kills
    team1_side: str | None  # "attack" or "defense" (None for backward compatibility)
    team2_side: str | None


def extract_round_features(events: list[ValoscribeEvent]) -> list[RoundFeatures]:
    """
    Extract per-round features from a list of Valoscribe events.

    Groups events by round number and extracts game state features for each round.
    Handles edge cases like missing round_end events, rounds with no kills, and
    missing sides field for backward compatibility with pre-Phase 6 data.

    Args:
        events: List of all events for a single map

    Returns:
        List of RoundFeatures, one per complete round (rounds without round_end
        events are skipped)

    Example:
        >>> events = load_events_from_jsonl("map_123/events.jsonl")
        >>> round_features = extract_round_features(events)
        >>> for rf in round_features:
        ...     print(f"Round {rf.round_number}: {rf.winning_team} wins")
    """
    # Group events by round number
    rounds_dict: dict[int, list[ValoscribeEvent]] = defaultdict(list)
    for event in events:
        rounds_dict[event.round].append(event)

    round_features_list = []

    # Process each round
    for round_num in sorted(rounds_dict.keys()):
        round_events = rounds_dict[round_num]

        # Find round_end event (required for complete round)
        round_end = None
        for event in round_events:
            if isinstance(event, RoundEndEvent):
                round_end = event
                break

        # Skip rounds without round_end (incomplete round)
        if round_end is None:
            continue

        # Extract basic round info from round_end
        winning_team = round_end.winning_team
        score_team1 = round_end.score_team1
        score_team2 = round_end.score_team2
        score_differential = score_team1 - score_team2

        # Extract sides if available (Phase 6+)
        team1_side = None
        team2_side = None
        if round_end.sides is not None:
            # sides is a dict like {"Team A": "attack", "Team B": "defense"}
            # We need to map to team1/team2 consistently
            # For now, we'll extract in the order they appear
            sides_list = list(round_end.sides.values())
            if len(sides_list) >= 2:
                team1_side = sides_list[0]
                team2_side = sides_list[1]
            elif len(sides_list) == 1:
                # Only one team side tracked (edge case)
                team1_side = sides_list[0]

        # Check for spike events
        spike_planted = any(isinstance(e, SpikePlantEvent) for e in round_events)
        spike_defused = any(isinstance(e, SpikeDefuseEvent) for e in round_events)

        # Count kills per team
        kills_team1 = 0
        kills_team2 = 0

        for event in round_events:
            if isinstance(event, KillEvent):
                # Determine which team got the kill
                # We need to match killer_team to team1/team2
                # Since we don't have team names in this function, we'll use the teams
                # from the round_end event's sides dict keys if available
                # Otherwise, we'll count based on killer_team string directly

                # For now, we'll assume team1 is the first team in the sides dict
                # and team2 is the second. If no sides, we can't reliably map.
                if round_end.sides is not None:
                    team_names = list(round_end.sides.keys())
                    if len(team_names) >= 2:
                        team1_name = team_names[0]
                        team2_name = team_names[1]

                        if event.killer_team == team1_name:
                            kills_team1 += 1
                        elif event.killer_team == team2_name:
                            kills_team2 += 1
                    elif len(team_names) == 1:
                        # Only one team tracked
                        team1_name = team_names[0]
                        if event.killer_team == team1_name:
                            kills_team1 += 1
                        else:
                            kills_team2 += 1
                else:
                    # No sides field - we can't reliably map team names to team1/team2
                    # For backward compatibility, we'll use a heuristic:
                    # First unique killer_team encountered = team1, second = team2
                    # This is a best-effort approach for old data
                    pass  # We'll handle this with a separate pass

        # Backward compatibility: if no sides, infer team mapping from kill events
        if round_end.sides is None:
            # Build team name mapping from all kill events
            unique_teams = set()
            for event in round_events:
                if isinstance(event, KillEvent):
                    unique_teams.add(event.killer_team)

            team_list = sorted(list(unique_teams))  # Sort for consistency
            team1_name = team_list[0] if len(team_list) > 0 else None
            team2_name = team_list[1] if len(team_list) > 1 else None

            # Recount kills with inferred team mapping
            kills_team1 = 0
            kills_team2 = 0
            for event in round_events:
                if isinstance(event, KillEvent):
                    if team1_name and event.killer_team == team1_name:
                        kills_team1 += 1
                    elif team2_name and event.killer_team == team2_name:
                        kills_team2 += 1

        kill_differential = kills_team1 - kills_team2

        # Create RoundFeatures instance
        rf = RoundFeatures(
            round_number=round_num,
            winning_team=winning_team,
            score_team1=score_team1,
            score_team2=score_team2,
            score_differential=score_differential,
            spike_planted=spike_planted,
            spike_defused=spike_defused,
            kills_team1=kills_team1,
            kills_team2=kills_team2,
            kill_differential=kill_differential,
            team1_side=team1_side,
            team2_side=team2_side,
        )

        round_features_list.append(rf)

    return round_features_list
