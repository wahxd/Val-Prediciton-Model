"""Dataset expansion CLI - discover and process VCT VODs.

Standalone script for expanding the training dataset by:
1. Discovering VODs from VLR.gg event pages
2. Downloading and processing them through Valoscribe
3. Tracking state in manifest.json for resumability

Usage examples:
    # Discover + process VODs from Masters Bangkok
    python scripts/expand_dataset.py "https://www.vlr.gg/event/matches/2094/masters-bangkok/"

    # Only discover VODs (queue for later processing)
    python scripts/expand_dataset.py "https://www.vlr.gg/event/matches/2094/masters-bangkok/" --discover-only

    # Resume processing (no discovery, just process pending)
    python scripts/expand_dataset.py --process-only

    # Dry run (show what would be done)
    python scripts/expand_dataset.py "https://www.vlr.gg/event/2094/" --dry-run
"""

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

# Add project root and Valoscribe to sys.path for imports
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

# Add Valoscribe src to path (for vlr_scraper import)
valoscribe_src = Path("D:/Git/valoscribe/src").resolve()
if valoscribe_src.exists():
    sys.path.insert(0, str(valoscribe_src))

from src.scraping import ProcessingConfig, ProcessingManifest, VODOrchestrator


def extract_tournament_name(event_url: str) -> str:
    """Extract tournament name from VLR.gg event URL.

    Args:
        event_url: VLR.gg event URL

    Returns:
        Tournament name (slug from URL)
    """
    parsed = urlparse(event_url)
    parts = parsed.path.strip('/').split('/')

    # URL format: /event/matches/ID/tournament-slug/
    # or: /event/ID/tournament-slug/
    if 'event' in parts:
        # Find the tournament slug (last non-numeric part)
        for part in reversed(parts):
            if part and not part.isdigit() and part != 'event' and part != 'matches':
                return part.replace('-', ' ').title()

    return "Unknown Tournament"


def main():
    parser = argparse.ArgumentParser(
        description="Expand dataset by discovering and processing VCT VODs from VLR.gg",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Discover + process VODs from Masters Bangkok
  python scripts/expand_dataset.py "https://www.vlr.gg/event/matches/2094/masters-bangkok/"

  # Only discover VODs (queue for later processing)
  python scripts/expand_dataset.py "https://www.vlr.gg/event/matches/2094/masters-bangkok/" --discover-only

  # Resume processing (no discovery, just process pending)
  python scripts/expand_dataset.py --process-only

  # Check what's in the manifest
  python scripts/summarize_progress.py
        """
    )

    parser.add_argument(
        'event_url',
        nargs='?',
        help='VLR.gg event URL to discover VODs from'
    )

    parser.add_argument(
        '--manifest',
        type=Path,
        default=Path('data/processing/manifest.json'),
        help='Path to manifest file (default: data/processing/manifest.json)'
    )

    parser.add_argument(
        '--output-dir',
        type=Path,
        help='Output directory for processed data (default: data/processing/processed)'
    )

    parser.add_argument(
        '--discover-only',
        action='store_true',
        help='Only scrape VLR.gg and populate manifest, do not process'
    )

    parser.add_argument(
        '--process-only',
        action='store_true',
        help='Skip discovery, only process existing pending VODs in manifest'
    )

    parser.add_argument(
        '--tournament',
        type=str,
        help='Tournament name for manifest metadata (default: extracted from event URL)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without executing'
    )

    parser.add_argument(
        '--valoscribe-repo',
        type=Path,
        help='Path to Valoscribe repo (default: D:/Git/valoscribe or EXPANSION_VALOSCRIBE_REPO env var)'
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.process_only and not args.event_url:
        parser.error("event_url is required unless --process-only is specified")

    if args.discover_only and args.process_only:
        parser.error("--discover-only and --process-only are mutually exclusive")

    # Create config
    config_kwargs = {}
    if args.output_dir:
        config_kwargs['output_dir'] = args.output_dir
    if args.valoscribe_repo:
        config_kwargs['valoscribe_repo'] = args.valoscribe_repo
    if args.manifest:
        config_kwargs['manifest_path'] = args.manifest

    config = ProcessingConfig(**config_kwargs)

    # Create or load manifest
    manifest = ProcessingManifest(config.manifest_path)

    # Create orchestrator
    orchestrator = VODOrchestrator(config, manifest)

    print("=" * 60)
    print("Dataset Expansion")
    print("=" * 60)
    print(f"Manifest: {config.manifest_path}")
    print(f"Output:   {config.output_dir}")
    print(f"Mode:     {'DRY RUN' if args.dry_run else 'LIVE'}")
    print()

    # Step 1: Discovery (if not --process-only)
    if not args.process_only and args.event_url:
        tournament_name = args.tournament or extract_tournament_name(args.event_url)

        print(f"Discovering VODs from: {args.event_url}")
        print(f"Tournament: {tournament_name}")
        print()

        if args.dry_run:
            print("[DRY RUN] Would discover VODs and add to manifest")
        else:
            new_vods = orchestrator.scrape_and_populate(args.event_url, tournament_name)
            print(f"✓ Discovered {new_vods} new VODs")
            print()

    # Step 2: Processing (if not --discover-only)
    if not args.discover_only:
        pending = manifest.get_pending()
        print(f"Pending VODs: {len(pending)}")

        if len(pending) == 0:
            print("No pending VODs to process.")
        elif args.dry_run:
            print(f"[DRY RUN] Would process {len(pending)} VODs:")
            for record in pending[:5]:  # Show first 5
                print(f"  - {record.vod_id}: {record.teams[0]} vs {record.teams[1]} on {record.map_name}")
            if len(pending) > 5:
                print(f"  ... and {len(pending) - 5} more")
        else:
            print("Starting processing pipeline...")
            print()
            summary = orchestrator.run_pipeline()

            print()
            print("=" * 60)
            print("Processing Complete")
            print("=" * 60)
            print(f"Total VODs:     {summary['total']}")
            print(f"Complete:       {summary['by_status'].get('complete', 0)}")
            print(f"Failed:         {summary['by_status'].get('failed', 0)}")
            print(f"Skipped:        {summary['by_status'].get('skipped', 0)}")
            print(f"Pending:        {summary['by_status'].get('pending', 0)}")

            if summary.get('total_processing_time_seconds'):
                hours = summary['total_processing_time_seconds'] / 3600
                print(f"Processing time: {hours:.2f} hours")

    # Final summary
    if not args.dry_run:
        summary = manifest.get_summary()
        print()
        print(f"Manifest saved to: {config.manifest_path}")
        print(f"Run 'python scripts/summarize_progress.py' for detailed progress report")


if __name__ == '__main__':
    main()
