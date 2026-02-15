"""VLR.gg event page scraper for discovering match URLs from tournament listing pages.

This module provides the DISCOVERY layer for VOD processing. While Valoscribe's
VLRScraper handles individual match pages, this scraper discovers WHICH matches
to process by parsing VLR.gg event/results listing pages.
"""

import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
import structlog
from bs4 import BeautifulSoup

# Import Valoscribe's match scraper
try:
    from valoscribe.scraper.vlr_scraper import scrape_match
except ImportError:
    # If Valoscribe is not on path, scrape_match will fail at runtime
    # Plan 02 handles adding Valoscribe to sys.path
    scrape_match = None

from src.pipeline.manifest import ProcessingManifest, VODRecord

log = structlog.get_logger(__name__)


class VLREventScraper:
    """Scraper for VLR.gg event/tournament listing pages.

    Discovers match URLs from event results pages and creates VODRecord entries
    for each map with VOD available.
    """

    def __init__(self, rate_limit_seconds: float = 1.5):
        """Initialize event scraper.

        Args:
            rate_limit_seconds: Minimum seconds between requests (polite scraping)
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.rate_limit = rate_limit_seconds
        self.last_request_time = 0.0

    def _rate_limit_delay(self) -> None:
        """Sleep if needed to respect rate limit."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self.last_request_time = time.time()

    def _fetch_page(self, url: str) -> BeautifulSoup:
        """Fetch page with rate limiting.

        Args:
            url: URL to fetch

        Returns:
            BeautifulSoup object of parsed HTML
        """
        self._rate_limit_delay()
        log.info(f"Fetching {url}")

        response = self.session.get(url, timeout=10)
        response.raise_for_status()

        return BeautifulSoup(response.text, 'lxml')

    def discover_match_urls(self, event_url: str) -> list[str]:
        """Discover match URLs from VLR.gg event results page.

        Args:
            event_url: VLR.gg event URL (e.g., https://www.vlr.gg/event/matches/2094/...)

        Returns:
            List of full match URLs
        """
        soup = self._fetch_page(event_url)

        match_urls = []
        base_url = "https://www.vlr.gg"

        # VLR.gg match links are within wf-card containers
        # The link format is /NUMBER/team1-vs-team2
        # Try multiple selector patterns
        match_links = []

        # Pattern 1: Look for direct match item links
        match_links.extend(soup.find_all('a', href=re.compile(r'^/\d+/.*')))

        # Pattern 2: Look for links within wf-card containers
        cards = soup.find_all('div', class_='wf-card')
        for card in cards:
            links = card.find_all('a', href=re.compile(r'^/\d+/.*'))
            match_links.extend(links)

        # Extract unique match URLs
        seen = set()
        for link in match_links:
            href = link.get('href', '')
            if not href or href in seen:
                continue

            # Match links look like: /12345/team-a-vs-team-b
            # Sometimes there are other links like /team/123, filter those out
            if re.match(r'^/\d+/[a-z0-9\-]+vs[a-z0-9\-]+', href):
                full_url = urljoin(base_url, href)
                match_urls.append(full_url)
                seen.add(href)

        if not match_urls:
            log.warning(
                f"Found 0 match URLs on {event_url}. "
                f"This may indicate VLR.gg HTML structure has changed. "
                f"Check selectors in discover_match_urls()."
            )

        log.info(f"Discovered {len(match_urls)} match URLs from {event_url}")
        return match_urls

    def discover_vods(
        self,
        event_url: str,
        manifest: ProcessingManifest,
        tournament_name: str
    ) -> int:
        """Discover VODs from event page and add to manifest.

        Args:
            event_url: VLR.gg event URL
            manifest: Processing manifest to add VODRecords to
            tournament_name: Tournament name for metadata

        Returns:
            Count of new VODs added
        """
        if scrape_match is None:
            raise ImportError(
                "valoscribe.scraper.vlr_scraper.scrape_match is not available. "
                "Ensure Valoscribe is installed or on sys.path."
            )

        match_urls = self.discover_match_urls(event_url)
        new_vods = []

        log.info(f"Processing {len(match_urls)} matches for {tournament_name}")

        for i, match_url in enumerate(match_urls, 1):
            log.info(f"[{i}/{len(match_urls)}] Scraping match: {match_url}")

            try:
                # Rate limit before Valoscribe scraper call
                self._rate_limit_delay()

                # Scrape match page using Valoscribe
                match_data = scrape_match(match_url)

                teams = match_data.get('teams', [])
                maps = match_data.get('maps', [])

                # Extract match ID from URL
                match_id = extract_match_id_from_url(match_url)

                for map_data in maps:
                    map_number = map_data.get('map_number')
                    vod_url = map_data.get('vod_url')

                    # Skip if no VOD URL
                    if not vod_url:
                        log.debug(f"Skipping map {map_number} (no VOD URL)")
                        continue

                    # Build VOD ID
                    vod_id = f"{match_id}_map{map_number}"

                    # Skip if already in manifest (idempotent)
                    if vod_id in manifest.records:
                        log.debug(f"Skipping {vod_id} (already in manifest)")
                        continue

                    # Extract team names and metadata
                    map_name = map_data.get('map_name', 'Unknown')

                    # Build VODRecord
                    record = VODRecord(
                        vod_id=vod_id,
                        youtube_url=vod_url,
                        vlr_match_url=match_url,
                        teams=teams,
                        map_name=map_name,
                        map_number=map_number,
                        tournament=tournament_name,
                        date="",  # VLR doesn't always provide dates
                        patch_version=None,
                        status="pending",
                    )

                    new_vods.append(record)
                    log.info(f"Added {vod_id}: {teams[0]} vs {teams[1]} on {map_name}")

            except Exception as e:
                log.error(f"Failed to scrape {match_url}: {e}")
                continue

        # Bulk add to manifest
        if new_vods:
            manifest.add_vods(new_vods)

        log.info(
            f"Discovered {len(new_vods)} new VODs from {len(match_urls)} matches "
            f"for {tournament_name}"
        )

        return len(new_vods)


def extract_match_id_from_url(url: str) -> str:
    """Extract numeric match ID from VLR.gg match URL.

    Args:
        url: VLR.gg match URL (e.g., https://www.vlr.gg/12345/team-a-vs-team-b)

    Returns:
        Match ID as string (e.g., "12345")
    """
    parsed = urlparse(url)
    path_parts = parsed.path.strip('/').split('/')
    if path_parts:
        # First part should be the numeric ID
        match_id = path_parts[0]
        if match_id.isdigit():
            return match_id
    raise ValueError(f"Could not extract match ID from URL: {url}")


def discover_matches(
    event_url: str,
    manifest_path: Path,
    tournament_name: str,
    rate_limit: float = 1.5
) -> int:
    """Convenience function to discover matches from an event page.

    Args:
        event_url: VLR.gg event URL
        manifest_path: Path to manifest.json
        tournament_name: Tournament name for metadata
        rate_limit: Seconds between requests

    Returns:
        Count of new VODs added
    """
    scraper = VLREventScraper(rate_limit_seconds=rate_limit)
    manifest = ProcessingManifest(manifest_path)

    return scraper.discover_vods(event_url, manifest, tournament_name)
