"""Tests for async VLREventScraper."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.scraping import VLREventScraper


# Fixture HTML for event page with match links
FIXTURE_EVENT_PAGE_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div class="wf-card">
        <a href="/12345/sentinels-vs-nrg">SEN vs NRG</a>
        <a href="/12346/loud-vs-furia">LOUD vs FURIA</a>
    </div>
    <div class="wf-card">
        <a href="/12347/100t-vs-eg">100T vs EG</a>
    </div>
    <a href="/team/123">Team Page (should be filtered out)</a>
</body>
</html>
"""


# Fixture HTML for match page (minimal version of VLRMatchScraper fixture)
FIXTURE_MATCH_PAGE_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div class="match-header">
        <a class="match-header-link"><div class="wf-title-med">Sentinels</div></a>
        <div class="match-header-vs-score">
            <div class="js-spoiler">2</div>
            <div class="js-spoiler">1</div>
        </div>
        <a class="match-header-link"><div class="wf-title-med">NRG</div></a>
        <div class="moment-tz-convert" data-utc-ts="1704067200">Jan 1, 2024</div>
    </div>
    <div class="vm-stats-gamesnav">
        <div class="vm-stats-gamesnav-item" data-game-id="all">All Maps</div>
        <div class="vm-stats-gamesnav-item" data-game-id="123">1Ascent</div>
    </div>
    <table class="wf-table-inset mod-overview"><tr><th>All</th></tr></table>
    <table class="wf-table-inset mod-overview"><tr><th>All</th></tr></table>
    <table class="wf-table-inset mod-overview">
        <tr>
            <td><a href="/player/1001/tenz"><div style="font-weight: 700">TenZ</div></a></td>
            <td><img title="jett" /></td>
            <td>1.8</td><td>320</td><td>25</td><td>18</td><td>5</td><td>+7</td><td>80</td><td>200</td><td>28</td><td>4</td><td>1</td>
        </tr>
    </table>
    <table class="wf-table-inset mod-overview"><tr><th>NRG</th></tr></table>
    <div class="vlr-rounds"><div class="vlr-rounds-row"><div></div></div></div>
</body>
</html>
"""


@pytest.mark.asyncio
async def test_async_context_manager():
    """Test that VLREventScraper works as async context manager."""
    async with VLREventScraper(cache_dir="data/cache/test") as scraper:
        assert scraper.client is not None

    # Client should be closed after exiting context
    # (can't test directly, but no errors should occur)


@pytest.mark.asyncio
async def test_discover_match_urls_finds_correct_urls():
    """Test that discover_match_urls extracts correct match URLs from event page."""
    # Mock httpx response
    mock_response = MagicMock()
    mock_response.text = FIXTURE_EVENT_PAGE_HTML
    mock_response.raise_for_status = MagicMock()

    # Create scraper and manually inject mock client
    scraper = VLREventScraper()

    # Mock client
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    # Manually set client (bypass async context manager for test)
    scraper.client = mock_client

    urls = await scraper.discover_match_urls("https://www.vlr.gg/event/2094/test")

    # Should find 3 match URLs (filter out /team/123)
    assert len(urls) == 3
    assert "https://www.vlr.gg/12345/sentinels-vs-nrg" in urls
    assert "https://www.vlr.gg/12346/loud-vs-furia" in urls
    assert "https://www.vlr.gg/12347/100t-vs-eg" in urls


@pytest.mark.asyncio
async def test_scrape_match_delegates_to_match_scraper():
    """Test that scrape_match delegates to VLRMatchScraper and returns parsed data."""
    # Mock httpx response
    mock_response = MagicMock()
    mock_response.text = FIXTURE_MATCH_PAGE_HTML
    mock_response.raise_for_status = MagicMock()

    # Create scraper and manually inject mock client
    scraper = VLREventScraper()

    # Mock client
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    # Manually set client
    scraper.client = mock_client

    match_data = await scraper.scrape_match("https://www.vlr.gg/12345/sen-vs-nrg")

    # Verify match data structure (VLRMatchScraper was used)
    assert match_data["match_url"] == "https://www.vlr.gg/12345/sen-vs-nrg?game=all&tab=overview"
    assert match_data["teams"] == ["Sentinels", "NRG"]
    assert match_data["match_score"] == "2-1"
    assert len(match_data["maps"]) == 1


@pytest.mark.asyncio
async def test_scrape_match_adds_game_all_parameter():
    """Test that scrape_match adds game=all parameter if missing."""
    mock_response = MagicMock()
    mock_response.text = FIXTURE_MATCH_PAGE_HTML
    mock_response.raise_for_status = MagicMock()

    # Create scraper and manually inject mock client
    scraper = VLREventScraper()

    # Mock client
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    # Manually set client
    scraper.client = mock_client

    await scraper.scrape_match("https://www.vlr.gg/12345/sen-vs-nrg")

    # Verify get was called with game=all parameter
    call_args = mock_client.get.call_args[0][0]
    assert "game=all" in call_args
    assert "tab=overview" in call_args


@pytest.mark.asyncio
async def test_scrape_tournament_scrapes_multiple_matches():
    """Test that scrape_tournament discovers and scrapes all matches."""
    # Mock responses for event page and match pages
    mock_event_response = MagicMock()
    mock_event_response.text = FIXTURE_EVENT_PAGE_HTML
    mock_event_response.raise_for_status = MagicMock()

    mock_match_response = MagicMock()
    mock_match_response.text = FIXTURE_MATCH_PAGE_HTML
    mock_match_response.raise_for_status = MagicMock()

    # Create scraper and manually inject mock client
    scraper = VLREventScraper()

    # Mock client with side_effect for multiple calls
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[
        mock_event_response,  # Event page
        mock_match_response,  # Match 1
        mock_match_response,  # Match 2
        mock_match_response,  # Match 3
    ])

    # Manually set client
    scraper.client = mock_client

    results = await scraper.scrape_tournament(
        "https://www.vlr.gg/event/2094/test",
        "Test Tournament"
    )

    # Should return 3 match data dicts
    assert len(results) == 3
    for result in results:
        assert result["teams"] == ["Sentinels", "NRG"]
        assert result["match_score"] == "2-1"


@pytest.mark.asyncio
async def test_context_manager_raises_if_not_used():
    """Test that methods raise RuntimeError if not used in async context."""
    scraper = VLREventScraper()

    # Should raise RuntimeError because client is None
    with pytest.raises(RuntimeError, match="must be used as async context manager"):
        await scraper.discover_match_urls("https://www.vlr.gg/event/2094/test")

    with pytest.raises(RuntimeError, match="must be used as async context manager"):
        await scraper.scrape_match("https://www.vlr.gg/12345/sen-vs-nrg")

    with pytest.raises(RuntimeError, match="must be used as async context manager"):
        await scraper.scrape_tournament("https://www.vlr.gg/event/2094/test", "Test")


@pytest.mark.asyncio
async def test_imports_cleanly():
    """Test that VLREventScraper and VLRMatchScraper can be imported from src.scraping."""
    from src.scraping import VLREventScraper, VLRMatchScraper

    assert VLREventScraper is not None
    assert VLRMatchScraper is not None
