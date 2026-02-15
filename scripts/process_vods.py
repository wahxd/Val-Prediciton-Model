"""CLI script for batch VOD processing through Valoscribe.

Usage:
    python scripts/process_vods.py                    # Process default batch (20 VODs)
    python scripts/process_vods.py --batch 50         # Process 50 VODs
    python scripts/process_vods.py --retry-failed     # Include previously failed VODs
    python scripts/process_vods.py --circuit-breaker 3  # Trip after 3 consecutive failures
    python scripts/process_vods.py --status            # Show manifest status only (no processing)

Output:
    - Processed maps in D:/Git/valoscribe/data/processed/{map_id}/
    - Quality metrics stored in data/processing/manifest.json
    - Batch report saved to data/processing/batch_report.txt
"""

import argparse
import shutil
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# Create parser for tests to import
parser = argparse.ArgumentParser(description="Batch VOD processing pipeline")
parser.add_argument("--batch", type=int, default=None, help="Number of VODs to process (default: config value)")
parser.add_argument("--retry-failed", action="store_true", help="Include previously failed VODs in batch")
parser.add_argument("--circuit-breaker", type=int, default=None, help="Consecutive failure threshold (default: config value)")
parser.add_argument("--status", action="store_true", help="Show manifest status and exit (no processing)")
parser.add_argument("--min-disk-gb", type=float, default=None, help="Minimum free disk space in GB (default: config value)")


def check_disk_space(path: Path, min_gb: float) -> bool:
    """Check if path has sufficient free disk space.

    Args:
        path: Directory path to check
        min_gb: Minimum required free space in GB

    Returns:
        True if free space >= min_gb, False otherwise
    """
    import structlog
    log = structlog.get_logger()

    usage = shutil.disk_usage(path)
    free_gb = usage.free / (1024 ** 3)
    required_gb = min_gb

    log.info(
        "disk_space_check",
        path=str(path),
        free_gb=f"{free_gb:.2f}",
        required_gb=f"{required_gb:.2f}",
        sufficient=free_gb >= required_gb
    )

    return free_gb >= required_gb


def show_status(manifest) -> None:
    """Print detailed manifest status to stdout.

    Args:
        manifest: ProcessingManifest to summarize
    """
    summary = manifest.get_summary()

    print("\n== Manifest Status ==")
    print(f"Total records: {summary['total']}")
    print()

    # By status
    print("By Status:")
    by_status = summary['by_status']
    for status in ["pending", "complete", "download_failed", "processing_failed", "failed", "skipped"]:
        count = by_status.get(status, 0)
        if count > 0:
            status_label = status.replace("_", " ").title()
            print(f"  {status_label}: {count}")

    # Quality distribution (for completed records)
    complete_records = manifest.get_by_status("complete")
    if complete_records:
        print()
        print(f"Quality Distribution ({len(complete_records)} complete):")

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

        for tier in ["high", "medium", "low", "unvalidated"]:
            count = quality_dist[tier]
            if count > 0:
                pct = (count / len(complete_records) * 100)
                tier_label = tier.capitalize()
                print(f"  {tier_label}: {count} ({pct:.1f}%)")

    # By tournament
    all_records = list(manifest.records.values())
    if all_records:
        print()
        print("By Tournament:")

        tournament_stats = {}
        for record in all_records:
            if record.tournament not in tournament_stats:
                tournament_stats[record.tournament] = {
                    "total": 0,
                    "complete": 0,
                    "pending": 0,
                    "failed": 0,
                }

            tournament_stats[record.tournament]["total"] += 1

            if record.status == "complete":
                tournament_stats[record.tournament]["complete"] += 1
            elif record.status == "pending":
                tournament_stats[record.tournament]["pending"] += 1
            elif record.status in ["failed", "download_failed", "processing_failed"]:
                tournament_stats[record.tournament]["failed"] += 1

        for tournament, stats in tournament_stats.items():
            print(f"  {tournament}: {stats['total']} total, {stats['complete']} complete, {stats['pending']} pending, {stats['failed']} failed")

    # ETA estimate
    if summary['eta_seconds'] is not None:
        eta_hours = summary['eta_seconds'] / 3600
        pending = by_status.get("pending", 0)
        avg_minutes = (summary['total_processing_time_seconds'] / by_status.get("complete", 1)) / 60
        print()
        print(f"Estimated remaining time: ~{eta_hours:.1f} hours ({pending} VODs x ~{avg_minutes:.1f} min/VOD)")

    print()


def main():
    """Main CLI entry point."""
    import structlog
    from src.config.processing import ProcessingConfig
    from src.pipeline.batch_processor import BatchProcessor
    from src.pipeline.manifest import ProcessingManifest
    from src.pipeline.orchestrator import VODOrchestrator
    from src.pipeline.quality_validator import QualityValidator

    args = parser.parse_args()

    # Configure structlog for readable console output
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
        ]
    )

    log = structlog.get_logger()

    # Load config
    config = ProcessingConfig()

    # Override config with CLI args
    if args.batch is not None:
        config.batch_size = args.batch
    if args.circuit_breaker is not None:
        config.circuit_breaker_threshold = args.circuit_breaker
    if args.min_disk_gb is not None:
        config.min_disk_space_gb = args.min_disk_gb

    # Load manifest
    log.info("loading_manifest", path=str(config.manifest_path))
    manifest = ProcessingManifest(config.manifest_path)

    # Status-only mode
    if args.status:
        show_status(manifest)
        return 0

    # Pre-flight disk space check
    download_path = config.download_dir
    download_path.mkdir(parents=True, exist_ok=True)

    if not check_disk_space(download_path, config.min_disk_space_gb):
        log.error(
            "insufficient_disk_space",
            required_gb=config.min_disk_space_gb,
            suggestion="Free up disk space or use --min-disk-gb to lower threshold"
        )
        return 1

    # Initialize pipeline components
    orchestrator = VODOrchestrator(config, manifest)
    validator = QualityValidator(config.output_dir)
    processor = BatchProcessor(orchestrator, manifest, validator, config)

    # Run batch processing
    pending_count = len(manifest.get_pending())
    log.info(
        "batch_starting",
        batch_size=config.batch_size,
        pending=pending_count,
        retry_failed=args.retry_failed
    )

    summary = processor.process_batch(
        batch_size=config.batch_size,
        retry_failed=args.retry_failed
    )

    # Print and save report
    report = processor.format_batch_report(summary)
    print("\n" + report)

    # Save report to file
    report_path = Path("data/processing/batch_report.txt")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    log.info("report_saved", path=str(report_path))

    # Show updated status
    print()  # Blank line separator
    show_status(manifest)

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
