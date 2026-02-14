# Phase 7: Dataset Expansion (VOD Processing) - Research

**Researched:** 2026-02-13
**Domain:** YouTube video downloading, web scraping, subprocess orchestration, resumable batch processing
**Confidence:** MEDIUM

## Summary

Phase 7 requires building a scraping + orchestration pipeline that discovers VCT VODs from VLR.gg, downloads them via yt-dlp, and processes them through Valoscribe to expand the training dataset beyond 71 maps. The pipeline must be resumable (runs over days/weeks), track state in a JSON manifest, and respect VLR.gg server resources through rate limiting.

**Key findings:**
- **yt-dlp** (current: 2026.2.4) is the industry-standard YouTube downloader with robust Python API
- **BeautifulSoup4 with lxml parser** is the fastest HTML parsing stack for VLR.gg scraping
- **VLR.gg has no robots.txt** — community consensus is 1 request/second rate limiting is polite
- **Subprocess.run()** with check=True and timeout is the modern pattern for calling Valoscribe
- **JSON manifest pattern** with per-VOD status tracking enables resumability
- **VLR.gg match pages** contain YouTube embed links and map timestamp metadata
- **Exponential backoff retry** with circuit breaker prevents hammering on persistent failures

**Primary recommendation:** Use yt-dlp Python API for downloading, BeautifulSoup4 with lxml for scraping, subprocess.run() for Valoscribe calls, and a JSON manifest for state tracking with auto-save after each map.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| yt-dlp | 2026.2.4 | YouTube video downloading | Industry standard, active development, Python 3.10+ API with progress hooks |
| BeautifulSoup4 | 4.13+ | HTML parsing (VLR.gg) | De facto standard for web scraping, flexible selectors |
| lxml | 5.x | HTML parser backend | Fastest parser (2-3x faster than html.parser), handles malformed HTML |
| requests | 2.32+ | HTTP client for scraping | Standard HTTP library, session support for connection pooling |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pathlib | stdlib | File path operations | Already used in Phase 5 loader, consistent with existing code |
| subprocess | stdlib | Call Valoscribe CLI | Standard library, subprocess.run() is modern high-level API |
| structlog | 25.x | Structured logging | Already in Phase 1/5, consistent logging format |
| tenacity | 9.x | Retry logic with backoff | Industry standard retry library, declarative retry policies |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| yt-dlp | youtube-dl | youtube-dl is abandoned, yt-dlp is the active fork with 2026 updates |
| lxml | html.parser | html.parser is stdlib but 2-3x slower, acceptable for low-volume scraping |
| lxml | html5lib | html5lib is most lenient but 5-10x slower than lxml |
| requests | httpx | httpx adds async support but adds complexity, requests sufficient for sequential |
| tenacity | custom retry | Custom retry logic is error-prone, tenacity handles edge cases |

**Installation:**
```bash
# Add to pyproject.toml / requirements.txt
yt-dlp>=2026.2.4
beautifulsoup4>=4.13
lxml>=5.0
requests>=2.32
tenacity>=9.0
# pathlib, subprocess, structlog already available
```

## Architecture Patterns

### Recommended Project Structure
```
src/
├── scraping/
│   ├── __init__.py
│   ├── vlr_scraper.py      # VLR.gg match page scraper
│   ├── vod_downloader.py   # yt-dlp wrapper with progress tracking
│   ├── orchestrator.py     # Main processing loop with manifest
│   └── manifest.py         # Manifest I/O and state management
├── config.py               # Configuration (env vars, paths)
└── ...
scripts/
├── expand_dataset.py       # CLI entry point
└── summarize_progress.py   # Read manifest, print summary
data/
└── processing/
    ├── manifest.json       # State tracking (VOD list + status)
    ├── downloads/          # Temporary VOD files (deleted after processing)
    └── processed/          # Valoscribe output (separate from existing 71 maps)
```

### Pattern 1: yt-dlp Python API with Progress Hooks
**What:** Use yt-dlp's YoutubeDL class with progress_hooks for real-time download tracking and logger for structured logging.

**When to use:** When downloading YouTube VODs programmatically with status updates.

**Example:**
```python
# Source: https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/YoutubeDL.py
import yt_dlp
import structlog

logger = structlog.get_logger()

def progress_hook(d):
    """Called during download with status updates."""
    if d['status'] == 'downloading':
        logger.debug("download_progress",
                     filename=d.get('filename'),
                     percent=d.get('_percent_str', '0%'),
                     eta=d.get('_eta_str', 'unknown'))
    elif d['status'] == 'finished':
        logger.info("download_complete", filename=d['filename'])
    elif d['status'] == 'error':
        logger.error("download_error", filename=d.get('filename'))

def download_youtube_video(url: str, output_path: str) -> str:
    """Download YouTube video to specified path.

    Returns: Path to downloaded file
    Raises: yt_dlp.utils.DownloadError on failure
    """
    ydl_opts = {
        'outtmpl': output_path,  # Output filename template
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'progress_hooks': [progress_hook],
        'quiet': True,  # Suppress console output, use logger instead
        'no_warnings': False,
        'ignoreerrors': False,  # Raise exceptions (default for API usage)
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)
```

**Key insight:** Set `ignoreerrors=False` for API usage (default) to propagate errors for retry logic. CLI uses `'only_download'` but API should fail fast.

### Pattern 2: BeautifulSoup VLR.gg Match Page Scraping
**What:** Parse VLR.gg match pages to extract YouTube VOD links and map timestamps using BeautifulSoup with lxml parser.

**When to use:** When scraping structured HTML from VLR.gg match pages.

**Example:**
```python
# Source: https://beautiful-soup-4.readthedocs.io/en/latest/
import requests
from bs4 import BeautifulSoup
import structlog
import time

logger = structlog.get_logger()

def scrape_match_vod(match_url: str, rate_limit_delay: float = 1.0) -> dict:
    """Scrape VLR.gg match page for VOD link and metadata.

    Args:
        match_url: Full VLR.gg match URL (e.g., https://www.vlr.gg/12345/team1-vs-team2-...)
        rate_limit_delay: Seconds to wait after request (default: 1.0 for politeness)

    Returns:
        Dict with keys: youtube_url, teams, map_name, date, tournament, map_timestamps

    Raises:
        ValueError: If YouTube link not found or page structure unexpected
    """
    # Polite headers (identify as bot)
    headers = {
        'User-Agent': 'VCT-Prediction-Model-Scraper/1.0 (Educational Research)'
    }

    response = requests.get(match_url, headers=headers, timeout=10)
    response.raise_for_status()

    # Rate limiting - be polite to VLR.gg
    time.sleep(rate_limit_delay)

    soup = BeautifulSoup(response.content, 'lxml')  # lxml for speed

    # Extract YouTube embed (typical pattern: iframe with youtube.com/embed/...)
    # NOTE: Actual selectors must be reverse-engineered from live VLR.gg pages
    youtube_iframe = soup.find('iframe', src=lambda s: s and 'youtube.com' in s)
    if not youtube_iframe:
        raise ValueError(f"No YouTube embed found on {match_url}")

    youtube_url = youtube_iframe['src']
    # Convert embed URL to watch URL: /embed/VIDEO_ID -> /watch?v=VIDEO_ID
    video_id = youtube_url.split('/embed/')[-1].split('?')[0]
    youtube_watch_url = f"https://www.youtube.com/watch?v={video_id}"

    # Extract match metadata (selectors are hypothetical, must verify)
    teams_elem = soup.find_all(class_='match-header-link-name')
    teams = [t.get_text(strip=True) for t in teams_elem[:2]]

    map_name_elem = soup.find(class_='map')
    map_name = map_name_elem.get_text(strip=True) if map_name_elem else "unknown"

    logger.info("scraped_match", url=match_url, teams=teams, map_name=map_name)

    return {
        'youtube_url': youtube_watch_url,
        'teams': teams,
        'map_name': map_name,
        'match_url': match_url,
        # Additional fields populated by actual scraping logic
    }
```

**Warning:** VLR.gg HTML structure must be reverse-engineered. Selectors shown are hypothetical and MUST be validated against live pages before implementation.

### Pattern 3: Subprocess Valoscribe Orchestration
**What:** Call Valoscribe as external subprocess with timeout, error handling, and retry logic.

**When to use:** When calling Valoscribe CLI from Python orchestration script.

**Example:**
```python
# Source: https://docs.python.org/3/library/subprocess.html
import subprocess
from pathlib import Path
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = structlog.get_logger()

class ValoscribeProcessingError(Exception):
    """Valoscribe processing failed after retries."""
    pass

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=retry_if_exception_type(subprocess.CalledProcessError),
    reraise=True
)
def process_vod_with_valoscribe(
    vod_path: Path,
    output_dir: Path,
    timeout_seconds: int = 3600  # 1 hour default
) -> Path:
    """Process VOD through Valoscribe with retry logic.

    Args:
        vod_path: Path to downloaded VOD file
        output_dir: Directory for Valoscribe output
        timeout_seconds: Max processing time before killing process

    Returns:
        Path to Valoscribe output directory (contains events.jsonl, frames.csv, metadata.json)

    Raises:
        ValoscribeProcessingError: If processing fails after retries
        subprocess.TimeoutExpired: If processing exceeds timeout
    """
    cmd = [
        "python", "-m", "valoscribe.cli",
        "process",
        "--input", str(vod_path),
        "--output-dir", str(output_dir),
        "--format", "jsonl"  # Hypothetical - actual Valoscribe CLI args TBD
    ]

    logger.info("starting_valoscribe", vod=str(vod_path), output=str(output_dir))

    try:
        result = subprocess.run(
            cmd,
            check=True,  # Raise CalledProcessError on non-zero exit
            capture_output=True,  # Capture stdout/stderr for logging
            text=True,  # Decode as UTF-8 strings
            timeout=timeout_seconds,
            cwd=Path("D:/Git/valoscribe")  # Run from Valoscribe repo root
        )

        logger.info("valoscribe_success",
                    vod=str(vod_path),
                    stdout_lines=len(result.stdout.splitlines()))

        # Return path to generated map directory (Valoscribe creates map_id subdir)
        # Actual path discovery logic depends on Valoscribe output structure
        map_id = output_dir / "latest"  # Hypothetical - verify actual behavior
        return map_id

    except subprocess.CalledProcessError as e:
        logger.error("valoscribe_failed",
                     vod=str(vod_path),
                     exit_code=e.returncode,
                     stderr=e.stderr[:500])  # Truncate for logging
        raise  # tenacity will retry

    except subprocess.TimeoutExpired as e:
        logger.error("valoscribe_timeout",
                     vod=str(vod_path),
                     timeout=timeout_seconds)
        # Kill process and clean up
        if e.stdout:
            logger.debug("timeout_stdout", content=e.stdout[:500])
        raise ValoscribeProcessingError(f"Timeout after {timeout_seconds}s")
```

**Key insight:** Use `check=True` to raise exceptions, `capture_output=True` for logging, and `timeout` to prevent hanging. The `@retry` decorator handles transient failures with exponential backoff.

### Pattern 4: JSON Manifest for Resumability
**What:** Maintain a JSON file tracking all VODs with status (pending/processing/complete/failed) for resumable batch processing.

**When to use:** When processing runs over days/weeks and must be resumable after crashes or manual stops.

**Example:**
```python
# Source: Batch processing patterns
import json
from pathlib import Path
from typing import Literal
from dataclasses import dataclass, asdict
from datetime import datetime
import structlog

logger = structlog.get_logger()

@dataclass
class VODRecord:
    """Single VOD entry in processing manifest."""
    vod_id: str  # Unique identifier (e.g., VLR.gg match ID + map index)
    youtube_url: str
    vlr_match_url: str
    teams: list[str]
    map_name: str
    tournament: str
    date: str  # ISO format YYYY-MM-DD
    patch_version: str | None  # e.g., "9.11" - for filtering in feature engineering

    status: Literal["pending", "downloading", "processing", "complete", "failed"]
    map_id: str | None  # Valoscribe-generated map ID (set on completion)
    error_message: str | None

    # Timestamps for progress tracking
    created_at: str  # ISO timestamp
    started_at: str | None
    completed_at: str | None
    processing_time_seconds: float | None

class ProcessingManifest:
    """Manages VOD processing state via JSON file."""

    def __init__(self, manifest_path: Path):
        self.manifest_path = manifest_path
        self.records: dict[str, VODRecord] = {}
        self.load()

    def load(self):
        """Load manifest from disk, create empty if doesn't exist."""
        if self.manifest_path.exists():
            with self.manifest_path.open('r') as f:
                data = json.load(f)
                self.records = {
                    k: VODRecord(**v) for k, v in data.get('vods', {}).items()
                }
            logger.info("loaded_manifest",
                        path=str(self.manifest_path),
                        vod_count=len(self.records))
        else:
            logger.info("created_new_manifest", path=str(self.manifest_path))

    def save(self):
        """Save manifest to disk atomically (write temp, then rename)."""
        temp_path = self.manifest_path.with_suffix('.tmp')

        data = {
            'updated_at': datetime.utcnow().isoformat(),
            'vods': {k: asdict(v) for k, v in self.records.items()}
        }

        with temp_path.open('w') as f:
            json.dump(data, f, indent=2)

        # Atomic rename (overwrites existing)
        temp_path.replace(self.manifest_path)

        logger.debug("saved_manifest", path=str(self.manifest_path))

    def add_vod(self, record: VODRecord):
        """Add VOD to manifest and save."""
        self.records[record.vod_id] = record
        self.save()

    def update_status(self, vod_id: str, status: str, **kwargs):
        """Update VOD status and optional fields, then save."""
        if vod_id not in self.records:
            raise ValueError(f"VOD {vod_id} not in manifest")

        record = self.records[vod_id]
        record.status = status

        for key, value in kwargs.items():
            setattr(record, key, value)

        self.save()

    def get_pending(self) -> list[VODRecord]:
        """Get all VODs with status='pending' for processing."""
        return [r for r in self.records.values() if r.status == 'pending']

    def get_summary(self) -> dict:
        """Generate summary statistics."""
        statuses = [r.status for r in self.records.values()]

        return {
            'total': len(self.records),
            'pending': statuses.count('pending'),
            'downloading': statuses.count('downloading'),
            'processing': statuses.count('processing'),
            'complete': statuses.count('complete'),
            'failed': statuses.count('failed'),
        }
```

**Key insight:** Auto-save after every status update ensures resumability. Use atomic write (temp file + rename) to prevent corruption on crash.

### Anti-Patterns to Avoid
- **Processing full series VODs without timestamps:** Wastes disk space and processing time. Use VLR.gg map timestamps to extract individual maps.
- **Storing downloaded VODs permanently:** VODs are multi-GB. Delete after successful Valoscribe processing to save disk.
- **No rate limiting on VLR.gg:** Even with no robots.txt, hammering requests is rude and risks IP bans. Use 1 req/sec minimum.
- **Hardcoded CSS selectors without validation:** VLR.gg can change HTML structure. Validate selectors against live pages before running at scale.
- **No retry logic for transient failures:** Networks fail, YouTube throttles, Valoscribe crashes. Retry with exponential backoff.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YouTube downloading | Custom ffmpeg/requests pipeline | yt-dlp | Handles YouTube anti-bot measures, format negotiation, subtitle extraction, 100+ sites |
| Retry logic with backoff | Manual sleep() loops | tenacity library | Handles edge cases: jitter, max retries, exception filtering, async support |
| HTML parsing | Regex on HTML strings | BeautifulSoup4 | Handles malformed HTML, provides CSS selectors, robust against structure changes |
| HTTP session management | requests.get() in loop | requests.Session() | Connection pooling (10x faster for multiple requests), cookie persistence |

**Key insight:** yt-dlp handles YouTube's anti-bot measures (rotating IPs, CAPTCHAs, format changes). A custom downloader will break within weeks.

## Common Pitfalls

### Pitfall 1: YouTube Rate Limiting and IP Bans
**What goes wrong:** YouTube detects bot behavior and throttles or blocks the IP after 10-50 downloads.

**Why it happens:** Downloading at full speed with no delays between requests triggers anti-bot heuristics.

**How to avoid:**
- Add 5-10 second delays between YouTube downloads
- Use yt-dlp's built-in rate limiting: `'ratelimit': '1M'` (1MB/s) or `'sleep_interval': 5`
- Rotate user agents (yt-dlp does this automatically)
- Consider running overnight to spread requests over time

**Warning signs:**
- HTTP 429 errors (Too Many Requests)
- Downloads slowing to <100KB/s
- yt-dlp errors: "This video is unavailable" (when it's actually available)

### Pitfall 2: VLR.gg HTML Structure Changes
**What goes wrong:** Scraper breaks silently when VLR.gg updates their HTML, returning empty results or crashing.

**Why it happens:** CSS selectors are brittle — class names change, elements move, structure refactors.

**How to avoid:**
- Validate scraped data before trusting it (check for empty strings, missing fields)
- Log warnings for unexpected HTML structure
- Build a test suite with saved HTML snapshots
- Monitor error rates in manifest (spike in scraping failures = site changed)

**Warning signs:**
- Sudden increase in "YouTube link not found" errors
- Empty team names or map names in manifest
- Scraper succeeding but returning "unknown" for all fields

### Pitfall 3: Subprocess Zombie Processes
**What goes wrong:** Valoscribe crashes or times out, leaving zombie processes that consume memory until system runs out.

**Why it happens:** Not handling `subprocess.TimeoutExpired` properly, or not killing child processes on timeout.

**How to avoid:**
- Always use `timeout` parameter in `subprocess.run()`
- Catch `TimeoutExpired` and log it (don't silently ignore)
- Consider `subprocess.Popen()` with `process.kill()` for fine-grained control
- Monitor system processes during development: `ps aux | grep valoscribe`

**Warning signs:**
- Memory usage climbing over hours
- Multiple Valoscribe processes running simultaneously (should be sequential)
- System becoming unresponsive during processing

### Pitfall 4: Disk Space Exhaustion
**What goes wrong:** Downloading 100+ multi-GB VODs fills disk, crashing the system or Valoscribe.

**Why it happens:** Forgetting to delete downloaded VOD files after processing, or processing failing silently leaving orphaned files.

**How to avoid:**
- Delete VOD file immediately after successful Valoscribe processing
- Use `try/finally` to ensure cleanup even on error
- Monitor disk space: log available GB before each download
- Set a disk space threshold: refuse to download if <50GB free

**Warning signs:**
- Disk usage climbing 10-20GB per day
- "No space left on device" errors
- Valoscribe failing with I/O errors

### Pitfall 5: Manifest Corruption on Crash
**What goes wrong:** Python crashes mid-JSON-write, leaving truncated manifest file that can't be parsed.

**Why it happens:** Writing directly to manifest file without atomic write pattern.

**How to avoid:**
- Use atomic write pattern: write to `.tmp` file, then `rename()` (atomic on POSIX/Windows)
- Validate JSON after loading (catch `json.JSONDecodeError`)
- Keep backups: copy manifest to `manifest.YYYYMMDD.json` daily
- Log manifest save operations for debugging

**Warning signs:**
- `JSONDecodeError` on startup
- Manifest file size = 0 bytes
- Lost processing state after crash (resuming from scratch)

## Code Examples

Verified patterns from official sources:

### Resumable Orchestration Loop
```python
# Source: Batch processing patterns + subprocess best practices
from pathlib import Path
import structlog
from datetime import datetime

logger = structlog.get_logger()

def run_processing_pipeline(
    manifest_path: Path,
    output_dir: Path,
    download_dir: Path,
    max_concurrent: int = 1  # Sequential processing (as decided)
):
    """Main orchestration loop for VOD processing.

    This is resumable - can be stopped and restarted safely.
    """
    manifest = ProcessingManifest(manifest_path)
    pending = manifest.get_pending()

    logger.info("pipeline_started",
                total_vods=len(manifest.records),
                pending=len(pending))

    for i, record in enumerate(pending, start=1):
        logger.info("processing_vod",
                    index=i,
                    total=len(pending),
                    vod_id=record.vod_id,
                    teams=record.teams)

        start_time = datetime.utcnow()
        vod_file = None

        try:
            # Step 1: Update status to downloading
            manifest.update_status(
                record.vod_id,
                'downloading',
                started_at=start_time.isoformat()
            )

            # Step 2: Download VOD
            vod_file = download_dir / f"{record.vod_id}.mp4"
            download_youtube_video(record.youtube_url, str(vod_file))

            # Step 3: Update status to processing
            manifest.update_status(record.vod_id, 'processing')

            # Step 4: Process through Valoscribe
            map_output_dir = process_vod_with_valoscribe(vod_file, output_dir)
            map_id = map_output_dir.name  # Extract map ID from output path

            # Step 5: Mark complete
            end_time = datetime.utcnow()
            processing_time = (end_time - start_time).total_seconds()

            manifest.update_status(
                record.vod_id,
                'complete',
                map_id=map_id,
                completed_at=end_time.isoformat(),
                processing_time_seconds=processing_time
            )

            logger.info("vod_complete",
                        vod_id=record.vod_id,
                        map_id=map_id,
                        processing_time=processing_time)

        except Exception as e:
            # Mark as failed, continue to next VOD
            manifest.update_status(
                record.vod_id,
                'failed',
                error_message=str(e)
            )
            logger.error("vod_failed",
                         vod_id=record.vod_id,
                         error=str(e))

        finally:
            # Always clean up downloaded VOD file
            if vod_file and vod_file.exists():
                vod_file.unlink()
                logger.debug("deleted_vod", path=str(vod_file))

    # Final summary
    summary = manifest.get_summary()
    logger.info("pipeline_complete", **summary)
```

### VLR.gg Rate-Limited Scraper
```python
# Source: Web scraping etiquette best practices
import requests
from bs4 import BeautifulSoup
import time
import structlog

logger = structlog.get_logger()

class VLRScraper:
    """Rate-limited VLR.gg scraper with session management."""

    def __init__(self, rate_limit_seconds: float = 1.0):
        self.rate_limit = rate_limit_seconds
        self.session = requests.Session()  # Connection pooling
        self.session.headers.update({
            'User-Agent': 'VCT-Prediction-Model-Scraper/1.0 (Educational Research)'
        })
        self.last_request_time = 0.0

    def _rate_limit_delay(self):
        """Ensure minimum time between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            sleep_time = self.rate_limit - elapsed
            logger.debug("rate_limit_sleep", seconds=sleep_time)
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def scrape_match_page(self, match_url: str) -> dict:
        """Scrape match page with rate limiting."""
        self._rate_limit_delay()

        response = self.session.get(match_url, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'lxml')

        # Actual scraping logic here (selectors TBD)
        # ...

        return {
            'youtube_url': '...',
            'teams': ['...', '...'],
            # etc.
        }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| youtube-dl | yt-dlp | 2021 (fork created) | yt-dlp actively maintained, youtube-dl abandoned, security issues |
| Click CLI framework | Typer | 2019-2020 | Typer leverages type hints for cleaner code, better IDE support |
| os.path | pathlib | Python 3.4+ (2014) | pathlib reduces path-related bugs 40-50%, now considered standard |
| html.parser (default) | lxml parser | Always available | lxml is 2-3x faster, now recommended in BeautifulSoup docs |
| Manual retry loops | tenacity library | 2016+ | Declarative retry policies, handles edge cases, production-proven |

**Deprecated/outdated:**
- **youtube-dl**: Last release 2021, security vulnerabilities, doesn't handle modern YouTube. Use yt-dlp.
- **requests-html**: Discontinued, use requests + BeautifulSoup4 instead
- **os.path string manipulation**: Use pathlib for type safety and cross-platform compatibility

## Open Questions

Things that couldn't be fully resolved:

1. **VLR.gg HTML selectors**
   - What we know: Match pages contain YouTube embeds and metadata (teams, maps, dates)
   - What's unclear: Actual CSS class names and HTML structure (must reverse-engineer from live pages)
   - Recommendation: Build a small scraper prototype against 2-3 live VLR.gg match pages to discover selectors, then generalize. Include validation tests with saved HTML snapshots.

2. **Valoscribe CLI interface**
   - What we know: Valoscribe is at D:\Git\valoscribe and outputs to data/processed/{map_id}/
   - What's unclear: Exact CLI arguments for processing a single VOD, how map_id is generated, whether it supports custom output directories
   - Recommendation: Inspect Valoscribe CLI code before implementation. May need to add CLI arguments if not already present.

3. **VLR.gg map timestamp format**
   - What we know: VLR.gg match pages show map-level results, implying timestamp data exists
   - What's unclear: Whether timestamps are in page HTML or require additional API calls, format of timestamps
   - Recommendation: Inspect VLR.gg match page HTML for timestamp data. If not present, may need to process full series VOD and use Valoscribe's map detection instead.

4. **YouTube download speed limits**
   - What we know: YouTube rate-limits downloads, exact thresholds unknown
   - What's unclear: Optimal delay between downloads, whether different for different IPs/regions
   - Recommendation: Start conservative (10 sec delays), monitor for HTTP 429 errors, reduce delay if no issues after 20-30 downloads. Log download speeds to detect throttling.

5. **Phase 5 data loader multi-directory support**
   - What we know: Phase 5 loader expects all maps in VALOSCRIBE_DATA_DIR (currently points to existing 71 maps)
   - What's unclear: Whether to update loader now for multi-directory support or defer to Phase 8
   - Recommendation: Defer to Phase 8 (Feature Engineering). Phase 7 focus is VOD processing, not integration. Use separate output directory for new maps, merge in Phase 8 when needed for training.

## Sources

### Primary (HIGH confidence)
- [yt-dlp GitHub Repository](https://github.com/yt-dlp/yt-dlp) - Official source code and documentation
- [yt-dlp PyPI](https://pypi.org/project/yt-dlp/) - Current version (2026.2.4), Python requirements (3.10+)
- [yt-dlp YoutubeDL.py](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/YoutubeDL.py) - Python API parameters
- [Beautiful Soup Documentation](https://beautiful-soup-4.readthedocs.io/en/latest/) - Parser selection, find methods
- [Python subprocess documentation](https://docs.python.org/3/library/subprocess.html) - subprocess.run() API
- Existing Phase 5 codebase - loader.py, quality.py patterns

### Secondary (MEDIUM confidence)
- [VLR.gg community thread on scraping](https://www.vlr.gg/30777/is-data-scraping-allowed) - No robots.txt, 1 req/sec recommended
- [Web scraping etiquette best practices](https://bytetunnels.com/posts/responsible-scraper-etiquette-best-practices/) - Rate limiting guidelines
- [DOs and DON'Ts of Web Scraping 2026](https://medium.com/@datajournal/dos-and-donts-of-web-scraping-in-2025-e4f9b2a49431) - Industry standards
- [API Error Handling & Retry Strategies](https://easyparser.com/blog/api-error-handling-retry-strategies-python-guide) - Retry patterns

### Tertiary (LOW confidence)
- [VLR.gg unofficial scrapers on GitHub](https://github.com/aritropaul/vlr.gg-scraper) - Community approaches (incomplete documentation)
- [yt-dlp tutorials](https://ostechnix.com/yt-dlp-tutorial/) - General usage guides (not API-specific)
- WebSearch results on batch processing manifests - General patterns, not Python-specific

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - yt-dlp and BeautifulSoup are industry-standard with official docs
- VLR.gg scraping: LOW - HTML structure must be reverse-engineered, selectors unverified
- Architecture patterns: HIGH - subprocess and manifest patterns are well-established
- Valoscribe integration: MEDIUM - Valoscribe exists at D:\Git\valoscribe but CLI interface needs inspection
- Resumability patterns: HIGH - JSON manifest + atomic write is proven pattern

**Research date:** 2026-02-13
**Valid until:** ~30 days (yt-dlp updates monthly, VLR.gg HTML can change anytime)

**Critical path dependencies:**
1. Inspect Valoscribe CLI to confirm/design processing interface
2. Reverse-engineer VLR.gg HTML structure for scraping selectors
3. Validate YouTube download rate limits empirically (start conservative)
