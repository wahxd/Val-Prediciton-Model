# Phase 12: Data Sourcing / VLR.gg Scraping - Context

**Gathered:** 2026-02-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Scraper retrieves match metadata and YouTube VOD links from VLR.gg for 80-100 additional maps across 2-3 tournaments. Populates ProcessingManifest with VODRecords ready for Phase 13 processing. Does NOT process VODs (Phase 13) or run experiments (Phase 14).

</domain>

<decisions>
## Implementation Decisions

### Tournament targeting
- Primary targets: Masters Bangkok 2024 (international) + VCT Americas 2024 (regional)
- Mix of tiers for variety: one international event, one regional league
- If two tournaments don't yield 80 maps, add a third event (e.g., Masters Shanghai 2024 or VCT EMEA 2024)
- Existing data: Champions 2025 (71 maps from v2) — no overlap with new targets

### VOD discovery strategy
- Two-source approach: scrape match metadata from VLR.gg, then search YouTube Data API v3 for individual map VODs
- YouTube API key required (user will set up Google Cloud project + enable YouTube Data API v3 before execution)
- Validate VOD accessibility upfront before adding to manifest — avoids wasted processing time in Phase 13
- Maps without a discoverable/accessible YouTube VOD are skipped entirely

### Missing data policy
- Hard requirement: VOD link must exist and be accessible — maps without VODs are skipped, not stored as partial records
- Soft metadata: player stats (ACS, K/D/A, KAST%, ADR, HS%, FK/FD) are supplementary — include map even if some stats are incomplete
- Soft metadata: agent compositions are supplementary — include map even if agent picks aren't listed
- Summary report generated after scraping run: total maps found, maps included, maps skipped with reasons (no VOD, VOD inaccessible, etc.)

### Team & player identity
- Team names: Claude's discretion on normalization approach (manual mapping table vs fuzzy matching vs hybrid)
- Player identity matters more than org identity — teams change rosters frequently, players are the stable unit
- Use VLR.gg player profile IDs as canonical player identifiers — unique, reliable, cross-tournament
- Track individual players across tournaments via VLR.gg IDs, enabling future player-level features
- Org rebrandings: not a priority to track — player-centric model means team name is secondary

### Claude's Discretion
- Team name normalization method (manual mapping, fuzzy matching, or hybrid)
- HTML parsing approach and VLR.gg page structure handling
- YouTube search query construction (team names + tournament + date)
- Caching strategy for scraped pages
- Third tournament selection if needed (based on VOD availability)

</decisions>

<specifics>
## Specific Ideas

- "Teams matter less than players since teams change so often" — player-centric identity model
- YouTube Data API free tier (10,000 quota units/day) is sufficient for ~100 map searches
- User will set up YouTube API key before Phase 12 execution

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 12-data-sourcing-vlr-scraping*
*Context gathered: 2026-02-14*
