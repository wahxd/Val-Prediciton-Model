"""End-to-end tournament scraper integrating VLR.gg scraping + YouTube VOD discovery.

Wires together:
- VLREventScraper: Match discovery and rich metadata extraction
- YouTubeVODFinder: VOD discovery and accessibility validation
- ProcessingManifest: Persistent storage of VODRecords

Purpose: Populate manifest with 80-100 VODRecords ready for Phase 13 processing.
"""

import asyncio
from collections import defaultdict
from pathlib import Path

import structlog

from src.pipeline.manifest import ProcessingManifest, VODRecord
from src.scraping.team_normalizer import TeamNormalizer
from src.scraping.vlr_events import VLREventScraper, extract_match_id_from_url
from src.scraping.youtube_vod_finder import YouTubeVODFinder, QuotaExhaustedError

log = structlog.get_logger(__name__)


class TournamentScraper:
    """End-to-end tournament scraper for populating processing manifest.

    Orchestrates:
    1. VLREventScraper: Discover match URLs and scrape rich metadata
    2. YouTubeVODFinder: Find and validate accessible VODs
    3. ProcessingManifest: Store VODRecords with complete metadata

    Features:
    - Skips maps without accessible VODs (not stored as partial records)
    - Handles YouTube quota exhaustion (falls back to VLR URLs only)
    - Idempotent (skips already-processed vod_ids)
    - Generates human-readable summary report

    Example:
        manifest = ProcessingManifest(Path("data/processing/manifest.json"))
        scraper = TournamentScraper(manifest, youtube_api_key="...")
        stats = await scraper.scrape_tournament(event_url, "Masters Bangkok 2024")
        report = scraper.generate_report(stats)
        print(report)
    """

    def __init__(
        self,
        manifest: ProcessingManifest,
        youtube_api_key: str | None = None,
        cache_dir: str | Path = "data/cache/vlr_pages",
        rate_per_second: float = 1.0,
    ):
        """Initialize tournament scraper.

        Args:
            manifest: ProcessingManifest for storing VODRecords
            youtube_api_key: YouTube Data API key (reads from env if None)
            cache_dir: Directory for VLR.gg page caching
            rate_per_second: VLR.gg request rate limit (default: 1.0)
        """
        self.manifest = manifest
        self.cache_dir = Path(cache_dir)
        self.rate_per_second = rate_per_second

        # Create YouTubeVODFinder (or None if no API key)
        try:
            self.youtube_finder = YouTubeVODFinder(api_key=youtube_api_key)
        except ValueError as e:
            log.warning(
                "youtube_api_key_missing",
                message=str(e),
                impact="YouTube search disabled, VLR URLs only"
            )
            self.youtube_finder = None

        # Create shared TeamNormalizer instance
        self.team_normalizer = TeamNormalizer()

        # Stats tracking: {tournament_name: {maps_found, maps_with_vod, ...}}
        self.stats: dict[str, dict] = {}

    async def scrape_tournament(
        self,
        event_url: str,
        tournament_name: str
    ) -> dict:
        """Scrape a single tournament and populate manifest with VODRecords.

        End-to-end workflow:
        1. Discover match URLs from event page via VLREventScraper
        2. For each match, scrape rich metadata (player stats, agents, scores)
        3. For each map in match:
           a. Validate VLR.gg VOD URL (if present)
           b. Fall back to YouTube search (if VLR URL missing/invalid)
           c. Skip map if no accessible VOD found
           d. Create VODRecord with complete metadata
        4. Bulk add all new VODRecords to manifest
        5. Return stats dict

        Args:
            event_url: VLR.gg event URL (e.g., https://www.vlr.gg/event/matches/1921/...)
            tournament_name: Tournament name for metadata and logging

        Returns:
            Stats dict: {
                "matches_found": int,
                "maps_found": int,
                "maps_with_vod": int,
                "maps_skipped": int,
                "skip_reasons": list[str]
            }
        """
        log.info(
            "tournament_scraping_started",
            tournament=tournament_name,
            event_url=event_url
        )

        # Initialize stats
        stats = {
            "matches_found": 0,
            "maps_found": 0,
            "maps_with_vod": 0,
            "maps_skipped": 0,
            "skip_reasons": []
        }

        # Track YouTube quota exhaustion
        youtube_quota_exhausted = False

        # Create VLREventScraper as async context manager
        async with VLREventScraper(
            cache_dir=self.cache_dir,
            rate_per_second=self.rate_per_second,
            team_normalizer=self.team_normalizer
        ) as scraper:
            # Discover match URLs
            match_urls = await scraper.discover_match_urls(event_url)
            stats["matches_found"] = len(match_urls)

            if not match_urls:
                log.warning(
                    "no_matches_discovered",
                    tournament=tournament_name,
                    event_url=event_url
                )
                self.stats[tournament_name] = stats
                return stats

            # Scrape all matches
            log.info(
                "scraping_matches",
                tournament=tournament_name,
                count=len(match_urls)
            )

            new_records = []

            for i, match_url in enumerate(match_urls, 1):
                log.info(
                    "scraping_match",
                    progress=f"{i}/{len(match_urls)}",
                    url=match_url
                )

                try:
                    match_data = await scraper.scrape_match(match_url)
                except Exception as e:
                    log.error(
                        "match_scraping_failed",
                        url=match_url,
                        error=str(e)
                    )
                    continue

                # Extract match-level metadata
                teams = match_data.get("teams", ["Team1", "Team2"])
                date = match_data.get("date", "")
                match_score = match_data.get("match_score", "")
                maps = match_data.get("maps", [])

                stats["maps_found"] += len(maps)

                # Process each map
                for map_data in maps:
                    map_number = map_data["map_number"]
                    map_name = map_data["map_name"]
                    vlr_vod_url = map_data.get("vod_url")

                    # Generate vod_id
                    match_id = extract_match_id_from_url(match_url)
                    vod_id = f"{match_id}_map{map_number}"

                    # Check idempotency: skip if already in manifest
                    if vod_id in self.manifest.records:
                        log.debug(
                            "map_already_in_manifest",
                            vod_id=vod_id,
                            teams=teams,
                            map_name=map_name
                        )
                        stats["maps_skipped"] += 1
                        stats["skip_reasons"].append(
                            f"{vod_id}: Already in manifest"
                        )
                        continue

                    # Find accessible VOD URL
                    youtube_url = None

                    # Step 1: Validate VLR.gg VOD URL if present
                    if vlr_vod_url and self.youtube_finder and not youtube_quota_exhausted:
                        video_id = self.youtube_finder.extract_video_id(vlr_vod_url)
                        if video_id:
                            try:
                                # Validate via YouTube API (in thread to avoid blocking)
                                is_valid = await asyncio.to_thread(
                                    self.youtube_finder.validate_video,
                                    video_id
                                )
                                if is_valid:
                                    youtube_url = vlr_vod_url
                                    log.debug(
                                        "vlr_vod_validated",
                                        vod_id=vod_id,
                                        url=youtube_url
                                    )
                            except QuotaExhaustedError as e:
                                log.warning(
                                    "youtube_quota_exhausted",
                                    quota_used=e.quota_used,
                                    quota_limit=e.quota_limit,
                                    action="Continuing with VLR URLs only"
                                )
                                youtube_quota_exhausted = True

                    elif vlr_vod_url and not self.youtube_finder:
                        # No YouTube API available, accept VLR URL as-is
                        youtube_url = vlr_vod_url
                        log.debug(
                            "vlr_vod_accepted_without_validation",
                            vod_id=vod_id,
                            url=youtube_url
                        )

                    # Step 2: Fall back to YouTube search if no VLR URL or invalid
                    if not youtube_url and self.youtube_finder and not youtube_quota_exhausted:
                        try:
                            # Search via YouTube API (in thread to avoid blocking)
                            youtube_url = await asyncio.to_thread(
                                self.youtube_finder.find_map_vod,
                                teams=teams,
                                tournament=tournament_name,
                                map_name=map_name,
                                date=date,
                                map_number=map_number
                            )

                            if youtube_url:
                                log.debug(
                                    "youtube_search_success",
                                    vod_id=vod_id,
                                    url=youtube_url
                                )

                        except QuotaExhaustedError as e:
                            log.warning(
                                "youtube_quota_exhausted",
                                quota_used=e.quota_used,
                                quota_limit=e.quota_limit,
                                action="Continuing with VLR URLs only"
                            )
                            youtube_quota_exhausted = True

                    # Step 3: Skip map if no accessible VOD found
                    if not youtube_url:
                        log.info(
                            "map_skipped_no_vod",
                            vod_id=vod_id,
                            teams=teams,
                            map_name=map_name,
                            vlr_vod_url=vlr_vod_url or "None"
                        )
                        stats["maps_skipped"] += 1

                        if vlr_vod_url:
                            reason = f"{vod_id}: VLR VOD inaccessible (private/deleted)"
                        else:
                            reason = f"{vod_id}: No YouTube VOD found"

                        stats["skip_reasons"].append(reason)
                        continue

                    # Step 4: Create VODRecord with complete metadata
                    record = VODRecord(
                        vod_id=vod_id,
                        youtube_url=youtube_url,
                        vlr_match_url=match_url,
                        teams=teams,
                        map_name=map_name,
                        map_number=map_number,
                        tournament=tournament_name,
                        date=date,
                        patch_version=None,  # Unknown at scraping time
                        status="pending",
                        player_stats=map_data.get("player_stats"),
                        agent_compositions=map_data.get("agent_compositions"),
                        player_vlr_ids=map_data.get("player_vlr_ids"),
                        match_score=match_score,
                        match_outcome=None  # Unknown until Valoscribe processing
                    )

                    new_records.append(record)
                    stats["maps_with_vod"] += 1

                    log.debug(
                        "vod_record_created",
                        vod_id=vod_id,
                        teams=teams,
                        map_name=map_name
                    )

            # Bulk add all new VODRecords to manifest
            if new_records:
                self.manifest.add_vods(new_records)
                log.info(
                    "manifest_updated",
                    tournament=tournament_name,
                    new_records=len(new_records)
                )

        # Store stats for this tournament
        self.stats[tournament_name] = stats

        log.info(
            "tournament_scraping_complete",
            tournament=tournament_name,
            matches=stats["matches_found"],
            maps_found=stats["maps_found"],
            maps_with_vod=stats["maps_with_vod"],
            maps_skipped=stats["maps_skipped"]
        )

        return stats

    async def scrape_all(self, tournaments: list[dict]) -> dict:
        """Scrape multiple tournaments sequentially.

        Args:
            tournaments: List of {"event_url": str, "name": str} dicts

        Returns:
            Combined stats dict with totals across all tournaments
        """
        log.info(
            "multi_tournament_scraping_started",
            count=len(tournaments)
        )

        combined_stats = {
            "matches_found": 0,
            "maps_found": 0,
            "maps_with_vod": 0,
            "maps_skipped": 0,
            "skip_reasons": []
        }

        for i, tournament in enumerate(tournaments, 1):
            event_url = tournament["event_url"]
            tournament_name = tournament["name"]

            log.info(
                "processing_tournament",
                progress=f"{i}/{len(tournaments)}",
                name=tournament_name
            )

            # Scrape tournament
            stats = await self.scrape_tournament(event_url, tournament_name)

            # Update combined stats
            combined_stats["matches_found"] += stats["matches_found"]
            combined_stats["maps_found"] += stats["maps_found"]
            combined_stats["maps_with_vod"] += stats["maps_with_vod"]
            combined_stats["maps_skipped"] += stats["maps_skipped"]
            combined_stats["skip_reasons"].extend(stats["skip_reasons"])

            # Log progress
            if self.youtube_finder:
                log.info(
                    "tournament_complete",
                    name=tournament_name,
                    youtube_quota_remaining=self.youtube_finder.quota_remaining
                )

        # Check if we have enough maps
        total_maps = combined_stats["maps_with_vod"]
        if total_maps < 80:
            log.warning(
                "insufficient_maps",
                found=total_maps,
                target=80,
                suggestion="Add a third tournament to reach 80+ maps"
            )

        log.info(
            "multi_tournament_scraping_complete",
            total_maps_with_vod=total_maps
        )

        return combined_stats

    def generate_report(self, stats: dict | None = None) -> str:
        """Generate human-readable summary report.

        Args:
            stats: Combined stats dict from scrape_all() (or uses self.stats if None)

        Returns:
            Multi-line report string
        """
        lines = []
        lines.append("=" * 50)
        lines.append("SCRAPING REPORT")
        lines.append("=" * 50)
        lines.append("")

        # Per-tournament breakdown
        if self.stats:
            for tournament_name, tournament_stats in self.stats.items():
                lines.append(f"Tournament: {tournament_name}")
                lines.append(f"  Matches found: {tournament_stats['matches_found']}")
                lines.append(f"  Maps found: {tournament_stats['maps_found']}")
                lines.append(f"  Maps with accessible VOD: {tournament_stats['maps_with_vod']}")
                lines.append(f"  Maps skipped: {tournament_stats['maps_skipped']}")

                # Group skip reasons by type
                if tournament_stats["skip_reasons"]:
                    skip_reason_counts = defaultdict(int)
                    for reason in tournament_stats["skip_reasons"]:
                        # Extract reason type (after ": ")
                        if ": " in reason:
                            reason_type = reason.split(": ", 1)[1]
                            skip_reason_counts[reason_type] += 1

                    for reason_type, count in skip_reason_counts.items():
                        lines.append(f"    - {reason_type}: {count}")

                lines.append("")

        # Totals
        if stats:
            lines.append("=" * 50)
            lines.append("TOTALS")
            lines.append("=" * 50)
            lines.append(f"Total matches found: {stats['matches_found']}")
            lines.append(f"Total maps found: {stats['maps_found']}")
            lines.append(f"Total maps with VODs: {stats['maps_with_vod']}")
            lines.append(f"Total maps skipped: {stats['maps_skipped']}")

            if self.youtube_finder:
                lines.append(f"YouTube API quota used: {self.youtube_finder.quota_used}/{self.youtube_finder.QUOTA_LIMIT}")
                lines.append(f"YouTube API quota remaining: {self.youtube_finder.quota_remaining}")

            # Manifest summary
            manifest_summary = self.manifest.get_summary()
            pending_count = manifest_summary["by_status"].get("pending", 0)
            lines.append(f"Manifest records (pending): {pending_count}")
            lines.append("")

            # Warnings
            if stats["maps_with_vod"] < 80:
                lines.append("⚠ WARNING: Fewer than 80 maps with VODs found")
                lines.append("  Suggestion: Add a third tournament to reach target")
                lines.append("")

        report_text = "\n".join(lines)

        # Save report to file
        report_path = Path("data/processing/scraping_report.txt")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_text, encoding="utf-8")

        log.info("report_saved", path=str(report_path))

        return report_text
