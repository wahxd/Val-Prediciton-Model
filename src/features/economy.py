"""Economy reconstruction and tier classification for Valorant matches.

This module tracks team credits per round using Valorant's deterministic economy rules
and classifies economy tiers for feature engineering.

Economy Rules (from Valorant game mechanics):
- Pistol rounds (R1, R13): 800 credits per player
- Win bonus: 3000 credits per player
- Loss bonus escalation: 1900 -> 2400 -> 2900 (max, per player)
- Spike plant bonus: 300 credits per player (attacking team, even on loss)
- Kill reward: ~200 credits per kill (simplified average)
- Overtime: flat 5000 credits per player, no loss bonus

Economy Tier Thresholds (per-player average):
- pistol: rounds 1 and 13 (tagged separately)
- eco: 0-2500 credits
- light_buy: 2500-3500 credits
- half_buy: 3500-3900 credits
- full_buy: 3900+ credits

NOTE: Credit tracking is APPROXIMATE. The goal is tier classification, not exact values.
We don't track individual player spending or exact loadout costs. Assumptions:
- Pistol round: players spend all ~800 credits
- Eco round: players spend ~500 credits
- Light buy: players spend ~2000 credits
- Full buy: players spend ~4000 credits (rifle + armor + abilities)
"""

from dataclasses import dataclass
from typing import Literal

from src.data.schemas import RoundEndEvent, SpikePlantEvent, ValoscribeEvent


# Economy tier types
EconomyTier = Literal["pistol", "eco", "light_buy", "half_buy", "full_buy"]

# Constants
CREDITS_PER_PLAYER_PISTOL = 800
CREDITS_PER_PLAYER_WIN_BONUS = 3000
CREDITS_PER_PLAYER_PLANT_BONUS = 300
CREDITS_PER_PLAYER_OT = 5000
LOSS_BONUS_SEQUENCE = [1900, 2400, 2900]  # Escalates per consecutive loss
PLAYERS_PER_TEAM = 5

# Spending assumptions (for credit tracking between rounds)
SPENDING_PISTOL = 800  # Spend all on pistol round
SPENDING_ECO = 500
SPENDING_LIGHT_BUY = 2000
SPENDING_HALF_BUY = 3000
SPENDING_FULL_BUY = 4000


@dataclass
class RoundEconomy:
    """Economy state for a single round.

    Attributes:
        round_number: Round number (1-indexed)
        team1_credits: Estimated team1 total credits at round start
        team2_credits: Estimated team2 total credits at round start
        team1_tier: Economy tier classification for team1
        team2_tier: Economy tier classification for team2
        team1_loss_streak: Consecutive losses entering this round
        team2_loss_streak: Consecutive losses entering this round
    """

    round_number: int
    team1_credits: int
    team2_credits: int
    team1_tier: EconomyTier
    team2_tier: EconomyTier
    team1_loss_streak: int
    team2_loss_streak: int


def is_pistol_round(round_number: int) -> bool:
    """Check if round is a pistol round (R1 or R13).

    Args:
        round_number: Round number (1-indexed)

    Returns:
        True if pistol round, False otherwise
    """
    return round_number in (1, 13)


def is_overtime_round(round_number: int, max_regulation_rounds: int = 24) -> bool:
    """Check if round is in overtime.

    Args:
        round_number: Round number (1-indexed)
        max_regulation_rounds: Maximum regulation rounds (default 24)

    Returns:
        True if overtime round, False otherwise
    """
    return round_number > max_regulation_rounds


def classify_economy_tier(
    per_player_credits: int, round_number: int
) -> EconomyTier:
    """Classify economy tier based on per-player credits.

    Pistol rounds (1 and 13) are always classified as "pistol" regardless of credits.

    Tier thresholds (non-pistol rounds):
    - eco: 0-2500
    - light_buy: 2500-3500
    - half_buy: 3500-3900
    - full_buy: 3900+

    Args:
        per_player_credits: Average credits per player
        round_number: Round number (1-indexed)

    Returns:
        Economy tier classification
    """
    if is_pistol_round(round_number):
        return "pistol"

    if per_player_credits <= 2500:
        return "eco"
    elif per_player_credits <= 3500:
        return "light_buy"
    elif per_player_credits <= 3900:
        return "half_buy"
    else:
        return "full_buy"


class EconomyTracker:
    """Tracks economy state across rounds for a single map.

    Uses Valorant's deterministic economy rules to reconstruct per-team credits
    and classify economy tiers for each round.
    """

    def __init__(self, events: list[ValoscribeEvent]):
        """Initialize tracker with map events.

        Args:
            events: All events for a single map (from Valoscribe)
        """
        self.events = events
        self.team1_name: str | None = None
        self.team2_name: str | None = None

    def _extract_teams(self) -> tuple[str, str] | None:
        """Extract team names from first round_end event.

        Returns:
            Tuple of (team1_name, team2_name) or None if no round_end events
        """
        for event in self.events:
            if isinstance(event, RoundEndEvent):
                # Determine teams from scores
                # team1 is the team with score_team1, team2 has score_team2
                # winning_team tells us which team won
                winning_team = event.winning_team

                # We need to infer team names from the winning_team and scores
                # If score_team1 increased, winning_team == team1
                # For first round, we can use winning_team as one of the teams
                # and infer the other from sides or just use a placeholder

                # Actually, we need both team names. Let's check if sides exist.
                if event.sides:
                    teams = list(event.sides.keys())
                    if len(teams) == 2:
                        return teams[0], teams[1]

                # Fallback: use winning_team as team1, infer team2 later
                # For now, just return winning_team and "Unknown"
                # This is a limitation - we need both team names
                # Let's look for teams in metadata or use generic names
                return "Team A", "Team B"

        return None

    def _get_loss_bonus(self, loss_streak: int) -> int:
        """Get loss bonus credits per player based on loss streak.

        Args:
            loss_streak: Number of consecutive losses

        Returns:
            Loss bonus credits per player
        """
        if loss_streak == 0:
            return 0
        # Loss bonus sequence: 1900, 2400, 2900 (max)
        # loss_streak 1 -> 1900, 2 -> 2400, 3+ -> 2900
        index = min(loss_streak - 1, len(LOSS_BONUS_SEQUENCE) - 1)
        return LOSS_BONUS_SEQUENCE[index]

    def _estimate_spending(self, tier: EconomyTier) -> int:
        """Estimate per-player spending based on economy tier.

        Args:
            tier: Economy tier for the round

        Returns:
            Estimated credits spent per player
        """
        if tier == "pistol":
            return SPENDING_PISTOL
        elif tier == "eco":
            return SPENDING_ECO
        elif tier == "light_buy":
            return SPENDING_LIGHT_BUY
        elif tier == "half_buy":
            return SPENDING_HALF_BUY
        else:  # full_buy
            return SPENDING_FULL_BUY

    def reconstruct(self) -> list[RoundEconomy]:
        """Reconstruct economy state for all rounds.

        Returns:
            List of RoundEconomy for each round, in chronological order
        """
        if not self.events:
            return []

        # Extract team names
        teams = self._extract_teams()
        if not teams:
            return []

        self.team1_name, self.team2_name = teams

        # Filter to relevant events and sort by round
        round_end_events: list[RoundEndEvent] = []
        spike_plants_by_round: dict[int, SpikePlantEvent] = {}

        for event in self.events:
            if isinstance(event, RoundEndEvent):
                round_end_events.append(event)
            elif isinstance(event, SpikePlantEvent):
                spike_plants_by_round[event.round] = event

        # Sort by round number
        round_end_events.sort(key=lambda e: e.round)

        results: list[RoundEconomy] = []

        # Process each round
        for i, event in enumerate(round_end_events):
            round_num = event.round

            # Calculate credits AT START of this round
            if is_pistol_round(round_num):
                # Pistol round: reset to 800 per player
                team1_credits = CREDITS_PER_PLAYER_PISTOL * PLAYERS_PER_TEAM
                team2_credits = CREDITS_PER_PLAYER_PISTOL * PLAYERS_PER_TEAM
                team1_loss_streak = 0
                team2_loss_streak = 0
            elif is_overtime_round(round_num):
                # Overtime: flat 5000 per player
                team1_credits = CREDITS_PER_PLAYER_OT * PLAYERS_PER_TEAM
                team2_credits = CREDITS_PER_PLAYER_OT * PLAYERS_PER_TEAM
            else:
                # Calculate based on previous round
                if i == 0:
                    # First round should be pistol, but handle edge case
                    team1_credits = CREDITS_PER_PLAYER_PISTOL * PLAYERS_PER_TEAM
                    team2_credits = CREDITS_PER_PLAYER_PISTOL * PLAYERS_PER_TEAM
                    team1_loss_streak = 0
                    team2_loss_streak = 0
                else:
                    # Get previous round info
                    prev_event = round_end_events[i - 1]
                    prev_round = results[-1]

                    # Start with previous round credits
                    team1_credits = prev_round.team1_credits
                    team2_credits = prev_round.team2_credits
                    team1_loss_streak = prev_round.team1_loss_streak
                    team2_loss_streak = prev_round.team2_loss_streak

                    # Subtract estimated spending
                    spending_team1 = self._estimate_spending(prev_round.team1_tier)
                    spending_team2 = self._estimate_spending(prev_round.team2_tier)
                    team1_credits -= spending_team1 * PLAYERS_PER_TEAM
                    team2_credits -= spending_team2 * PLAYERS_PER_TEAM
                    team1_credits = max(0, team1_credits)
                    team2_credits = max(0, team2_credits)

                    # Determine who won previous round
                    team1_won_prev = self._team1_won(prev_event)

                    # Apply win/loss bonuses
                    if team1_won_prev:
                        team1_credits += CREDITS_PER_PLAYER_WIN_BONUS * PLAYERS_PER_TEAM
                        team2_loss_streak += 1
                        team2_credits += self._get_loss_bonus(team2_loss_streak) * PLAYERS_PER_TEAM
                        team1_loss_streak = 0
                    else:
                        team2_credits += CREDITS_PER_PLAYER_WIN_BONUS * PLAYERS_PER_TEAM
                        team1_loss_streak += 1
                        team1_credits += self._get_loss_bonus(team1_loss_streak) * PLAYERS_PER_TEAM
                        team2_loss_streak = 0

                    # Apply spike plant bonus from previous round
                    prev_round_num = prev_event.round
                    if prev_round_num in spike_plants_by_round:
                        if prev_event.sides:
                            for team, side in prev_event.sides.items():
                                if side == "attack":
                                    if team == self.team1_name:
                                        team1_credits += CREDITS_PER_PLAYER_PLANT_BONUS * PLAYERS_PER_TEAM
                                    elif team == self.team2_name:
                                        team2_credits += CREDITS_PER_PLAYER_PLANT_BONUS * PLAYERS_PER_TEAM
                                    break

            # Classify tiers for this round
            team1_per_player = team1_credits / PLAYERS_PER_TEAM
            team2_per_player = team2_credits / PLAYERS_PER_TEAM
            team1_tier = classify_economy_tier(int(team1_per_player), round_num)
            team2_tier = classify_economy_tier(int(team2_per_player), round_num)

            # Record round economy
            results.append(
                RoundEconomy(
                    round_number=round_num,
                    team1_credits=team1_credits,
                    team2_credits=team2_credits,
                    team1_tier=team1_tier,
                    team2_tier=team2_tier,
                    team1_loss_streak=team1_loss_streak,
                    team2_loss_streak=team2_loss_streak,
                )
            )

        return results

    def _team1_won(self, event: RoundEndEvent) -> bool:
        """Determine if team1 won the round.

        Args:
            event: RoundEndEvent

        Returns:
            True if team1 won, False if team2 won
        """
        if event.sides:
            return event.winning_team == self.team1_name
        else:
            # Fallback: check if winning_team matches our team1_name pattern
            return event.winning_team == self.team1_name or "Team A" in event.winning_team
