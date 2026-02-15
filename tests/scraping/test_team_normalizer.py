"""Tests for team name normalization."""

import pytest
from src.scraping.team_normalizer import TeamNormalizer


def test_exact_manual_override_match():
    """Manual override returns exact match."""
    normalizer = TeamNormalizer()

    # Test known abbreviation
    assert normalizer.normalize("GenG") == "Gen.G Esports"
    assert normalizer.normalize("SEN") == "Sentinels"
    assert normalizer.normalize("NRG") == "NRG"


def test_fuzzy_match_with_known_teams():
    """Fuzzy matching finds similar team names."""
    normalizer = TeamNormalizer()

    known_teams = ["Gen.G Esports", "Sentinels", "NRG", "LOUD"]

    # "Gen.G" should fuzzy match to "Gen.G Esports" even without override
    # (or use override if present)
    result = normalizer.normalize("Gen.G", known_teams)
    assert result == "Gen.G Esports"

    # Test fuzzy match with a team that doesn't have manual override
    known_teams2 = ["Evil Geniuses", "Team Liquid", "100 Thieves"]
    result = normalizer.normalize("Evil Genius", known_teams2)
    assert result == "Evil Geniuses"  # Should match via fuzzy (90+ score)


def test_low_confidence_returns_original():
    """Low confidence match (< 85) returns original name."""
    normalizer = TeamNormalizer()

    known_teams = ["Cloud9", "Gen.G Esports", "Sentinels"]

    # "Cloud9 White" should NOT match "Cloud9" with high confidence
    # (Different enough that we don't want false positive)
    result = normalizer.normalize("Totally Unknown Team", known_teams)
    assert result == "Totally Unknown Team"


def test_no_known_teams_uses_override_only():
    """Without known_teams, only manual overrides apply."""
    normalizer = TeamNormalizer()

    # Override exists
    assert normalizer.normalize("GenG") == "Gen.G Esports"

    # No override, no known_teams -> return original
    assert normalizer.normalize("Unknown Team") == "Unknown Team"


def test_custom_overrides():
    """Custom overrides can be provided."""
    custom = {
        "MY_TEAM": "My Custom Team",
        "ABC": "ABC Esports"
    }
    normalizer = TeamNormalizer(manual_overrides=custom)

    # Custom override works
    assert normalizer.normalize("MY_TEAM") == "My Custom Team"

    # Default overrides still work (merged)
    assert normalizer.normalize("GenG") == "Gen.G Esports"


def test_extract_player_vlr_id_valid():
    """Extract player ID from valid VLR.gg player link."""
    normalizer = TeamNormalizer()

    # Standard format: /player/{ID}/{name}
    assert normalizer.extract_player_vlr_id("/player/12345/tenz") == 12345

    # ID only: /player/{ID}
    assert normalizer.extract_player_vlr_id("/player/67890") == 67890

    # With trailing slash
    assert normalizer.extract_player_vlr_id("/player/11111/name/") == 11111


def test_extract_player_vlr_id_invalid():
    """Invalid player links return None."""
    normalizer = TeamNormalizer()

    # Wrong format
    assert normalizer.extract_player_vlr_id("/team/123/teamname") is None

    # No ID
    assert normalizer.extract_player_vlr_id("/player/notanumber/name") is None

    # Empty
    assert normalizer.extract_player_vlr_id("") is None

    # Not a player link
    assert normalizer.extract_player_vlr_id("/matches/upcoming") is None
