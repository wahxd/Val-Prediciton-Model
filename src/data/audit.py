"""Audit report generator for Valoscribe data quality assessment.

Generates dual-format reports (JSON + Markdown) documenting data quality,
usability, and issues for all processed maps.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from src.data.catalog import DataCatalog
from src.data.loader import LoadResult, get_map_index
from src.data.quality import QualityScore, score_map_quality

logger = structlog.get_logger()


@dataclass
class AuditResult:
    """Complete audit results for all maps."""

    timestamp: str
    total_maps: int
    maps_loaded: int
    maps_failed: int
    quality_scores: dict[str, QualityScore]
    load_failures: dict[str, str]  # map_id -> error message
    catalog: DataCatalog
    map_index: list[dict[str, Any]]
    tier_summary: dict[str, int] = field(
        default_factory=lambda: {"high": 0, "medium": 0, "low": 0}
    )


def run_audit(load_results: dict[str, LoadResult]) -> AuditResult:
    """Run complete audit on loaded map data.

    Args:
        load_results: Dict of map_id -> LoadResult from loader

    Returns:
        AuditResult with all quality scores and catalog
    """
    timestamp = datetime.utcnow().isoformat() + "Z"
    total_maps = len(load_results)
    maps_loaded = sum(1 for r in load_results.values() if r.success)
    maps_failed = total_maps - maps_loaded

    quality_scores = {}
    load_failures = {}
    catalog = DataCatalog()
    tier_summary = {"high": 0, "medium": 0, "low": 0}

    logger.info("running_audit", total_maps=total_maps)

    # Process successful loads
    for map_id, result in load_results.items():
        if result.success and result.data:
            # Score quality
            quality = score_map_quality(
                events=result.data.events,
                metadata=result.data.metadata,
                map_id=map_id,
            )
            quality_scores[map_id] = quality
            tier_summary[quality.tier] += 1

            # Add to catalog
            catalog.add_map_events(result.data.events)

            logger.debug(
                "map_audited",
                map_id=map_id,
                score=quality.overall_score,
                tier=quality.tier,
            )
        else:
            # Record failure
            load_failures[map_id] = result.error or "Unknown error"

    # Get map index
    map_index = get_map_index(load_results)

    logger.info(
        "audit_complete",
        maps_loaded=maps_loaded,
        maps_failed=maps_failed,
        tier_summary=tier_summary,
    )

    return AuditResult(
        timestamp=timestamp,
        total_maps=total_maps,
        maps_loaded=maps_loaded,
        maps_failed=maps_failed,
        quality_scores=quality_scores,
        load_failures=load_failures,
        catalog=catalog,
        map_index=map_index,
        tier_summary=tier_summary,
    )


def generate_json_report(audit: AuditResult, output_path: Path) -> Path:
    """Generate JSON audit report.

    Args:
        audit: AuditResult to serialize
        output_path: Directory to write report

    Returns:
        Path to generated JSON file
    """
    import json

    output_path.mkdir(parents=True, exist_ok=True)

    # Generate timestamp-based filename
    timestamp_clean = audit.timestamp.replace(":", "-").replace(".", "-")
    filename = f"audit_{timestamp_clean}.json"
    file_path = output_path / filename

    # Build JSON structure
    report = {
        "timestamp": audit.timestamp,
        "summary": {
            "total_maps": audit.total_maps,
            "maps_loaded": audit.maps_loaded,
            "maps_failed": audit.maps_failed,
            "tier_summary": audit.tier_summary,
        },
        "map_index": audit.map_index,
        "quality_scores": {
            map_id: {
                "overall_score": score.overall_score,
                "tier": score.tier,
                "flagged_for_review": score.flagged_for_review,
                "checks": [
                    {
                        "name": check.name,
                        "score": check.score,
                        "weight": check.weight,
                        "issues": check.issues,
                        "warnings": check.warnings,
                        "details": check.details,
                    }
                    for check in score.checks
                ],
                "valoscribe_validation": score.valoscribe_validation,
                "cross_check_disagreements": score.cross_check_disagreements,
                "all_issues": score.all_issues,
                "all_warnings": score.all_warnings,
            }
            for map_id, score in sorted(audit.quality_scores.items())
        },
        "load_failures": audit.load_failures,
        "catalog": audit.catalog.to_dict(),
    }

    # Write to file
    with file_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    logger.info("json_report_generated", path=str(file_path))
    return file_path


def generate_markdown_report(audit: AuditResult, output_path: Path) -> Path:
    """Generate Markdown audit report.

    Args:
        audit: AuditResult to document
        output_path: Directory to write report

    Returns:
        Path to generated Markdown file
    """
    output_path.mkdir(parents=True, exist_ok=True)

    # Generate timestamp-based filename
    timestamp_clean = audit.timestamp.replace(":", "-").replace(".", "-")
    filename = f"audit_{timestamp_clean}.md"
    file_path = output_path / filename

    # Build Markdown content
    lines = []

    # Header
    lines.extend(
        [
            f"# Valoscribe Data Quality Audit Report",
            f"",
            f"**Generated:** {audit.timestamp}",
            f"",
            f"---",
            f"",
        ]
    )

    # Executive Summary
    total_usable = audit.tier_summary["high"] + audit.tier_summary["medium"]
    usable_pct = (
        (total_usable / audit.maps_loaded * 100) if audit.maps_loaded > 0 else 0
    )

    lines.extend(
        [
            f"## Executive Summary",
            f"",
            f"**Total Maps Discovered:** {audit.total_maps}",
            f"**Successfully Loaded:** {audit.maps_loaded}",
            f"**Load Failures:** {audit.maps_failed}",
            f"",
            f"**Quality Tier Distribution:**",
            f"- **High Quality:** {audit.tier_summary['high']} maps ({audit.tier_summary['high'] / max(1, audit.maps_loaded) * 100:.1f}%)",
            f"- **Medium Quality:** {audit.tier_summary['medium']} maps ({audit.tier_summary['medium'] / max(1, audit.maps_loaded) * 100:.1f}%)",
            f"- **Low Quality:** {audit.tier_summary['low']} maps ({audit.tier_summary['low'] / max(1, audit.maps_loaded) * 100:.1f}%)",
            f"",
            f"**Dataset Readiness:** {total_usable} usable maps ({usable_pct:.1f}% of loaded)",
            f"",
            f"---",
            f"",
        ]
    )

    # Data Catalog Summary
    lines.extend(
        [
            f"## Data Catalog Summary",
            f"",
            f"Event types discovered across {audit.catalog.total_maps} maps:",
            f"",
            f"| Event Type | Count | Fields |",
            f"|------------|-------|--------|",
        ]
    )

    for event_type, entry in sorted(audit.catalog.entries.items()):
        lines.append(
            f"| {event_type} | {entry.count:,} | {len(entry.fields)} |"
        )

    lines.extend([f"", f"**Total Events:** {audit.catalog.total_events:,}", f"", f"---", f""])

    # Summary Table
    lines.extend(
        [
            f"## Summary Table",
            f"",
            f"All maps sorted by quality score (highest first):",
            f"",
            f"| Map ID | Teams | Map | Tier | Score | Events | Kills | Rounds | Issues | Final Score |",
            f"|--------|-------|-----|------|-------|--------|-------|--------|--------|-------------|",
        ]
    )

    # Combine index with quality scores and sort by score descending
    for map_id in sorted(
        audit.quality_scores.keys(),
        key=lambda mid: audit.quality_scores[mid].overall_score,
        reverse=True,
    ):
        score = audit.quality_scores[map_id]

        # Find matching map_index entry
        index_entry = next(
            (entry for entry in audit.map_index if entry["map_id"] == map_id), None
        )

        if index_entry:
            teams_str = " vs ".join(index_entry["teams"])
            map_name = index_entry["map_name"]
            event_count = index_entry["event_count"]
        else:
            teams_str = "unknown"
            map_name = "unknown"
            event_count = 0

        # Calculate kill count and round count from quality checks
        kill_count = 0
        round_count = 0
        final_score = "N/A"

        for check in score.checks:
            if check.name == "kill_count":
                kill_count = check.details.get("kill_count", 0)
            elif check.name == "round_progression":
                round_count = check.details.get("total_rounds", 0)

        # Get final score from map metadata if available (need to lookup)
        # For now, leave as N/A since we don't have easy access to round_end events

        issue_count = len(score.all_issues)
        issue_flag = "⚠️" if issue_count > 0 else "✓"

        lines.append(
            f"| {map_id} | {teams_str} | {map_name} | {score.tier} | {score.overall_score:.2f} | {event_count} | {kill_count} | {round_count} | {issue_flag} {issue_count} | {final_score} |"
        )

    lines.extend([f"", f"---", f""])

    # Load Failures Section
    if audit.load_failures:
        lines.extend(
            [
                f"## Load Failures",
                f"",
                f"Maps that failed to load:",
                f"",
                f"| Map ID | Error |",
                f"|--------|-------|",
            ]
        )

        for map_id, error in sorted(audit.load_failures.items()):
            # Truncate error message to fit table
            error_short = (
                error[:80] + "..." if len(error) > 80 else error
            )
            lines.append(f"| {map_id} | {error_short} |")

        lines.extend([f"", f"---", f""])

    # Cross-Check Disagreements
    disagreements = [
        (map_id, score)
        for map_id, score in audit.quality_scores.items()
        if score.cross_check_disagreements
    ]

    if disagreements:
        lines.extend(
            [
                f"## Cross-Check Disagreements",
                f"",
                f"Maps where our quality assessment disagrees with Valoscribe's validation:",
                f"",
            ]
        )

        for map_id, score in disagreements:
            lines.extend(
                [
                    f"**{map_id}:** (score: {score.overall_score:.2f}, tier: {score.tier})",
                ]
            )
            for disagreement in score.cross_check_disagreements:
                lines.append(f"  - {disagreement}")
            lines.append(f"")

        lines.extend([f"---", f""])

    # Table of Contents for Per-Map Details
    lines.extend(
        [
            f"## Per-Map Details",
            f"",
            f"**Table of Contents:**",
            f"",
        ]
    )

    for map_id in sorted(audit.quality_scores.keys()):
        lines.append(f"- [{map_id}](#{map_id})")

    lines.extend([f"", f"---", f""])

    # Per-Map Details
    for map_id in sorted(audit.quality_scores.keys()):
        score = audit.quality_scores[map_id]

        lines.extend(
            [
                f"### {map_id}",
                f"",
                f"**Overall Score:** {score.overall_score:.2f} / 1.00",
                f"**Tier:** {score.tier}",
                f"**Flagged for Review:** {'Yes' if score.flagged_for_review else 'No'}",
                f"",
            ]
        )

        # Component scores table
        lines.extend(
            [
                f"**Component Scores:**",
                f"",
                f"| Check | Score | Weight | Issues | Warnings |",
                f"|-------|-------|--------|--------|----------|",
            ]
        )

        for check in score.checks:
            lines.append(
                f"| {check.name} | {check.score:.2f} | {check.weight:.2f} | {len(check.issues)} | {len(check.warnings)} |"
            )

        lines.append(f"")

        # Issues
        if score.all_issues:
            lines.extend([f"**Issues:**", f""])
            for issue in score.all_issues:
                lines.append(f"- {issue}")
            lines.append(f"")

        # Warnings
        if score.all_warnings:
            lines.extend([f"**Warnings:**", f""])
            for warning in score.all_warnings:
                lines.append(f"- {warning}")
            lines.append(f"")

        # Round-by-round breakdown
        lines.extend(
            [
                f"**Round-by-Round Breakdown:**",
                f"",
            ]
        )

        # Extract round-level detail from quality checks
        for check in score.checks:
            if check.name == "event_completeness" and check.details.get(
                "incomplete_rounds"
            ):
                incomplete = check.details["incomplete_rounds"]
                lines.append(
                    f"- Incomplete rounds (missing expected events): {incomplete}"
                )

            if check.name == "timing_consistency":
                short_rounds = check.details.get("short_rounds", [])
                long_gaps = check.details.get("long_gaps", [])
                if short_rounds:
                    lines.append(f"- Suspiciously short rounds: {short_rounds}")
                if long_gaps:
                    lines.append(f"- Long gaps after rounds: {long_gaps}")

        lines.extend([f"", f"---", f""])

    # Write to file
    with file_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info("markdown_report_generated", path=str(file_path))
    return file_path


def generate_audit(
    load_results: dict[str, LoadResult], output_dir: Path
) -> tuple[Path, Path]:
    """Run audit and generate both JSON and Markdown reports.

    Convenience function combining run_audit + both report generators.

    Args:
        load_results: Dict of map_id -> LoadResult from loader
        output_dir: Directory to write reports

    Returns:
        Tuple of (json_path, markdown_path)
    """
    logger.info("generating_audit_reports", output_dir=str(output_dir))

    # Run audit
    audit_result = run_audit(load_results)

    # Generate both reports
    json_path = generate_json_report(audit_result, output_dir)
    md_path = generate_markdown_report(audit_result, output_dir)

    logger.info(
        "audit_reports_complete",
        json=str(json_path),
        markdown=str(md_path),
    )

    return json_path, md_path
