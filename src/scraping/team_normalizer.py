"""Team name normalization for VLR.gg scraping.

VLR.gg uses inconsistent team names across pages (abbreviations, suffixes, etc.).
This module provides fuzzy matching with manual overrides for common cases.
"""

import re
import structlog
from rapidfuzz import fuzz, process

logger = structlog.get_logger()


class TeamNormalizer:
    """Normalize VLR.gg team names to canonical forms.

    Uses a combination of:
    1. Manual overrides for known abbreviations/variants
    2. RapidFuzz token_sort_ratio for fuzzy matching against known teams

    Example:
        normalizer = TeamNormalizer()
        normalized = normalizer.normalize("GenG", ["Gen.G Esports", "T1"])
        # Returns "Gen.G Esports" (matched via manual override or fuzzy match)
    """

    DEFAULT_OVERRIDES = {
        # VCT Americas 2024
        "SEN": "Sentinels",
        "Sentinels": "Sentinels",
        "NRG": "NRG",
        "NRG Esports": "NRG",
        "EG": "Evil Geniuses",
        "Evil Geniuses": "Evil Geniuses",
        "C9": "Cloud9",
        "Cloud9": "Cloud9",
        "100T": "100 Thieves",
        "100 Thieves": "100 Thieves",
        "LOUD": "LOUD",
        "FURIA": "FURIA Esports",
        "FURIA Esports": "FURIA Esports",
        "LEV": "Leviatán",
        "Leviatán": "Leviatán",
        "KRÜ": "KRÜ Esports",
        "KRÜ Esports": "KRÜ Esports",
        # VCT Pacific 2024
        "GenG": "Gen.G Esports",
        "Gen.G": "Gen.G Esports",
        "Gen.G Esports": "Gen.G Esports",
        "PRX": "Paper Rex",
        "Paper Rex": "Paper Rex",
        "DRX": "DRX",
        "T1": "T1",
        "ZETA": "ZETA DIVISION",
        "ZETA DIVISION": "ZETA DIVISION",
        # VCT EMEA 2024
        "FNC": "Fnatic",
        "Fnatic": "Fnatic",
        "TH": "Team Heretics",
        "Team Heretics": "Team Heretics",
        "NAVI": "Natus Vincere",
        "Natus Vincere": "Natus Vincere",
        "FUT": "FUT Esports",
        "FUT Esports": "FUT Esports",
    }

    def __init__(self, manual_overrides: dict[str, str] | None = None):
        """Initialize normalizer with optional custom overrides.

        Args:
            manual_overrides: Custom team name mappings (overrides defaults)
        """
        self.manual_overrides = self.DEFAULT_OVERRIDES.copy()
        if manual_overrides:
            self.manual_overrides.update(manual_overrides)

    def normalize(
        self,
        vlr_name: str,
        known_teams: list[str] | None = None
    ) -> str:
        """Normalize a VLR.gg team name to canonical form.

        Process:
        1. Check manual overrides (exact match)
        2. If known_teams provided, fuzzy match with RapidFuzz
        3. Threshold: >= 85 score -> return match
        4. Below threshold -> log warning, return original

        Args:
            vlr_name: Team name from VLR.gg
            known_teams: List of known canonical team names for fuzzy matching

        Returns:
            Canonical team name (or original if no confident match)

        Example:
            >>> normalizer = TeamNormalizer()
            >>> normalizer.normalize("GenG", ["Gen.G Esports"])
            'Gen.G Esports'
            >>> normalizer.normalize("Unknown Team", ["Gen.G Esports"])
            'Unknown Team'  # Falls back to original
        """
        # Step 1: Check manual overrides
        if vlr_name in self.manual_overrides:
            return self.manual_overrides[vlr_name]

        # Step 2: Fuzzy match if known_teams provided
        if known_teams:
            result = process.extractOne(
                vlr_name,
                known_teams,
                scorer=fuzz.token_sort_ratio
            )

            if result:
                match, score, _ = result
                if score >= 85:
                    logger.debug(
                        "fuzzy_team_match",
                        vlr_name=vlr_name,
                        matched=match,
                        score=score
                    )
                    return match
                else:
                    logger.warning(
                        "low_confidence_team_match",
                        vlr_name=vlr_name,
                        best_match=match,
                        score=score
                    )

        # Step 3: Fall back to original
        return vlr_name

    def extract_player_vlr_id(self, player_link_href: str) -> int | None:
        """Extract player VLR ID from player link href.

        VLR.gg player links follow pattern: /player/{ID}/{name}

        Args:
            player_link_href: href attribute from player link

        Returns:
            Player ID as int, or None if invalid format

        Example:
            >>> normalizer = TeamNormalizer()
            >>> normalizer.extract_player_vlr_id("/player/12345/tenz")
            12345
            >>> normalizer.extract_player_vlr_id("/invalid/path")
            None
        """
        # Pattern: /player/{ID}/{name} or /player/{ID}
        match = re.match(r'^/player/(\d+)(?:/.*)?$', player_link_href)
        if match:
            return int(match.group(1))
        return None
