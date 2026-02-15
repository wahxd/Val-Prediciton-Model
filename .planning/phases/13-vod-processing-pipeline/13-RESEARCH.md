# Phase 13: VOD Processing Pipeline - Research

**Researched:** 2026-02-15
**Domain:** Batch video processing pipeline with Python subprocess orchestration
**Confidence:** HIGH

## Summary

Phase 13 implements a batch processing pipeline that downloads 169 queued YouTube VODs, processes each through Valoscribe's OCR pipeline, validates output quality, and tracks progress. The pipeline must be resumable, handle failures gracefully, and provide visibility into processing status.

The standard approach combines:
- **tqdm** for progress visualization (already in project dependencies per STATE.md)
- **Python subprocess** with timeout handling for Valoscribe CLI invocation
- **Atomic file operations** for crash-safe manifest updates
- **Tournament-ordered processing** for per-tournament quality assessment
- **Circuit breaker pattern** for detecting systemic failures

Existing codebase provides strong foundations:
- `ProcessingManifest` with atomic writes and status tracking (src/pipeline/manifest.py)
- `VODOrchestrator.process_single_vod()` implements download → process → cleanup workflow
- `QualityScore` framework with 5 quality checks (src/data/quality.py)
- `VODRecord` dataclass with complete metadata including player stats and agent compositions

**Primary recommendation:** Extend existing VODOrchestrator with batch processing loop, tqdm progress bars, circuit breaker logic, and quality validation integration. Leverage tournament grouping in manifest for ordered processing.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| tqdm | Latest | Progress bars | De facto standard for Python batch processing, 200+ code snippets in Context7, 91.7 quality score |
| subprocess | stdlib | CLI execution | Built-in Python module, robust timeout and error handling since 3.3 |
| shutil | stdlib | Disk space checks | Standard library `disk_usage()` since Python 3.3, cross-platform |
| pathlib | stdlib | Path operations | Modern Python path handling, preferred over os.path |
| structlog | Existing | Structured logging | Already used throughout project, consistent logging |

### Supporting

| Library | Purpose | When to Use |
|---------|---------|-------------|
| yt-dlp | YouTube downloads | Already integrated in Valoscribe, handles private/deleted/region-locked detection |
| dataclasses.asdict | Summary reports | Convert VODRecord and QualityScore to dicts for reporting |
| json | Manifest persistence | Already used in ProcessingManifest.save() |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| tqdm | Rich library | Rich has more features but tqdm is lighter, more stable, already planned in STATE.md |
| subprocess | asyncio.create_subprocess_exec | Async not needed for sequential processing, subprocess is simpler |
| Circuit breaker library | pybreaker, circuitbreaker | Manual counter is sufficient for N consecutive failures (simpler than library overhead) |

**Installation:**
```bash
# tqdm already planned in STATE.md, likely already installed
# All other libraries are stdlib or already in project
```

## Architecture Patterns

### Recommended Project Structure
```
src/pipeline/
├── manifest.py              # Existing: VODRecord, ProcessingManifest
├── orchestrator.py          # Existing: VODOrchestrator.process_single_vod()
├── batch_processor.py       # NEW: BatchProcessor with tqdm loop, circuit breaker
└── quality_validator.py     # NEW: Wrapper integrating src/data/quality.py

scripts/
├── process_vods.py          # NEW: CLI entry point for batch processing
└── scrape_tournaments.py    # Existing: Tournament scraping
```

### Pattern 1: Batch Processing Loop with tqdm

**What:** Tournament-ordered processing with visible progress bar and circuit breaker
**When to use:** Sequential batch operations with resumability
**Example:**
```python
# Source: Context7 /tqdm/tqdm - Manual Control
from tqdm import tqdm

pending = manifest.get_pending()
# Group by tournament for ordered processing
by_tournament = defaultdict(list)
for record in pending:
    by_tournament[record.tournament].append(record)

consecutive_failures = 0
circuit_breaker_threshold = 5

with tqdm(total=len(pending), desc="Processing VODs") as pbar:
    for tournament_name, records in by_tournament.items():
        pbar.set_description(f"Processing {tournament_name}")

        for record in records:
            pbar.set_postfix(
                teams=f"{record.teams[0]} vs {record.teams[1]}",
                map=record.map_name
            )

            success = process_single_vod(record)

            if success:
                consecutive_failures = 0
                pbar.update(1)
            else:
                consecutive_failures += 1
                if consecutive_failures >= circuit_breaker_threshold:
                    pbar.write(f"Circuit breaker: {consecutive_failures} consecutive failures")
                    break  # Stop batch
```

### Pattern 2: Subprocess Timeout and Error Handling

**What:** Robust subprocess execution with timeout, graceful vs forceful termination
**When to use:** Calling external CLI tools that may hang or fail
**Example:**
```python
# Source: Python subprocess documentation + WebSearch findings
import subprocess
from pathlib import Path

def run_valoscribe_cmd(args: list[str], timeout: int | None = None) -> subprocess.CompletedProcess:
    """Run Valoscribe CLI with timeout and error handling."""
    cmd = ["python", "-m", "valoscribe"] + args

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=valoscribe_repo
        )
        return result

    except subprocess.TimeoutExpired as e:
        # Timeout means process is still running - must terminate it
        log.error("Command timeout", cmd=cmd, timeout=timeout)
        raise

    except subprocess.CalledProcessError as e:
        # Non-zero exit code
        log.error("Command failed", cmd=cmd, exit_code=e.returncode, stderr=e.stderr[:500])
        raise
```

### Pattern 3: Atomic File Cleanup on Failure

**What:** Delete incomplete output files when processing fails, prevent corrupt data
**When to use:** Processing that creates multiple output files (events.jsonl, frames.csv, metadata.json)
**Example:**
```python
# Source: WebSearch findings on atomic file operations + existing VODOrchestrator pattern
def cleanup_partial_output(output_dir: Path) -> None:
    """Delete incomplete Valoscribe output on processing failure."""
    if not output_dir.exists():
        return

    for file in ["events.jsonl", "frames.csv", "metadata.json"]:
        file_path = output_dir / file
        if file_path.exists():
            try:
                file_path.unlink()
                log.debug("Deleted partial output", file=str(file_path))
            except Exception as e:
                log.warning("Failed to delete partial output", file=str(file_path), error=str(e))

    # Remove empty directory
    try:
        output_dir.rmdir()
    except Exception:
        pass  # Directory not empty or doesn't exist
```

### Pattern 4: Disk Space Pre-flight Check

**What:** Check available disk space before starting batch to prevent mid-batch failures
**When to use:** Batch operations that download/process large files (VODs are ~500MB-2GB each)
**Example:**
```python
# Source: WebSearch findings on shutil.disk_usage
import shutil

def check_disk_space(download_dir: Path, min_gb: float = 50.0) -> bool:
    """Check if sufficient disk space available before starting batch.

    Args:
        download_dir: Directory where VODs will be downloaded
        min_gb: Minimum GB required (default: 50GB for safety)

    Returns:
        True if sufficient space, False otherwise
    """
    usage = shutil.disk_usage(download_dir)
    free_gb = usage.free / (1024 ** 3)

    if free_gb < min_gb:
        log.error(
            "insufficient_disk_space",
            free_gb=f"{free_gb:.1f}",
            required_gb=min_gb,
            path=str(download_dir)
        )
        return False

    log.info("disk_space_ok", free_gb=f"{free_gb:.1f}", path=str(download_dir))
    return True
```

### Pattern 5: Batch Summary Report Generation

**What:** Human-readable summary after batch completion with quality distribution
**When to use:** After batch processing to provide visibility into results
**Example:**
```python
# Source: WebSearch findings + existing TournamentScraper.generate_report pattern
from dataclasses import asdict

def generate_batch_report(
    manifest: ProcessingManifest,
    quality_scores: dict[str, QualityScore],
    start_time: datetime,
    end_time: datetime
) -> str:
    """Generate human-readable batch processing report."""
    summary = manifest.get_summary()
    duration = (end_time - start_time).total_seconds()

    # Quality distribution
    tier_counts = {"high": 0, "medium": 0, "low": 0}
    for score in quality_scores.values():
        tier_counts[score.tier] += 1

    lines = [
        "=" * 50,
        "VOD PROCESSING BATCH REPORT",
        "=" * 50,
        "",
        f"Duration: {duration / 3600:.1f} hours",
        f"Total VODs: {summary['total']}",
        f"  Complete: {summary['by_status'].get('complete', 0)}",
        f"  Failed: {summary['by_status'].get('failed', 0)}",
        f"  Pending: {summary['by_status'].get('pending', 0)}",
        "",
        "Quality Distribution:",
        f"  High: {tier_counts['high']} ({tier_counts['high']/max(1,len(quality_scores))*100:.1f}%)",
        f"  Medium: {tier_counts['medium']} ({tier_counts['medium']/max(1,len(quality_scores))*100:.1f}%)",
        f"  Low: {tier_counts['low']} ({tier_counts['low']/max(1,len(quality_scores))*100:.1f}%)",
        "",
        "Flagged for Review:",
    ]

    for vod_id, score in quality_scores.items():
        if score.flagged_for_review:
            lines.append(f"  {vod_id}: {score.tier} tier, {len(score.all_issues)} issues")

    return "\n".join(lines)
```

### Anti-Patterns to Avoid

- **Re-downloading on retry:** Download once per VOD, mark as failed if download fails (don't retry download)
- **Global exception handlers:** Catch exceptions per-VOD, not globally (prevents single failure from killing entire batch)
- **Silent failures:** Always log error reason in manifest.error_message field
- **Blocking on I/O:** VOD processing is CPU-intensive (OCR), sequential processing is appropriate (don't add async complexity)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Progress bars | Custom print statements | tqdm | Handles terminal width, nested bars, rate estimation, time-to-completion |
| Atomic writes | Manual temp file logic | Existing ProcessingManifest.save() | Already implemented write-to-.tmp-then-rename pattern |
| Disk space checks | Parse `df -h` output | shutil.disk_usage() | Cross-platform, returns bytes directly, stdlib since 3.3 |
| Quality scoring | Custom heuristics | Existing QualityScore framework | 5 comprehensive checks already implemented (kill_count, round_progression, etc.) |
| VOD accessibility | Parse yt-dlp errors | yt-dlp extract_info(download=False) | Built-in metadata extraction without download |

**Key insight:** Valoscribe already handles the hard OCR work. This pipeline is orchestration: sequential execution, state management, error handling, and reporting. Leverage existing tools rather than reimplementing workflow logic.

## Common Pitfalls

### Pitfall 1: Not Terminating Timed-Out Subprocesses

**What goes wrong:** subprocess.run() with timeout kills the subprocess, but TimeoutExpired is raised while process is being terminated. If not handled properly, zombie processes accumulate.

**Why it happens:** Developers assume timeout automatically cleans up the process completely.

**How to avoid:** Always catch TimeoutExpired, log it, and let subprocess.run() handle termination. Don't try to manually kill the process.

**Warning signs:** Increasing memory usage during batch processing, multiple python/yt-dlp processes in task manager after script exits.

**Source:** [Python subprocess documentation](https://docs.python.org/3/library/subprocess.html), [WebSearch: subprocess timeout handling 2026](https://www.codestudy.net/blog/run-a-process-and-kill-it-if-it-doesn-t-end-within-one-hour/)

### Pitfall 2: Circuit Breaker Threshold Too Low

**What goes wrong:** Setting circuit breaker to N=2 consecutive failures causes batch to stop prematurely when encountering a few bad VODs in a row (common with tournament footage that has intermittent quality issues).

**Why it happens:** Developer assumes failures are always systemic (API down, disk full) rather than per-VOD issues (private video, corrupt upload).

**How to avoid:** Use N=5 as minimum threshold. Systemic issues (Valoscribe crash, disk full, YouTube API down) will hit 5 failures quickly. Per-VOD issues won't.

**Warning signs:** Batch stops after processing <10 VODs, but restarting the batch successfully processes more VODs.

**Source:** [WebSearch: circuit breaker pattern Python 2026](https://thebackenddevelopers.substack.com/p/implementing-the-circuit-breaker)

### Pitfall 3: Forgetting to Delete VOD Files After Processing

**What goes wrong:** VOD files (500MB-2GB each) accumulate in download_dir, filling disk during batch processing. Batch fails mid-way due to insufficient disk space.

**Why it happens:** Developer focuses on processing workflow, forgets cleanup step.

**How to avoid:** VODOrchestrator already has `delete_vod_after_processing` config flag and cleanup in `finally` block. Ensure it's set to True in production config. Add pre-flight disk space check as safety net.

**Warning signs:** Batch succeeds for first 20-30 VODs, then fails with "No space left on device" errors.

**Source:** Existing VODOrchestrator.process_single_vod() finally block (lines 306-312 in src/pipeline/orchestrator.py)

### Pitfall 4: Processing VODs in Arbitrary Order

**What goes wrong:** VODs from multiple tournaments are interleaved. When analyzing results, can't easily assess per-tournament quality (e.g., "Masters Bangkok had 95% success rate, VCT Americas had 60%").

**Why it happens:** Processing manifest.get_pending() directly without grouping.

**How to avoid:** Group pending VODs by tournament before processing loop. Process one tournament fully before starting next. Enables per-tournament batch summary reports.

**Warning signs:** Batch summary shows overall stats but no tournament-level breakdown, making it hard to diagnose quality issues (e.g., older tournaments have worse video quality).

**Source:** CONTEXT.md user decision: "VODs processed by tournament: complete one tournament fully before starting the next"

### Pitfall 5: Not Recording Error Messages in Manifest

**What goes wrong:** VOD fails, manifest shows status="failed", but no information about why it failed (download error? OCR crash? timeout?). Debugging requires re-running failed VODs.

**Why it happens:** Catching exceptions but not storing str(e) in manifest.error_message field.

**How to avoid:** Every exception handler should call `manifest.update_status(vod_id, "failed", error_message=str(e))`. Error messages are the primary diagnostic tool.

**Warning signs:** Manifest has many failed records but all error_message fields are None or empty.

**Source:** CONTEXT.md user decision: "Log error reason/exception message in manifest for each failure"

## Code Examples

Verified patterns from official sources:

### Batch Processing with Explicit Batch Size
```python
# Source: CONTEXT.md user decision + tqdm Context7 examples
def process_batch(manifest: ProcessingManifest, batch_size: int | None = None):
    """Process VODs with optional batch size limit."""
    pending = manifest.get_pending()

    # Tournament-ordered grouping
    by_tournament = defaultdict(list)
    for record in pending:
        by_tournament[record.tournament].append(record)

    # Flatten back to list (preserves tournament grouping)
    ordered_pending = []
    for records in by_tournament.values():
        ordered_pending.extend(records)

    # Apply batch limit
    to_process = ordered_pending[:batch_size] if batch_size else ordered_pending

    log.info("batch_starting", total=len(to_process), batch_size=batch_size or "unlimited")

    consecutive_failures = 0
    processed_count = 0

    with tqdm(total=len(to_process), desc="Processing VODs") as pbar:
        for record in to_process:
            # Update progress bar description
            pbar.set_description(f"[{record.tournament}] {record.teams[0]} vs {record.teams[1]}")

            success = process_single_vod(record)

            if success:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                if consecutive_failures >= 5:  # Circuit breaker
                    pbar.write(f"⚠️  Circuit breaker: {consecutive_failures} consecutive failures")
                    break

            processed_count += 1
            pbar.update(1)

    log.info("batch_complete", processed=processed_count, remaining=len(pending) - processed_count)
```

### YouTube VOD Accessibility Check (Before Download)
```python
# Source: yt-dlp Context7 examples + WebSearch findings
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

def check_vod_accessible(youtube_url: str) -> tuple[bool, str | None]:
    """Check if YouTube VOD is accessible before downloading.

    Returns:
        (accessible, error_reason) - error_reason is None if accessible
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,  # Need full metadata
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)

            # Check availability field
            availability = info.get('availability')
            if availability in ['private', 'premium_only', 'subscriber_only', 'needs_auth']:
                return False, f"Video unavailable: {availability}"

            # Additional checks
            if info.get('is_live'):
                return False, "Video is live stream (not VOD)"

            return True, None

    except DownloadError as e:
        error_msg = str(e)
        if 'Private video' in error_msg:
            return False, "Video is private"
        elif 'Video unavailable' in error_msg:
            return False, "Video unavailable (deleted or region-locked)"
        else:
            return False, f"Download error: {error_msg[:100]}"
```

### Quality Validation Integration
```python
# Source: Existing src/data/quality.py + new integration wrapper
from src.data.quality import score_map_quality
from src.data.schemas import ValoscribeEvent, MapMetadata
import json

def validate_processed_output(output_dir: Path, vod_id: str) -> QualityScore:
    """Validate Valoscribe output quality after processing.

    Reads events.jsonl and metadata.json, runs quality checks.
    """
    events_file = output_dir / "events.jsonl"
    metadata_file = output_dir / "metadata.json"

    # Load events
    events = []
    with open(events_file, 'r') as f:
        for line in f:
            event_data = json.loads(line)
            events.append(ValoscribeEvent(**event_data))

    # Load metadata (optional)
    metadata = None
    if metadata_file.exists():
        with open(metadata_file, 'r') as f:
            metadata_data = json.load(f)
            metadata = MapMetadata(**metadata_data)

    # Run quality checks
    quality_score = score_map_quality(events, metadata, map_id=vod_id)

    log.info(
        "quality_validated",
        vod_id=vod_id,
        tier=quality_score.tier,
        overall_score=f"{quality_score.overall_score:.2f}",
        flagged=quality_score.flagged_for_review
    )

    return quality_score
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual VOD download scripts | yt-dlp Python API | 2020+ | Programmatic error detection, metadata extraction without download |
| os.path string manipulation | pathlib | Python 3.4+ | Type-safe paths, cleaner cross-platform code |
| Custom progress prints | tqdm | 2015+ | Automatic rate estimation, nested bars, terminal-aware |
| print() for batch logs | structlog | 2023+ (project adoption) | Structured logging enables better diagnostics |
| Retry on all failures | Skip and circuit breaker | 2024+ | Faster failure detection, better for batch jobs |

**Deprecated/outdated:**
- `youtube-dl`: Unmaintained since 2021, replaced by yt-dlp (actively maintained fork)
- Manual disk space checks via subprocess: shutil.disk_usage() is stdlib since Python 3.3
- Asyncio for CPU-bound work: OCR processing is CPU-intensive, sequential processing is appropriate

## Open Questions

1. **VOD file retention after processing**
   - What we know: ProcessingConfig has `delete_vod_after_processing` flag, VODOrchestrator implements cleanup in finally block
   - What's unclear: Should we default to True (save disk space) or False (enable re-processing)? 169 VODs × ~1GB = ~169GB disk usage if kept.
   - Recommendation: Default to True (delete after processing). Re-processing is rare, and VODs can be re-downloaded if needed. Disk space is more valuable than re-download time.

2. **Cross-validation against VLR.gg data**
   - What we know: VODRecord contains player_stats and match_score from VLR.gg scraping. Valoscribe outputs metadata.json with team names and scores.
   - What's unclear: Should pipeline compare Valoscribe's detected scores against VLR.gg scraped scores? Or defer to Phase 14 experiments?
   - Recommendation: Store both in manifest, flag disagreements in quality report, but don't auto-exclude. Phase 14 experiments decide filtering thresholds.

3. **Retry-failed mechanism**
   - What we know: CONTEXT.md specifies "No retries on either failure type". Manifest tracks retry_count field.
   - What's unclear: Should we add a --retry-failed CLI flag for manual retry of previously failed VODs? Or require manual manifest editing?
   - Recommendation: Add --retry-failed flag that resets status to "pending" for failed VODs. Useful for retrying after fixing systemic issues (disk space, API quota).

4. **Exact consecutive failure threshold**
   - What we know: CONTEXT.md suggests 3-5 range. Circuit breaker research recommends 5+ for batch processing.
   - What's unclear: Should threshold be configurable or hardcoded?
   - Recommendation: Hardcode N=5 initially. Make configurable via CLI flag (--circuit-breaker-threshold N) if users need different thresholds.

5. **Download timeout duration**
   - What we know: ProcessingConfig has processing_timeout_seconds=7200 (2 hours). Download is separate step.
   - What's unclear: What timeout for yt-dlp download step? VODs are 45-90 min videos (~500MB-2GB).
   - Recommendation: Set download timeout to 30 minutes (1800 seconds). Large files at 1 Mbps = ~2GB in 5 hours, but modern connections are faster. 30 min is safety net for slow connections.

## Sources

### Primary (HIGH confidence)

- Context7: /tqdm/tqdm - [Manual control, postfix updates, dynamic descriptions](https://github.com/tqdm/tqdm)
- Context7: /yt-dlp/yt-dlp - [Error handling, authentication, availability detection](https://context7.com/yt-dlp/yt-dlp/llms.txt)
- [Python subprocess documentation](https://docs.python.org/3/library/subprocess.html) - Timeout and error handling
- [shutil.disk_usage documentation](https://docs.python.org/3/library/shutil.html#shutil.disk_usage) - Disk space checks
- Existing codebase:
  - src/pipeline/manifest.py - VODRecord, ProcessingManifest
  - src/pipeline/orchestrator.py - VODOrchestrator.process_single_vod()
  - src/data/quality.py - QualityScore framework
  - src/scraping/tournament_scraper.py - Report generation pattern

### Secondary (MEDIUM confidence)

- [Python subprocess timeout best practices 2026](https://www.codestudy.net/blog/run-a-process-and-kill-it-if-it-doesn-t-end-within-one-hour/) - TimeoutExpired handling
- [Implementing Circuit Breaker Pattern in Python](https://thebackenddevelopers.substack.com/p/implementing-the-circuit-breaker) - Circuit breaker thresholds
- [Python atomic file operations](https://sahmanish20.medium.com/better-file-writing-in-python-embrace-atomic-updates-593843bfab4f) - Cleanup on failure patterns
- [yt-dlp private/deleted video detection](https://github.com/yt-dlp/yt-dlp/issues/689) - Availability field usage
- [Python disk space checking 2026](https://www.silicloud.com/blog/how-does-python-check-available-disk-space/) - shutil.disk_usage() best practices

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - tqdm, subprocess, shutil are well-established, existing codebase provides strong foundations
- Architecture: HIGH - Patterns derived from existing VODOrchestrator and TournamentScraper implementations
- Pitfalls: HIGH - Based on existing code patterns and documented best practices

**Research date:** 2026-02-15
**Valid until:** 60 days (stable domain: batch processing, CLI tools, quality validation)
