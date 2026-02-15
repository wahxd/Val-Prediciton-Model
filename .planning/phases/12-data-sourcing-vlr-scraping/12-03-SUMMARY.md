---
phase: 12-data-sourcing-vlr-scraping
plan: 03
subsystem: data-sourcing
tags: [youtube, api, vod-discovery, quota-management, accessibility-validation]
requires: [12-01-PLAN]
provides:
  - youtube-vod-finder
  - video-accessibility-validation
  - quota-tracking-system
affects:
  - 12-04-PLAN
  - 12-05-PLAN
tech-stack:
  added: []
  patterns:
    - youtube-data-api-v3-integration
    - quota-exhaustion-detection
    - url-format-extraction
    - vlr-url-preference-with-fallback
key-files:
  created:
    - src/scraping/youtube_vod_finder.py
    - tests/scraping/test_youtube_vod_finder.py
  modified:
    - src/scraping/__init__.py
decisions:
  - id: QUOTA-01
    what: "Consume quota before API call (regardless of success/failure)"
    why: "YouTube API charges quota on request submission, not successful response. Tracking must match actual billing."
    impact: "QuotaExhaustedError raised before making call. Quota consumed even on API errors."
  - id: SEARCH-01
    what: "videoDuration='long' filter (>20min videos only)"
    why: "Map VODs are typically 30-60min. Highlights/clips are <10min. Long filter excludes clips without excluding full maps."
    impact: "Reduces false positives from highlight reels. May miss very short maps (<20min)."
  - id: VALIDATION-01
    what: "Check public + processed status, ignore embeddable"
    why: "yt-dlp downloads videos (doesn't embed them). Embeddable status is irrelevant for downloading."
    impact: "Videos marked 'not embeddable' are still considered valid if public and processed."
  - id: FALLBACK-01
    what: "Prefer VLR.gg URLs, fall back to YouTube search when missing/invalid"
    why: "VLR.gg URLs are curated and correct when present. Search is backup for missing links."
    impact: "Quota consumed validating VLR URLs before search. Failed validation triggers search fallback."
metrics:
  duration: "3m 46s"
  completed: "2026-02-15"
  tasks: 1
  commits: 1
  tests-added: 27
  tests-passing: 27
---

# Phase 12 Plan 03: YouTube VOD Finder Summary

**One-liner:** YouTube Data API v3 integration for map-specific VOD discovery with accessibility validation and 10,000-unit daily quota tracking

## What Was Built

### YouTubeVODFinder Class (src/scraping/youtube_vod_finder.py)

**Core Methods:**
1. `find_map_vod(teams, tournament, map_name, date, map_number) -> str | None`
   - Constructs search query: "{team1} vs {team2} {map_name} {tournament} [Map N]"
   - Date filtering: publishedAfter (date-7d), publishedBefore (date+30d)
   - Filters for long videos (>20min) to exclude highlights/clips
   - Returns first accessible video URL or None
   - Costs: 100 quota units for search + 1 unit per validation

2. `validate_video(video_id: str) -> bool`
   - Calls videos().list(part="status") to check accessibility
   - Validates: privacyStatus == "public" AND uploadStatus == "processed"
   - Ignores embeddable status (not relevant for yt-dlp downloads)
   - Costs: 1 quota unit per call

3. `find_vods_for_match(match_data: dict) -> dict[int, str | None]`
   - Processes all maps in a match
   - Prefers VLR.gg URLs when present and valid
   - Falls back to YouTube search when VLR URL missing or inaccessible
   - Returns map_number -> youtube_url mapping

**Quota Management:**
- `QUOTA_LIMIT = 10000` (daily limit)
- `quota_used` counter incremented before each API call
- `quota_remaining` property for monitoring
- `QuotaExhaustedError` raised before calls that would exceed limit

**URL Parsing:**
- `extract_video_id(url: str) -> str | None`
- Handles formats: youtube.com/watch?v=ID, youtu.be/ID, youtube.com/embed/ID
- Returns None for non-YouTube URLs

**Initialization:**
- Reads API key from YOUTUBE_API_KEY env var or explicit parameter
- Raises ValueError if API key not provided
- Creates YouTube API service via googleapiclient.discovery.build()
- Uses structlog for structured logging

## Commits

1. `8aaf72d` - feat(12-03): implement YouTube VOD finder with API v3 integration
   - YouTubeVODFinder class with search, validation, quota tracking
   - QuotaExhaustedError custom exception
   - URL extraction for all YouTube formats
   - 27 tests with fully mocked API (no real calls)

## Test Coverage

**27 tests passing** (all new)

- `TestInitialization` (3 tests)
  - Explicit API key, env var, missing key error

- `TestExtractVideoId` (5 tests)
  - Watch URL, watch with params, short URL, embed URL, invalid URL

- `TestValidateVideo` (5 tests)
  - Public/processed video, private video, unprocessed video
  - Nonexistent video, API error handling

- `TestFindMapVod` (5 tests)
  - Successful search with validation
  - No results, all videos private
  - Date filtering, query construction

- `TestQuotaManagement` (3 tests)
  - quota_remaining property
  - QuotaExhaustedError on search/validate
  - Quota tracking increments

- `TestFindVodsForMatch` (6 tests)
  - VLR URL preference, search fallback
  - Invalid VLR URL triggers fallback
  - Multiple maps, None for unfound VODs

**No real API calls:** All tests use unittest.mock.MagicMock to mock googleapiclient responses. Zero quota consumed during testing.

## Decisions Made

See frontmatter `decisions` section for full rationale.

**Key decision:** Quota consumed before API call (QUOTA-01). YouTube API charges quota on request submission regardless of success/failure. This matches actual billing behavior and prevents exceeding quota mid-call.

**Search optimization:** videoDuration='long' filter (SEARCH-01) excludes <20min videos. Map VODs are typically 30-60min. This dramatically reduces false positives from highlight reels.

**Validation pragmatism:** Ignore embeddable status (VALIDATION-01). We download via yt-dlp, not embed. Only public + processed matters.

## Deviations from Plan

None - plan executed exactly as written.

## Next Phase Readiness

**Ready for Plan 12-04** (VLR.gg Match Scraper Integration)

This plan provides:
- `YouTubeVODFinder` class for on-demand VOD discovery
- Quota tracking to prevent exceeding daily limits
- VLR URL validation before search fallback
- URL extraction for all YouTube formats

**Blockers:** None

**Concerns:**
- **Quota limits:** 10,000 units/day = ~100 searches. If scraping >100 matches/day, need to batch or use multiple API keys.
- **Search accuracy:** Query construction is heuristic. Team names with special characters or alternate spellings may fail. Future: add team name synonyms to improve search recall.
- **Date window:** 7 days before match, 30 days after. Assumes VODs uploaded within this window. Very old tournaments may require wider window.

## Files Changed

**Created (2 files):**
- src/scraping/youtube_vod_finder.py (366 lines)
- tests/scraping/test_youtube_vod_finder.py (630 lines)

**Modified (1 file):**
- src/scraping/__init__.py (+2 exports: YouTubeVODFinder, QuotaExhaustedError)

**Total:** 3 files, 996 lines added (code + tests)

## Integration Points

**Consumed by (future plans):**
- 12-04: VLR.gg Match Scraper will use find_vods_for_match() to fill missing VOD links
- 12-05: Orchestrator will check quota_remaining before batch scraping
- 13-XX: VOD processing pipeline may use extract_video_id() for URL normalization

**Consumes:**
- 12-01: Not directly (google-api-python-client installed in 12-01)
- Environment: YOUTUBE_API_KEY env var

## User Setup Required (Before Plan 12-04)

Per plan frontmatter `user_setup`:

1. **Enable YouTube Data API v3**
   - Google Cloud Console → APIs & Services → Library
   - Search "YouTube Data API v3" → Enable

2. **Create API Key**
   - Google Cloud Console → APIs & Services → Credentials
   - Create Credentials → API Key
   - (Optional) Restrict key to YouTube Data API v3 only

3. **Set Environment Variable**
   ```bash
   export YOUTUBE_API_KEY="your_api_key_here"
   ```
   Or add to .env file (if using python-dotenv)

4. **Verify Setup**
   ```python
   from src.scraping.youtube_vod_finder import YouTubeVODFinder
   finder = YouTubeVODFinder()  # Should not raise ValueError
   print(f"Quota remaining: {finder.quota_remaining}")
   ```

**Note:** Plan 12-04 will handle YOUTUBE_API_KEY as an optional enhancement. If key not set, scraper will use only VLR.gg URLs without YouTube search fallback.
