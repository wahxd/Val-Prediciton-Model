"""Tests for process_vods.py CLI script."""

import sys
from pathlib import Path
from unittest.mock import Mock, patch
from io import StringIO

import pytest

# Import functions from scripts/process_vods.py
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from process_vods import check_disk_space, show_status, parser

from src.pipeline.manifest import ProcessingManifest, VODRecord


@pytest.fixture
def temp_manifest_path(tmp_path):
    """Temporary manifest path."""
    return tmp_path / "manifest.json"


@pytest.fixture
def sample_manifest(temp_manifest_path):
    """Create a sample manifest with various statuses."""
    manifest = ProcessingManifest(temp_manifest_path)

    # Add records with different statuses
    manifest.add_vods([
        VODRecord(
            vod_id="123_map1",
            youtube_url="https://youtube.com/watch?v=test1",
            vlr_match_url="https://vlr.gg/123",
            teams=["Team A", "Team B"],
            map_name="Bind",
            map_number=1,
            tournament="Test Tournament 2024",
            date="2024-01-15",
            patch_version="8.11",
            status="complete",
            quality_metrics={"tier": "high", "overall_score": 0.92}
        ),
        VODRecord(
            vod_id="123_map2",
            youtube_url="https://youtube.com/watch?v=test2",
            vlr_match_url="https://vlr.gg/123",
            teams=["Team A", "Team B"],
            map_name="Haven",
            map_number=2,
            tournament="Test Tournament 2024",
            date="2024-01-15",
            patch_version="8.11",
            status="pending"
        ),
        VODRecord(
            vod_id="456_map1",
            youtube_url="https://youtube.com/watch?v=test3",
            vlr_match_url="https://vlr.gg/456",
            teams=["Team C", "Team D"],
            map_name="Ascent",
            map_number=1,
            tournament="Another Tournament 2024",
            date="2024-01-20",
            patch_version="8.11",
            status="download_failed",
            error_message="Video unavailable"
        ),
    ])

    return manifest


class TestCheckDiskSpace:
    """Tests for check_disk_space function."""

    def test_sufficient_space(self, tmp_path):
        """Test disk space check when space is sufficient."""
        # Mock disk_usage to return 50GB free
        mock_usage = Mock()
        mock_usage.free = 50 * (1024 ** 3)  # 50 GB in bytes

        with patch('shutil.disk_usage', return_value=mock_usage):
            result = check_disk_space(tmp_path, min_gb=10.0)

        assert result is True

    def test_insufficient_space(self, tmp_path):
        """Test disk space check when space is insufficient."""
        # Mock disk_usage to return 5GB free
        mock_usage = Mock()
        mock_usage.free = 5 * (1024 ** 3)  # 5 GB in bytes

        with patch('shutil.disk_usage', return_value=mock_usage):
            result = check_disk_space(tmp_path, min_gb=10.0)

        assert result is False

    def test_exactly_minimum_space(self, tmp_path):
        """Test disk space check when space exactly equals minimum."""
        # Mock disk_usage to return exactly 10GB free
        mock_usage = Mock()
        mock_usage.free = 10 * (1024 ** 3)

        with patch('shutil.disk_usage', return_value=mock_usage):
            result = check_disk_space(tmp_path, min_gb=10.0)

        assert result is True  # >= min_gb


class TestShowStatus:
    """Tests for show_status function."""

    def test_show_status_with_records(self, sample_manifest):
        """Test show_status with a manifest containing various records."""
        # Capture stdout
        captured_output = StringIO()

        with patch('sys.stdout', captured_output):
            show_status(sample_manifest)

        output = captured_output.getvalue()

        # Verify key elements in output
        assert "== Manifest Status ==" in output
        assert "Total records: 3" in output
        assert "Pending: 1" in output
        assert "Complete: 1" in output
        assert "Download Failed: 1" in output
        assert "Quality Distribution (1 complete):" in output
        assert "High: 1 (100.0%)" in output
        assert "Test Tournament 2024" in output
        assert "Another Tournament 2024" in output

    def test_show_status_empty_manifest(self, temp_manifest_path):
        """Test show_status with an empty manifest."""
        manifest = ProcessingManifest(temp_manifest_path)

        # Should not crash
        captured_output = StringIO()
        with patch('sys.stdout', captured_output):
            show_status(manifest)

        output = captured_output.getvalue()
        assert "Total records: 0" in output

    def test_show_status_with_unvalidated_quality(self, temp_manifest_path):
        """Test show_status with complete records lacking quality_metrics."""
        manifest = ProcessingManifest(temp_manifest_path)

        manifest.add_vod(VODRecord(
            vod_id="789_map1",
            youtube_url="https://youtube.com/watch?v=test",
            vlr_match_url="https://vlr.gg/789",
            teams=["Team E", "Team F"],
            map_name="Split",
            map_number=1,
            tournament="Test Tournament",
            date="2024-01-01",
            patch_version="8.11",
            status="complete",
            quality_metrics=None  # No quality validation
        ))

        captured_output = StringIO()
        with patch('sys.stdout', captured_output):
            show_status(manifest)

        output = captured_output.getvalue()
        assert "Unvalidated: 1 (100.0%)" in output


class TestArgparse:
    """Tests for argparse configuration."""

    def test_defaults(self):
        """Test that argument parser has correct defaults."""
        args = parser.parse_args([])

        assert args.batch is None
        assert args.retry_failed is False
        assert args.circuit_breaker is None
        assert args.status is False
        assert args.min_disk_gb is None

    def test_batch_flag(self):
        """Test --batch flag."""
        args = parser.parse_args(["--batch", "50"])
        assert args.batch == 50

    def test_retry_failed_flag(self):
        """Test --retry-failed flag."""
        args = parser.parse_args(["--retry-failed"])
        assert args.retry_failed is True

    def test_circuit_breaker_flag(self):
        """Test --circuit-breaker flag."""
        args = parser.parse_args(["--circuit-breaker", "3"])
        assert args.circuit_breaker == 3

    def test_status_flag(self):
        """Test --status flag."""
        args = parser.parse_args(["--status"])
        assert args.status is True

    def test_min_disk_gb_flag(self):
        """Test --min-disk-gb flag."""
        args = parser.parse_args(["--min-disk-gb", "5.0"])
        assert args.min_disk_gb == 5.0

    def test_all_flags_together(self):
        """Test parsing all flags together."""
        args = parser.parse_args([
            "--batch", "50",
            "--retry-failed",
            "--circuit-breaker", "3",
            "--min-disk-gb", "5.0"
        ])

        assert args.batch == 50
        assert args.retry_failed is True
        assert args.circuit_breaker == 3
        assert args.min_disk_gb == 5.0

    def test_status_flag_standalone(self):
        """Test --status flag can be used alone."""
        args = parser.parse_args(["--status"])
        assert args.status is True
        assert args.batch is None
