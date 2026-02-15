"""CLI script to scrape VCT tournaments and populate processing manifest.

Usage:
    python scripts/scrape_tournaments.py

Requirements:
    - YOUTUBE_API_KEY environment variable set (or in .env file)

Output:
    - data/processing/manifest.json: Populated with 80-100 VODRecords
    - data/processing/scraping_report.txt: Summary report
"""

import asyncio
import os
import sys
from pathlib import Path

import structlog

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.pipeline.manifest import ProcessingManifest
from src.scraping.tournament_scraper import TournamentScraper

# Configure structlog for readable console output
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
    ]
)

log = structlog.get_logger()


# Tournament configuration
# NOTE: Verify event URLs at runtime. If 404, check VLR.gg for correct event page.
# To find correct URL:
# 1. Go to vlr.gg
# 2. Navigate to the tournament page
# 3. Click "Results" or "Matches" tab
# 4. Copy the URL (should contain /event/matches/{ID}/)
TOURNAMENTS = [
    {
        "event_url": "https://www.vlr.gg/event/matches/2094/valorant-champions-tour-2024-masters-bangkok/",
        "name": "Masters Bangkok 2024"
    },
    {
        "event_url": "https://www.vlr.gg/event/matches/2097/valorant-champions-tour-2024-americas-stage-1/",
        "name": "VCT Americas 2024 Stage 1"
    },
    # Add a third tournament if fewer than 80 maps found:
    # {
    #     "event_url": "https://www.vlr.gg/event/matches/XXXX/...",
    #     "name": "VCT Pacific 2024"
    # },
]


async def main():
    """Main scraping workflow."""
    log.info("scraping_script_started")

    # Load YouTube API key from environment
    youtube_api_key = os.environ.get("YOUTUBE_API_KEY")

    if not youtube_api_key:
        # Try loading from .env file
        try:
            from dotenv import load_dotenv
            load_dotenv()
            youtube_api_key = os.environ.get("YOUTUBE_API_KEY")
        except ImportError:
            log.warning("python-dotenv not installed, skipping .env file")

    if not youtube_api_key:
        log.warning(
            "youtube_api_key_missing",
            impact="YouTube search disabled, will only use VLR.gg VOD URLs",
            suggestion="Set YOUTUBE_API_KEY environment variable for full functionality"
        )

    # Initialize manifest
    manifest_path = Path("data/processing/manifest.json")
    log.info("loading_manifest", path=str(manifest_path))
    manifest = ProcessingManifest(manifest_path)

    initial_count = len(manifest.records)
    log.info("manifest_loaded", existing_records=initial_count)

    # Create tournament scraper
    scraper = TournamentScraper(
        manifest=manifest,
        youtube_api_key=youtube_api_key,
        cache_dir="data/cache/vlr_pages",
        rate_per_second=1.0
    )

    # Scrape all tournaments
    log.info("starting_tournament_scraping", count=len(TOURNAMENTS))
    stats = await scraper.scrape_all(TOURNAMENTS)

    # Generate and print report
    report = scraper.generate_report(stats)
    print("\n" + report)

    # Final summary
    final_count = len(manifest.records)
    new_records = final_count - initial_count

    log.info(
        "scraping_complete",
        initial_records=initial_count,
        new_records=new_records,
        final_records=final_count,
        maps_with_vod=stats["maps_with_vod"]
    )

    if stats["maps_with_vod"] < 80:
        log.warning(
            "insufficient_maps",
            found=stats["maps_with_vod"],
            target=80,
            suggestion="Add a third tournament to TOURNAMENTS list and re-run"
        )
        return 1  # Exit code 1 to indicate incomplete

    return 0  # Success


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
