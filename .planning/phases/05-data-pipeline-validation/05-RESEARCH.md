# Phase 5: Data Pipeline & Validation - Research

**Researched:** 2026-02-13
**Domain:** Python data pipeline, JSONL parsing, quality scoring, audit reporting
**Confidence:** HIGH

## Summary

Phase 5 requires building a robust Python data pipeline to ingest Valoscribe's JSONL events, CSV frames, and JSON metadata with comprehensive quality scoring and dual-format audit reports (JSON + Markdown). The research focused on establishing the standard stack for modern Python data pipelines in 2026 and understanding patterns for resilient, production-grade data loading systems.

**Key findings:**
- **Pydantic v2** is the standard for data validation and parsing, with `model_validate_json()` for efficient JSONL processing
- **Typer** has emerged as the modern CLI framework of choice over Click, leveraging Python type hints for cleaner code
- **pathlib** is now the standard over `os.path`, reducing path-related errors by 40-50%
- **pandas with PyArrow engine** provides 2-3x faster CSV parsing for the frames.csv files
- **structlog** is already in use in this codebase (Phase 1) for structured JSON logging
- **Error handling pattern:** Continue on failure, collect all errors, report at end (maximizes usable data from 71-map dataset)

**Primary recommendation:** Use Pydantic for schema validation, Typer for CLI, pathlib for all file operations, pandas with PyArrow for CSV, and build a composable Python API with thin CLI wrapper.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Pydantic | 2.x | Data validation, JSONL parsing | Industry standard for runtime validation, efficient `model_validate_json()` method, already used in Phase 1 codebase |
| pandas | 2.x | CSV frame parsing | De facto standard for tabular data, optimized PyArrow engine for 2-3x speed gains |
| pathlib | stdlib | File path operations | Standard library since Python 3.4, reduces path errors 40-50% vs os.path |
| Typer | 0.12+ | CLI framework | Modern Click wrapper with type hints, cleaner than Click decorators, excellent IDE support |
| structlog | 25.x | Structured logging | Already in Phase 1 codebase, JSON output for observability |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic-settings | 2.x | Environment variable management | For .env file loading and configuration management |
| rich | 14.x | Progress bars, formatted output | For per-map progress display and human-readable CLI output |
| pytest | 8.x | Testing framework | Already in Phase 1, continue pattern |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Typer | Click | Click is mature but requires decorators vs type hints, worse IDE support |
| Typer | argparse | argparse is stdlib but far more verbose, no automatic help generation |
| pathlib | os.path | os.path is legacy, error-prone string manipulation |
| rich | tqdm | tqdm is lighter but less visually polished, both are valid choices |

**Installation:**
```bash
# Add to requirements.txt
pydantic>=2.0
pydantic-settings>=2.0
pandas>=2.0
pyarrow>=10.0  # For fast CSV parsing
typer>=0.12
rich>=14.0
structlog>=25.0  # Already installed from Phase 1
pytest>=8.0  # Already installed from Phase 1
```

## Architecture Patterns

### Recommended Project Structure
```
src/
├── data/
│   ├── __init__.py
│   ├── loader.py         # Core loading logic (Python API)
│   ├── schemas.py        # Pydantic models for Valoscribe formats
│   ├── quality.py        # Quality scoring logic
│   ├── audit.py          # Audit report generation
│   └── cli.py            # Typer CLI wrapper
├── config.py             # pydantic-settings configuration
└── ...
data/
├── audit/                # Output location
│   ├── audit_YYYYMMDD_HHMMSS.json
│   └── audit_YYYYMMDD_HHMMSS.md
└── ...
tests/
└── data/
    ├── test_loader.py
    ├── test_schemas.py
    ├── test_quality.py
    └── fixtures/         # Sample Valoscribe data for testing
```

### Pattern 1: Pydantic Models for Unknown Schema Discovery
**What:** Use Pydantic with flexible field typing to discover Valoscribe's actual output format while preserving all data.

**When to use:** When the upstream data format isn't fully documented (Phase 5 is a data exploration exercise).

**Example:**
```python
# Source: Based on Pydantic best practices
from pydantic import BaseModel, Field, field_validator
from typing import Any, Literal

class ValoscribeEvent(BaseModel):
    """Base event model - preserves all fields via extra='allow'."""
    type: str
    timestamp: float
    round: int

    model_config = {
        'extra': 'allow',  # Preserve unrecognized fields
        'strict': False,   # Allow type coercion for discovery
    }

class KillEvent(ValoscribeEvent):
    """Kill event with known fields, preserves extras."""
    type: Literal["kill"]
    killer: str
    victim: str
    weapon: str
    killer_team: str
    victim_team: str

    @field_validator('round')
    @classmethod
    def round_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError(f"Round must be >= 1, got {v}")
        return v
```

**Key insight:** Use `extra='allow'` during discovery phase, then tighten to `extra='forbid'` in Phase 6 once schema is fully documented.

### Pattern 2: Continue-on-Failure Error Collection
**What:** Process all maps even when some fail, collecting errors for end-of-run reporting.

**When to use:** When maximizing data coverage is more important than failing fast (71 maps total, want all usable data).

**Example:**
```python
# Source: Data pipeline error handling patterns
from dataclasses import dataclass
from pathlib import Path

@dataclass
class LoadResult:
    """Per-map load result with success/failure tracking."""
    map_id: str
    success: bool
    data: dict | None = None
    error: Exception | None = None
    error_phase: str | None = None  # "discovery", "events", "frames", "metadata"

def load_all_maps(valoscribe_dir: Path) -> dict[str, LoadResult]:
    """Load all maps, continue on failure, return comprehensive results."""
    results = {}
    map_dirs = discover_map_directories(valoscribe_dir)

    for map_id, map_dir in map_dirs.items():
        try:
            data = load_map(map_dir)
            results[map_id] = LoadResult(map_id=map_id, success=True, data=data)
        except Exception as e:
            # Continue processing, record failure
            results[map_id] = LoadResult(
                map_id=map_id,
                success=False,
                error=e,
                error_phase=determine_error_phase(e)
            )
            logger.warning("map_load_failed", map_id=map_id, error=str(e))

    # Report all failures at end
    failures = [r for r in results.values() if not r.success]
    if failures:
        logger.error("load_summary", total=len(results), failures=len(failures))

    return results
```

### Pattern 3: Pydantic Settings for Configuration
**What:** Use pydantic-settings to manage environment variables and .env files with type validation.

**When to use:** For all configuration (Valoscribe data path, output directory, etc.).

**Example:**
```python
# Source: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class DataPipelineConfig(BaseSettings):
    """Configuration for data pipeline with .env support."""
    valoscribe_data_dir: Path
    audit_output_dir: Path = Path("data/audit")
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="VPM_",  # Environment variables: VPM_VALOSCRIBE_DATA_DIR
        env_ignore_empty=True,  # Use defaults if env var is empty
    )
```

### Pattern 4: JSONL Parsing with Pydantic
**What:** Use `model_validate_json()` for line-by-line JSONL parsing with validation.

**When to use:** For parsing Valoscribe's events.jsonl files.

**Example:**
```python
# Source: https://docs.pydantic.dev/latest/concepts/json/
from pydantic import ValidationError
from pathlib import Path

def parse_events_jsonl(events_file: Path) -> list[ValoscribeEvent]:
    """Parse JSONL events file with per-line validation."""
    events = []
    errors = []

    with events_file.open('r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                # model_validate_json is faster than json.loads + validate
                event = ValoscribeEvent.model_validate_json(line)
                events.append(event)
            except ValidationError as e:
                errors.append({
                    'line': line_num,
                    'error': e.errors(),
                    'raw': line
                })

    if errors:
        logger.warning("jsonl_parse_errors", file=str(events_file), error_count=len(errors))

    return events
```

### Pattern 5: Pandas CSV Loading with PyArrow
**What:** Use pandas with PyArrow engine for 2-3x faster CSV parsing.

**When to use:** For loading Valoscribe's frames.csv files.

**Example:**
```python
# Source: https://docs.kanaries.net/topics/Pandas/pandas-read-csv
import pandas as pd
from pathlib import Path

def load_frames_csv(frames_file: Path) -> pd.DataFrame:
    """Load frames CSV with optimized PyArrow engine."""
    return pd.read_csv(
        frames_file,
        engine='pyarrow',
        dtype_backend='pyarrow',  # Use PyArrow types for speed
        # Specify dtypes if known to skip inference:
        # dtype={'timestamp': 'float64', 'team1_alive': 'int64', ...}
    )
```

### Pattern 6: Typer CLI with Rich Progress
**What:** Use Typer for CLI commands with Rich for progress bars and formatted output.

**When to use:** For the thin CLI wrapper around the Python API.

**Example:**
```python
# Source: https://typer.tiangolo.com/tutorial/commands/
import typer
from rich.progress import track
from pathlib import Path

app = typer.Typer(no_args_is_help=True)

@app.command()
def load(
    data_dir: Path = typer.Option(
        None,
        "--data-dir",
        help="Path to Valoscribe data directory (overrides VALOSCRIBE_DATA_DIR env var)"
    ),
    audit: bool = typer.Option(
        False,
        "--audit",
        help="Run quality audit after loading"
    ),
    verbose: bool = typer.Option(
        False,
        "-v",
        "--verbose",
        help="Show detailed progress"
    ),
):
    """Load Valoscribe data and optionally run quality audit."""
    config = get_config(data_dir_override=data_dir)

    map_dirs = discover_map_directories(config.valoscribe_data_dir)

    for map_id, map_dir in track(map_dirs.items(), description="Loading maps..."):
        if verbose:
            typer.echo(f"Loading {map_id}...")
        load_map(map_dir)

    if audit:
        typer.echo("Running quality audit...")
        run_audit()

    typer.secho("✓ Load complete", fg=typer.colors.GREEN)

if __name__ == "__main__":
    app()
```

### Anti-Patterns to Avoid
- **Loading entire files into memory:** Use line-by-line JSONL parsing, not `json.load()` on the whole file
- **Using os.path for path operations:** Use pathlib.Path for all file paths (reduces errors 40-50%)
- **Fail-fast on single map errors:** Continue processing, collect errors, report at end
- **Hardcoding paths:** Use pydantic-settings with .env for environment-specific configuration
- **String-based path concatenation:** Use pathlib's `/` operator: `base_dir / "subdir" / "file.json"`
- **Ignoring Pydantic ValidationError details:** Use `e.errors()` to extract structured error information
- **Not preserving unknown fields during discovery:** Use `extra='allow'` to discover full Valoscribe schema

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CLI argument parsing | Custom argparse boilerplate | Typer | Type-hint based, auto-generates help, excellent IDE support |
| Environment variable loading | Manual os.environ access | pydantic-settings | Type validation, .env support, defaults, mandatory checks |
| Progress indication | Print statements | rich.progress | Professional output, handles terminal width, multiple bars |
| File path manipulation | String concatenation | pathlib.Path | Cross-platform, prevents path errors, cleaner API |
| JSONL parsing | Manual line splitting + json.loads | Pydantic.model_validate_json() | Faster, validates schema per-line, better error messages |
| Structured logging | Print with timestamps | structlog | JSON output, context binding, already in Phase 1 codebase |
| Data validation | Manual type checks | Pydantic models | Comprehensive validation, clear error messages, serialization |

**Key insight:** With only 71 maps, simplicity and reliability trump micro-optimization. Use proven libraries to minimize bugs and maximize maintainability.

## Common Pitfalls

### Pitfall 1: Memory Overflow on Large Files
**What goes wrong:** Loading entire JSONL or CSV files into memory causes OOM errors on large datasets.

**Why it happens:** Calling `json.load()` on a multi-MB JSONL file or `pd.read_csv()` without chunking loads everything into RAM.

**How to avoid:**
- JSONL: Parse line-by-line with a generator pattern
- CSV: For frames.csv (likely small per map), full load is fine; if needed, use `chunksize` parameter
- Never use `.readlines()` or `json.load()` on potentially large JSONL files

**Warning signs:**
- MemoryError exceptions
- Process memory usage growing linearly with file size
- Slow startup before processing begins

### Pitfall 2: Path Errors from String Concatenation
**What goes wrong:** Path strings concatenated with `/` or `+` fail on Windows, produce wrong paths, or create security vulnerabilities.

**Why it happens:** Windows uses backslashes, forward slash concatenation is error-prone, `..\` traversal isn't caught.

**How to avoid:**
- Always use `pathlib.Path` for all file operations
- Use `/` operator for path joining: `base / "subdir" / "file.txt"`
- Validate paths with `.resolve()` to catch traversal attacks
- Never construct paths with f-strings or string addition

**Warning signs:**
- `FileNotFoundError` on valid-looking paths
- Different behavior on Windows vs Linux
- Paths with mixed separators (`data/\maps\file.json`)

### Pitfall 3: Swallowing ValidationError Details
**What goes wrong:** Catching Pydantic ValidationError but only logging generic message loses critical debugging info.

**Why it happens:** `str(e)` on ValidationError is verbose, developers simplify to just "validation failed".

**How to avoid:**
- Use `e.errors()` to get structured error details (field, error type, message)
- Log the field path, error type, and input value for debugging
- In reports, include sample invalid data and specific validation failure

**Warning signs:**
- Log says "validation error" but doesn't say which field
- Can't reproduce validation failures without debugging
- Users report "data failed to load" without specifics

### Pitfall 4: Not Discovering Schema Before Constraining
**What goes wrong:** Define strict Pydantic models with `extra='forbid'` before exploring data, lose fields you didn't know existed.

**Why it happens:** Assumption that CLAUDE.md's data format description is complete and up-to-date.

**How to avoid:**
- Start with `extra='allow'` to discover all fields
- Catalog ALL fields seen across all 71 maps
- Log when unexpected fields appear
- Only tighten to `extra='forbid'` after Phase 6 when schema is documented

**Warning signs:**
- Valoscribe adds new field, your parser silently drops it
- Phase 6 discovers data you "loaded" in Phase 5 is incomplete
- Comparing raw JSONL to loaded data shows missing fields

### Pitfall 5: Fail-Fast Losing Partial Dataset
**What goes wrong:** First map error aborts entire load, lose 70 usable maps because one is corrupted.

**Why it happens:** Standard exception handling with early exit, no error collection.

**How to avoid:**
- Use continue-on-failure pattern (see Architecture Patterns)
- Collect all errors in a list
- Report failures at end with summary counts
- Return both successful loads and error details

**Warning signs:**
- One bad map prevents seeing errors in other maps
- Re-running after fixing one error reveals another (whack-a-mole)
- Can't get aggregate failure statistics

### Pitfall 6: Ignoring Valoscribe's validation_results
**What goes wrong:** Build independent quality checks but don't compare to Valoscribe's self-reported validation.

**Why it happens:** Treating Valoscribe as black box, not checking metadata.json's validation_results.

**How to avoid:**
- Parse validation_results from metadata.json
- Cross-check: Valoscribe says "pass" but your quality check fails → interesting!
- Flag disagreements in audit report
- Investigate root cause of disagreements (your logic wrong? Valoscribe's validation incomplete?)

**Warning signs:**
- Excluding maps Valoscribe says are valid
- Including maps Valoscribe flagged as invalid
- No comparison metric in audit report

### Pitfall 7: Not Validating Environment Variables
**What goes wrong:** VALOSCRIBE_DATA_DIR is set to non-existent path, cryptic errors deep in load logic.

**Why it happens:** No upfront validation of configuration.

**How to avoid:**
- Use pydantic-settings validators to check directory exists
- Validate required environment variables at startup
- Provide clear error message if path is missing or invalid

**Warning signs:**
- "FileNotFoundError: [path]/..." errors during map discovery
- Error message doesn't explain root cause (bad config)
- Developer confusion about where to set paths

## Code Examples

Verified patterns from official sources:

### Quality Scoring Function
```python
# Source: Based on data quality scoring patterns research
from dataclasses import dataclass
from typing import Literal

@dataclass
class QualityScore:
    """Per-map quality score with issue tracking."""
    map_id: str
    overall_score: float  # 0.0-1.0
    tier: Literal["high", "medium", "low"]

    # Component scores
    kill_count_score: float
    round_progression_score: float
    event_completeness_score: float
    timing_consistency_score: float

    # Issues found
    issues: list[str]
    warnings: list[str]

def score_map_quality(events: list[ValoscribeEvent], metadata: dict) -> QualityScore:
    """Score data quality for a single map."""
    issues = []
    warnings = []

    # Kill count vs expected (should be ~150-300 for a full map)
    kill_events = [e for e in events if e.type == "kill"]
    kill_score = min(1.0, len(kill_events) / 150)
    if len(kill_events) < 50:
        issues.append(f"Low kill count: {len(kill_events)} (expected ~150-300)")

    # Round progression (round numbers should be sequential)
    round_starts = [e for e in events if e.type == "round_start"]
    round_numbers = [e.round for e in round_starts]
    expected_rounds = list(range(1, len(round_numbers) + 1))
    progression_score = 1.0 if round_numbers == expected_rounds else 0.5
    if round_numbers != expected_rounds:
        issues.append(f"Non-sequential rounds: {round_numbers}")

    # Event completeness (every round should have start, end, kills)
    # ... (implementation based on quality signals from CONTEXT.md)

    # Calculate overall score (weighted average)
    overall = (kill_score * 0.3 + progression_score * 0.3 +
               completeness_score * 0.2 + timing_score * 0.2)

    # Determine tier
    if overall >= 0.8:
        tier = "high"
    elif overall >= 0.5:
        tier = "medium"
    else:
        tier = "low"

    return QualityScore(
        map_id=metadata.get("map_id", "unknown"),
        overall_score=overall,
        tier=tier,
        kill_count_score=kill_score,
        round_progression_score=progression_score,
        event_completeness_score=completeness_score,
        timing_consistency_score=timing_score,
        issues=issues,
        warnings=warnings
    )
```

### Markdown Report Generation
```python
# Source: Based on markdown generation research
from pathlib import Path
from datetime import datetime

def generate_markdown_report(
    audit_results: dict[str, QualityScore],
    output_path: Path
) -> None:
    """Generate human-readable Markdown audit report."""

    # Calculate summary statistics
    total_maps = len(audit_results)
    high_quality = sum(1 for r in audit_results.values() if r.tier == "high")
    medium_quality = sum(1 for r in audit_results.values() if r.tier == "medium")
    low_quality = sum(1 for r in audit_results.values() if r.tier == "low")

    lines = [
        f"# Valoscribe Data Quality Audit Report",
        f"",
        f"**Generated:** {datetime.now().isoformat()}",
        f"**Total Maps:** {total_maps}",
        f"",
        f"## Executive Summary",
        f"",
        f"| Quality Tier | Count | Percentage |",
        f"|--------------|-------|------------|",
        f"| High (≥0.8)  | {high_quality} | {high_quality/total_maps*100:.1f}% |",
        f"| Medium (0.5-0.8) | {medium_quality} | {medium_quality/total_maps*100:.1f}% |",
        f"| Low (<0.5)   | {low_quality} | {low_quality/total_maps*100:.1f}% |",
        f"",
        f"**Dataset Readiness:** {(high_quality + medium_quality) / total_maps * 100:.1f}% maps usable for training",
        f"",
        f"## Table of Contents",
        f"",
    ]

    # Generate TOC
    for map_id in sorted(audit_results.keys()):
        # Convert map_id to anchor-safe format
        anchor = map_id.lower().replace(" ", "-").replace("_", "-")
        lines.append(f"- [{map_id}](#{anchor})")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Per-map details
    for map_id, score in sorted(audit_results.items()):
        lines.append(f"## {map_id}")
        lines.append(f"")
        lines.append(f"**Overall Score:** {score.overall_score:.2f} ({score.tier.upper()})")
        lines.append(f"")
        lines.append(f"### Component Scores")
        lines.append(f"")
        lines.append(f"| Component | Score |")
        lines.append(f"|-----------|-------|")
        lines.append(f"| Kill Count | {score.kill_count_score:.2f} |")
        lines.append(f"| Round Progression | {score.round_progression_score:.2f} |")
        lines.append(f"| Event Completeness | {score.event_completeness_score:.2f} |")
        lines.append(f"| Timing Consistency | {score.timing_consistency_score:.2f} |")
        lines.append(f"")

        if score.issues:
            lines.append(f"### Issues")
            lines.append(f"")
            for issue in score.issues:
                lines.append(f"- ⚠️ {issue}")
            lines.append(f"")

        if score.warnings:
            lines.append(f"### Warnings")
            lines.append(f"")
            for warning in score.warnings:
                lines.append(f"- ⚡ {warning}")
            lines.append(f"")

        lines.append(f"---")
        lines.append(f"")

    # Write to file
    output_path.write_text("\n".join(lines), encoding="utf-8")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Click for CLI | Typer | 2020-2021 | Type hints replace decorators, better IDE support, cleaner code |
| os.path | pathlib.Path | Python 3.4+ (2014) | 40-50% fewer path errors, cross-platform by default |
| json.loads() | Pydantic.model_validate_json() | Pydantic v2 (2023) | Faster parsing, validation, better errors |
| pandas default engine | pandas with PyArrow | 2023-2024 | 2-3x faster CSV parsing, better type handling |
| argparse | Typer | 2020+ | Auto-generated help, type safety, less boilerplate |

**Deprecated/outdated:**
- **os.path for new code:** Use pathlib (stdlib since Python 3.4, now the standard)
- **Click for new projects:** Typer is the modern wrapper (Click still valid, but Typer is preferred)
- **Pydantic v1:** Pydantic v2 (2023+) has breaking changes but significant performance improvements

## Open Questions

Things that couldn't be fully resolved:

1. **Valoscribe's Actual Data Format**
   - What we know: CLAUDE.md describes events.jsonl, frames.csv, metadata.json with some fields
   - What's unclear: Complete schema of ALL fields, ALL event types, value ranges, optional vs required
   - Recommendation: Phase 5 must discover and catalog actual format; use `extra='allow'` on Pydantic models

2. **Quality Scoring Thresholds**
   - What we know: Need to score kill count, round progression, event completeness, timing
   - What's unclear: Specific threshold values (e.g., "low kill count" = <50? <100?), tier boundaries
   - Recommendation: Start with conservative thresholds, adjust after seeing actual distribution across 71 maps

3. **Valoscribe validation_results Format**
   - What we know: metadata.json contains validation_results field
   - What's unclear: What Valoscribe's validation checks, what format validation_results uses
   - Recommendation: Discover format in Phase 5, use for cross-validation in quality scoring

4. **Series-Level Data Organization**
   - What we know: 71 Champions 2025 maps, likely multiple maps per series (BO3/BO5)
   - What's unclear: How maps are grouped into series, if Valoscribe preserves series structure
   - Recommendation: Out of scope for Phase 5 (per CONTEXT.md), defer to Phase 8

## Sources

### Primary (HIGH confidence)
- [Pydantic Settings Documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) - Environment variables, .env loading
- [Pydantic JSON Documentation](https://docs.pydantic.dev/latest/concepts/json/) - model_validate_json() method
- [Typer Commands Tutorial](https://typer.tiangolo.com/tutorial/commands/) - CLI structure, subcommands
- [Python pathlib Documentation](https://docs.python.org/3/library/pathlib.html) - File path operations
- [pandas read_csv Documentation](https://docs.kanaries.net/topics/Pandas/pandas-read-csv) - PyArrow engine, optimizations
- [structlog Documentation](https://www.structlog.org/) - Already verified in Phase 1 codebase
- Existing Phase 1 codebase (D:\git\Val-Prediciton-Model\src) - Pydantic patterns, structlog usage, pytest patterns

### Secondary (MEDIUM confidence)
- [Click vs Typer Comparison](https://typer.tiangolo.com/alternatives/) - Framework tradeoffs, when to use each
- [Data Pipeline Error Handling Patterns](https://medium.com/towards-data-engineering/error-handling-and-logging-in-data-pipelines-ensuring-data-reliability-227df82ba782) - Continue-on-failure pattern
- [Pydantic ValidationError Handling](https://docs.pydantic.dev/latest/errors/errors/) - Exception handling best practices
- [Python pathlib Best Practices (2026)](https://devtoolbox.dedyn.io/blog/python-pathlib-complete-guide) - Security, performance
- [Data Quality Metrics for ML](https://research.aimultiple.com/data-quality-ai/) - Quality scoring dimensions
- [JSONL Format Guide](https://jsonlines.org/) - Official JSON Lines specification
- [Rich Progress Display](https://rich.readthedocs.io/en/latest/progress.html) - Progress bar patterns

### Tertiary (LOW confidence - marked for validation)
- WebSearch results on data pipeline anti-patterns - Need to verify specific claims against official docs
- WebSearch results on markdown generation - Multiple libraries found, need to evaluate for this use case

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries have official documentation, most already in Phase 1 codebase
- Architecture patterns: HIGH - Patterns verified from official docs and existing codebase
- Pitfalls: MEDIUM - Based on research and general Python experience, not Valoscribe-specific

**Research date:** 2026-02-13
**Valid until:** ~60 days (stable domain, but Pydantic and pandas evolve quickly)

**Note:** Phase 5 is explicitly a data exploration exercise per CONTEXT.md. Cannot fully verify patterns until actual Valoscribe data is inspected. Research focused on establishing robust foundations to handle whatever the data format turns out to be.
