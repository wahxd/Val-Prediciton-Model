# Phase 12: Data Sourcing / VLR.gg Scraping - Research

**Researched:** 2026-02-14
**Domain:** Web scraping, YouTube Data API, VLR.gg data extraction
**Confidence:** HIGH

## Summary

Phase 12 requires scraping 80-100 map VOD records from VLR.gg tournament pages, extracting match metadata, and discovering YouTube VOD links via YouTube Data API v3. The standard approach uses **httpx** for async HTTP requests, **Hishel** for RFC 9111-compliant HTTP caching, **pyrate-limiter** for rate limiting (replacing the basic time.sleep pattern), and **google-api-python-client** for YouTube API integration. VLR.gg provides static HTML (no JavaScript required), making BeautifulSoup + lxml sufficient for parsing.

Key findings:
1. **Existing VLRScraper in Valoscribe** extracts player stats, agent compositions, and starting sides from match pages—this already satisfies SCRP-03 and SCRP-04 requirements
2. **YouTube Data API** free tier (10,000 quota/day) supports ~100 map searches at 100 quota per search.list call
3. **Player identity via VLR.gg player profile IDs** (extracted from player links: `/player/{ID}/{name}`) provides stable cross-tournament tracking
4. **Team name normalization** should use **RapidFuzz** (faster, MIT license, drop-in replacement for TheFuzz) with manual mapping table fallback for common org rebrandings

**Primary recommendation:** Migrate from `requests` to `httpx.AsyncClient` with `Hishel` caching and `pyrate-limiter` rate limiting. Use Valoscribe's existing `scrape_match` for metadata extraction, then augment with YouTube API for VOD discovery validation.

## Standard Stack

The established libraries/tools for web scraping + API integration domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | >=0.28 | Async HTTP client | Industry standard for async Python HTTP; HTTP/2 support, connection pooling, cleaner API than aiohttp |
| Hishel | >=1.1 | HTTP caching for httpx | RFC 9111-compliant caching with filesystem/SQLite backends; seamless httpx integration |
| pyrate-limiter | >=4.0 | Rate limiting | Leaky bucket algorithm with multiple rate tiers; dedicated httpx transport integration |
| google-api-python-client | >=2.170 | YouTube Data API v3 | Official Google client library; handles auth, quota, pagination |
| BeautifulSoup4 | >=4.13 | HTML parsing | Already in requirements.txt; VLR.gg is static HTML |
| lxml | >=5.0 | HTML parser backend | Already in requirements.txt; 10-50x faster than html.parser |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| RapidFuzz | >=3.14 | Fuzzy string matching | Team name normalization across VLR.gg/Valoscribe; C++-backed, faster than TheFuzz |
| structlog | >=25.0 | Structured logging | Already in requirements.txt; track scraping progress, cache hits, API quota usage |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| httpx + Hishel | requests + requests-cache | httpx is async-native with better connection pooling; Hishel is more actively maintained (2026) |
| pyrate-limiter | Custom time.sleep() | Existing VLREventScraper uses time.sleep; pyrate-limiter handles multi-tier limits (1/sec + 100/min) and async locks |
| RapidFuzz | TheFuzz (FuzzyWuzzy) | RapidFuzz is MIT-licensed, 10x+ faster, drop-in compatible |
| google-api-python-client | Direct REST calls | Official client handles auth refreshing, quota tracking, error retries |

**Installation:**
```bash
pip install httpx>=0.28 hishel>=1.1 pyrate-limiter>=4.0 google-api-python-client>=2.170 RapidFuzz>=3.14
```

## Architecture Patterns

### Recommended Project Structure
```
src/
├── scraping/
│   ├── vlr_events.py          # VLREventScraper (DISCOVERY layer)
│   ├── youtube_vod_finder.py  # NEW: YouTube API integration
│   └── team_normalizer.py     # NEW: Team name normalization
├── pipeline/
│   ├── manifest.py             # ProcessingManifest + VODRecord (existing)
│   └── orchestrator.py         # VOD processing orchestrator (Phase 13)
data/
├── cache/
│   ├── vlr_pages/              # Hishel filesystem cache for VLR.gg pages
│   └── youtube_responses/      # Hishel cache for YouTube API responses
└── manifest.json               # ProcessingManifest persistence
```

### Pattern 1: Async HTTP Client with Connection Pooling
**What:** Single long-lived AsyncClient instance shared across scraping session
**When to use:** All HTTP requests (VLR.gg scraping, YouTube API calls)
**Example:**
```python
# Source: https://www.python-httpx.org/async/
import httpx
from hishel import AsyncCacheClient, AsyncFileStorage, CacheOptions

async def scrape_tournament(event_url: str):
    # Single AsyncClient for entire scraping session (connection pooling)
    storage = AsyncFileStorage(base_path="data/cache/vlr_pages")

    async with AsyncCacheClient(
        storage=storage,
        cache_options=CacheOptions(ttl=86400)  # 24-hour cache
    ) as client:
        # All requests reuse TCP connections
        event_page = await client.get(event_url)
        match_urls = discover_match_urls(event_page.text)

        # Concurrent match scraping with shared client
        tasks = [scrape_match(client, url) for url in match_urls]
        results = await asyncio.gather(*tasks)
```

### Pattern 2: Rate Limiting via Transport Layer
**What:** pyrate-limiter integrated as httpx transport (automatic enforcement)
**When to use:** VLR.gg scraping (1 req/sec polite scraping), YouTube API (within quota)
**Example:**
```python
# Source: https://pyratelimiter.readthedocs.io/
from pyrate_limiter import Duration, Rate, Limiter
from pyrate_limiter.extras.httpx_limiter import AsyncRateLimiterTransport
from hishel.httpx import AsyncCacheTransport
import httpx

# Define multi-tier rate limits
rates = [
    Rate(1, Duration.SECOND),    # 1 req/sec (VLR.gg polite scraping)
    Rate(100, Duration.MINUTE),  # 100 req/min (extra safety)
]
limiter = Limiter(*rates)

# Stack transports: caching -> rate limiting -> HTTP
cache_transport = AsyncCacheTransport(
    next_transport=AsyncRateLimiterTransport(
        limiter=limiter,
        next_transport=httpx.AsyncHTTPTransport()
    ),
    storage=AsyncFileStorage(base_path="data/cache/vlr_pages")
)

async with httpx.AsyncClient(transport=cache_transport) as client:
    # Automatic rate limiting + caching
    response = await client.get("https://www.vlr.gg/event/...")
```

### Pattern 3: YouTube API VOD Discovery
**What:** Search for map-specific VODs, validate accessibility before adding to manifest
**When to use:** After extracting match metadata from VLR.gg, before creating VODRecord
**Example:**
```python
# Source: https://developers.google.com/youtube/v3/docs
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

class YouTubeVODFinder:
    def __init__(self, api_key: str):
        self.youtube = build('youtube', 'v3', developerKey=api_key)

    async def find_map_vod(
        self,
        teams: list[str],
        tournament: str,
        map_name: str,
        date: str
    ) -> str | None:
        """Search for map VOD and validate accessibility."""
        query = f"{teams[0]} vs {teams[1]} {tournament} {map_name}"

        try:
            # search.list costs 100 quota units
            search_response = self.youtube.search().list(
                q=query,
                part="id,snippet",
                type="video",
                maxResults=5,
                publishedAfter=date  # Filter by tournament date
            ).execute()

            for item in search_response.get('items', []):
                video_id = item['id']['videoId']

                # videos.list costs 1 quota unit (validate accessibility)
                video_response = self.youtube.videos().list(
                    part="status,contentDetails",
                    id=video_id
                ).execute()

                if video_response['items']:
                    video = video_response['items'][0]
                    # Check embeddable, public, not blocked
                    if video['status']['embeddable'] and video['status']['privacyStatus'] == 'public':
                        return f"https://www.youtube.com/watch?v={video_id}"

            return None  # No accessible VOD found

        except HttpError as e:
            if e.resp.status == 403:  # quotaExceeded
                raise QuotaExceededError("YouTube API quota exceeded")
            raise
```

### Pattern 4: Player Identity Tracking via VLR.gg Profile IDs
**What:** Extract numeric player IDs from player profile links during match scraping
**When to use:** Enhancing VODRecord with player metadata for future player-level features
**Example:**
```python
# VLR.gg player links: https://www.vlr.gg/player/{ID}/{name}
def extract_player_ids(soup: BeautifulSoup) -> dict[str, int]:
    """Extract player name -> VLR.gg player ID mapping."""
    player_ids = {}

    # Player links in stat tables
    player_links = soup.find_all('a', href=re.compile(r'^/player/\d+/'))

    for link in player_links:
        href = link['href']  # e.g., "/player/12345/tenz"
        match = re.match(r'/player/(\d+)/(\w+)', href)
        if match:
            player_id = int(match.group(1))
            player_name = link.get_text(strip=True)
            player_ids[player_name] = player_id

    return player_ids
```

### Pattern 5: Team Name Normalization with RapidFuzz
**What:** Fuzzy match VLR.gg team names to Valoscribe outputs, with manual override table
**When to use:** After scraping team names from VLR.gg, before creating VODRecord
**Example:**
```python
# Source: https://github.com/rapidfuzz/RapidFuzz
from rapidfuzz import fuzz, process

class TeamNormalizer:
    def __init__(self):
        # Manual mapping for known org rebrandings
        self.manual_overrides = {
            "Sentinels": "SEN",
            "Team Liquid": "Liquid",
            "LOUD": "LOUD",
            # Add more as discovered
        }

    def normalize(self, vlr_name: str, known_teams: list[str]) -> str:
        """Normalize VLR.gg team name to canonical form."""
        # Check manual overrides first
        if vlr_name in self.manual_overrides:
            return self.manual_overrides[vlr_name]

        # Fuzzy match against known team names (from Valoscribe data)
        match, score, _ = process.extractOne(
            vlr_name,
            known_teams,
            scorer=fuzz.token_sort_ratio
        )

        # High confidence threshold (90+) for auto-matching
        if score >= 90:
            return match
        else:
            # Low confidence - log for manual review, return VLR name
            log.warning(f"Low confidence match: {vlr_name} -> {match} (score={score})")
            return vlr_name
```

### Anti-Patterns to Avoid
- **Creating AsyncClient per request:** Kills connection pooling and TLS handshake reuse—use single long-lived client
- **Hardcoded CSS selectors with zero fallback:** VLR.gg HTML structure can change—use multiple selector patterns (see existing VLREventScraper.discover_match_urls)
- **Ignoring YouTube API quota:** search.list costs 100 units; hitting 10,000/day limit breaks scraping—cache responses, batch searches
- **Storing VODRecords without VOD validation:** Phase 13 will waste time on inaccessible videos—validate via videos.list before adding to manifest
- **Random train/test splits on scraped data:** Temporal ordering critical for walk-forward validation—never shuffle match dates

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP caching | Custom file-based cache with dict storage | Hishel with AsyncFileStorage or AsyncSQLiteStorage | RFC 9111 compliance (cache headers, ETags), atomic writes, corruption recovery, 1.1.8 release (2026-01-11) |
| Rate limiting | time.sleep() with manual timing | pyrate-limiter with AsyncRateLimiterTransport | Multi-tier limits (1/sec + 100/min), async locks prevent race conditions, integration with httpx transport layer |
| Fuzzy string matching | Custom Levenshtein distance implementation | RapidFuzz | C++-backed (10-50x faster than pure Python), partial matching, token-based matching, MIT license |
| YouTube API auth | Manual OAuth flow + token refresh | google-api-python-client | Handles token expiry, refresh, error retries, quota tracking, official support |
| HTML parsing for static sites | Regex on raw HTML | BeautifulSoup + lxml | Handles malformed HTML, selector flexibility, 10-50x faster than html.parser |

**Key insight:** VLR.gg scraping is I/O-bound (network latency dominates), not CPU-bound. Caching (Hishel) + async concurrency (httpx.AsyncClient) provides 10-100x speedup over sync requests without caching. YouTube API quota (100 units/search) is the bottleneck, not request speed.

## Common Pitfalls

### Pitfall 1: YouTube API Quota Exhaustion
**What goes wrong:** search.list costs 100 quota units per call; 10,000 quota/day = 100 searches max. Scraping 100 maps without caching hits limit immediately.
**Why it happens:** Multiple searches per map (retries, typos in team names), no response caching, testing without quota awareness.
**How to avoid:**
- Cache YouTube API responses with Hishel (24-hour TTL)
- Use videos.list (1 unit) to validate accessibility instead of re-searching
- Construct precise search queries (team names + tournament + map name + date filter)
- Monitor quota usage via Google Cloud Console
**Warning signs:**
- `HttpError 403: quotaExceeded` errors
- Scraping stops after ~50-60 maps (if some searches required retries)

### Pitfall 2: VLR.gg HTML Structure Changes Breaking Selectors
**What goes wrong:** Hardcoded CSS class names (`wf-card`, `vm-stats-gamesnav-item`) change during VLR.gg site updates, breaking match discovery or metadata extraction.
**Why it happens:** VLR.gg has no official API; site redesigns happen without notice (see existing code warning: "This may indicate VLR.gg HTML structure has changed").
**How to avoid:**
- Use multiple selector patterns with fallbacks (see VLREventScraper.discover_match_urls: tries 2 patterns)
- Prefer structural selectors (parent-child relationships) over exact class names
- Log warnings when selectors return 0 results
- Cache scraped pages (Hishel) so re-scraping doesn't hit VLR.gg if selectors need fixing
- Add integration tests with real VLR.gg match URLs (detect breakage early)
**Warning signs:**
- `log.warning("Found 0 match URLs on {event_url}")` appearing in logs
- Empty `maps` list returned from scrape_match
- Missing player stats or agent compositions

### Pitfall 3: Storing Inaccessible YouTube VODs
**What goes wrong:** VOD links from VLR.gg or YouTube search point to deleted/private/region-blocked videos. Phase 13 processes these, wastes time downloading, then fails.
**Why it happens:** VLR.gg VOD links can be stale (video deleted after match page creation), YouTube search returns videos later made private.
**How to avoid:**
- Validate every VOD before adding to manifest: call `videos.list(id=video_id, part="status")` (1 quota unit)
- Check `status.privacyStatus == "public"` and `status.embeddable == true`
- Check `status.uploadStatus == "processed"` (not "deleted" or "failed")
- Skip maps with inaccessible VODs entirely (per context decisions: "hard requirement")
- Generate summary report: "80 maps scraped, 72 with accessible VODs, 8 skipped (no VOD: 3, private: 5)"
**Warning signs:**
- High failure rate in Phase 13 VOD processing
- YouTube API errors during download: "Video unavailable", "This video is private"

### Pitfall 4: AsyncClient Connection Pool Exhaustion
**What goes wrong:** Creating new AsyncClient for every match URL causes "too many open files" or connection timeout errors.
**Why it happens:** AsyncClient maintains connection pool; creating new client per request doesn't close old connections properly, especially in async loops.
**How to avoid:**
- **Single AsyncClient for entire scraping session** (see Pattern 1)
- Use `async with httpx.AsyncClient() as client:` at top level, pass client to functions
- Limit concurrent requests with asyncio.Semaphore (e.g., max 10 concurrent match scrapes)
- Set connection limits: `httpx.AsyncClient(limits=httpx.Limits(max_connections=20))`
**Warning signs:**
- `OSError: [Errno 24] Too many open files`
- Requests hanging/timing out after initial batch succeeds
- Memory usage growing continuously during scraping

### Pitfall 5: Team Name Normalization False Matches
**What goes wrong:** Fuzzy matching maps "Team Liquid" to "Liquid MIBR" or "Sentinels" to "Sentinels Academy" due to substring matches.
**Why it happens:** Default fuzzy matching algorithms (partial_ratio) prioritize substring matches; esports orgs have academy teams, variant names.
**How to avoid:**
- Use `fuzz.token_sort_ratio` (not `fuzz.partial_ratio`) to avoid substring bias
- Set high confidence threshold (90+) for auto-matching
- Maintain manual override table for known ambiguous cases
- Log low-confidence matches for manual review
- Add team name to VODRecord metadata for post-scraping correction
**Warning signs:**
- Valoscribe processing fails with "team name not found in metadata"
- VODRecords show mismatched team names (e.g., "Team A" in VLR, "Team A Academy" in record)

### Pitfall 6: Ignoring robots.txt and Rate Limits
**What goes wrong:** Scraping VLR.gg too aggressively triggers IP bans or request throttling (503 errors).
**Why it happens:** No robots.txt check, no rate limiting, concurrent requests without delays.
**How to avoid:**
- Respect 1 req/sec rate limit (VLR.gg community standard, per WebSearch findings)
- Use pyrate-limiter with multi-tier limits (1/sec + 100/min)
- Add User-Agent header (existing code already does this)
- Implement exponential backoff for 429/503 responses
- Cache pages with Hishel (avoids redundant requests during development/testing)
**Warning signs:**
- HTTP 429 (Too Many Requests) or 503 (Service Unavailable) errors
- IP address blocked from VLR.gg (requests timeout or return 403)
- VLR.gg discussion forum post about scraper abuse

## Code Examples

Verified patterns from official sources:

### Async HTTP Client with Hishel Caching
```python
# Source: https://hishel.com/1.0/integrations/httpx/
from hishel import AsyncCacheClient, AsyncFileStorage, CacheOptions
import httpx

async def scrape_with_cache():
    storage = AsyncFileStorage(base_path="data/cache/vlr_pages")

    async with AsyncCacheClient(
        storage=storage,
        cache_options=CacheOptions(ttl=86400),  # 24-hour cache
        timeout=httpx.Timeout(10.0)
    ) as client:
        response = await client.get("https://www.vlr.gg/event/...")
        # Subsequent requests hit cache if within TTL
        return response.text
```

### Rate-Limited Async Requests
```python
# Source: https://pyratelimiter.readthedocs.io/
from pyrate_limiter import Duration, Rate, Limiter
from pyrate_limiter.extras.httpx_limiter import AsyncRateLimiterTransport
import httpx

rates = [Rate(1, Duration.SECOND)]
limiter = Limiter(*rates)

transport = AsyncRateLimiterTransport(
    limiter=limiter,
    next_transport=httpx.AsyncHTTPTransport()
)

async with httpx.AsyncClient(transport=transport) as client:
    # Automatic 1 req/sec rate limiting
    for url in match_urls:
        response = await client.get(url)
```

### YouTube API VOD Search
```python
# Source: https://developers.google.com/youtube/v3/docs
from googleapiclient.discovery import build

youtube = build('youtube', 'v3', developerKey=api_key)

# Search for map VOD (100 quota units)
search_response = youtube.search().list(
    q=f"{team1} vs {team2} {tournament} {map_name}",
    part="id,snippet",
    type="video",
    maxResults=5,
    publishedAfter="2024-01-01T00:00:00Z"
).execute()

video_id = search_response['items'][0]['id']['videoId']

# Validate accessibility (1 quota unit)
video_response = youtube.videos().list(
    part="status",
    id=video_id
).execute()

is_accessible = (
    video_response['items'][0]['status']['privacyStatus'] == 'public' and
    video_response['items'][0]['status']['embeddable'] == True
)
```

### Concurrent Match Scraping with Semaphore
```python
# Source: https://www.python-httpx.org/async/
import asyncio

async def scrape_matches(client: httpx.AsyncClient, match_urls: list[str]):
    semaphore = asyncio.Semaphore(10)  # Max 10 concurrent requests

    async def scrape_one(url: str):
        async with semaphore:
            response = await client.get(url)
            return parse_match(response.text)

    tasks = [scrape_one(url) for url in match_urls]
    return await asyncio.gather(*tasks)
```

### RapidFuzz Team Name Matching
```python
# Source: https://github.com/rapidfuzz/RapidFuzz
from rapidfuzz import fuzz, process

def normalize_team_name(vlr_name: str, known_teams: list[str]) -> str:
    match, score, _ = process.extractOne(
        vlr_name,
        known_teams,
        scorer=fuzz.token_sort_ratio  # Avoids substring bias
    )

    if score >= 90:
        return match
    else:
        log.warning(f"Low confidence: {vlr_name} -> {match} ({score})")
        return vlr_name  # Return original if uncertain
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| requests (sync) | httpx AsyncClient | 2020+ | 10-100x throughput via async concurrency + connection pooling |
| time.sleep() rate limiting | pyrate-limiter transport | 2023+ | Multi-tier limits, async-safe, automatic enforcement |
| Custom file caching | Hishel RFC 9111 caching | 2024+ | Standards-compliant cache headers, atomic writes, SQLite backend |
| FuzzyWuzzy | RapidFuzz | 2021+ (rename) | 10-50x faster (C++ vs Python), MIT license vs GPL |
| Manual YouTube search | YouTube Data API v3 | Always standard | Quota management, official support, structured responses |

**Deprecated/outdated:**
- **requests-cache**: Last major update 2023; Hishel (2026) has better async support and httpx integration
- **FuzzyWuzzy**: Renamed to TheFuzz (2021) due to licensing; RapidFuzz is faster and more permissive
- **Selenium for VLR.gg**: Unnecessary; VLR.gg is static HTML (confirmed via WebSearch + existing VLRScraper)
- **Storing VODs without validation**: Old approach didn't check accessibility; new approach validates via videos.list (CONTEXT.md decision)

## Open Questions

Things that couldn't be fully resolved:

1. **VLR.gg player stats availability across all tournaments**
   - What we know: Valoscribe VLRScraper extracts ACS, K/D/A from stat tables; CONTEXT.md marks stats as "soft metadata"
   - What's unclear: Are stats available for all VCT tournaments (Masters Bangkok 2024, VCT Americas 2024)? Older tournaments may have incomplete stats.
   - Recommendation: Mark stats as optional in VODRecord schema; log when stats are missing but still create record if VOD is accessible

2. **YouTube API error codes for specific unavailability reasons**
   - What we know: videos.list returns status.privacyStatus ("public", "private", "unlisted"); search.list can return videos later deleted
   - What's unclear: How to distinguish "deleted" vs "region-blocked" vs "age-restricted" programmatically
   - Recommendation: Check status.uploadStatus ("processed", "deleted", "failed", "rejected") + status.embeddable; log full status object for debugging

3. **Third tournament selection if Bangkok + Americas yield <80 maps**
   - What we know: CONTEXT.md suggests Masters Shanghai 2024 or VCT EMEA 2024 as third option
   - What's unclear: Which has better VOD availability? Shanghai (international) or EMEA (regional)?
   - Recommendation: Check VLR.gg event pages for VOD link count before committing; Shanghai likely has more official VODs (Riot coverage)

4. **VLR.gg rate limiting threshold before IP ban**
   - What we know: Community standard is 1 req/sec (per WebSearch); no robots.txt file; ToS non-existent
   - What's unclear: Is 1 req/sec a hard limit or conservative estimate? Can we burst to 2-3 req/sec safely?
   - Recommendation: Start with 1 req/sec; monitor for 429/503 errors; increase conservatively if no issues after 50+ requests

## Sources

### Primary (HIGH confidence)
- [HTTPX Async Support](https://www.python-httpx.org/async/) - AsyncClient usage, connection pooling
- [Hishel httpx Integration](https://hishel.com/1.0/integrations/httpx/) - Caching with httpx AsyncClient
- [pyrate-limiter Documentation](https://pyratelimiter.readthedocs.io/) - Rate limiting patterns
- [YouTube Data API Quota Calculator](https://developers.google.com/youtube/v3/determine_quota_cost) - search.list (100 units), videos.list (1 unit), 10,000/day limit
- [YouTube Data API Reference](https://developers.google.com/youtube/v3/docs) - search.list, videos.list parameters
- [RapidFuzz GitHub](https://github.com/rapidfuzz/RapidFuzz) - Fuzzy matching API, performance comparison
- Valoscribe VLRScraper (D:\git\valoscribe\src\valoscribe\scraper\vlr_scraper.py) - Existing match scraper with player stats, agents, starting sides

### Secondary (MEDIUM confidence)
- [8 httpx + asyncio Patterns](https://medium.com/@sparknp1/8-httpx-asyncio-patterns-for-safer-faster-clients-f27bc82e93e6) - Connection pooling best practices (WebSearch verified with official docs)
- [Scrapfly: How to Use Cache in Web Scraping](https://scrapfly.io/blog/posts/how-to-use-cache-in-web-scraping) - Disk caching strategies (general patterns)
- [BeautifulSoup Web Scraping Guide 2026](https://www.javascriptdoctor.blog/2026/02/beautifulsoup-web-scraping.html) - lxml best practices
- [VLR.gg Scraping Discussion](https://www.vlr.gg/199479/vlr-scraping) - Community confirmation: no robots.txt, 1 req/sec polite scraping

### Tertiary (LOW confidence - needs validation)
- VLR.gg HTML structure stability: Multiple GitHub scrapers exist (axsddlr/vlrggapi, aritropaul/vlr.gg-scraper) but no guarantees structure won't change
- YouTube API video unavailability error codes: Official docs list 403/404 but don't enumerate all status.uploadStatus values
- Team name normalization accuracy: RapidFuzz benchmarks show 90%+ accuracy for company names, but esports team names (with academy/variant teams) may differ

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - httpx, Hishel, pyrate-limiter, google-api-python-client all have official docs and active 2026 releases
- Architecture: HIGH - Existing VLRScraper validates BeautifulSoup + lxml approach; httpx async patterns well-documented
- YouTube API: HIGH - Official quota costs, API reference, Python quickstart guide
- VLR.gg scraping: MEDIUM - No official API/docs; relying on community practices and existing Valoscribe scraper
- Team normalization: MEDIUM - RapidFuzz well-documented, but esports-specific accuracy untested
- Pitfalls: MEDIUM - Based on general web scraping best practices + YouTube API docs, not Phase 12-specific experience

**Research date:** 2026-02-14
**Valid until:** 2026-03-16 (30 days - web scraping practices and library versions stable; VLR.gg HTML structure can change anytime)
