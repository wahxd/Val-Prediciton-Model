"""Tests for extended VODRecord fields (Phase 12 additions)."""

import json
from pathlib import Path

import pytest

from src.pipeline.manifest import ProcessingManifest, VODRecord


def test_vodrecord_with_extended_fields(tmp_path):
    """VODRecord accepts and preserves extended fields."""
    manifest_path = tmp_path / "manifest.json"
    manifest = ProcessingManifest(manifest_path)

    player_stats = {
        "TenZ": {
            "acs": 285.5,
            "kills": 22,
            "deaths": 15,
            "assists": 5,
            "kast_pct": 75.0,
            "adr": 165.2,
            "hs_pct": 28.4,
            "fk": 3,
            "fd": 1
        },
        "Zekken": {
            "acs": 268.3,
            "kills": 20,
            "deaths": 14,
            "assists": 7,
            "kast_pct": 72.0,
            "adr": 158.7,
            "hs_pct": 25.1,
            "fk": 2,
            "fd": 2
        }
    }

    agent_comps = [
        {"name": "TenZ", "team": "Sentinels", "agent": "Jett"},
        {"name": "Zekken", "team": "Sentinels", "agent": "Raze"},
    ]

    player_vlr_ids = {
        "TenZ": 12345,
        "Zekken": 67890
    }

    record = VODRecord(
        vod_id="12345_map1",
        youtube_url="https://youtube.com/watch?v=test",
        vlr_match_url="https://vlr.gg/12345",
        teams=["Sentinels", "NRG"],
        map_name="Bind",
        map_number=1,
        tournament="VCT 2025",
        date="2025-01-15",
        patch_version="9.0",
        player_stats=player_stats,
        agent_compositions=agent_comps,
        player_vlr_ids=player_vlr_ids,
        match_score="2-1",
        match_outcome="team1_win"
    )

    manifest.add_vod(record)

    # Reload and verify
    manifest2 = ProcessingManifest(manifest_path)
    loaded = manifest2.records["12345_map1"]

    assert loaded.player_stats == player_stats
    assert loaded.agent_compositions == agent_comps
    assert loaded.player_vlr_ids == player_vlr_ids
    assert loaded.match_score == "2-1"
    assert loaded.match_outcome == "team1_win"


def test_vodrecord_backward_compatibility(tmp_path):
    """VODRecord without extended fields still works (None defaults)."""
    manifest_path = tmp_path / "manifest.json"
    manifest = ProcessingManifest(manifest_path)

    # Create record WITHOUT new fields
    record = VODRecord(
        vod_id="12345_map1",
        youtube_url="https://youtube.com/watch?v=test",
        vlr_match_url="https://vlr.gg/12345",
        teams=["Team A", "Team B"],
        map_name="Bind",
        map_number=1,
        tournament="VCT 2025",
        date="2025-01-15",
        patch_version="9.0",
    )

    manifest.add_vod(record)

    # Reload
    manifest2 = ProcessingManifest(manifest_path)
    loaded = manifest2.records["12345_map1"]

    # Extended fields should be None
    assert loaded.player_stats is None
    assert loaded.agent_compositions is None
    assert loaded.player_vlr_ids is None
    assert loaded.match_score is None
    assert loaded.match_outcome is None

    # Core fields still work
    assert loaded.map_name == "Bind"
    assert loaded.teams == ["Team A", "Team B"]


def test_load_old_manifest_format(tmp_path):
    """Can load manifest.json created before Phase 12 (missing extended fields)."""
    manifest_path = tmp_path / "manifest.json"

    # Simulate old manifest format (no extended fields)
    old_data = {
        "updated_at": "2025-01-15T00:00:00Z",
        "vods": {
            "12345_map1": {
                "vod_id": "12345_map1",
                "youtube_url": "https://youtube.com/watch?v=test",
                "vlr_match_url": "https://vlr.gg/12345",
                "teams": ["Team A", "Team B"],
                "map_name": "Bind",
                "map_number": 1,
                "tournament": "VCT 2025",
                "date": "2025-01-15",
                "patch_version": "9.0",
                "status": "complete",
                "map_id": "bind_12345",
                "error_message": None,
                "retry_count": 0,
                "created_at": "2025-01-15T00:00:00Z",
                "started_at": "2025-01-15T00:01:00Z",
                "completed_at": "2025-01-15T00:05:00Z",
                "processing_time_seconds": 240.0
            }
        }
    }

    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(old_data, f)

    # Load should succeed
    manifest = ProcessingManifest(manifest_path)

    assert len(manifest.records) == 1
    record = manifest.records["12345_map1"]

    # Core fields loaded
    assert record.map_name == "Bind"
    assert record.status == "complete"

    # Extended fields default to None
    assert record.player_stats is None
    assert record.agent_compositions is None
    assert record.player_vlr_ids is None
    assert record.match_score is None
    assert record.match_outcome is None


def test_round_trip_preserves_all_fields(tmp_path):
    """Save and load preserves both core and extended fields."""
    manifest_path = tmp_path / "manifest.json"
    manifest = ProcessingManifest(manifest_path)

    record = VODRecord(
        vod_id="12345_map1",
        youtube_url="https://youtube.com/watch?v=test",
        vlr_match_url="https://vlr.gg/12345",
        teams=["Team A", "Team B"],
        map_name="Bind",
        map_number=1,
        tournament="VCT 2025",
        date="2025-01-15",
        patch_version="9.0",
        player_stats={"Player1": {"acs": 250.0}},
        agent_compositions=[{"name": "Player1", "team": "Team A", "agent": "Jett"}],
        player_vlr_ids={"Player1": 111},
        match_score="2-0",
        match_outcome="team1_win"
    )

    manifest.add_vod(record)

    # Load into new manifest instance
    manifest2 = ProcessingManifest(manifest_path)
    loaded = manifest2.records["12345_map1"]

    # Verify all fields preserved
    assert loaded.vod_id == record.vod_id
    assert loaded.youtube_url == record.youtube_url
    assert loaded.teams == record.teams
    assert loaded.player_stats == record.player_stats
    assert loaded.agent_compositions == record.agent_compositions
    assert loaded.player_vlr_ids == record.player_vlr_ids
    assert loaded.match_score == record.match_score
    assert loaded.match_outcome == record.match_outcome


def test_update_status_with_extended_fields(tmp_path):
    """update_status can set extended fields."""
    manifest_path = tmp_path / "manifest.json"
    manifest = ProcessingManifest(manifest_path)

    record = VODRecord(
        vod_id="12345_map1",
        youtube_url="https://youtube.com/watch?v=test",
        vlr_match_url="https://vlr.gg/12345",
        teams=["Team A", "Team B"],
        map_name="Bind",
        map_number=1,
        tournament="VCT 2025",
        date="2025-01-15",
        patch_version="9.0",
    )

    manifest.add_vod(record)

    # Update with extended fields
    manifest.update_status(
        "12345_map1",
        "complete",
        player_stats={"Player1": {"acs": 280.0}},
        match_score="2-1"
    )

    updated = manifest.records["12345_map1"]
    assert updated.status == "complete"
    assert updated.player_stats == {"Player1": {"acs": 280.0}}
    assert updated.match_score == "2-1"
