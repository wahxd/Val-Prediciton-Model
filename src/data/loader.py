"""Data loader for Valoscribe output files.

Discovers and loads Valoscribe map data (JSONL events, CSV frames, JSON metadata)
with continue-on-error resilience and comprehensive error collection.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import structlog
from pydantic import ValidationError

from src.data.schemas import MapMetadata, ValoscribeEvent, parse_event

logger = structlog.get_logger()


@dataclass
class MapData:
    """Loaded data for a single map."""

    map_id: str
    map_dir: Path
    events: list[ValoscribeEvent]
    frames: pd.DataFrame | None
    metadata: MapMetadata | None
    files_found: list[str]
    event_count: int
    parse_errors: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class LoadResult:
    """Result of loading a single map."""

    map_id: str
    success: bool
    data: MapData | None = None
    error: str | None = None
    error_phase: str | None = None  # "discovery", "events", "frames", "metadata"


def discover_maps(data_dir: Path) -> dict[str, Path]:
    """Discover all map directories in the Valoscribe data directory.

    Args:
        data_dir: Path to Valoscribe data directory

    Returns:
        Dict mapping map_id (directory name) to map directory path, sorted by map_id

    Raises:
        FileNotFoundError: If data_dir doesn't exist
    """
    if not data_dir.exists():
        raise FileNotFoundError(
            f"Valoscribe data directory not found: {data_dir}\n"
            f"Please ensure VALOSCRIBE_DATA_DIR is set correctly."
        )

    # Scan for subdirectories - each is a map
    map_dirs = {}
    for item in sorted(data_dir.iterdir()):
        if item.is_dir():
            map_id = item.name
            map_dirs[map_id] = item

    logger.info("discovered_maps", count=len(map_dirs), data_dir=str(data_dir))
    return map_dirs


def load_events(events_file: Path) -> tuple[list[ValoscribeEvent], list[dict]]:
    """Load and parse JSONL events file line-by-line.

    Args:
        events_file: Path to events.jsonl file

    Returns:
        Tuple of (parsed events list, parse errors list)
        Each error dict contains: {"line": int, "error": str, "raw": str (truncated)}
    """
    events = []
    parse_errors = []

    with events_file.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                event = parse_event(line)
                events.append(event)
            except (ValidationError, ValueError, Exception) as e:
                error_msg = str(e)
                # Truncate raw line to 200 chars for error reporting
                raw_truncated = line[:200] + "..." if len(line) > 200 else line
                parse_errors.append(
                    {"line": line_num, "error": error_msg, "raw": raw_truncated}
                )

    if parse_errors:
        logger.warning(
            "events_parse_errors",
            file=str(events_file),
            error_count=len(parse_errors),
            total_lines=line_num,
        )

    logger.debug(
        "loaded_events",
        file=str(events_file),
        event_count=len(events),
        error_count=len(parse_errors),
    )

    return events, parse_errors


def load_frames(frames_file: Path) -> pd.DataFrame:
    """Load CSV frames file.

    Args:
        frames_file: Path to frames.csv file

    Returns:
        DataFrame with frame data
    """
    # Try PyArrow engine for performance, fall back to default if not available
    try:
        df = pd.read_csv(frames_file, engine="pyarrow")
    except Exception:
        # PyArrow not available or incompatible, use default
        df = pd.read_csv(frames_file)

    logger.debug("loaded_frames", file=str(frames_file), rows=len(df))
    return df


def load_metadata(metadata_file: Path) -> MapMetadata:
    """Load and parse JSON metadata file.

    Args:
        metadata_file: Path to metadata.json file

    Returns:
        Parsed MapMetadata object
    """
    import json

    with metadata_file.open("r", encoding="utf-8") as f:
        raw_data = json.load(f)

    metadata = MapMetadata.model_validate(raw_data)
    logger.debug("loaded_metadata", file=str(metadata_file))
    return metadata


def load_map(map_dir: Path) -> MapData:
    """Load all data for a single map.

    Args:
        map_dir: Path to map directory

    Returns:
        MapData with all loaded files

    Raises:
        ValueError: If events.jsonl is missing (required file)
        Various exceptions from file loading errors
    """
    map_id = map_dir.name
    files_found = []

    # Check which files exist
    events_file = map_dir / "events.jsonl"
    frames_file = map_dir / "frames.csv"
    metadata_file = map_dir / "metadata.json"

    # events.jsonl is required
    if not events_file.exists():
        raise ValueError(
            f"Required file missing: {events_file}\n"
            f"events.jsonl is required for map {map_id}"
        )

    # Load events (required)
    events, parse_errors = load_events(events_file)
    files_found.append("events.jsonl")

    # Load frames (optional)
    frames = None
    if frames_file.exists():
        frames = load_frames(frames_file)
        files_found.append("frames.csv")

    # Load metadata (optional)
    metadata = None
    if metadata_file.exists():
        metadata = load_metadata(metadata_file)
        files_found.append("metadata.json")

    map_data = MapData(
        map_id=map_id,
        map_dir=map_dir,
        events=events,
        frames=frames,
        metadata=metadata,
        files_found=files_found,
        event_count=len(events),
        parse_errors=parse_errors,
    )

    logger.info(
        "loaded_map",
        map_id=map_id,
        event_count=len(events),
        files_found=files_found,
        parse_errors=len(parse_errors),
    )

    return map_data


def load_all_maps(
    data_dir: Path, map_ids: list[str] | None = None
) -> dict[str, LoadResult]:
    """Load all maps with continue-on-error.

    Args:
        data_dir: Path to Valoscribe data directory
        map_ids: Optional list of specific map IDs to load (default: all)

    Returns:
        Dict mapping map_id to LoadResult (includes both successes and failures)
    """
    # Discover all maps
    all_map_dirs = discover_maps(data_dir)

    # Filter if specific map_ids requested
    if map_ids is not None:
        map_dirs = {
            map_id: map_dir
            for map_id, map_dir in all_map_dirs.items()
            if map_id in map_ids
        }
    else:
        map_dirs = all_map_dirs

    total = len(map_dirs)
    results = {}

    logger.info("loading_maps", total=total)

    # Load each map with continue-on-error
    for i, (map_id, map_dir) in enumerate(map_dirs.items(), start=1):
        logger.info("loading_map_progress", index=i, total=total, map_id=map_id)

        try:
            map_data = load_map(map_dir)
            results[map_id] = LoadResult(map_id=map_id, success=True, data=map_data)
        except Exception as e:
            error_msg = str(e)
            error_phase = _determine_error_phase(e, map_dir)

            results[map_id] = LoadResult(
                map_id=map_id,
                success=False,
                error=error_msg,
                error_phase=error_phase,
            )

            logger.warning(
                "map_load_failed",
                map_id=map_id,
                error=error_msg,
                error_phase=error_phase,
            )

    # Summary
    success_count = sum(1 for r in results.values() if r.success)
    failure_count = total - success_count

    logger.info(
        "load_summary",
        total=total,
        success=success_count,
        failures=failure_count,
    )

    return results


def get_map_index(results: dict[str, LoadResult]) -> list[dict[str, Any]]:
    """Extract summary index from load results.

    Args:
        results: Dict of map_id to LoadResult

    Returns:
        List of summary dicts for successful loads, sorted by map_id
        Each dict contains: map_id, teams, map_name, date, event_count, files_found
    """
    index = []

    for map_id in sorted(results.keys()):
        result = results[map_id]

        if not result.success or result.data is None:
            continue

        data = result.data

        # Extract metadata fields, use "unknown" for missing
        teams = data.metadata.teams if data.metadata else ["unknown", "unknown"]
        map_name = data.metadata.map_name if data.metadata else "unknown"
        date = data.metadata.date if data.metadata else "unknown"

        index.append(
            {
                "map_id": map_id,
                "teams": teams,
                "map_name": map_name,
                "date": date,
                "event_count": data.event_count,
                "files_found": data.files_found,
            }
        )

    return index


def _determine_error_phase(error: Exception, map_dir: Path) -> str:
    """Determine which phase of loading failed based on error type and context."""
    error_msg = str(error).lower()

    if "events.jsonl" in error_msg or "required file missing" in error_msg:
        return "events"
    elif "frames.csv" in error_msg:
        return "frames"
    elif "metadata.json" in error_msg:
        return "metadata"
    elif not map_dir.exists():
        return "discovery"
    else:
        # Default to events phase if unclear
        return "events"
