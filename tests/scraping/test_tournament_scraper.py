"""Tests for TournamentScraper integration."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from src.pipeline.manifest import ProcessingManifest, VODRecord
from src.scraping.tournament_scraper import TournamentScraper
from src.scraping.youtube_vod_finder import QuotaExhaustedError


@pytest.fixture
def temp_manifest(tmp_path):
    """Create a temporary manifest for testing."""
    manifest_path = tmp_path / "manifest.json"
    return ProcessingManifest(manifest_path)


@pytest.fixture
def mock_match_data():
    """Mock match data from VLRMatchScraper."""
    return {
        "match_url": "https://www.vlr.gg/12345/team-a-vs-team-b",
        "teams": ["Sentinels", "Fnatic"],
        "match_score": "2-1",
        "date": "2024-08-01",
        "maps": [
            {
                "map_number": 1,
                "map_name": "Ascent",
                "map_score": "13-9",
                "vod_url": "https://youtube.com/watch?v=valid_video_1",
                "starting_sides": {"team1": "attack", "team2": "defense"},
                "player_stats": {
                    "TenZ": {
                        "acs": 280.5,
                        "kills": 24,
                        "deaths": 16,
                        "assists": 5,
                        "kast_pct": 75.0,
                        "adr": 165.2,
                        "hs_pct": 28.5,
                        "fk": 3,
                        "fd": 1
                    }
                },
                "agent_compositions": [
                    {"name": "TenZ", "team": "Sentinels", "agent": "jett"}
                ],
                "player_vlr_ids": {"TenZ": 9001}
            },
            {
                "map_number": 2,
                "map_name": "Bind",
                "map_score": "11-13",
                "vod_url": None,  # No VLR URL
                "starting_sides": {"team1": "defense", "team2": "attack"},
                "player_stats": {},
                "agent_compositions": [],
                "player_vlr_ids": {}
            },
            {
                "map_number": 3,
                "map_name": "Haven",
                "map_score": "13-8",
                "vod_url": "https://youtube.com/watch?v=private_video",  # Invalid
                "starting_sides": {"team1": "attack", "team2": "defense"},
                "player_stats": {},
                "agent_compositions": [],
                "player_vlr_ids": {}
            }
        ]
    }


@pytest.mark.asyncio
async def test_scrape_tournament_creates_vod_records(temp_manifest, mock_match_data):
    """Test that scrape_tournament creates VODRecords with correct fields."""
    # Mock VLREventScraper
    with patch("src.scraping.tournament_scraper.VLREventScraper") as mock_scraper_class:
        mock_scraper = AsyncMock()
        mock_scraper_class.return_value.__aenter__.return_value = mock_scraper

        # Mock discover_match_urls
        mock_scraper.discover_match_urls.return_value = [
            "https://www.vlr.gg/12345/team-a-vs-team-b"
        ]

        # Mock scrape_match
        mock_scraper.scrape_match.return_value = mock_match_data

        # Mock YouTubeVODFinder
        with patch("src.scraping.tournament_scraper.YouTubeVODFinder") as mock_youtube_class:
            mock_youtube = Mock()
            mock_youtube_class.return_value = mock_youtube

            # Map 1: VLR URL valid
            # Map 2: No VLR URL, YouTube search finds video
            # Map 3: VLR URL invalid, YouTube search finds nothing
            mock_youtube.extract_video_id.side_effect = lambda url: (
                "valid_video_1" if "valid_video_1" in url else
                "private_video" if "private_video" in url else
                None
            )
            mock_youtube.validate_video.side_effect = lambda vid: vid == "valid_video_1"
            mock_youtube.find_map_vod.side_effect = lambda **kwargs: (
                "https://youtube.com/watch?v=search_result_2"
                if kwargs.get("map_number") == 2 else
                None
            )

            # Create scraper
            scraper = TournamentScraper(
                manifest=temp_manifest,
                youtube_api_key="test_key"
            )

            # Scrape tournament
            stats = await scraper.scrape_tournament(
                "https://www.vlr.gg/event/matches/1921/test-tournament/",
                "Test Tournament"
            )

            # Verify stats
            assert stats["matches_found"] == 1
            assert stats["maps_found"] == 3
            assert stats["maps_with_vod"] == 2  # Maps 1 and 2
            assert stats["maps_skipped"] == 1  # Map 3

            # Verify manifest records
            assert len(temp_manifest.records) == 2

            # Check Map 1 record
            record_1 = temp_manifest.records["12345_map1"]
            assert record_1.vod_id == "12345_map1"
            assert record_1.youtube_url == "https://youtube.com/watch?v=valid_video_1"
            assert record_1.vlr_match_url == "https://www.vlr.gg/12345/team-a-vs-team-b"
            assert record_1.teams == ["Sentinels", "Fnatic"]
            assert record_1.map_name == "Ascent"
            assert record_1.map_number == 1
            assert record_1.tournament == "Test Tournament"
            assert record_1.date == "2024-08-01"
            assert record_1.status == "pending"
            assert record_1.player_stats is not None
            assert "TenZ" in record_1.player_stats
            assert record_1.agent_compositions is not None
            assert record_1.player_vlr_ids == {"TenZ": 9001}
            assert record_1.match_score == "2-1"

            # Check Map 2 record (YouTube search result)
            record_2 = temp_manifest.records["12345_map2"]
            assert record_2.vod_id == "12345_map2"
            assert record_2.youtube_url == "https://youtube.com/watch?v=search_result_2"
            assert record_2.map_name == "Bind"
            assert record_2.map_number == 2


@pytest.mark.asyncio
async def test_maps_without_vods_skipped(temp_manifest, mock_match_data):
    """Test that maps without accessible VODs are skipped (not stored)."""
    with patch("src.scraping.tournament_scraper.VLREventScraper") as mock_scraper_class:
        mock_scraper = AsyncMock()
        mock_scraper_class.return_value.__aenter__.return_value = mock_scraper

        mock_scraper.discover_match_urls.return_value = [
            "https://www.vlr.gg/12345/team-a-vs-team-b"
        ]
        mock_scraper.scrape_match.return_value = mock_match_data

        with patch("src.scraping.tournament_scraper.YouTubeVODFinder") as mock_youtube_class:
            mock_youtube = Mock()
            mock_youtube_class.return_value = mock_youtube

            # All videos invalid/not found
            mock_youtube.extract_video_id.return_value = "invalid"
            mock_youtube.validate_video.return_value = False
            mock_youtube.find_map_vod.return_value = None

            scraper = TournamentScraper(
                manifest=temp_manifest,
                youtube_api_key="test_key"
            )

            stats = await scraper.scrape_tournament(
                "https://www.vlr.gg/event/matches/1921/test-tournament/",
                "Test Tournament"
            )

            # All maps skipped
            assert stats["maps_with_vod"] == 0
            assert stats["maps_skipped"] == 3
            assert len(temp_manifest.records) == 0


@pytest.mark.asyncio
async def test_idempotency_skips_existing_records(temp_manifest, mock_match_data):
    """Test that running twice doesn't duplicate records."""
    # Add existing record
    existing_record = VODRecord(
        vod_id="12345_map1",
        youtube_url="https://youtube.com/watch?v=existing",
        vlr_match_url="https://www.vlr.gg/12345/team-a-vs-team-b",
        teams=["Sentinels", "Fnatic"],
        map_name="Ascent",
        map_number=1,
        tournament="Test Tournament",
        date="2024-08-01",
        patch_version=None,
        status="complete"
    )
    temp_manifest.add_vod(existing_record)

    with patch("src.scraping.tournament_scraper.VLREventScraper") as mock_scraper_class:
        mock_scraper = AsyncMock()
        mock_scraper_class.return_value.__aenter__.return_value = mock_scraper

        mock_scraper.discover_match_urls.return_value = [
            "https://www.vlr.gg/12345/team-a-vs-team-b"
        ]
        mock_scraper.scrape_match.return_value = mock_match_data

        with patch("src.scraping.tournament_scraper.YouTubeVODFinder") as mock_youtube_class:
            mock_youtube = Mock()
            mock_youtube_class.return_value = mock_youtube

            mock_youtube.extract_video_id.return_value = "valid"
            mock_youtube.validate_video.return_value = True
            mock_youtube.find_map_vod.return_value = "https://youtube.com/watch?v=new"

            scraper = TournamentScraper(
                manifest=temp_manifest,
                youtube_api_key="test_key"
            )

            stats = await scraper.scrape_tournament(
                "https://www.vlr.gg/event/matches/1921/test-tournament/",
                "Test Tournament"
            )

            # Map 1 skipped (already exists), Maps 2-3 processed
            assert stats["maps_skipped"] >= 1
            assert "Already in manifest" in str(stats["skip_reasons"])

            # Record count: 1 existing + 2 new (maps 2 and 3)
            assert len(temp_manifest.records) == 3

            # Existing record unchanged
            assert temp_manifest.records["12345_map1"].youtube_url == "https://youtube.com/watch?v=existing"
            assert temp_manifest.records["12345_map1"].status == "complete"


@pytest.mark.asyncio
async def test_quota_exhausted_falls_back_to_vlr_urls(temp_manifest, mock_match_data):
    """Test that QuotaExhaustedError stops YouTube searches and continues with VLR URLs."""
    with patch("src.scraping.tournament_scraper.VLREventScraper") as mock_scraper_class:
        mock_scraper = AsyncMock()
        mock_scraper_class.return_value.__aenter__.return_value = mock_scraper

        mock_scraper.discover_match_urls.return_value = [
            "https://www.vlr.gg/12345/team-a-vs-team-b"
        ]
        mock_scraper.scrape_match.return_value = mock_match_data

        with patch("src.scraping.tournament_scraper.YouTubeVODFinder") as mock_youtube_class:
            mock_youtube = Mock()
            mock_youtube_class.return_value = mock_youtube

            # First validate_video call raises QuotaExhaustedError
            mock_youtube.validate_video.side_effect = QuotaExhaustedError(9999, 10000)

            scraper = TournamentScraper(
                manifest=temp_manifest,
                youtube_api_key="test_key"
            )

            stats = await scraper.scrape_tournament(
                "https://www.vlr.gg/event/matches/1921/test-tournament/",
                "Test Tournament"
            )

            # After quota exhaustion, no more YouTube API calls
            # Map 1: Had VLR URL but validation raised QuotaExhaustedError, should skip
            # Map 2: No VLR URL, can't search, should skip
            # Map 3: Had VLR URL but can't validate, should skip
            # All maps should be skipped
            assert stats["maps_skipped"] == 3
            assert len(temp_manifest.records) == 0


@pytest.mark.asyncio
async def test_generate_report_correct_totals(temp_manifest):
    """Test that generate_report produces correct summary statistics."""
    # Manually populate stats
    scraper = TournamentScraper(
        manifest=temp_manifest,
        youtube_api_key="test_key"
    )

    scraper.stats = {
        "Tournament A": {
            "matches_found": 10,
            "maps_found": 25,
            "maps_with_vod": 20,
            "maps_skipped": 5,
            "skip_reasons": [
                "12345_map1: No YouTube VOD found",
                "12346_map2: No YouTube VOD found",
                "12347_map3: VLR VOD inaccessible (private/deleted)",
                "12348_map1: Already in manifest",
                "12349_map2: Already in manifest"
            ]
        },
        "Tournament B": {
            "matches_found": 8,
            "maps_found": 20,
            "maps_with_vod": 18,
            "maps_skipped": 2,
            "skip_reasons": [
                "12350_map1: No YouTube VOD found",
                "12351_map2: VLR VOD inaccessible (private/deleted)"
            ]
        }
    }

    combined_stats = {
        "matches_found": 18,
        "maps_found": 45,
        "maps_with_vod": 38,
        "maps_skipped": 7,
        "skip_reasons": scraper.stats["Tournament A"]["skip_reasons"] + scraper.stats["Tournament B"]["skip_reasons"]
    }

    report = scraper.generate_report(combined_stats)

    # Verify report content
    assert "Tournament A" in report
    assert "Tournament B" in report
    assert "Matches found: 10" in report
    assert "Matches found: 8" in report
    assert "Total maps with VODs: 38" in report
    assert "Total maps skipped: 7" in report


@pytest.mark.asyncio
async def test_no_youtube_api_key_uses_vlr_urls_only(temp_manifest, mock_match_data):
    """Test that scraper works without YouTube API key (VLR URLs only)."""
    with patch("src.scraping.tournament_scraper.VLREventScraper") as mock_scraper_class:
        mock_scraper = AsyncMock()
        mock_scraper_class.return_value.__aenter__.return_value = mock_scraper

        mock_scraper.discover_match_urls.return_value = [
            "https://www.vlr.gg/12345/team-a-vs-team-b"
        ]
        mock_scraper.scrape_match.return_value = mock_match_data

        # Create scraper without YouTube API key
        with patch("src.scraping.tournament_scraper.YouTubeVODFinder") as mock_youtube_class:
            mock_youtube_class.side_effect = ValueError("API key required")

            scraper = TournamentScraper(
                manifest=temp_manifest,
                youtube_api_key=None  # No API key
            )

            # youtube_finder should be None
            assert scraper.youtube_finder is None

            stats = await scraper.scrape_tournament(
                "https://www.vlr.gg/event/matches/1921/test-tournament/",
                "Test Tournament"
            )

            # Map 1 and Map 3 have VLR URLs (accepted without validation)
            # Map 2 has no VLR URL -> skipped
            assert stats["maps_with_vod"] == 2
            assert stats["maps_skipped"] == 1
            assert len(temp_manifest.records) == 2

            # Map 1 record should use VLR URL without validation
            record_1 = temp_manifest.records["12345_map1"]
            assert record_1.youtube_url == "https://youtube.com/watch?v=valid_video_1"

            # Map 3 record also accepted (even though it's actually private)
            record_3 = temp_manifest.records["12345_map3"]
            assert record_3.youtube_url == "https://youtube.com/watch?v=private_video"


@pytest.mark.asyncio
async def test_scrape_all_combines_stats(temp_manifest, mock_match_data):
    """Test that scrape_all correctly combines stats from multiple tournaments."""
    with patch("src.scraping.tournament_scraper.VLREventScraper") as mock_scraper_class:
        mock_scraper = AsyncMock()
        mock_scraper_class.return_value.__aenter__.return_value = mock_scraper

        # Mock different match URLs for each tournament
        call_count = 0

        async def mock_discover(event_url):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ["https://www.vlr.gg/12345/match1"]
            else:
                return ["https://www.vlr.gg/12346/match2"]

        mock_scraper.discover_match_urls.side_effect = mock_discover
        mock_scraper.scrape_match.return_value = mock_match_data

        with patch("src.scraping.tournament_scraper.YouTubeVODFinder") as mock_youtube_class:
            mock_youtube = Mock()
            mock_youtube_class.return_value = mock_youtube

            mock_youtube.extract_video_id.return_value = "valid"
            mock_youtube.validate_video.return_value = True
            mock_youtube.find_map_vod.return_value = "https://youtube.com/watch?v=found"
            mock_youtube.quota_remaining = 5000

            scraper = TournamentScraper(
                manifest=temp_manifest,
                youtube_api_key="test_key"
            )

            tournaments = [
                {"event_url": "https://www.vlr.gg/event/1/", "name": "Tournament A"},
                {"event_url": "https://www.vlr.gg/event/2/", "name": "Tournament B"}
            ]

            combined_stats = await scraper.scrape_all(tournaments)

            # 2 matches × 3 maps each = 6 maps total
            assert combined_stats["matches_found"] == 2
            assert combined_stats["maps_found"] == 6

            # Both tournaments scraped
            assert "Tournament A" in scraper.stats
            assert "Tournament B" in scraper.stats
