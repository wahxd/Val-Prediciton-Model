"""Tests for processing manifest."""

import json
from pathlib import Path
from datetime import datetime, timezone

import pytest

from src.pipeline.manifest import ProcessingManifest, VODRecord


def test_create_empty_manifest(tmp_path):
    """New manifest has 0 records."""
    manifest_path = tmp_path / "manifest.json"
    manifest = ProcessingManifest(manifest_path)

    assert len(manifest.records) == 0


def test_add_vod(tmp_path):
    """Add a record and verify it's in records."""
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

    assert "12345_map1" in manifest.records
    assert manifest.records["12345_map1"].map_name == "Bind"
    assert manifest.records["12345_map1"].status == "pending"


def test_save_and_load(tmp_path):
    """Save manifest, create new instance from same path, verify records match."""
    manifest_path = tmp_path / "manifest.json"
    manifest = ProcessingManifest(manifest_path)

    # Add records
    record1 = VODRecord(
        vod_id="12345_map1",
        youtube_url="https://youtube.com/watch?v=test1",
        vlr_match_url="https://vlr.gg/12345",
        teams=["Team A", "Team B"],
        map_name="Bind",
        map_number=1,
        tournament="VCT 2025",
        date="2025-01-15",
        patch_version="9.0",
    )
    record2 = VODRecord(
        vod_id="12345_map2",
        youtube_url="https://youtube.com/watch?v=test2",
        vlr_match_url="https://vlr.gg/12345",
        teams=["Team A", "Team B"],
        map_name="Haven",
        map_number=2,
        tournament="VCT 2025",
        date="2025-01-15",
        patch_version="9.0",
        status="complete",
    )

    manifest.add_vods([record1, record2])

    # Load from disk
    manifest2 = ProcessingManifest(manifest_path)

    assert len(manifest2.records) == 2
    assert manifest2.records["12345_map1"].map_name == "Bind"
    assert manifest2.records["12345_map1"].status == "pending"
    assert manifest2.records["12345_map2"].map_name == "Haven"
    assert manifest2.records["12345_map2"].status == "complete"


def test_atomic_write(tmp_path):
    """Verify .tmp file is cleaned up after save."""
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

    # Verify .tmp file doesn't exist after save
    tmp_file = manifest_path.with_suffix('.tmp')
    assert not tmp_file.exists()

    # Verify manifest.json exists
    assert manifest_path.exists()


def test_update_status(tmp_path):
    """Change status, verify fields updated."""
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

    # Update status with additional fields
    manifest.update_status(
        "12345_map1",
        "complete",
        map_id="bind_12345_map1",
        completed_at=datetime.now(timezone.utc).isoformat(),
        processing_time_seconds=120.5,
    )

    updated = manifest.records["12345_map1"]
    assert updated.status == "complete"
    assert updated.map_id == "bind_12345_map1"
    assert updated.processing_time_seconds == 120.5
    assert updated.completed_at is not None


def test_get_pending(tmp_path):
    """Add 3 records (2 pending, 1 complete), verify get_pending returns 2."""
    manifest_path = tmp_path / "manifest.json"
    manifest = ProcessingManifest(manifest_path)

    records = [
        VODRecord(
            vod_id="12345_map1",
            youtube_url="https://youtube.com/watch?v=test1",
            vlr_match_url="https://vlr.gg/12345",
            teams=["Team A", "Team B"],
            map_name="Bind",
            map_number=1,
            tournament="VCT 2025",
            date="2025-01-15",
            patch_version="9.0",
            status="pending",
        ),
        VODRecord(
            vod_id="12345_map2",
            youtube_url="https://youtube.com/watch?v=test2",
            vlr_match_url="https://vlr.gg/12345",
            teams=["Team A", "Team B"],
            map_name="Haven",
            map_number=2,
            tournament="VCT 2025",
            date="2025-01-15",
            patch_version="9.0",
            status="complete",
        ),
        VODRecord(
            vod_id="12345_map3",
            youtube_url="https://youtube.com/watch?v=test3",
            vlr_match_url="https://vlr.gg/12345",
            teams=["Team A", "Team B"],
            map_name="Ascent",
            map_number=3,
            tournament="VCT 2025",
            date="2025-01-15",
            patch_version="9.0",
            status="pending",
        ),
    ]

    manifest.add_vods(records)

    pending = manifest.get_pending()
    assert len(pending) == 2
    assert all(r.status == "pending" for r in pending)


def test_get_summary(tmp_path):
    """Verify counts are correct."""
    manifest_path = tmp_path / "manifest.json"
    manifest = ProcessingManifest(manifest_path)

    records = [
        VODRecord(
            vod_id="12345_map1",
            youtube_url="https://youtube.com/watch?v=test1",
            vlr_match_url="https://vlr.gg/12345",
            teams=["Team A", "Team B"],
            map_name="Bind",
            map_number=1,
            tournament="VCT 2025",
            date="2025-01-15",
            patch_version="9.0",
            status="pending",
        ),
        VODRecord(
            vod_id="12345_map2",
            youtube_url="https://youtube.com/watch?v=test2",
            vlr_match_url="https://vlr.gg/12345",
            teams=["Team A", "Team B"],
            map_name="Haven",
            map_number=2,
            tournament="VCT 2025",
            date="2025-01-15",
            patch_version="9.0",
            status="complete",
            processing_time_seconds=120.0,
        ),
        VODRecord(
            vod_id="12345_map3",
            youtube_url="https://youtube.com/watch?v=test3",
            vlr_match_url="https://vlr.gg/12345",
            teams=["Team A", "Team B"],
            map_name="Ascent",
            map_number=3,
            tournament="VCT 2025",
            date="2025-01-15",
            patch_version="9.0",
            status="complete",
            processing_time_seconds=150.0,
        ),
        VODRecord(
            vod_id="67890_map1",
            youtube_url="https://youtube.com/watch?v=test4",
            vlr_match_url="https://vlr.gg/67890",
            teams=["Team C", "Team D"],
            map_name="Split",
            map_number=1,
            tournament="VCT 2025",
            date="2025-01-16",
            patch_version="9.0",
            status="failed",
            error_message="Download failed",
        ),
    ]

    manifest.add_vods(records)

    summary = manifest.get_summary()

    assert summary['total'] == 4
    assert summary['by_status']['pending'] == 1
    assert summary['by_status']['complete'] == 2
    assert summary['by_status']['failed'] == 1
    assert summary['total_processing_time_seconds'] == 270.0
    assert summary['eta_seconds'] is not None  # Should have ETA estimate


def test_bulk_add(tmp_path):
    """add_vods with multiple records, verify single save."""
    manifest_path = tmp_path / "manifest.json"
    manifest = ProcessingManifest(manifest_path)

    records = [
        VODRecord(
            vod_id=f"12345_map{i}",
            youtube_url=f"https://youtube.com/watch?v=test{i}",
            vlr_match_url="https://vlr.gg/12345",
            teams=["Team A", "Team B"],
            map_name=f"Map{i}",
            map_number=i,
            tournament="VCT 2025",
            date="2025-01-15",
            patch_version="9.0",
        )
        for i in range(1, 6)
    ]

    manifest.add_vods(records)

    # Verify all records added
    assert len(manifest.records) == 5

    # Verify file was written
    assert manifest_path.exists()

    # Load and verify
    manifest2 = ProcessingManifest(manifest_path)
    assert len(manifest2.records) == 5


def test_resume_after_crash(tmp_path):
    """Save with some complete + some pending, reload, verify pending list correct."""
    manifest_path = tmp_path / "manifest.json"
    manifest = ProcessingManifest(manifest_path)

    records = [
        VODRecord(
            vod_id="12345_map1",
            youtube_url="https://youtube.com/watch?v=test1",
            vlr_match_url="https://vlr.gg/12345",
            teams=["Team A", "Team B"],
            map_name="Bind",
            map_number=1,
            tournament="VCT 2025",
            date="2025-01-15",
            patch_version="9.0",
            status="complete",
        ),
        VODRecord(
            vod_id="12345_map2",
            youtube_url="https://youtube.com/watch?v=test2",
            vlr_match_url="https://vlr.gg/12345",
            teams=["Team A", "Team B"],
            map_name="Haven",
            map_number=2,
            tournament="VCT 2025",
            date="2025-01-15",
            patch_version="9.0",
            status="pending",
        ),
        VODRecord(
            vod_id="12345_map3",
            youtube_url="https://youtube.com/watch?v=test3",
            vlr_match_url="https://vlr.gg/12345",
            teams=["Team A", "Team B"],
            map_name="Ascent",
            map_number=3,
            tournament="VCT 2025",
            date="2025-01-15",
            patch_version="9.0",
            status="processing",
        ),
        VODRecord(
            vod_id="67890_map1",
            youtube_url="https://youtube.com/watch?v=test4",
            vlr_match_url="https://vlr.gg/67890",
            teams=["Team C", "Team D"],
            map_name="Split",
            map_number=1,
            tournament="VCT 2025",
            date="2025-01-16",
            patch_version="9.0",
            status="pending",
        ),
    ]

    manifest.add_vods(records)

    # Simulate crash and reload
    manifest2 = ProcessingManifest(manifest_path)

    # Verify state restored correctly
    assert len(manifest2.records) == 4

    pending = manifest2.get_pending()
    assert len(pending) == 2
    assert "12345_map2" in [r.vod_id for r in pending]
    assert "67890_map1" in [r.vod_id for r in pending]

    complete = manifest2.get_by_status("complete")
    assert len(complete) == 1
    assert complete[0].vod_id == "12345_map1"

    processing = manifest2.get_by_status("processing")
    assert len(processing) == 1
    assert processing[0].vod_id == "12345_map3"
