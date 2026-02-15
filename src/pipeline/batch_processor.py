"""Batch VOD processing with progress tracking, circuit breaker, and quality validation.

Replaces VODOrchestrator.run_pipeline() with:
- tqdm progress bars with ETA
- Circuit breaker for consecutive failures
- Tournament-ordered processing
- Quality validation after each successful VOD
- Configurable batch size
"""

import shutil
from pathlib import Path

import structlog
from tqdm import tqdm

from src.config.processing import ProcessingConfig
from src.pipeline.manifest import ProcessingManifest, VODRecord
from src.pipeline.quality_validator import QualityValidator


class BatchProcessor:
    """Batch VOD processor with progress tracking and failure resilience.

    Features:
    - tqdm progress bars showing current VOD, tournament, and ETA
    - Circuit breaker: stops after N consecutive failures
    - Tournament ordering: processes all maps from one tournament before next
    - Quality validation: runs QualityValidator after each successful VOD
    - Partial output cleanup: removes incomplete Valoscribe output on failure
    - Retry support: optionally include failed records in processing queue
    """

    def __init__(
        self,
        orchestrator,  # VODOrchestrator (avoid circular import in type hint)
        manifest: ProcessingManifest,
        quality_validator: QualityValidator,
        config: ProcessingConfig,
    ):
        """Initialize batch processor.

        Args:
            orchestrator: VODOrchestrator instance for processing individual VODs
            manifest: ProcessingManifest for state tracking
            quality_validator: QualityValidator for post-processing quality checks
            config: ProcessingConfig with batch settings
        """
        self.orchestrator = orchestrator
        self.manifest = manifest
        self.validator = quality_validator
        self.config = config
        self.log = structlog.get_logger(__name__)

    def _get_processing_queue(self, batch_size: int, retry_failed: bool = False) -> list[VODRecord]:
        """Get processing queue ordered by tournament then vod_id.

        Args:
            batch_size: Maximum number of VODs to include
            retry_failed: If True, include download_failed and processing_failed records

        Returns:
            List of VODRecord ordered by (tournament, vod_id), limited to batch_size
        """
        # Start with pending records
        queue = self.manifest.get_by_status("pending")

        # Add failed records if retry requested
        if retry_failed:
            download_failed = self.manifest.get_by_status("download_failed")
            processing_failed = self.manifest.get_by_status("processing_failed")

            # Reset their status to pending for retry
            for record in download_failed + processing_failed:
                self.manifest.update_status(record.vod_id, "pending")

            # Re-fetch pending after status updates
            queue = self.manifest.get_by_status("pending")

        # Sort by tournament then vod_id to group by tournament
        queue.sort(key=lambda r: (r.tournament, r.vod_id))

        # Limit to batch size
        return queue[:batch_size]

    def _cleanup_partial_output(self, record: VODRecord) -> None:
        """Clean up partial/corrupt Valoscribe output after processing failure.

        Args:
            record: VODRecord that failed processing
        """
        output_dir = self.config.output_dir / record.vod_id

        if not output_dir.exists():
            return

        try:
            # List files to delete
            files_to_delete = [
                output_dir / "events.jsonl",
                output_dir / "frames.csv",
                output_dir / "metadata.json",
            ]

            deleted_files = []
            for file_path in files_to_delete:
                if file_path.exists():
                    file_path.unlink()
                    deleted_files.append(file_path.name)

            # Remove directory if empty
            if not list(output_dir.iterdir()):
                output_dir.rmdir()
                self.log.info(
                    "cleaned_partial_output",
                    vod_id=record.vod_id,
                    deleted_files=deleted_files,
                    removed_dir=True
                )
            else:
                self.log.info(
                    "cleaned_partial_output",
                    vod_id=record.vod_id,
                    deleted_files=deleted_files,
                    removed_dir=False
                )

        except Exception as e:
            # Cleanup is best-effort -- don't propagate errors
            self.log.warning(
                "cleanup_failed",
                vod_id=record.vod_id,
                error=str(e)
            )

    def _generate_batch_summary(
        self,
        queue: list[VODRecord],
        processed: int,
        succeeded: int,
        failed: int
    ) -> dict:
        """Generate batch processing summary.

        Args:
            queue: Original processing queue
            processed: Number of VODs processed
            succeeded: Number of successful VODs
            failed: Number of failed VODs

        Returns:
            Summary dict with processing statistics
        """
        # Calculate quality distribution from completed records
        complete_records = self.manifest.get_by_status("complete")

        quality_dist = {
            "high": 0,
            "medium": 0,
            "low": 0,
            "unvalidated": 0,
        }

        for record in complete_records:
            if record.quality_metrics is None:
                quality_dist["unvalidated"] += 1
            else:
                tier = record.quality_metrics.get("tier", "unvalidated")
                if tier in quality_dist:
                    quality_dist[tier] += 1
                else:
                    quality_dist["unvalidated"] += 1

        # Check if circuit breaker tripped
        circuit_breaker_tripped = (
            failed > 0 and
            failed >= self.config.circuit_breaker_threshold and
            processed < len(queue)
        )

        return {
            "batch_size": len(queue),
            "processed": processed,
            "succeeded": succeeded,
            "failed": failed,
            "circuit_breaker_tripped": circuit_breaker_tripped,
            "quality_distribution": quality_dist,
            "manifest_summary": self.manifest.get_summary(),
        }

    def process_batch(self, batch_size: int | None = None, retry_failed: bool = False) -> dict:
        """Process a batch of VODs with progress tracking and circuit breaker.

        Args:
            batch_size: Number of VODs to process (default: config.batch_size)
            retry_failed: If True, retry download_failed and processing_failed records

        Returns:
            Batch summary dict with processing statistics
        """
        batch_size = batch_size or self.config.batch_size
        queue = self._get_processing_queue(batch_size, retry_failed)

        if not queue:
            self.log.info("no_vods_to_process")
            return self._generate_batch_summary([], 0, 0, 0)

        consecutive_failures = 0
        processed = 0
        succeeded = 0
        failed = 0

        # Track current tournament for progress display
        current_tournament = None

        with tqdm(total=len(queue), desc="Processing VODs", unit="vod") as pbar:
            for record in queue:
                # Log tournament transitions
                if record.tournament != current_tournament:
                    current_tournament = record.tournament
                    self.log.info("tournament_start", tournament=current_tournament)
                    pbar.set_postfix(tournament=current_tournament[:30])

                # Update progress bar description
                teams_str = f"{record.teams[0]} vs {record.teams[1]}" if len(record.teams) >= 2 else str(record.teams)
                pbar.set_description(f"{record.map_name}: {teams_str}"[:50])

                # Process the VOD
                success = self.orchestrator.process_single_vod(record)

                if success:
                    consecutive_failures = 0
                    succeeded += 1

                    # Run quality validation
                    try:
                        metrics = self.validator.validate(record.vod_id)
                        self.manifest.update_status(
                            record.vod_id,
                            "complete",  # Keep status as complete (already set by process_single_vod)
                            quality_metrics=metrics
                        )
                        self.log.info(
                            "quality_validated",
                            vod_id=record.vod_id,
                            score=metrics.get("overall_score", 0),
                            tier=metrics.get("tier", "unknown")
                        )
                    except Exception as e:
                        self.log.warning(
                            "quality_validation_failed",
                            vod_id=record.vod_id,
                            error=str(e)
                        )
                        # Quality validation failure is non-fatal -- VOD is still "complete"
                else:
                    consecutive_failures += 1
                    failed += 1

                    # Clean up partial output
                    self._cleanup_partial_output(record)

                # Always increment processed count
                processed += 1
                pbar.update(1)

                # Circuit breaker check (after incrementing processed)
                if not success and consecutive_failures >= self.config.circuit_breaker_threshold:
                    self.log.error(
                        "circuit_breaker_tripped",
                        consecutive_failures=consecutive_failures,
                        threshold=self.config.circuit_breaker_threshold,
                        remaining=len(queue) - processed
                    )
                    pbar.set_description("STOPPED: Circuit breaker tripped")
                    break

        return self._generate_batch_summary(queue, processed, succeeded, failed)

    def format_batch_report(self, summary: dict) -> str:
        """Format batch summary as human-readable report.

        Args:
            summary: Summary dict from process_batch()

        Returns:
            Multi-line formatted report string
        """
        manifest_summary = summary["manifest_summary"]
        quality_dist = summary["quality_distribution"]

        # Calculate percentages
        succeeded = summary["succeeded"]
        total_complete = manifest_summary["by_status"].get("complete", 0)

        succeeded_pct = (succeeded / summary["batch_size"] * 100) if summary["batch_size"] > 0 else 0.0

        # Quality percentages (of succeeded VODs)
        quality_total = sum(quality_dist.values())

        lines = [
            "== Batch Processing Report ==",
            f"Processed: {summary['processed']}/{summary['batch_size']} VODs",
            f"Succeeded: {succeeded} ({succeeded_pct:.1f}%)",
            f"Failed: {summary['failed']}",
            "",
            "Quality Distribution:",
        ]

        for tier in ["high", "medium", "low", "unvalidated"]:
            count = quality_dist[tier]
            pct = (count / quality_total * 100) if quality_total > 0 else 0.0
            tier_name = tier.capitalize()
            lines.append(f"  {tier_name}: {count} ({pct:.1f}%)")

        lines.extend([
            "",
            "Manifest Status:",
        ])

        by_status = manifest_summary["by_status"]
        status_labels = {
            "pending": "Pending",
            "complete": "Complete",
            "download_failed": "Download Failed",
            "processing_failed": "Processing Failed",
            "failed": "Failed",
            "skipped": "Skipped",
        }

        for status, label in status_labels.items():
            count = by_status.get(status, 0)
            if count > 0:
                lines.append(f"  {label}: {count}")

        # Circuit breaker status
        if summary["circuit_breaker_tripped"]:
            lines.extend([
                "",
                f"Circuit Breaker: TRIPPED ({summary['failed']} consecutive failures)"
            ])
        else:
            consecutive = summary["failed"] if summary["processed"] == summary["failed"] else 0
            lines.extend([
                "",
                f"Circuit Breaker: OK ({consecutive} consecutive failures)"
            ])

        return "\n".join(lines)
