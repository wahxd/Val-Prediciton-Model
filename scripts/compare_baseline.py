#!/usr/bin/env python3
"""Compare baseline and modified Valoscribe output.

Compares event counts and quality between baseline (pre-Phase-6) and modified
(post-Phase-6) Valoscribe output to identify:
- Regressions (valid events disappeared)
- Improvements (duplicate events removed, new features added)

Usage:
    python scripts/compare_baseline.py <baseline_dir> <modified_dir> [--output <json_path>]

Example:
    python scripts/compare_baseline.py D:/Git/valoscribe-baseline D:/Git/valoscribe/champs2025_processed_vods
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def find_events_file(map_dir: Path) -> Path | None:
    """Find events file in map directory (handles old and new naming).

    Args:
        map_dir: Path to map directory

    Returns:
        Path to events file, or None if not found
    """
    # New format: events.jsonl in map directory
    new_format = map_dir / "events.jsonl"
    if new_format.exists():
        return new_format

    # Old format: output/event_log.jsonl
    old_format = map_dir / "output" / "event_log.jsonl"
    if old_format.exists():
        return old_format

    return None


def load_events(events_file: Path) -> list[dict[str, Any]]:
    """Load events from JSONL file.

    Args:
        events_file: Path to events.jsonl or event_log.jsonl

    Returns:
        List of event dicts
    """
    events = []
    with events_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse line in {events_file}: {e}", file=sys.stderr)
                continue
    return events


def analyze_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Analyze events for comparison metrics.

    Args:
        events: List of event dicts

    Returns:
        Analysis dict with counts and quality metrics
    """
    # Count by type
    type_counts = Counter(e.get("type") for e in events)

    # Count new Phase 6 event types
    new_types = {
        "buy_phase": type_counts.get("buy_phase", 0),
        "ult_usage": type_counts.get("ult_usage", 0),
        "timeout": type_counts.get("timeout", 0),
    }

    # Check round events for sides field
    round_events = [e for e in events if e.get("type") in ("round_start", "round_end")]
    round_events_with_sides = sum(1 for e in round_events if "attacker" in e and "defender" in e)

    return {
        "total_events": len(events),
        "event_types": dict(type_counts),
        "new_phase6_types": new_types,
        "round_events_with_sides": round_events_with_sides,
        "total_round_events": len(round_events),
    }


def find_map_pairs(baseline_dir: Path, modified_dir: Path) -> list[tuple[str, Path, Path]]:
    """Find map directories present in both baseline and modified.

    Args:
        baseline_dir: Path to baseline data directory
        modified_dir: Path to modified data directory

    Returns:
        List of (map_id, baseline_map_path, modified_map_path) tuples
    """
    pairs = []

    # Walk baseline series directories
    for baseline_series in sorted(baseline_dir.iterdir()):
        if not baseline_series.is_dir():
            continue

        modified_series = modified_dir / baseline_series.name
        if not modified_series.exists() or not modified_series.is_dir():
            continue

        # Walk map directories
        for baseline_map in sorted(baseline_series.iterdir()):
            if not baseline_map.is_dir():
                continue

            # Skip metadata directories
            if baseline_map.name in ("metadata", "series_metadata"):
                continue

            modified_map = modified_series / baseline_map.name
            if not modified_map.exists() or not modified_map.is_dir():
                continue

            # Check if both have events files
            baseline_events = find_events_file(baseline_map)
            modified_events = find_events_file(modified_map)

            if baseline_events and modified_events:
                map_id = f"{baseline_series.name}/{baseline_map.name}"
                pairs.append((map_id, baseline_map, modified_map))

    return pairs


def compare_maps(baseline_map: Path, modified_map: Path) -> dict[str, Any]:
    """Compare baseline and modified events for a single map.

    Args:
        baseline_map: Path to baseline map directory
        modified_map: Path to modified map directory

    Returns:
        Comparison dict with deltas and flags
    """
    baseline_file = find_events_file(baseline_map)
    modified_file = find_events_file(modified_map)

    baseline_events = load_events(baseline_file)
    modified_events = load_events(modified_file)

    baseline_analysis = analyze_events(baseline_events)
    modified_analysis = analyze_events(modified_events)

    # Calculate deltas
    total_delta = modified_analysis["total_events"] - baseline_analysis["total_events"]
    total_delta_pct = round(100 * total_delta / baseline_analysis["total_events"], 1) if baseline_analysis["total_events"] > 0 else 0

    # Per-type deltas for significant types
    type_deltas = {}
    all_types = set(baseline_analysis["event_types"].keys()) | set(modified_analysis["event_types"].keys())
    for event_type in all_types:
        baseline_count = baseline_analysis["event_types"].get(event_type, 0)
        modified_count = modified_analysis["event_types"].get(event_type, 0)
        delta = modified_count - baseline_count
        if delta != 0:  # Only include changed types
            type_deltas[event_type] = {
                "baseline": baseline_count,
                "modified": modified_count,
                "delta": delta,
            }

    # Flag regressions and improvements
    regression = False
    regression_reasons = []

    # Regression: Significant loss of core events (kills, round events)
    core_event_types = ["kill", "round_start", "round_end"]
    for event_type in core_event_types:
        baseline_count = baseline_analysis["event_types"].get(event_type, 0)
        modified_count = modified_analysis["event_types"].get(event_type, 0)
        if baseline_count > 0 and modified_count < baseline_count * 0.9:  # >10% loss
            regression = True
            regression_reasons.append(f"{event_type}: {baseline_count} → {modified_count} (-{baseline_count - modified_count})")

    # Improvements
    improvements = []

    # Improvement: New Phase 6 features added
    for feature, count in modified_analysis["new_phase6_types"].items():
        if count > 0 and baseline_analysis["new_phase6_types"].get(feature, 0) == 0:
            improvements.append(f"Added {feature} events ({count})")

    # Improvement: Sides tracking added
    if modified_analysis["round_events_with_sides"] > baseline_analysis["round_events_with_sides"]:
        improvements.append(
            f"Sides tracking: {baseline_analysis['round_events_with_sides']} → {modified_analysis['round_events_with_sides']}"
        )

    # Improvement: Overall event count reduction (likely replay removal)
    if total_delta < 0:
        improvements.append(f"Event count reduced by {abs(total_delta)} ({total_delta_pct}%, likely replay removal)")

    return {
        "baseline": baseline_analysis,
        "modified": modified_analysis,
        "total_delta": total_delta,
        "total_delta_pct": total_delta_pct,
        "type_deltas": type_deltas,
        "regression": regression,
        "regression_reasons": regression_reasons,
        "improvements": improvements,
    }


def aggregate_comparison(comparisons: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Aggregate comparison metrics across all maps.

    Args:
        comparisons: Dict of map_id to comparison results

    Returns:
        Aggregated metrics dict
    """
    total_maps = len(comparisons)
    regressions = sum(1 for c in comparisons.values() if c["regression"])
    improvements = sum(1 for c in comparisons.values() if c["improvements"])

    # Aggregate deltas
    total_baseline_events = sum(c["baseline"]["total_events"] for c in comparisons.values())
    total_modified_events = sum(c["modified"]["total_events"] for c in comparisons.values())
    total_delta = total_modified_events - total_baseline_events
    total_delta_pct = round(100 * total_delta / total_baseline_events, 1) if total_baseline_events > 0 else 0

    # Count new features
    maps_with_buy_phase = sum(1 for c in comparisons.values() if c["modified"]["new_phase6_types"]["buy_phase"] > 0)
    maps_with_ult_usage = sum(1 for c in comparisons.values() if c["modified"]["new_phase6_types"]["ult_usage"] > 0)
    maps_with_timeout = sum(1 for c in comparisons.values() if c["modified"]["new_phase6_types"]["timeout"] > 0)
    maps_with_sides = sum(1 for c in comparisons.values() if c["modified"]["round_events_with_sides"] > 0)

    # Aggregate type deltas
    aggregate_type_deltas = Counter()
    for c in comparisons.values():
        for event_type, delta_info in c["type_deltas"].items():
            aggregate_type_deltas[event_type] += delta_info["delta"]

    return {
        "total_maps_compared": total_maps,
        "regressions": regressions,
        "improvements": improvements,
        "total_event_delta": {
            "baseline_total": total_baseline_events,
            "modified_total": total_modified_events,
            "delta": total_delta,
            "delta_pct": total_delta_pct,
        },
        "new_features": {
            "buy_phase": {
                "maps": maps_with_buy_phase,
                "coverage_pct": round(100 * maps_with_buy_phase / total_maps, 1) if total_maps > 0 else 0,
            },
            "ult_usage": {
                "maps": maps_with_ult_usage,
                "coverage_pct": round(100 * maps_with_ult_usage / total_maps, 1) if total_maps > 0 else 0,
            },
            "timeout": {
                "maps": maps_with_timeout,
                "coverage_pct": round(100 * maps_with_timeout / total_maps, 1) if total_maps > 0 else 0,
            },
            "sides_tracking": {
                "maps": maps_with_sides,
                "coverage_pct": round(100 * maps_with_sides / total_maps, 1) if total_maps > 0 else 0,
            },
        },
        "aggregate_type_deltas": dict(aggregate_type_deltas.most_common()),
    }


def print_summary(aggregate: dict[str, Any], comparisons: dict[str, dict[str, Any]]) -> None:
    """Print console summary of comparison results.

    Args:
        aggregate: Aggregated metrics
        comparisons: Per-map comparisons
    """
    print("=" * 70)
    print("Baseline vs Modified Comparison Summary")
    print("=" * 70)
    print()

    print(f"Total maps compared: {aggregate['total_maps_compared']}")
    print(f"Maps with regressions: {aggregate['regressions']}")
    print(f"Maps with improvements: {aggregate['improvements']}")
    print()

    print("Overall Event Count:")
    print("-" * 70)
    delta = aggregate["total_event_delta"]
    print(f"  Baseline: {delta['baseline_total']:,}")
    print(f"  Modified: {delta['modified_total']:,}")
    print(f"  Delta: {delta['delta']:+,} ({delta['delta_pct']:+.1f}%)")
    print()

    print("New Phase 6 Features:")
    print("-" * 70)
    for feature, data in aggregate["new_features"].items():
        print(f"  {feature}: {data['maps']}/{aggregate['total_maps_compared']} maps ({data['coverage_pct']}%)")
    print()

    print("Top Event Type Changes:")
    print("-" * 70)
    for event_type, delta in list(aggregate["aggregate_type_deltas"].items())[:10]:
        sign = "+" if delta > 0 else ""
        print(f"  {event_type}: {sign}{delta:,}")
    print()

    # Show regressions
    regression_maps = [
        (map_id, c) for map_id, c in comparisons.items() if c["regression"]
    ]
    if regression_maps:
        print("Maps with Regressions:")
        print("-" * 70)
        for map_id, c in regression_maps[:5]:  # Show first 5
            print(f"  {map_id}:")
            for reason in c["regression_reasons"]:
                print(f"    - {reason}")
        if len(regression_maps) > 5:
            print(f"  ... and {len(regression_maps) - 5} more")
        print()

    # Show notable improvements
    improvement_maps = [
        (map_id, c) for map_id, c in comparisons.items()
        if c["improvements"] and not c["regression"]
    ]
    if improvement_maps:
        print("Sample Improvements (first 5 maps):")
        print("-" * 70)
        for map_id, c in improvement_maps[:5]:
            print(f"  {map_id}:")
            for improvement in c["improvements"][:3]:  # First 3 improvements
                print(f"    - {improvement}")
        print()

    print("=" * 70)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Compare baseline and modified Valoscribe output")
    parser.add_argument(
        "baseline_dir",
        type=Path,
        help="Path to baseline data directory",
    )
    parser.add_argument(
        "modified_dir",
        type=Path,
        help="Path to modified data directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output JSON report path (optional)",
    )

    args = parser.parse_args()

    if not args.baseline_dir.exists():
        print(f"Error: Baseline directory not found: {args.baseline_dir}", file=sys.stderr)
        sys.exit(1)

    if not args.modified_dir.exists():
        print(f"Error: Modified directory not found: {args.modified_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Finding map pairs...")
    pairs = find_map_pairs(args.baseline_dir, args.modified_dir)
    print(f"Found {len(pairs)} maps present in both directories")
    print()

    print(f"Comparing maps...")
    comparisons = {}
    for i, (map_id, baseline_map, modified_map) in enumerate(pairs, start=1):
        if i % 10 == 0:
            print(f"  Progress: {i}/{len(pairs)}")
        comparisons[map_id] = compare_maps(baseline_map, modified_map)

    print(f"Aggregating results...")
    aggregate = aggregate_comparison(comparisons)

    # Print summary
    print()
    print_summary(aggregate, comparisons)

    # Write JSON report
    if args.output:
        report = {
            "aggregate": aggregate,
            "per_map": comparisons,
        }
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"JSON report written to: {args.output}")


if __name__ == "__main__":
    main()
