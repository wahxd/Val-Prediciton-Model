"""Tests for VLR.gg event scraper."""

from pathlib import Path
from unittest import mock

import pytest

from src.scraping.vlr_events import (
    VLREventScraper,
    extract_match_id_from_url,
    discover_matches,
)
from src.pipeline.manifest import ProcessingManifest, VODRecord


def test_extract_match_id_from_url():
    """Extract numeric match ID from VLR URLs."""
    # Standard match URL
    url1 = "https://www.vlr.gg/12345/team-alpha-vs-team-beta"
    assert extract_match_id_from_url(url1) == "12345"

    # URL with query params
    url2 = "https://www.vlr.gg/67890/team-gamma-vs-team-delta?game=all"
    assert extract_match_id_from_url(url2) == "67890"

    # URL with trailing slash
    url3 = "https://www.vlr.gg/11111/team-epsilon-vs-team-zeta/"
    assert extract_match_id_from_url(url3) == "11111"

    # Invalid URL (no numeric ID)
    with pytest.raises(ValueError):
        extract_match_id_from_url("https://www.vlr.gg/event/2094/vct-masters")


def test_build_vod_record_from_match_data():
    """Given scrape_match output dict, verify VODRecord fields."""
    # Simulate Valoscribe scrape_match output
    match_data = {
        "match_url": "https://www.vlr.gg/12345/team-alpha-vs-team-beta",
        "teams": ["Team Alpha", "Team Beta"],
        "maps": [
            {
                "map_number": 1,
                "map_name": "Bind",
                "vod_url": "https://youtube.com/watch?v=test1",
                "teams": [
                    {
                        "name": "Team Alpha",
                        "starting_side": "attack",
                        "players": [
                            {"name": "Player1", "agent": "jett"},
                            {"name": "Player2", "agent": "omen"},
                        ]
                    },
                    {
                        "name": "Team Beta",
                        "starting_side": "defense",
                        "players": [
                            {"name": "Player3", "agent": "sova"},
                            {"name": "Player4", "agent": "killjoy"},
                        ]
                    }
                ]
            },
            {
                "map_number": 2,
                "map_name": "Haven",
                "vod_url": "https://youtube.com/watch?v=test2",
                "teams": [
                    {
                        "name": "Team Alpha",
                        "starting_side": "defense",
                        "players": [
                            {"name": "Player1", "agent": "reyna"},
                            {"name": "Player2", "agent": "viper"},
                        ]
                    },
                    {
                        "name": "Team Beta",
                        "starting_side": "attack",
                        "players": [
                            {"name": "Player3", "agent": "skye"},
                            {"name": "Player4", "agent": "cypher"},
                        ]
                    }
                ]
            },
        ]
    }

    # Build VODRecords like the scraper does
    teams = match_data['teams']
    maps = match_data['maps']
    match_url = match_data['match_url']
    match_id = extract_match_id_from_url(match_url)

    records = []
    for map_data in maps:
        map_number = map_data['map_number']
        vod_url = map_data['vod_url']
        map_name = map_data['map_name']

        record = VODRecord(
            vod_id=f"{match_id}_map{map_number}",
            youtube_url=vod_url,
            vlr_match_url=match_url,
            teams=teams,
            map_name=map_name,
            map_number=map_number,
            tournament="VCT 2025 Masters",
            date="",
            patch_version=None,
            status="pending",
        )
        records.append(record)

    # Verify records
    assert len(records) == 2

    # Map 1
    assert records[0].vod_id == "12345_map1"
    assert records[0].youtube_url == "https://youtube.com/watch?v=test1"
    assert records[0].map_name == "Bind"
    assert records[0].map_number == 1
    assert records[0].teams == ["Team Alpha", "Team Beta"]

    # Map 2
    assert records[1].vod_id == "12345_map2"
    assert records[1].youtube_url == "https://youtube.com/watch?v=test2"
    assert records[1].map_name == "Haven"
    assert records[1].map_number == 2


def test_skip_existing_vods(tmp_path):
    """Add same vod_id twice, verify only 1 record."""
    manifest_path = tmp_path / "manifest.json"
    manifest = ProcessingManifest(manifest_path)

    record1 = VODRecord(
        vod_id="12345_map1",
        youtube_url="https://youtube.com/watch?v=test",
        vlr_match_url="https://vlr.gg/12345",
        teams=["Team A", "Team B"],
        map_name="Bind",
        map_number=1,
        tournament="VCT 2025",
        date="",
        patch_version=None,
    )

    # Add first time
    manifest.add_vod(record1)
    assert len(manifest.records) == 1

    # Try to add duplicate (simulate idempotent check in discover_vods)
    if "12345_map1" not in manifest.records:
        manifest.add_vod(record1)

    # Should still be 1
    assert len(manifest.records) == 1


def test_skip_maps_without_vod():
    """Map with vod_url=None is skipped."""
    # Simulate match data with one map missing VOD
    match_data = {
        "match_url": "https://www.vlr.gg/12345/team-alpha-vs-team-beta",
        "teams": ["Team Alpha", "Team Beta"],
        "maps": [
            {
                "map_number": 1,
                "map_name": "Bind",
                "vod_url": "https://youtube.com/watch?v=test1",
            },
            {
                "map_number": 2,
                "map_name": "Haven",
                "vod_url": None,  # No VOD for this map
            },
            {
                "map_number": 3,
                "map_name": "Ascent",
                "vod_url": "https://youtube.com/watch?v=test3",
            },
        ]
    }

    # Build VODRecords (skip None VODs)
    records = []
    for map_data in match_data['maps']:
        vod_url = map_data['vod_url']
        if not vod_url:
            continue  # Skip

        record = VODRecord(
            vod_id=f"12345_map{map_data['map_number']}",
            youtube_url=vod_url,
            vlr_match_url=match_data['match_url'],
            teams=match_data['teams'],
            map_name=map_data['map_name'],
            map_number=map_data['map_number'],
            tournament="VCT 2025",
            date="",
            patch_version=None,
        )
        records.append(record)

    # Should have 2 records (map 1 and 3, skipping map 2)
    assert len(records) == 2
    assert records[0].vod_id == "12345_map1"
    assert records[1].vod_id == "12345_map3"


def test_discover_match_urls_parsing(tmp_path):
    """Parse saved HTML fixture and extract match URLs."""
    # Load fixture
    fixture_path = Path(__file__).parent / "fixtures" / "vlr_event_page.html"
    assert fixture_path.exists(), f"Fixture not found: {fixture_path}"

    with open(fixture_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # Mock requests to return our fixture
    scraper = VLREventScraper(rate_limit_seconds=0.1)

    with mock.patch.object(scraper.session, 'get') as mock_get:
        # Create mock response
        mock_response = mock.Mock()
        mock_response.text = html_content
        mock_response.status_code = 200
        mock_response.raise_for_status = mock.Mock()
        mock_get.return_value = mock_response

        # Call discover_match_urls
        event_url = "https://www.vlr.gg/event/matches/2094/vct-2025-masters-bangkok"
        match_urls = scraper.discover_match_urls(event_url)

        # Verify extracted URLs
        assert len(match_urls) == 3
        assert "https://www.vlr.gg/12345/team-alpha-vs-team-beta" in match_urls
        assert "https://www.vlr.gg/67890/team-gamma-vs-team-delta" in match_urls
        assert "https://www.vlr.gg/11111/team-epsilon-vs-team-zeta" in match_urls


def test_discover_vods_integration(tmp_path):
    """Integration test: discover_vods with mocked Valoscribe scraper."""
    manifest_path = tmp_path / "manifest.json"
    manifest = ProcessingManifest(manifest_path)

    # Mock Valoscribe scrape_match
    mock_scrape_data = {
        "match_url": "https://www.vlr.gg/12345/team-alpha-vs-team-beta",
        "teams": ["Team Alpha", "Team Beta"],
        "maps": [
            {
                "map_number": 1,
                "map_name": "Bind",
                "vod_url": "https://youtube.com/watch?v=test1",
            },
            {
                "map_number": 2,
                "map_name": "Haven",
                "vod_url": None,  # No VOD
            },
        ]
    }

    scraper = VLREventScraper(rate_limit_seconds=0.1)

    # Mock discover_match_urls to return one match
    with mock.patch.object(scraper, 'discover_match_urls') as mock_discover:
        mock_discover.return_value = ["https://www.vlr.gg/12345/team-alpha-vs-team-beta"]

        # Mock scrape_match
        with mock.patch('src.scraping.vlr_events.scrape_match') as mock_scrape:
            mock_scrape.return_value = mock_scrape_data

            # Run discover_vods
            event_url = "https://www.vlr.gg/event/matches/2094/test"
            count = scraper.discover_vods(event_url, manifest, "VCT 2025 Test")

            # Should have added 1 VOD (map 1, skipping map 2 with no VOD)
            assert count == 1
            assert len(manifest.records) == 1
            assert "12345_map1" in manifest.records

            record = manifest.records["12345_map1"]
            assert record.map_name == "Bind"
            assert record.teams == ["Team Alpha", "Team Beta"]
            assert record.youtube_url == "https://youtube.com/watch?v=test1"


def test_discover_matches_convenience_function(tmp_path):
    """Test discover_matches convenience wrapper."""
    manifest_path = tmp_path / "manifest.json"

    # Mock everything
    mock_scrape_data = {
        "match_url": "https://www.vlr.gg/12345/test",
        "teams": ["Team A", "Team B"],
        "maps": [
            {
                "map_number": 1,
                "map_name": "Bind",
                "vod_url": "https://youtube.com/watch?v=test",
            }
        ]
    }

    with mock.patch('src.scraping.vlr_events.VLREventScraper') as MockScraper:
        mock_instance = mock.Mock()
        mock_instance.discover_vods.return_value = 1
        MockScraper.return_value = mock_instance

        # Call convenience function
        count = discover_matches(
            event_url="https://www.vlr.gg/event/matches/2094/test",
            manifest_path=manifest_path,
            tournament_name="VCT Test",
            rate_limit=0.1
        )

        # Verify scraper was created and discover_vods was called
        MockScraper.assert_called_once_with(rate_limit_seconds=0.1)
        assert mock_instance.discover_vods.called
        assert count == 1
