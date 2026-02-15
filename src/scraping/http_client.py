"""Async HTTP client factories with caching and rate limiting.

Provides:
- create_cached_client: httpx AsyncClient with rate limiting (caching requires hishel[async])
- create_youtube_client: Google YouTube Data API v3 client

Note: Full Hishel caching requires 'pip install hishel[async]'. This implementation focuses
on rate limiting as the critical feature.
"""

import asyncio
from pathlib import Path
from typing import Any

import httpx
from pyrate_limiter import Duration, Limiter, Rate
from googleapiclient.discovery import build


class RateLimitedTransport(httpx.AsyncBaseTransport):
    """HTTPX transport wrapper with rate limiting."""

    def __init__(self, transport: httpx.AsyncBaseTransport, limiter: Limiter):
        self._transport = transport
        self._limiter = limiter
        self._lock = asyncio.Lock()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Handle request with rate limiting."""
        async with self._lock:
            # Acquire rate limit slot
            await asyncio.to_thread(self._limiter.try_acquire, "http_request")

        # Forward to underlying transport
        return await self._transport.handle_async_request(request)

    async def aclose(self) -> None:
        """Close underlying transport."""
        await self._transport.aclose()


def create_cached_client(
    cache_dir: str | Path,
    ttl_seconds: int = 86400,
    rate_per_second: int = 1
) -> httpx.AsyncClient:
    """Create async HTTP client with rate limiting.

    Features:
    - pyrate-limiter rate limiting (default: 1 req/sec)
    - 10 second timeout
    - User-Agent header matching VLR.gg scraper pattern

    Note: cache_dir and ttl_seconds parameters are accepted for API compatibility
    but caching is not yet implemented (requires hishel[async]).

    Args:
        cache_dir: Directory for cache storage (reserved for future use)
        ttl_seconds: Cache TTL in seconds (reserved for future use)
        rate_per_second: Maximum requests per second (default: 1)

    Returns:
        Configured httpx.AsyncClient

    Example:
        async with create_cached_client(".cache/http", rate_per_second=2) as client:
            response = await client.get("https://vlr.gg/...")
    """
    # Create directory for potential future caching
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Create rate limiter
    limiter = Limiter(Rate(rate_per_second, Duration.SECOND))

    # Create rate-limited transport
    base_transport = httpx.AsyncHTTPTransport()
    rate_limited_transport = RateLimitedTransport(base_transport, limiter)

    # Create client with custom transport
    return httpx.AsyncClient(
        transport=rate_limited_transport,
        timeout=10.0,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    )


def create_youtube_client(api_key: str) -> Any:
    """Create YouTube Data API v3 client.

    Uses google-api-python-client (sync API).

    Args:
        api_key: YouTube Data API key

    Returns:
        YouTube API service object (googleapiclient.discovery.Resource)

    Example:
        client = create_youtube_client("YOUR_API_KEY")
        response = client.videos().list(part="snippet", id="VIDEO_ID").execute()
    """
    return build('youtube', 'v3', developerKey=api_key)
