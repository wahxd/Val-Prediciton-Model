"""Progress monitoring for dataset expansion.

Reads the processing manifest and provides human-readable progress reports
with statistics, ETA estimates, and failure details.

Usage examples:
    # Show progress summary
    python scripts/summarize_progress.py

    # Show detailed per-VOD breakdown
    python scripts/summarize_progress.py --verbose

    # Show only failed VODs with error messages
    python scripts/summarize_progress.py --failed
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

# Add project root to sys.path for imports
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

from src.scraping import ProcessingManifest


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "2h 15m", "45m 30s", "12s")
    """
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def main():
    parser = argparse.ArgumentParser(
        description="Show progress report for dataset expansion",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--manifest',
        type=Path,
        default=Path('data/processing/manifest.json'),
        help='Path to manifest file (default: data/processing/manifest.json)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show details for each VOD'
    )

    parser.add_argument(
        '--failed',
        action='store_true',
        help='Show only failed VODs with error messages'
    )

    args = parser.parse_args()

    # Check if manifest exists
    if not args.manifest.exists():
        print(f"Error: Manifest not found at {args.manifest}")
        print("Run 'python scripts/expand_dataset.py' to create it.")
        sys.exit(1)

    # Load manifest
    manifest = ProcessingManifest(args.manifest)
    summary = manifest.get_summary()

    # If showing failed only
    if args.failed:
        failed_vods = manifest.get_by_status('failed')

        if not failed_vods:
            print("No failed VODs in manifest.")
            sys.exit(0)

        print("=" * 70)
        print(f"Failed VODs ({len(failed_vods)})")
        print("=" * 70)
        print()

        for record in failed_vods:
            print(f"VOD ID:  {record.vod_id}")
            print(f"Teams:   {record.teams[0]} vs {record.teams[1]}" if len(record.teams) >= 2 else f"Teams: {record.teams}")
            print(f"Map:     {record.map_name}")
            print(f"URL:     {record.vlr_match_url}")
            print(f"Error:   {record.error_message or 'No error message'}")
            print(f"Retries: {record.retry_count}")
            print()

        sys.exit(0)

    # Otherwise, show full summary
    print("=" * 70)
    print("Dataset Expansion Progress")
    print("=" * 70)
    print()

    # Overall statistics
    total = summary['total']
    by_status = summary['by_status']

    print(f"Total VODs:     {total}")
    print(f"  Pending:      {by_status.get('pending', 0)}")
    print(f"  Downloading:  {by_status.get('downloading', 0)}")
    print(f"  Processing:   {by_status.get('processing', 0)}")
    print(f"  Complete:     {by_status.get('complete', 0)}")
    print(f"  Failed:       {by_status.get('failed', 0)}")
    print(f"  Skipped:      {by_status.get('skipped', 0)}")
    print()

    # Progress bar
    if total > 0:
        complete = by_status.get('complete', 0)
        progress_pct = (complete / total) * 100
        bar_width = 50
        filled = int(bar_width * complete / total)
        bar = '#' * filled + '-' * (bar_width - filled)
        print(f"Progress: [{bar}] {progress_pct:.1f}% ({complete}/{total})")
        print()

    # Group by tournament
    by_tournament = defaultdict(lambda: {
        'total': 0,
        'complete': 0,
        'pending': 0,
        'failed': 0,
        'skipped': 0
    })

    for record in manifest.records.values():
        tournament = record.tournament
        by_tournament[tournament]['total'] += 1
        by_tournament[tournament][record.status] += 1

    if by_tournament:
        print("By Tournament:")
        for tournament, stats in sorted(by_tournament.items()):
            print(f"  {tournament}:")
            print(f"    {stats['total']} VODs ({stats['complete']} complete, {stats['pending']} pending, {stats['failed']} failed)")
        print()

    # Processing time statistics
    total_time = summary.get('total_processing_time_seconds', 0)
    complete_count = by_status.get('complete', 0)
    pending_count = by_status.get('pending', 0)

    if complete_count > 0:
        avg_time = total_time / complete_count
        print("Processing Time:")
        print(f"  Total:   {format_duration(total_time)}")
        print(f"  Average: {format_duration(avg_time)} per map")

        if pending_count > 0:
            eta_seconds = avg_time * pending_count
            print(f"  ETA:     {format_duration(eta_seconds)} remaining ({pending_count} pending)")
        print()

    # Last processed
    complete_vods = manifest.get_by_status('complete')
    if complete_vods:
        # Sort by completed_at timestamp
        last_vod = max(complete_vods, key=lambda r: r.completed_at or '')
        print(f"Last processed: {last_vod.completed_at}")
        print(f"  VOD: {last_vod.vod_id}")
        print(f"  Map: {last_vod.map_name}")
        print()

    # Verbose output
    if args.verbose:
        print("=" * 70)
        print("All VODs")
        print("=" * 70)
        print()

        for record in manifest.records.values():
            status_symbol = {
                'pending': '○',
                'downloading': '⬇',
                'processing': '⚙',
                'complete': '✓',
                'failed': '✗',
                'skipped': '⊘'
            }.get(record.status, '?')

            teams_str = f"{record.teams[0]} vs {record.teams[1]}" if len(record.teams) >= 2 else str(record.teams)

            print(f"{status_symbol} {record.vod_id}")
            print(f"  {teams_str} - {record.map_name}")
            print(f"  Status: {record.status}")

            if record.status == 'complete':
                print(f"  Time: {format_duration(record.processing_time_seconds or 0)}")
            elif record.status == 'failed':
                print(f"  Error: {record.error_message}")
                print(f"  Retries: {record.retry_count}")

            print()


if __name__ == '__main__':
    main()
