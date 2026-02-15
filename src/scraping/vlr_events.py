"""VLR.gg event page scraper for discovering match URLs from tournament listing pages.

NOTE: VODOrchestrator.scrape_and_populate() references old API. Will be updated in Plan 04.

This module provides async DISCOVERY and SCRAPING for VLR.gg:
- Discovery: Parse event/results pages to find match URLs
- Scraping: Fetch match pages and extract rich metadata via VLRMatchScraper

Uses httpx + pyrate-limiter for async HTTP with rate limiting.
"""

import asyncio
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
import structlog
from bs4 import BeautifulSoup

from src.scraping.http_client import create_cached_client
from src.scraping.team_normalizer import TeamNormalizer
from src.scraping.vlr_match_scraper import VLRMatchScraper

log = structlog.get_logger(__name__)


class VLREventScraper:
    """Async scraper for VLR.gg event/tournament listing pages.

    Discovers match URLs from event results pages and scrapes individual match
    pages to extract rich metadata (player stats, agents, scores, etc.).

    Must be used as async context manager:
        async with VLREventScraper() as scraper:
            match_urls = await scraper.discover_match_urls(event_url)
            match_data = await scraper.scrape_match(match_urls[0])
    """

    def __init__(
        self,
        cache_dir: str | Path = "data/cache/vlr_pages",
        rate_per_second: float = 1.0,
        team_normalizer: TeamNormalizer | None = None,
    ):
        """Initialize event scraper.

        Args:
            cache_dir: Directory for HTTP cache storage
            rate_per_second: Maximum requests per second (default: 1.0)
            team_normalizer: TeamNormalizer instance (creates new if None)
        """
        self.cache_dir = Path(cache_dir)
        self.rate_per_second = rate_per_second
        self.client = None  # Created in async context

        # Create or use provided normalizer
        self.team_normalizer = team_normalizer or TeamNormalizer()

        # Create match scraper
        self.match_scraper = VLRMatchScraper(self.team_normalizer)

    async def __aenter__(self):
        """Enter async context: create HTTP client."""
        self.client = await create_cached_client(
            cache_dir=self.cache_dir,
            rate_per_second=int(self.rate_per_second)
        ).__aenter__()
        return self

    async def __aexit__(self, *args):
        """Exit async context: close HTTP client."""
        if self.client:
            await self.client.__aexit__(*args)

    async def discover_match_urls(self, event_url: str) -> list[str]:
        """Discover match URLs from VLR.gg event results page.

        Args:
            event_url: VLR.gg event URL (e.g., https://www.vlr.gg/event/matches/2094/...)

        Returns:
            List of full match URLs
        """
        if not self.client:
            raise RuntimeError("VLREventScraper must be used as async context manager")

        log.info(f"Discovering matches from {event_url}")

        # Fetch event page
        response = await self.client.get(event_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'lxml')

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

    async def scrape_match(self, match_url: str) -> dict:
        """Scrape a single VLR.gg match page for rich metadata.

        Args:
            match_url: VLR.gg match URL

        Returns:
            Match data dict from VLRMatchScraper.parse_match()
        """
        if not self.client:
            raise RuntimeError("VLREventScraper must be used as async context manager")

        # Ensure URL has game=all parameter
        if '?game=all' not in match_url and '&game=all' not in match_url:
            separator = '&' if '?' in match_url else '?'
            match_url = f"{match_url}{separator}game=all&tab=overview"

        log.debug(f"Fetching match page: {match_url}")

        # Fetch match page
        response = await self.client.get(match_url)
        response.raise_for_status()

        # Parse with VLRMatchScraper
        return self.match_scraper.parse_match(response.text, match_url)

    async def scrape_tournament(
        self,
        event_url: str,
        tournament_name: str
    ) -> list[dict]:
        """Scrape all matches from a tournament event page.

        Args:
            event_url: VLR.gg event URL
            tournament_name: Tournament name (for logging)

        Returns:
            List of match data dicts from VLRMatchScraper.parse_match()
        """
        if not self.client:
            raise RuntimeError("VLREventScraper must be used as async context manager")

        # Discover match URLs
        match_urls = await self.discover_match_urls(event_url)

        if not match_urls:
            log.warning(f"No matches found for {tournament_name}")
            return []

        log.info(f"Scraping {len(match_urls)} matches for {tournament_name}")

        # Scrape each match with concurrency limit
        # Semaphore limits concurrent requests, rate limiter handles pacing
        semaphore = asyncio.Semaphore(5)
        results = []

        async def scrape_with_semaphore(i: int, url: str):
            async with semaphore:
                log.info(f"[{i+1}/{len(match_urls)}] Scraping match: {url}")
                try:
                    match_data = await self.scrape_match(url)
                    return match_data
                except Exception as e:
                    log.error(f"Failed to scrape {url}: {e}")
                    return None

        # Create tasks for all matches
        tasks = [
            scrape_with_semaphore(i, url)
            for i, url in enumerate(match_urls)
        ]

        # Wait for all to complete
        results = await asyncio.gather(*tasks)

        # Filter out None results (failed scrapes)
        valid_results = [r for r in results if r is not None]

        log.info(
            f"Scraped {len(valid_results)}/{len(match_urls)} matches for {tournament_name}"
        )

        return valid_results


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
