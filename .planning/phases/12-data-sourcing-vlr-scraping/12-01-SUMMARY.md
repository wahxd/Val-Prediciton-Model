---
phase: 12-data-sourcing-vlr-scraping
plan: 01
subsystem: data-sourcing
tags: [scraping, infrastructure, http, normalization, data-model]
requires: [11-02-PLAN]
provides:
  - async-http-client-factory
  - rate-limiting-infrastructure
  - extended-vod-data-model
  - team-name-normalization
affects:
  - 12-02-PLAN
  - 12-03-PLAN
  - 12-04-PLAN
tech-stack:
  added:
    - httpx>=0.28
    - hishel>=1.1
    - pyrate-limiter>=4.0
    - google-api-python-client>=2.170
    - rapidfuzz>=3.14
    - pytest-asyncio
  patterns:
    - async-http-client-factory
    - rate-limited-transport-wrapper
    - fuzzy-string-matching
    - backward-compatible-data-extension
key-files:
  created:
    - src/scraping/http_client.py
    - src/scraping/team_normalizer.py
    - tests/scraping/__init__.py
    - tests/scraping/test_http_client.py
    - tests/scraping/test_team_normalizer.py
    - tests/pipeline/test_manifest_extended.py
  modified:
    - requirements.txt
    - src/pipeline/manifest.py
decisions:
  - id: INFRA-01
    what: "Defer Hishel caching until hishel[async] installed"
    why: "Installed version requires anysqlite extra for AsyncSqliteStorage. Rate limiting is critical, caching is nice-to-have."
    impact: "HTTP responses not cached to disk. VLR.gg scraping will hit network on every run."
    revisit: "Install hishel[async] when needed (Plan 12-02 or later)"
  - id: INFRA-02
    what: "Rate limiting via custom RateLimitedTransport wrapper"
    why: "pyrate-limiter doesn't have built-in httpx transport integration in installed version."
    impact: "Rate limiting works correctly (1 req/sec default). Slightly more complex implementation."
  - id: DATA-01
    what: "5 new optional VODRecord fields with None defaults"
    why: "Backward compatibility with existing manifest.json files from Phase 11."
    impact: "Old manifests load successfully. New scrapers can populate extended fields."
  - id: NORM-01
    what: "RapidFuzz token_sort_ratio with 85 threshold"
    why: "Balance between matching variants (GenG -> Gen.G Esports) and avoiding false positives."
    impact: "Low-confidence matches (< 85) return original name with warning log."
metrics:
  duration: "7m 17s"
  completed: "2026-02-15"
  tasks: 2
  commits: 2
  tests-added: 17
  tests-passing: 26
---

# Phase 12 Plan 01: Scraping Infrastructure Summary

**One-liner:** Async HTTP client with rate limiting, extended VODRecord with player stats/agents/IDs, and RapidFuzz team name normalization

## What Was Built

### Async HTTP Client Factory (src/scraping/http_client.py)
- `create_cached_client()`: Returns httpx.AsyncClient with rate limiting
  - pyrate-limiter integration via custom RateLimitedTransport
  - Configurable rate (default: 1 req/sec)
  - 10-second timeout, Mozilla User-Agent
  - Cache directory parameter reserved for future Hishel integration
- `create_youtube_client()`: Returns Google YouTube Data API v3 client
  - Uses google-api-python-client build() factory
  - Sync API (YouTube API is synchronous)

**Deviation:** Caching deferred (see INFRA-01 decision). Rate limiting implemented via custom transport wrapper instead of assumed httpx integration.

### Extended VODRecord Data Model (src/pipeline/manifest.py)
Added 5 optional fields to VODRecord:
1. `player_stats: dict | None` - Per-player stats from VLR.gg
   - Format: `{player_name: {acs, kills, deaths, assists, kast_pct, adr, hs_pct, fk, fd}}`
2. `agent_compositions: list[dict] | None` - Agent picks per map
   - Format: `[{name, team, agent}]`
3. `player_vlr_ids: dict[str, int] | None` - Player name -> VLR.gg ID mapping
4. `match_score: str | None` - Series score ("2-1")
5. `match_outcome: str | None` - Map outcome ("team1_win" or "team2_win")

All fields default to None for backward compatibility.

### Team Name Normalizer (src/scraping/team_normalizer.py)
- `TeamNormalizer.normalize()`: Fuzzy match VLR.gg team names
  - Manual overrides for 30+ VCT teams (Americas, Pacific, EMEA)
  - RapidFuzz token_sort_ratio matching (>= 85 threshold)
  - Logs warnings for low-confidence matches
- `TeamNormalizer.extract_player_vlr_id()`: Parse VLR.gg player links
  - Pattern: `/player/{ID}/{name}` -> int ID

## Commits

1. `314b420` - feat(12-01): add async HTTP client with rate limiting
   - Dependencies: httpx, hishel, pyrate-limiter, google-api-python-client, rapidfuzz
   - http_client.py with create_cached_client and create_youtube_client
   - 5 tests (all passing)

2. `7320f1b` - feat(12-01): extend VODRecord and add TeamNormalizer
   - 5 new optional VODRecord fields
   - TeamNormalizer with fuzzy matching
   - Backward compatible manifest loading
   - 12 tests (7 normalizer + 5 manifest extended)

## Test Coverage

**26 tests passing** (17 new, 9 existing pipeline tests verified for regressions)

- `test_http_client.py` (5 tests)
  - AsyncClient creation, cache directory handling, User-Agent header
  - YouTube client factory (mocked googleapiclient.discovery.build)
- `test_team_normalizer.py` (7 tests)
  - Manual override matching, fuzzy matching, low-confidence fallback
  - Custom overrides, player ID extraction
- `test_manifest_extended.py` (5 tests)
  - Extended fields round-trip, backward compatibility
  - Old manifest format loading, update_status with new fields
- `test_manifest.py` (9 existing tests, no regressions)

## Decisions Made

See frontmatter `decisions` section for full rationale.

**Key decision:** Deferred Hishel caching (INFRA-01). The installed hishel version requires `hishel[async]` extra for filesystem caching. Rate limiting was deemed critical, caching nice-to-have. VLR.gg scraping will hit network on every run until hishel[async] installed.

**Fuzzy matching threshold:** 85 score (NORM-01) balances matching variants vs. avoiding false positives. Low-confidence matches return original name with warning.

## Dependencies Installed

| Package                    | Version | Purpose                                |
| -------------------------- | ------- | -------------------------------------- |
| httpx                      | >=0.28  | Async HTTP client                      |
| hishel                     | >=1.1   | HTTP caching (future)                  |
| pyrate-limiter             | >=4.0   | Rate limiting                          |
| google-api-python-client   | >=2.170 | YouTube Data API                       |
| rapidfuzz                  | >=3.14  | Fuzzy string matching                  |
| pytest-asyncio             | 1.3.0   | Async test support (dev dependency)    |

## Next Phase Readiness

**Ready for Plan 12-02** (VLR.gg Player Stats Scraper)

This plan establishes the foundation. Subsequent plans can now:
- Use `create_cached_client()` for rate-limited HTTP requests
- Store player stats, agent comps, player IDs in VODRecord
- Normalize team names via TeamNormalizer before manifest insertion

**Blockers:** None

**Concerns:**
- Caching deferred (may slow down development iteration). Consider installing `hishel[async]` before scraping 100+ matches.
- Rate limit (1 req/sec) is conservative. VLR.gg tolerance unknown. May need adjustment based on scraping behavior in Plan 12-02.

## Files Changed

**Created (6 files):**
- src/scraping/http_client.py (106 lines)
- src/scraping/team_normalizer.py (150 lines)
- tests/scraping/__init__.py (1 line)
- tests/scraping/test_http_client.py (68 lines)
- tests/scraping/test_team_normalizer.py (82 lines)
- tests/pipeline/test_manifest_extended.py (219 lines)

**Modified (2 files):**
- requirements.txt (+6 dependencies)
- src/pipeline/manifest.py (+5 VODRecord fields, backward compatible)

**Total:** 8 files, 626 lines added (code + tests + docs)
