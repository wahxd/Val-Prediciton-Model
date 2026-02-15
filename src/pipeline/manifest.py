"""Processing manifest for tracking VOD processing state across days/weeks.

The manifest provides:
- VODRecord dataclass capturing all metadata for a single map VOD
- ProcessingManifest class with atomic JSON persistence
- Resumable state tracking (pending, downloading, processing, complete, failed, skipped)
- Crash-safe atomic writes (temp file + rename)
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal


StatusType = Literal["pending", "downloading", "processing", "complete", "failed", "skipped"]


@dataclass
class VODRecord:
    """A single VOD record with processing state.

    Attributes:
        vod_id: Unique identifier, format: "{vlr_match_id}_map{N}"
        youtube_url: YouTube VOD URL
        vlr_match_url: VLR.gg match page URL
        teams: List of 2 team names
        map_name: Valorant map name (Bind, Haven, etc.)
        map_number: Map number in the series (1-based)
        tournament: Tournament name
        date: ISO YYYY-MM-DD or empty string
        patch_version: Game patch version or None
        status: Processing status
        map_id: Valoscribe output directory name, set on completion
        error_message: Error message if status is "failed"
        retry_count: Number of retry attempts
        created_at: ISO timestamp when record was created
        started_at: ISO timestamp when processing started
        completed_at: ISO timestamp when processing completed
        processing_time_seconds: Total processing time
        player_stats: Per-player statistics from VLR.gg (optional)
        agent_compositions: Agent picks per map (optional)
        player_vlr_ids: Mapping of player names to VLR.gg player IDs (optional)
        match_score: Series score in "2-1" format (optional)
        match_outcome: Map outcome "team1_win" or "team2_win" (optional)
    """
    vod_id: str
    youtube_url: str
    vlr_match_url: str
    teams: list[str]
    map_name: str
    map_number: int
    tournament: str
    date: str
    patch_version: str | None
    status: StatusType = "pending"
    map_id: str | None = None
    error_message: str | None = None
    retry_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: str | None = None
    completed_at: str | None = None
    processing_time_seconds: float | None = None
    player_stats: dict | None = None
    agent_compositions: list[dict] | None = None
    player_vlr_ids: dict[str, int] | None = None
    match_score: str | None = None
    match_outcome: str | None = None


class ProcessingManifest:
    """Processing manifest with atomic JSON persistence.

    Manages a collection of VODRecord entries with:
    - Atomic saves (write to .tmp, then rename)
    - Resumable state (load existing manifest)
    - Status filtering and summary statistics
    - Bulk operations
    """

    def __init__(self, manifest_path: Path):
        """Initialize manifest, loading existing file if present.

        Args:
            manifest_path: Path to manifest.json file
        """
        self.manifest_path = Path(manifest_path)
        self.records: dict[str, VODRecord] = {}

        if self.manifest_path.exists():
            self.load()

    def load(self) -> None:
        """Load manifest from disk."""
        with open(self.manifest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.records = {
            vod_id: VODRecord(**vod_data)
            for vod_id, vod_data in data.get('vods', {}).items()
        }

    def save(self) -> None:
        """Atomically save manifest to disk.

        Uses write-to-temp-then-rename pattern for crash safety.
        """
        # Ensure parent directory exists
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)

        # Write to temp file
        tmp_path = self.manifest_path.with_suffix('.tmp')
        data = self.to_dict()

        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        # Atomic rename (works on Windows)
        tmp_path.replace(self.manifest_path)

    def to_dict(self) -> dict:
        """Serialize manifest to dict.

        Returns:
            Dict with updated_at timestamp and vods dict
        """
        return {
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'vods': {
                vod_id: asdict(record)
                for vod_id, record in self.records.items()
            }
        }

    def add_vod(self, record: VODRecord) -> None:
        """Add a single VOD record and save.

        Args:
            record: VODRecord to add
        """
        self.records[record.vod_id] = record
        self.save()

    def add_vods(self, records: list[VODRecord]) -> None:
        """Bulk add VOD records with single save.

        Args:
            records: List of VODRecord to add
        """
        for record in records:
            self.records[record.vod_id] = record
        self.save()

    def update_status(
        self,
        vod_id: str,
        status: StatusType,
        **kwargs
    ) -> None:
        """Update VOD status and optional fields, then save.

        Args:
            vod_id: VOD identifier
            status: New status
            **kwargs: Additional fields to update (map_id, error_message, etc.)
        """
        if vod_id not in self.records:
            raise KeyError(f"VOD {vod_id} not found in manifest")

        record = self.records[vod_id]
        record.status = status

        # Update additional fields
        for key, value in kwargs.items():
            if hasattr(record, key):
                setattr(record, key, value)

        self.save()

    def get_by_status(self, status: StatusType) -> list[VODRecord]:
        """Get all VODs with a specific status.

        Args:
            status: Status to filter by

        Returns:
            List of VODRecord with matching status
        """
        return [
            record for record in self.records.values()
            if record.status == status
        ]

    def get_pending(self) -> list[VODRecord]:
        """Get all pending VODs.

        Returns:
            List of VODRecord with status="pending"
        """
        return self.get_by_status("pending")

    def get_summary(self) -> dict:
        """Get summary statistics.

        Returns:
            Dict with counts by status, total processing time, etc.
        """
        status_counts = {}
        total_processing_time = 0.0

        for record in self.records.values():
            # Count by status
            status_counts[record.status] = status_counts.get(record.status, 0) + 1

            # Sum processing time
            if record.processing_time_seconds is not None:
                total_processing_time += record.processing_time_seconds

        # Calculate ETA estimate based on average processing time
        completed_count = status_counts.get("complete", 0)
        pending_count = status_counts.get("pending", 0)

        eta_seconds = None
        if completed_count > 0 and pending_count > 0:
            avg_time = total_processing_time / completed_count
            eta_seconds = avg_time * pending_count

        return {
            'total': len(self.records),
            'by_status': status_counts,
            'total_processing_time_seconds': total_processing_time,
            'eta_seconds': eta_seconds,
        }
