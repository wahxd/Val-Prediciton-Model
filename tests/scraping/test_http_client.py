"""Tests for HTTP client factories."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import httpx

from src.scraping.http_client import create_cached_client, create_youtube_client


@pytest.mark.asyncio
async def test_create_cached_client_returns_async_client(tmp_path):
    """create_cached_client returns an httpx.AsyncClient (or wrapper)."""
    cache_dir = tmp_path / "cache"
    client = create_cached_client(cache_dir, ttl_seconds=3600, rate_per_second=2)

    # Verify it's an AsyncClient
    assert isinstance(client, httpx.AsyncClient)

    # Clean up
    await client.aclose()


@pytest.mark.asyncio
async def test_cached_client_respects_cache_dir(tmp_path):
    """Cache directory is created and used."""
    cache_dir = tmp_path / "http_cache"
    assert not cache_dir.exists()

    client = create_cached_client(cache_dir, ttl_seconds=3600)

    # Cache directory should be created
    assert cache_dir.exists()
    assert cache_dir.is_dir()

    await client.aclose()


@pytest.mark.asyncio
async def test_cached_client_has_user_agent():
    """Client has User-Agent header set."""
    client = create_cached_client(".cache/test", rate_per_second=1)

    # Check headers
    assert "User-Agent" in client.headers
    assert "Mozilla" in client.headers["User-Agent"]

    await client.aclose()


def test_create_youtube_client_returns_resource():
    """create_youtube_client returns a Resource object when given API key."""
    # Mock googleapiclient.discovery.build
    with patch('src.scraping.http_client.build') as mock_build:
        mock_resource = MagicMock()
        mock_build.return_value = mock_resource

        client = create_youtube_client("test_api_key_12345")

        # Verify build was called with correct parameters
        mock_build.assert_called_once_with('youtube', 'v3', developerKey="test_api_key_12345")

        # Verify we got the resource back
        assert client is mock_resource


def test_create_youtube_client_with_empty_key():
    """create_youtube_client accepts empty API key (googleapiclient will handle validation)."""
    with patch('src.scraping.http_client.build') as mock_build:
        mock_resource = MagicMock()
        mock_build.return_value = mock_resource

        client = create_youtube_client("")

        # Should still call build (validation happens at API call time)
        mock_build.assert_called_once_with('youtube', 'v3', developerKey="")
