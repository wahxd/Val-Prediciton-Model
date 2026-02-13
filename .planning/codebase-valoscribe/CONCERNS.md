# Codebase Concerns

**Analysis Date:** 2026-02-13

## Tech Debt

**Hardcoded Ultimate Charges:**
- Issue: Ultimate charge counts are hardcoded to 7 instead of using agent-specific values from config
- Files: `D:\Git\Gitvaloscribe\src\valoscribe\detectors\preround_ultimate_detector.py` (line 141), `D:\Git\Gitvaloscribe\src\valoscribe\detectors\ultimate_detector.py` (line 143)
- Impact: Incorrect ultimate charge tracking for agents with different max charges (e.g., Raze has 8, Phoenix has 6)
- Fix approach: Read `max_charges` from `agents_champs2025.json` config and use agent-specific values

**Phase Detection Robustness:**
- Issue: Preround detection only checks player 0 for credits visibility, noted with TODO comment
- Files: `D:\Git\Gitvaloscribe\src\valoscribe\orchestration\phase_detector.py` (line 122)
- Impact: Single-player check may produce false negatives if player 0's UI is obscured
- Fix approach: Check multiple players (0-2) and use majority vote for phase determination

**Weapon Detection Not Implemented:**
- Issue: Kill events have `weapon` field marked as TODO, currently Optional and unused
- Files: `D:\Git\Gitvaloscribe\src\valoscribe\types\detections.py` (line 100)
- Impact: Kill events lack weapon information, limiting analytics capabilities
- Fix approach: Add weapon icon template matching or OCR parsing from killfeed entries

**Incomplete Command Stubs:**
- Issue: Two commands in utils have empty TODO implementations
- Files: `D:\Git\Gitvaloscribe\src\valoscribe\commands\utils.py` (lines 555, 565)
- Impact: Commands exist but don't function, potentially confusing for users
- Fix approach: Either implement the functionality or remove the stub commands

**Type Checking Disabled:**
- Issue: mypy strict mode disabled, `disallow_untyped_defs` set to false
- Files: `D:\Git\Gitvaloscribe\pyproject.toml` (line 48)
- Impact: Type safety compromised, potential runtime errors not caught during development
- Fix approach: Gradually add type hints to untyped functions and enable strict checking incrementally

**Minimal Type Coverage:**
- Issue: Only 7 type-related comments (`type: ignore`, `Any`) across codebase
- Files: `D:\Git\Gitvaloscribe\src\valoscribe\video\youtube.py`, `D:\Git\Gitvaloscribe\src\valoscribe\detectors\cropper.py`
- Impact: Type hints may be missing in critical areas
- Fix approach: Run mypy in strict mode and add type annotations where missing

## Known Bugs

**Killer Agent Attribution Mismatch:**
- Symptoms: BUG log messages indicating killer agent doesn't match victim's recorded killer
- Files: `D:\Git\Gitvaloscribe\src\valoscribe\orchestration\game_state_manager.py` (lines 924, 1202)
- Trigger: During kill validation when killfeed detection doesn't align with player state
- Workaround: Error is logged but event still processed; data may be inconsistent

**Round Start/End Mismatches:**
- Symptoms: 9 of 71 processed maps have unequal round_start and round_end event counts
- Files: Affects output validation in `D:\Git\Gitvaloscribe\scripts\validate_event_logs.sh`
- Trigger: Round replays, technical pauses, or broadcast interruptions during live games
- Workaround: Documented in README; 87% of maps pass validation

**Team Kills Not Supported:**
- Symptoms: Team kills (friendly fire in certain game modes) are not detected or logged
- Files: `D:\Git\Gitvaloscribe\src\valoscribe\detectors\killfeed_detector.py`, `D:\Git\Gitvaloscribe\src\valoscribe\orchestration\game_state_manager.py`
- Trigger: Rare team kill events during matches
- Workaround: None; documented as known issue, very low frequency in competitive play

**Preround Ability Usage Not Tracked:**
- Symptoms: Abilities used during preround phase are not logged as events
- Files: `D:\Git\Gitvaloscribe\src\valoscribe\orchestration\state_validator.py`, `D:\Git\Gitvaloscribe\src\valoscribe\detectors\preround_ability_detector.py`
- Trigger: Any ability used before round timer starts
- Workaround: None; documented as TODO for future implementation
- Impact: Missing data for preround utility placement and economy decisions

## Security Considerations

**External Dependencies - Web Scraping:**
- Risk: VLR.gg scraper relies on HTML structure that could change without notice
- Files: `D:\Git\Gitvaloscribe\src\valoscribe\scraper\vlr_scraper.py`
- Current mitigation: Timeout on requests (10 seconds), user-agent header set
- Recommendations: Add retry logic, better error handling for HTML parsing failures, version pinning for BeautifulSoup

**External Dependencies - YouTube Downloads:**
- Risk: yt-dlp could be outdated or fail if YouTube changes API/structure
- Files: `D:\Git\Gitvaloscribe\src\valoscribe\video\youtube.py`
- Current mitigation: Uses tqdm progress tracking, handles download errors
- Recommendations: Add version checking mechanism, fallback download strategies, rate limiting

**Tesseract OCR External Binary:**
- Risk: Requires system-level Tesseract installation, version inconsistencies across platforms
- Files: `D:\Git\Gitvaloscribe\src\valoscribe\utils\ocr.py`
- Current mitigation: Documented installation instructions in README
- Recommendations: Add Tesseract version check on startup, clearer error messages if not installed

**No Input Validation on User-Provided Paths:**
- Risk: File path traversal or injection through command-line arguments
- Files: All command files in `D:\Git\Gitvaloscribe\src\valoscribe\commands\`
- Current mitigation: Path existence checks, but no sanitization
- Recommendations: Validate and sanitize file paths, restrict to expected directories

## Performance Bottlenecks

**Processing Speed:**
- Problem: 20-40 minutes per map processing time at 4 FPS sampling rate
- Files: `D:\Git\Gitvaloscribe\src\valoscribe\orchestration\game_state_manager.py`
- Cause: Template matching operations on every frame for 10 players
- Improvement path: Implement frame skipping for stable states, GPU acceleration for template matching, parallel player processing

**Template Matching Overhead:**
- Problem: Multiple template matching operations per player per frame
- Files: `D:\Git\Gitvaloscribe\src\valoscribe\detectors\template_*.py` (7 template detector files)
- Cause: Sequential OpenCV template matching for agents, health, armor, abilities, score, timer
- Improvement path: Cache template match results, reduce template counts, optimize match methods

**OCR Engine Repeated Initialization:**
- Problem: OCR may be inefficient for high-frequency text extraction
- Files: `D:\Git\Gitvaloscribe\src\valoscribe\utils\ocr.py`, `D:\Git\Gitvaloscribe\src\valoscribe\detectors\killfeed_detector.py`
- Cause: Tesseract OCR called on every killfeed frame
- Improvement path: Batch OCR operations, use template matching instead of OCR where possible

**Large Detect Command File:**
- Problem: Single 4,675-line file with all detection command implementations
- Files: `D:\Git\Gitvaloscribe\src\valoscribe\commands\detect.py`
- Cause: All 15+ detector test commands in one file
- Improvement path: Split into separate command files per detector type, reduce code duplication

## Fragile Areas

**Agent-Specific Ability Limitations:**
- Files: Documented in README but affects `D:\Git\Gitvaloscribe\src\valoscribe\detectors\ability_detector.py`, `D:\Git\Gitvaloscribe\src\valoscribe\detectors\ultimate_detector.py`
- Why fragile: HUD displays abilities differently for Astra, Neon, Chamber, Jett, Viper
- Safe modification: Test against matches with these agents before deploying changes to ability detection
- Test coverage: Limited agent-specific test cases

**HUD Coordinate Dependency:**
- Files: `D:\Git\Gitvaloscribe\src\valoscribe\config\champs2025.json`, `D:\Git\Gitvaloscribe\src\valoscribe\detectors\cropper.py`
- Why fragile: All detection relies on exact pixel coordinates for 1080p broadcast HUD layout
- Safe modification: New tournament broadcasts require full coordinate recalibration and testing
- Test coverage: Only tested on Champions 2025 HUD layout

**Phase State Machine:**
- Files: `D:\Git\Gitvaloscribe\src\valoscribe\orchestration\phase_detector.py`
- Why fragile: Relies on timer, spike, and credits detection working correctly; single failure cascades
- Safe modification: Always verify phase transitions with multiple validation signals
- Test coverage: Basic state transition tests exist, but edge cases for replays/pauses not covered

**Killfeed Template Matching:**
- Files: `D:\Git\Gitvaloscribe\src\valoscribe\detectors\killfeed_detector.py`
- Why fragile: Requires exact agent icon templates for attack/defense sides, sensitive to confidence threshold
- Safe modification: Add new agent templates when roster changes, test against diverse VODs
- Test coverage: Template matching tests exist but may not cover all agent pairs

**VLR.gg HTML Scraping:**
- Files: `D:\Git\Gitvaloscribe\src\valoscribe\scraper\vlr_scraper.py`
- Why fragile: Breaks if VLR.gg changes HTML structure, CSS classes, or page layout
- Safe modification: Use defensive parsing with fallbacks, validate all extracted data
- Test coverage: No integration tests for scraper, relies on manual verification

## Scaling Limits

**Single-Machine Processing:**
- Current capacity: ~1.5-3 hours per match on 14-core MacBook Pro (71 maps took substantial time)
- Limit: Cannot efficiently process large datasets (100+ matches) on single machine
- Scaling path: Cloud parallelization with container orchestration (Docker + Kubernetes), distribute map processing across workers

**Memory Usage with Large Videos:**
- Current capacity: Loads full video into VideoCapture, processes frame-by-frame
- Limit: Very long VODs (3+ hours) or high resolution may cause memory issues
- Scaling path: Implement streaming video processing, chunk large files, add memory monitoring

**Output File Growth:**
- Current capacity: ~2,000-5,000 CSV rows per map, 200-850 events per map
- Limit: Batch processing 1,000+ maps produces gigabytes of CSV/JSONL files
- Scaling path: Database storage (PostgreSQL), compressed formats, aggregation pipelines

**Template Storage:**
- Current capacity: 25+ agent templates × 2 sides × multiple UI elements stored as PNG files
- Limit: Adding new agents or UI variants increases disk usage and load times
- Scaling path: Template compression, lazy loading, embed templates in binary format

## Dependencies at Risk

**OpenCV Version Lock:**
- Risk: OpenCV API changes could break template matching methods
- Impact: All computer vision detectors would fail
- Migration plan: Pin OpenCV version in pyproject.toml, test on new versions before upgrading

**Playwright for Scraping:**
- Risk: Heavy dependency for VLR.gg scraping, but not heavily used (only BeautifulSoup actively used)
- Impact: Installation overhead, unused browser automation
- Migration plan: Remove Playwright if not needed, or implement browser-based scraping if VLR.gg blocks requests

**Python 3.10+ Requirement:**
- Risk: Older environments cannot run Valoscribe
- Impact: Limits deployment on legacy systems
- Migration plan: Use `from __future__ import annotations` pattern is already in use, can backport to 3.9 if needed

**yt-dlp Ecosystem:**
- Risk: YouTube frequently breaks yt-dlp, requires constant updates
- Impact: VOD download failures block entire pipeline
- Migration plan: Pin working version, monitor yt-dlp releases, implement manual fallback instructions

## Missing Critical Features

**Replay Detection:**
- Problem: Broadcast replays cause false detections and duplicate events
- Blocks: Accurate event logs for matches with frequent replay segments
- Impact: Contributes to 13% validation failure rate (9/71 maps)

**Economy Tracking:**
- Problem: Credits detected in preround but not tracked per-round or used for economy analysis
- Blocks: Cannot analyze buy rounds, eco rounds, force buys
- Impact: Missing key analytics dimension for tactical analysis

**Weapon Identification:**
- Problem: Kill events lack weapon information
- Blocks: Cannot analyze weapon effectiveness, purchase patterns, meta trends
- Impact: Major analytics gap for competitive insights

**Multi-Tournament Support:**
- Problem: Only Champions 2025 HUD config available
- Blocks: Cannot process VODs from other tournaments without manual config creation
- Impact: Limited to single tournament dataset

**Real-Time Processing:**
- Problem: Designed for batch VOD processing, not live streams
- Blocks: Cannot generate live match analytics or real-time highlights
- Impact: Limits use cases to post-match analysis only

## Test Coverage Gaps

**Scraper Integration:**
- What's not tested: VLR.gg scraper has no automated tests
- Files: `D:\Git\Gitvaloscribe\src\valoscribe\scraper\vlr_scraper.py`
- Risk: HTML structure changes break silently until manual discovery
- Priority: Medium

**YouTube Download:**
- What's not tested: Actual YouTube download operations, only timestamp parsing tested
- Files: `D:\Git\Gitvaloscribe\src\valoscribe\video\youtube.py`
- Risk: Download failures not caught in CI/CD
- Priority: Medium

**End-to-End Pipeline:**
- What's not tested: Full pipeline from VLR scraping → download → processing → validation
- Files: All orchestration components
- Risk: Integration issues between components only discovered in production
- Priority: High

**Agent-Specific Edge Cases:**
- What's not tested: Astra, Neon, Chamber, Jett, Viper ability detection quirks
- Files: `D:\Git\Gitvaloscribe\src\valoscribe\detectors\ability_detector.py`, `D:\Git\Gitvaloscribe\src\valoscribe\detectors\ultimate_detector.py`
- Risk: Agent-specific bugs not caught during development
- Priority: High

**Broadcast Interruption Handling:**
- What's not tested: Behavior during technical pauses, desk segments, replays
- Files: `D:\Git\Gitvaloscribe\src\valoscribe\orchestration\phase_detector.py`, `D:\Git\Gitvaloscribe\src\valoscribe\orchestration\game_state_manager.py`
- Risk: Causes 13% of maps to fail validation
- Priority: High

**Template Matching Robustness:**
- What's not tested: Template matching under varying brightness, compression artifacts, encoding differences
- Files: All `D:\Git\Gitvaloscribe\src\valoscribe\detectors\template_*.py` files
- Risk: False negatives on different VOD sources or quality levels
- Priority: Medium

**Multi-Resolution Support:**
- What's not tested: Only 1080p tested, no validation for other resolutions
- Files: `D:\Git\Gitvaloscribe\src\valoscribe\detectors\cropper.py`
- Risk: Documented limitation but no graceful degradation
- Priority: Low

---

*Concerns audit: 2026-02-13*
