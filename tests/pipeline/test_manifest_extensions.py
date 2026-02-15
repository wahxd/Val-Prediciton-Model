"""Tests for Phase 13 manifest extensions: quality_metrics and new status types."""

import json
from pathlib import Path

import pytest

from src.pipeline.manifest import ProcessingManifest, VODRecord


def test_vod_record_with_quality_metrics():
    """VODRecord can be created with quality_metrics dict."""
    record = VODRecord(
        vod_id="test_map1",
        youtube_url="https://youtube.com/watch?v=test",
        vlr_match_url="https://vlr.gg/12345",
        teams=["Team A", "Team B"],
        map_name="Haven",
        map_number=1,
        tournament="VCT Test",
        date="2024-01-01",
        patch_version=None,
        status="complete",
        quality_metrics={
            "overall_score": 0.85,
            "tier": "high",
            "flagged_for_review": False,
            "checks": {
                "kill_count": {"score": 0.9, "issues": [], "warnings": []},
                "round_progression": {"score": 1.0, "issues": [], "warnings": []},
            },
        },
    )

    assert record.quality_metrics is not None
    assert record.quality_metrics["overall_score"] == 0.85
    assert record.quality_metrics["tier"] == "high"


def test_vod_record_with_download_failed_status():
    """VODRecord can be created with download_failed status."""
    record = VODRecord(
        vod_id="test_map1",
        youtube_url="https://youtube.com/watch?v=test",
        vlr_match_url="https://vlr.gg/12345",
        teams=["Team A", "Team B"],
        map_name="Haven",
        map_number=1,
        tournament="VCT Test",
        date="2024-01-01",
        patch_version=None,
        status="download_failed",
        error_message="Video is private",
    )

    assert record.status == "download_failed"
    assert record.error_message == "Video is private"


def test_vod_record_with_processing_failed_status():
    """VODRecord can be created with processing_failed status."""
    record = VODRecord(
        vod_id="test_map1",
        youtube_url="https://youtube.com/watch?v=test",
        vlr_match_url="https://vlr.gg/12345",
        teams=["Team A", "Team B"],
        map_name="Haven",
        map_number=1,
        tournament="VCT Test",
        date="2024-01-01",
        patch_version=None,
        status="processing_failed",
        error_message="OCR timeout",
    )

    assert record.status == "processing_failed"
    assert record.error_message == "OCR timeout"


def test_manifest_update_status_with_new_statuses(tmp_path):
    """manifest.update_status works with download_failed and processing_failed."""
    manifest_path = tmp_path / "manifest.json"
    manifest = ProcessingManifest(manifest_path)

    record = VODRecord(
        vod_id="test_map1",
        youtube_url="https://youtube.com/watch?v=test",
        vlr_match_url="https://vlr.gg/12345",
        teams=["Team A", "Team B"],
        map_name="Haven",
        map_number=1,
        tournament="VCT Test",
        date="2024-01-01",
        patch_version=None,
    )
    manifest.add_vod(record)

    # Test update to download_failed
    manifest.update_status("test_map1", "download_failed", error_message="Video is private")
    assert manifest.records["test_map1"].status == "download_failed"
    assert manifest.records["test_map1"].error_message == "Video is private"

    # Test update to processing_failed
    manifest.update_status("test_map1", "processing_failed", error_message="OCR error")
    assert manifest.records["test_map1"].status == "processing_failed"
    assert manifest.records["test_map1"].error_message == "OCR error"


def test_manifest_get_by_status_with_new_statuses(tmp_path):
    """manifest.get_by_status works with download_failed and processing_failed."""
    manifest_path = tmp_path / "manifest.json"
    manifest = ProcessingManifest(manifest_path)

    # Add records with various statuses
    records = [
        VODRecord(
            vod_id="map1",
            youtube_url="url1",
            vlr_match_url="vlr1",
            teams=["A", "B"],
            map_name="Haven",
            map_number=1,
            tournament="T1",
            date="2024-01-01",
            patch_version=None,
            status="pending",
        ),
        VODRecord(
            vod_id="map2",
            youtube_url="url2",
            vlr_match_url="vlr2",
            teams=["C", "D"],
            map_name="Bind",
            map_number=1,
            tournament="T1",
            date="2024-01-01",
            patch_version=None,
            status="download_failed",
        ),
        VODRecord(
            vod_id="map3",
            youtube_url="url3",
            vlr_match_url="vlr3",
            teams=["E", "F"],
            map_name="Split",
            map_number=1,
            tournament="T1",
            date="2024-01-01",
            patch_version=None,
            status="processing_failed",
        ),
        VODRecord(
            vod_id="map4",
            youtube_url="url4",
            vlr_match_url="vlr4",
            teams=["G", "H"],
            map_name="Ascent",
            map_number=1,
            tournament="T1",
            date="2024-01-01",
            patch_version=None,
            status="complete",
        ),
    ]
    manifest.add_vods(records)

    # Query by new statuses
    download_failed = manifest.get_by_status("download_failed")
    assert len(download_failed) == 1
    assert download_failed[0].vod_id == "map2"

    processing_failed = manifest.get_by_status("processing_failed")
    assert len(processing_failed) == 1
    assert processing_failed[0].vod_id == "map3"

    # Verify existing statuses still work
    pending = manifest.get_by_status("pending")
    assert len(pending) == 1
    assert pending[0].vod_id == "map1"

    complete = manifest.get_by_status("complete")
    assert len(complete) == 1
    assert complete[0].vod_id == "map4"


def test_quality_metrics_round_trip(tmp_path):
    """quality_metrics serializes to JSON and back correctly."""
    manifest_path = tmp_path / "manifest.json"
    manifest = ProcessingManifest(manifest_path)

    quality_metrics = {
        "overall_score": 0.75,
        "tier": "medium",
        "flagged_for_review": True,
        "checks": {
            "kill_count": {"score": 0.8, "issues": [], "warnings": ["Below expected"]},
            "round_progression": {"score": 0.7, "issues": ["Missing round 5"], "warnings": []},
        },
        "total_events": 250,
        "total_rounds": 13,
        "cross_check_disagreements": [],
        "all_issues": ["Missing round 5"],
        "all_warnings": ["Below expected"],
    }

    record = VODRecord(
        vod_id="test_map1",
        youtube_url="https://youtube.com/watch?v=test",
        vlr_match_url="https://vlr.gg/12345",
        teams=["Team A", "Team B"],
        map_name="Haven",
        map_number=1,
        tournament="VCT Test",
        date="2024-01-01",
        patch_version=None,
        status="complete",
        quality_metrics=quality_metrics,
    )
    manifest.add_vod(record)

    # Load from disk
    manifest2 = ProcessingManifest(manifest_path)
    loaded_record = manifest2.records["test_map1"]

    assert loaded_record.quality_metrics == quality_metrics
    assert loaded_record.quality_metrics["overall_score"] == 0.75
    assert loaded_record.quality_metrics["tier"] == "medium"
    assert loaded_record.quality_metrics["flagged_for_review"] is True
    assert loaded_record.quality_metrics["total_events"] == 250
    assert loaded_record.quality_metrics["checks"]["kill_count"]["score"] == 0.8


def test_backward_compatibility_missing_quality_metrics(tmp_path):
    """Existing records without quality_metrics load correctly (field defaults to None)."""
    manifest_path = tmp_path / "manifest.json"

    # Manually create a manifest file without quality_metrics field
    old_manifest_data = {
        "updated_at": "2024-01-01T00:00:00Z",
        "vods": {
            "old_map1": {
                "vod_id": "old_map1",
                "youtube_url": "https://youtube.com/watch?v=old",
                "vlr_match_url": "https://vlr.gg/11111",
                "teams": ["Team X", "Team Y"],
                "map_name": "Bind",
                "map_number": 1,
                "tournament": "Old Tournament",
                "date": "2023-12-01",
                "patch_version": None,
                "status": "complete",
                "map_id": "bind_12345",
                "error_message": None,
                "retry_count": 0,
                "created_at": "2023-12-01T12:00:00Z",
                "started_at": "2023-12-01T12:01:00Z",
                "completed_at": "2023-12-01T12:50:00Z",
                "processing_time_seconds": 2940.0,
                "player_stats": None,
                "agent_compositions": None,
                "player_vlr_ids": None,
                "match_score": None,
                "match_outcome": None,
            }
        }
    }

    with open(manifest_path, 'w') as f:
        json.dump(old_manifest_data, f)

    # Load manifest (should not crash)
    manifest = ProcessingManifest(manifest_path)

    assert "old_map1" in manifest.records
    record = manifest.records["old_map1"]
    assert record.quality_metrics is None  # Should default to None
    assert record.status == "complete"
    assert record.map_name == "Bind"
