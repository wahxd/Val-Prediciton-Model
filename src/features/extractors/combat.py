"""Combat metrics and side performance feature extraction.

This module extracts combat-focused features from Valoscribe events:
- First blood identification per round
- Clutch round detection (1vX situations)
- Multi-kill detection (2+ kills in short time window)
- Side performance (attack/defense win rates)
- Anti-eco conversion rates

These features capture tactical performance beyond basic round outcomes.
"""

from dataclasses import dataclass
from collections import defaultdict
from typing import Dict, List

from src.data.schemas import (
    ValoscribeEvent,
    KillEvent,
    RoundEndEvent,
    RoundStartEvent,
    BuyPhaseEvent,
)


@dataclass
class FirstBlood:
    """First kill of a round."""

    round_number: int
    killer: str
    killer_team: str
    victim: str
    timestamp: float


@dataclass
class ClutchRound:
    """Round won by a single player in a 1vX situation."""

    round_number: int
    clutch_player: str
    clutch_team: str
    opponents_remaining: int


@dataclass
class MultiKill:
    """Multiple kills by same player in short time window."""

    round_number: int
    player: str
    player_team: str
    kill_count: int
    time_window: float  # seconds between first and last kill


@dataclass
class SidePerformance:
    """Attack and defense performance per team."""

    team1_attack_wins: int
    team1_attack_rounds: int
    team1_defense_wins: int
    team1_defense_rounds: int
    team2_attack_wins: int
    team2_attack_rounds: int
    team2_defense_wins: int
    team2_defense_rounds: int

    @property
    def team1_attack_win_rate(self) -> float:
        """Team 1 attack win rate (0.0-1.0)."""
        return self.team1_attack_wins / self.team1_attack_rounds if self.team1_attack_rounds > 0 else 0.0

    @property
    def team1_defense_win_rate(self) -> float:
        """Team 1 defense win rate (0.0-1.0)."""
        return self.team1_defense_wins / self.team1_defense_rounds if self.team1_defense_rounds > 0 else 0.0

    @property
    def team2_attack_win_rate(self) -> float:
        """Team 2 attack win rate (0.0-1.0)."""
        return self.team2_attack_wins / self.team2_attack_rounds if self.team2_attack_rounds > 0 else 0.0

    @property
    def team2_defense_win_rate(self) -> float:
        """Team 2 defense win rate (0.0-1.0)."""
        return self.team2_defense_wins / self.team2_defense_rounds if self.team2_defense_rounds > 0 else 0.0


@dataclass
class AntiEcoStats:
    """Anti-eco conversion statistics (wins against eco-tier opponents)."""

    team1_anti_eco_wins: int
    team1_anti_eco_rounds: int
    team2_anti_eco_wins: int
    team2_anti_eco_rounds: int

    @property
    def team1_conversion_rate(self) -> float:
        """Team 1 anti-eco conversion rate (0.0-1.0)."""
        return self.team1_anti_eco_wins / self.team1_anti_eco_rounds if self.team1_anti_eco_rounds > 0 else 0.0

    @property
    def team2_conversion_rate(self) -> float:
        """Team 2 anti-eco conversion rate (0.0-1.0)."""
        return self.team2_anti_eco_wins / self.team2_anti_eco_rounds if self.team2_anti_eco_rounds > 0 else 0.0


def extract_first_bloods(events: list[ValoscribeEvent]) -> dict[int, FirstBlood]:
    """
    Extract first blood (first kill) for each round.

    Args:
        events: List of all events for a single map

    Returns:
        Dictionary mapping round number to FirstBlood instance.
        Rounds with no kills have no entry.

    Example:
        >>> first_bloods = extract_first_bloods(events)
        >>> if 1 in first_bloods:
        ...     fb = first_bloods[1]
        ...     print(f"Round 1 FB: {fb.killer} ({fb.killer_team})")
    """
    # Group kill events by round
    kills_by_round: dict[int, list[KillEvent]] = defaultdict(list)
    for event in events:
        if isinstance(event, KillEvent):
            kills_by_round[event.round].append(event)

    first_bloods = {}

    for round_num, kills in kills_by_round.items():
        if not kills:
            continue

        # Find kill with lowest timestamp
        first_kill = min(kills, key=lambda k: k.timestamp)

        first_bloods[round_num] = FirstBlood(
            round_number=round_num,
            killer=first_kill.killer,
            killer_team=first_kill.killer_team,
            victim=first_kill.victim,
            timestamp=first_kill.timestamp,
        )

    return first_bloods


def extract_clutch_rounds(events: list[ValoscribeEvent]) -> list[ClutchRound]:
    """
    Detect clutch rounds (1 player vs 2+ opponents wins).

    Simplified detection: if the winning team had only 1 unique killer in the
    final kills of the round and got 2+ kills, it's likely a clutch.

    Args:
        events: List of all events for a single map

    Returns:
        List of ClutchRound instances

    Example:
        >>> clutches = extract_clutch_rounds(events)
        >>> for clutch in clutches:
        ...     print(f"Round {clutch.round_number}: {clutch.clutch_player} 1v{clutch.opponents_remaining}")
    """
    # Group events by round
    rounds_dict: dict[int, list[ValoscribeEvent]] = defaultdict(list)
    for event in events:
        rounds_dict[event.round].append(event)

    clutch_rounds = []

    for round_num, round_events in rounds_dict.items():
        # Find round_end to identify winner
        round_end = None
        for event in round_events:
            if isinstance(event, RoundEndEvent):
                round_end = event
                break

        if round_end is None:
            continue

        winning_team = round_end.winning_team

        # Get all kills in the round
        kills = [e for e in round_events if isinstance(e, KillEvent)]

        if len(kills) < 2:
            # Need at least 2 kills for a clutch
            continue

        # Get kills by the winning team
        winning_kills = [k for k in kills if k.killer_team == winning_team]

        if len(winning_kills) < 2:
            continue

        # Check if all winning kills were by the same player
        unique_killers = set(k.killer for k in winning_kills)

        if len(unique_killers) == 1:
            # Single player got all kills for winning team
            clutch_player = unique_killers.pop()

            # Count how many opponents they killed (opponents_remaining)
            opponents_killed = len(winning_kills)

            # Only consider it a clutch if they killed 2+ opponents
            if opponents_killed >= 2:
                clutch_rounds.append(
                    ClutchRound(
                        round_number=round_num,
                        clutch_player=clutch_player,
                        clutch_team=winning_team,
                        opponents_remaining=opponents_killed,
                    )
                )

    return clutch_rounds


def extract_multi_kills(events: list[ValoscribeEvent]) -> list[MultiKill]:
    """
    Detect multi-kills (2+ kills by same player within 10 seconds in same round).

    Args:
        events: List of all events for a single map

    Returns:
        List of MultiKill instances

    Example:
        >>> multi_kills = extract_multi_kills(events)
        >>> for mk in multi_kills:
        ...     print(f"Round {mk.round_number}: {mk.player} got {mk.kill_count} kills in {mk.time_window:.1f}s")
    """
    # Group kill events by round and player
    kills_by_round_player: dict[tuple[int, str], list[KillEvent]] = defaultdict(list)

    for event in events:
        if isinstance(event, KillEvent):
            key = (event.round, event.killer)
            kills_by_round_player[key].append(event)

    multi_kills = []

    for (round_num, player), kills in kills_by_round_player.items():
        if len(kills) < 2:
            continue

        # Sort by timestamp
        kills.sort(key=lambda k: k.timestamp)

        # Find sequences of 2+ kills within 10 seconds
        i = 0
        while i < len(kills):
            # Start a potential multi-kill sequence
            sequence_start = i
            sequence_end = i

            # Extend sequence while kills are within 10s window
            while sequence_end < len(kills) - 1:
                time_gap = kills[sequence_end + 1].timestamp - kills[sequence_start].timestamp
                if time_gap <= 10.0:
                    sequence_end += 1
                else:
                    break

            # If sequence has 2+ kills, record it
            sequence_length = sequence_end - sequence_start + 1
            if sequence_length >= 2:
                time_window = kills[sequence_end].timestamp - kills[sequence_start].timestamp

                # Get team from first kill in sequence
                player_team = kills[sequence_start].killer_team

                multi_kills.append(
                    MultiKill(
                        round_number=round_num,
                        player=player,
                        player_team=player_team,
                        kill_count=sequence_length,
                        time_window=time_window,
                    )
                )

            # Move to next potential sequence
            i = sequence_end + 1

    return multi_kills


def extract_side_performance(events: list[ValoscribeEvent]) -> SidePerformance:
    """
    Compute attack and defense win rates per team.

    Uses sides field from round_end events when available. For data without
    sides field, infers from round number (R1-12 = initial sides, R13-24 = swapped).

    Args:
        events: List of all events for a single map

    Returns:
        SidePerformance instance with win counts and rates

    Example:
        >>> side_perf = extract_side_performance(events)
        >>> print(f"Team 1 attack: {side_perf.team1_attack_win_rate:.2%}")
        >>> print(f"Team 1 defense: {side_perf.team1_defense_win_rate:.2%}")
    """
    # Initialize counters
    team1_attack_wins = 0
    team1_attack_rounds = 0
    team1_defense_wins = 0
    team1_defense_rounds = 0
    team2_attack_wins = 0
    team2_attack_rounds = 0
    team2_defense_wins = 0
    team2_defense_rounds = 0

    # Get all round_end events
    round_ends = [e for e in events if isinstance(e, RoundEndEvent)]

    if not round_ends:
        # No round data
        return SidePerformance(
            team1_attack_wins=0,
            team1_attack_rounds=0,
            team1_defense_wins=0,
            team1_defense_rounds=0,
            team2_attack_wins=0,
            team2_attack_rounds=0,
            team2_defense_wins=0,
            team2_defense_rounds=0,
        )

    # Determine team names from first round with sides
    team1_name = None
    team2_name = None

    for re in round_ends:
        if re.sides is not None and len(re.sides) >= 2:
            team_names = list(re.sides.keys())
            team1_name = team_names[0]
            team2_name = team_names[1]
            break

    # If no sides field found, try to infer from round_end events
    if team1_name is None and round_ends:
        # Use winning_team from first two rounds to identify teams
        unique_teams = set()
        for re in round_ends[:5]:  # Check first 5 rounds to find both teams
            unique_teams.add(re.winning_team)
            if len(unique_teams) >= 2:
                break

        if unique_teams:
            team_list = sorted(list(unique_teams))
            team1_name = team_list[0] if len(team_list) > 0 else None
            team2_name = team_list[1] if len(team_list) > 1 else None

    # Process each round_end
    for re in round_ends:
        round_num = re.round

        # Determine sides for this round
        if re.sides is not None and team1_name and team2_name:
            # Use explicit sides field
            team1_side = re.sides.get(team1_name)
            team2_side = re.sides.get(team2_name)
        else:
            # Infer from round number
            # Rounds 1-12: initial sides, 13-24: swapped
            # For OT (25+), swap every 2 rounds
            if round_num <= 12:
                # Use initial sides (assume team1 starts on attack)
                team1_side = "attack"
                team2_side = "defense"
            elif round_num <= 24:
                # Halftime swap
                team1_side = "defense"
                team2_side = "attack"
            else:
                # OT: swap every 2 rounds
                ot_round = round_num - 24
                ot_period = (ot_round - 1) // 2
                if ot_period % 2 == 0:
                    team1_side = "defense"
                    team2_side = "attack"
                else:
                    team1_side = "attack"
                    team2_side = "defense"

        # Count rounds and wins
        if team1_side == "attack":
            team1_attack_rounds += 1
            if re.winning_team == team1_name:
                team1_attack_wins += 1
        elif team1_side == "defense":
            team1_defense_rounds += 1
            if re.winning_team == team1_name:
                team1_defense_wins += 1

        if team2_side == "attack":
            team2_attack_rounds += 1
            if re.winning_team == team2_name:
                team2_attack_wins += 1
        elif team2_side == "defense":
            team2_defense_rounds += 1
            if re.winning_team == team2_name:
                team2_defense_wins += 1

    return SidePerformance(
        team1_attack_wins=team1_attack_wins,
        team1_attack_rounds=team1_attack_rounds,
        team1_defense_wins=team1_defense_wins,
        team1_defense_rounds=team1_defense_rounds,
        team2_attack_wins=team2_attack_wins,
        team2_attack_rounds=team2_attack_rounds,
        team2_defense_wins=team2_defense_wins,
        team2_defense_rounds=team2_defense_rounds,
    )


def compute_anti_eco_stats(
    events: list[ValoscribeEvent], economy_tiers: list | None = None
) -> AntiEcoStats:
    """
    Track anti-eco conversion rates (wins when opponent is on eco).

    Requires economy tier data from Plan 01. Gracefully returns zero stats
    if economy_tiers is None.

    Args:
        events: List of all events for a single map
        economy_tiers: Optional list of economy tier classifications per round
            (from Plan 01's economy feature extraction)

    Returns:
        AntiEcoStats instance with conversion counts and rates

    Example:
        >>> stats = compute_anti_eco_stats(events, economy_tiers)
        >>> print(f"Team 1 anti-eco: {stats.team1_conversion_rate:.2%}")
    """
    if economy_tiers is None:
        # No economy data available, return zeros
        return AntiEcoStats(
            team1_anti_eco_wins=0,
            team1_anti_eco_rounds=0,
            team2_anti_eco_wins=0,
            team2_anti_eco_rounds=0,
        )

    # Initialize counters
    team1_anti_eco_wins = 0
    team1_anti_eco_rounds = 0
    team2_anti_eco_wins = 0
    team2_anti_eco_rounds = 0

    # Get round_end events for winners
    round_ends = [e for e in events if isinstance(e, RoundEndEvent)]

    # Determine team names
    team1_name = None
    team2_name = None

    for re in round_ends:
        if re.sides is not None and len(re.sides) >= 2:
            team_names = list(re.sides.keys())
            team1_name = team_names[0]
            team2_name = team_names[1]
            break

    if team1_name is None and round_ends:
        unique_teams = set()
        for re in round_ends[:5]:
            unique_teams.add(re.winning_team)
            if len(unique_teams) >= 2:
                break
        if unique_teams:
            team_list = sorted(list(unique_teams))
            team1_name = team_list[0] if len(team_list) > 0 else None
            team2_name = team_list[1] if len(team_list) > 1 else None

    # Process rounds where one team is on eco and other is on full_buy
    # This is a simplified version - full implementation would come from Plan 01
    # For now, we'll just return the initialized zeros as a placeholder

    return AntiEcoStats(
        team1_anti_eco_wins=team1_anti_eco_wins,
        team1_anti_eco_rounds=team1_anti_eco_rounds,
        team2_anti_eco_wins=team2_anti_eco_wins,
        team2_anti_eco_rounds=team2_anti_eco_rounds,
    )
