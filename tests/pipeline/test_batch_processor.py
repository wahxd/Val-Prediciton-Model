"""Tests for BatchProcessor with tqdm progress tracking and circuit breaker."""

import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

import pytest

from src.config.processing import ProcessingConfig
from src.pipeline.batch_processor import BatchProcessor
from src.pipeline.manifest import ProcessingManifest, VODRecord
from src.pipeline.quality_validator import QualityValidator


def make_record(vod_id, tournament="Test Tournament", status="pending", teams=None):
    """Create a test VODRecord fixture.

    Args:
        vod_id: Unique VOD identifier
        tournament: Tournament name
        status: Processing status
        teams: Team names (default: ["Team A", "Team B"])

    Returns:
        VODRecord instance
    """
    if teams is None:
        teams = ["Team A", "Team B"]

    return VODRecord(
        vod_id=vod_id,
        youtube_url=f"https://youtube.com/watch?v={vod_id}",
        vlr_match_url=f"https://vlr.gg/match/{vod_id}",
        teams=teams,
        map_name="Haven",
        map_number=1,
        tournament=tournament,
        date="2024-06-15",
        patch_version=None,
        status=status,
    )


@pytest.fixture
def temp_manifest(tmp_path):
    """Create a temporary manifest for testing."""
    manifest_path = tmp_path / "manifest.json"
    return ProcessingManifest(manifest_path)


@pytest.fixture
def mock_config(tmp_path):
    """Create a mock ProcessingConfig."""
    config = ProcessingConfig()
    config.batch_size = 20
    config.circuit_breaker_threshold = 3
    config.output_dir = tmp_path / "output"
    config.output_dir.mkdir()
    return config


@pytest.fixture
def mock_orchestrator():
    """Create a mock VODOrchestrator."""
    return Mock()


@pytest.fixture
def mock_validator():
    """Create a mock QualityValidator."""
    validator = Mock(spec=QualityValidator)
    validator.validate.return_value = {
        "overall_score": 0.85,
        "tier": "high",
        "flagged_for_review": False,
        "checks": {},
        "total_events": 1000,
        "total_rounds": 24,
        "cross_check_disagreements": [],
        "all_issues": [],
        "all_warnings": [],
    }
    return validator


@pytest.fixture
def batch_processor(mock_orchestrator, temp_manifest, mock_validator, mock_config):
    """Create a BatchProcessor instance with mocked dependencies."""
    return BatchProcessor(
        orchestrator=mock_orchestrator,
        manifest=temp_manifest,
        quality_validator=mock_validator,
        config=mock_config,
    )


def test_process_batch_all_success(batch_processor, temp_manifest, mock_orchestrator, mock_validator):
    """Test batch processing with all VODs succeeding."""
    # Setup: Add 3 pending VODs to manifest
    records = [
        make_record("vod1", "Tournament A"),
        make_record("vod2", "Tournament A"),
        make_record("vod3", "Tournament A"),
    ]
    temp_manifest.add_vods(records)

    # Mock process_single_vod to always succeed
    mock_orchestrator.process_single_vod.return_value = True

    # Process batch
    summary = batch_processor.process_batch()

    # Verify all VODs processed
    assert summary["batch_size"] == 3
    assert summary["processed"] == 3
    assert summary["succeeded"] == 3
    assert summary["failed"] == 0
    assert summary["circuit_breaker_tripped"] is False

    # Verify quality validation was called for each VOD
    assert mock_validator.validate.call_count == 3

    # Verify manifest status updates
    for record in records:
        updated_record = temp_manifest.records[record.vod_id]
        assert updated_record.status == "complete"
        assert updated_record.quality_metrics is not None


def test_process_batch_with_failures(batch_processor, temp_manifest, mock_orchestrator):
    """Test batch processing with some failures."""
    # Setup: Add 5 pending VODs
    records = [make_record(f"vod{i}") for i in range(1, 6)]
    temp_manifest.add_vods(records)

    # Mock process_single_vod to fail on 2nd and 4th VODs
    mock_orchestrator.process_single_vod.side_effect = [True, False, True, False, True]

    # Process batch
    summary = batch_processor.process_batch()

    # Verify counts
    assert summary["batch_size"] == 5
    assert summary["processed"] == 5
    assert summary["succeeded"] == 3
    assert summary["failed"] == 2
    assert summary["circuit_breaker_tripped"] is False


def test_circuit_breaker_trips(batch_processor, temp_manifest, mock_orchestrator):
    """Test circuit breaker stops processing after threshold consecutive failures."""
    # Setup: Add 10 pending VODs
    records = [make_record(f"vod{i}") for i in range(1, 11)]
    temp_manifest.add_vods(records)

    # Mock process_single_vod to always fail
    mock_orchestrator.process_single_vod.return_value = False

    # Process batch (circuit breaker threshold = 3)
    summary = batch_processor.process_batch()

    # Verify processing stopped after 3 failures
    assert summary["batch_size"] == 10
    assert summary["processed"] == 3  # Stopped after 3 consecutive failures
    assert summary["succeeded"] == 0
    assert summary["failed"] == 3
    assert summary["circuit_breaker_tripped"] is True


def test_batch_size_limits_queue(batch_processor, temp_manifest, mock_orchestrator):
    """Test batch_size parameter limits the processing queue."""
    # Setup: Add 10 pending VODs
    records = [make_record(f"vod{i}") for i in range(1, 11)]
    temp_manifest.add_vods(records)

    # Mock process_single_vod to succeed
    mock_orchestrator.process_single_vod.return_value = True

    # Process batch with batch_size=3
    summary = batch_processor.process_batch(batch_size=3)

    # Verify only 3 VODs processed
    assert summary["batch_size"] == 3
    assert summary["processed"] == 3
    assert summary["succeeded"] == 3


def test_tournament_ordering(batch_processor, temp_manifest, mock_orchestrator):
    """Test VODs are processed in tournament order."""
    # Setup: Create 6 VODs from 2 tournaments (interleaved by vod_id)
    records = [
        make_record("vod1", "Tournament B"),
        make_record("vod2", "Tournament A"),
        make_record("vod3", "Tournament B"),
        make_record("vod4", "Tournament A"),
        make_record("vod5", "Tournament B"),
        make_record("vod6", "Tournament A"),
    ]
    temp_manifest.add_vods(records)

    # Track processing order
    processed_vods = []
    def track_processing(record):
        processed_vods.append(record.vod_id)
        return True

    mock_orchestrator.process_single_vod.side_effect = track_processing

    # Process batch
    batch_processor.process_batch()

    # Verify tournament ordering: all Tournament A, then Tournament B
    # (sorted by tournament, then vod_id)
    expected_order = ["vod2", "vod4", "vod6", "vod1", "vod3", "vod5"]
    assert processed_vods == expected_order


def test_retry_failed_includes_failed_records(batch_processor, temp_manifest, mock_orchestrator):
    """Test retry_failed=True includes download_failed and processing_failed records."""
    # Setup: Create 2 pending + 2 download_failed + 1 processing_failed
    records = [
        make_record("vod1", status="pending"),
        make_record("vod2", status="pending"),
        make_record("vod3", status="download_failed"),
        make_record("vod4", status="download_failed"),
        make_record("vod5", status="processing_failed"),
    ]
    temp_manifest.add_vods(records)

    # Mock process_single_vod to succeed
    mock_orchestrator.process_single_vod.return_value = True

    # Process batch with retry_failed=True
    summary = batch_processor.process_batch(retry_failed=True)

    # Verify all 5 VODs were processed (2 pending + 2 download_failed + 1 processing_failed)
    assert summary["batch_size"] == 5
    assert summary["processed"] == 5
    assert summary["succeeded"] == 5


def test_empty_queue_returns_summary(batch_processor):
    """Test processing with no pending VODs returns empty summary."""
    # No VODs in manifest

    # Process batch
    summary = batch_processor.process_batch()

    # Verify empty summary
    assert summary["batch_size"] == 0
    assert summary["processed"] == 0
    assert summary["succeeded"] == 0
    assert summary["failed"] == 0


def test_cleanup_partial_output(batch_processor, temp_manifest, mock_orchestrator, mock_config):
    """Test _cleanup_partial_output removes incomplete Valoscribe output."""
    # Setup: Create a VOD record
    record = make_record("vod1")
    temp_manifest.add_vod(record)

    # Create partial output directory with files
    output_dir = mock_config.output_dir / "vod1"
    output_dir.mkdir(parents=True)
    (output_dir / "events.jsonl").write_text('{"type": "kill"}')
    (output_dir / "frames.csv").write_text('timestamp,team1_alive,team2_alive')
    (output_dir / "metadata.json").write_text('{"teams": []}')

    # Mock process_single_vod to fail
    mock_orchestrator.process_single_vod.return_value = False

    # Process batch
    batch_processor.process_batch()

    # Verify output files were cleaned up
    assert not (output_dir / "events.jsonl").exists()
    assert not (output_dir / "frames.csv").exists()
    assert not (output_dir / "metadata.json").exists()
    assert not output_dir.exists()  # Directory should be removed


def test_quality_validation_failure_non_fatal(batch_processor, temp_manifest, mock_orchestrator, mock_validator):
    """Test quality validation failure doesn't prevent VOD from being marked complete."""
    # Setup: Add 1 pending VOD
    record = make_record("vod1")
    temp_manifest.add_vod(record)

    # Mock process_single_vod to succeed and update manifest status
    def mock_process(rec):
        temp_manifest.update_status(rec.vod_id, "complete")
        return True

    mock_orchestrator.process_single_vod.side_effect = mock_process

    # Mock quality validator to raise an exception
    mock_validator.validate.side_effect = Exception("Quality validation error")

    # Process batch
    summary = batch_processor.process_batch()

    # Verify VOD is still marked as succeeded
    assert summary["succeeded"] == 1
    assert summary["failed"] == 0

    # Verify VOD status is still "complete"
    updated_record = temp_manifest.records["vod1"]
    assert updated_record.status == "complete"


def test_circuit_breaker_resets_on_success(batch_processor, temp_manifest, mock_orchestrator):
    """Test circuit breaker counter resets after a successful processing."""
    # Setup: Add 10 pending VODs
    records = [make_record(f"vod{i}") for i in range(1, 11)]
    temp_manifest.add_vods(records)

    # Mock process_single_vod: fail, fail, succeed, fail, fail, succeed, etc.
    # Pattern: 2 failures, 1 success, 2 failures, 1 success, ...
    # This should NOT trip circuit breaker (threshold=3 consecutive)
    mock_orchestrator.process_single_vod.side_effect = [
        False, False, True,  # 2 failures then success (resets counter)
        False, False, True,  # 2 failures then success (resets counter)
        False, False, True,  # 2 failures then success (resets counter)
        True  # Final success
    ]

    # Process batch
    summary = batch_processor.process_batch()

    # Verify all 10 VODs processed (circuit breaker never tripped)
    assert summary["processed"] == 10
    assert summary["succeeded"] == 4
    assert summary["failed"] == 6
    assert summary["circuit_breaker_tripped"] is False


def test_format_batch_report(batch_processor, temp_manifest, mock_orchestrator, mock_validator):
    """Test format_batch_report generates human-readable output."""
    # Setup: Add 5 VODs and process them
    records = [make_record(f"vod{i}") for i in range(1, 6)]
    temp_manifest.add_vods(records)

    # Mock mixed results
    mock_orchestrator.process_single_vod.side_effect = [True, True, True, False, True]

    # Mock quality metrics with different tiers
    mock_validator.validate.side_effect = [
        {"overall_score": 0.9, "tier": "high"},
        {"overall_score": 0.75, "tier": "medium"},
        {"overall_score": 0.85, "tier": "high"},
        {"overall_score": 0.80, "tier": "high"},
    ]

    # Process batch
    summary = batch_processor.process_batch()

    # Generate report
    report = batch_processor.format_batch_report(summary)

    # Verify report contains key sections
    assert "== Batch Processing Report ==" in report
    assert "Processed: 5/5 VODs" in report
    assert "Succeeded: 4 (80.0%)" in report
    assert "Failed: 1" in report
    assert "Quality Distribution:" in report
    assert "Manifest Status:" in report
    assert "Circuit Breaker:" in report


def test_cleanup_handles_missing_directory(batch_processor, temp_manifest, mock_orchestrator):
    """Test _cleanup_partial_output handles missing output directory gracefully."""
    # Setup: Create a VOD record (but no output directory)
    record = make_record("vod1")

    # Call cleanup directly
    batch_processor._cleanup_partial_output(record)

    # Should not raise an exception (graceful handling)
    # Test passes if no exception is raised


def test_get_processing_queue_ordering(batch_processor, temp_manifest):
    """Test _get_processing_queue returns VODs in tournament order."""
    # Setup: Add VODs from multiple tournaments
    records = [
        make_record("vod5", "Tournament C"),
        make_record("vod2", "Tournament A"),
        make_record("vod4", "Tournament B"),
        make_record("vod1", "Tournament A"),
        make_record("vod3", "Tournament B"),
    ]
    temp_manifest.add_vods(records)

    # Get processing queue
    queue = batch_processor._get_processing_queue(batch_size=10)

    # Verify ordering: Tournament A (vod1, vod2), Tournament B (vod3, vod4), Tournament C (vod5)
    expected_order = ["vod1", "vod2", "vod3", "vod4", "vod5"]
    actual_order = [r.vod_id for r in queue]
    assert actual_order == expected_order
