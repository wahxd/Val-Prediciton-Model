"""Quality scoring for Valoscribe map data.

Per-map quality assessment with multiple signals:
- Kill count vs expected
- Round progression consistency
- Round start/end balance
- Event completeness per round
- Timing consistency

Maps are tiered (high/medium/low) and flagged for review, NOT auto-excluded.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from src.data.schemas import ValoscribeEvent, MapMetadata


@dataclass
class QualityCheck:
    """Result from a single quality check signal."""

    name: str  # e.g., "kill_count", "round_progression"
    score: float  # 0.0-1.0
    weight: float  # contribution to overall score
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityScore:
    """Complete quality assessment for a single map."""

    map_id: str
    overall_score: float  # 0.0-1.0, weighted average
    tier: Literal["high", "medium", "low"]
    checks: list[QualityCheck]
    valoscribe_validation: dict[str, Any] | None
    cross_check_disagreements: list[str]
    all_issues: list[str]
    all_warnings: list[str]
    flagged_for_review: bool


def check_kill_count(events: list[ValoscribeEvent], metadata: MapMetadata | None = None) -> QualityCheck:
    """Check kill count against expected range for a standard map.

    Standard Valorant map: ~150-300 kills (13-24 rounds, ~10-15 kills/round).
    Score scales from 0.0 at 0 kills to 1.0 at 100+ kills.
    """
    kill_events = [e for e in events if e.type == "kill"]
    kill_count = len(kill_events)

    # Score: 1.0 if >= 100 kills, linear scale below that
    score = min(1.0, kill_count / 100.0) if kill_count > 0 else 0.0

    issues = []
    warnings = []

    if kill_count < 50:
        issues.append(f"Critically low kill count: {kill_count} (expected ~150-300)")
    elif kill_count < 100:
        warnings.append(f"Below expected kill count: {kill_count} (expected ~150-300)")

    return QualityCheck(
        name="kill_count",
        score=score,
        weight=0.25,
        issues=issues,
        warnings=warnings,
        details={
            "kill_count": kill_count,
            "expected_min": 100,
            "expected_max": 300,
        },
    )


def check_round_progression(events: list[ValoscribeEvent]) -> QualityCheck:
    """Check that round numbers are sequential and complete.

    Round numbers should be 1, 2, 3, ..., N with no gaps.
    Each round should have both round_start and round_end events.
    """
    round_starts = [e for e in events if e.type == "round_start"]
    round_ends = [e for e in events if e.type == "round_end"]

    start_rounds = sorted([e.round for e in round_starts])
    end_rounds = sorted([e.round for e in round_ends])

    all_rounds = sorted(set(start_rounds + end_rounds))

    issues = []
    warnings = []
    missing_starts = []
    missing_ends = []
    gaps = []

    # Check for sequential progression
    if all_rounds:
        expected = list(range(1, max(all_rounds) + 1))
        if all_rounds != expected:
            gaps = [r for r in expected if r not in all_rounds]
            issues.append(f"Non-sequential rounds detected: missing {gaps}")

        # Check for missing starts/ends
        for rnd in all_rounds:
            if rnd not in start_rounds:
                missing_starts.append(rnd)
            if rnd not in end_rounds:
                missing_ends.append(rnd)

        if missing_starts:
            issues.append(f"Missing round_start events for rounds: {missing_starts}")
        if missing_ends:
            issues.append(f"Missing round_end events for rounds: {missing_ends}")

    # Score: 1.0 if perfect, deduct proportionally for issues
    total_rounds = len(all_rounds) if all_rounds else 1
    issues_count = len(gaps) + len(missing_starts) + len(missing_ends)
    score = max(0.0, 1.0 - (issues_count / total_rounds))

    return QualityCheck(
        name="round_progression",
        score=score,
        weight=0.25,
        issues=issues,
        warnings=warnings,
        details={
            "total_rounds": len(all_rounds),
            "missing_starts": missing_starts,
            "missing_ends": missing_ends,
            "gaps": gaps,
        },
    )


def check_round_start_end_balance(events: list[ValoscribeEvent]) -> QualityCheck:
    """Check that round_start and round_end counts are balanced.

    Should be equal, or round_start = round_end + 1 if last round incomplete.
    """
    start_count = sum(1 for e in events if e.type == "round_start")
    end_count = sum(1 for e in events if e.type == "round_end")

    difference = abs(start_count - end_count)
    issues = []
    warnings = []

    # Score based on balance
    if difference == 0:
        score = 1.0
    elif difference == 1:
        score = 0.8
        warnings.append(f"Round start/end off by 1: {start_count} starts vs {end_count} ends (likely incomplete last round)")
    else:
        score = max(0.0, 0.5 - (difference - 2) * 0.1)
        issues.append(f"Round start/end imbalance: {start_count} starts vs {end_count} ends (difference: {difference})")

    return QualityCheck(
        name="round_start_end_balance",
        score=score,
        weight=0.15,
        issues=issues,
        warnings=warnings,
        details={
            "round_starts": start_count,
            "round_ends": end_count,
            "difference": difference,
        },
    )


def check_event_completeness(events: list[ValoscribeEvent]) -> QualityCheck:
    """Check that each round has expected event types.

    Each round should have: round_start, round_end, and at least one kill.
    """
    # Group events by round
    rounds: dict[int, list[ValoscribeEvent]] = {}
    for event in events:
        if event.round not in rounds:
            rounds[event.round] = []
        rounds[event.round].append(event)

    issues = []
    warnings = []
    incomplete_rounds = []

    complete_count = 0
    for rnd, round_events in sorted(rounds.items()):
        event_types = {e.type for e in round_events}

        has_start = "round_start" in event_types
        has_end = "round_end" in event_types
        has_kills = "kill" in event_types

        if has_start and has_end and has_kills:
            complete_count += 1
        else:
            incomplete_rounds.append(rnd)
            if not has_kills:
                warnings.append(f"Round {rnd} has no kill events -- possible OCR gap")

    total_rounds = len(rounds) if rounds else 1
    score = complete_count / total_rounds

    if incomplete_rounds:
        issues.append(f"Incomplete rounds (missing expected events): {incomplete_rounds}")

    return QualityCheck(
        name="event_completeness",
        score=score,
        weight=0.20,
        issues=issues,
        warnings=warnings,
        details={
            "rounds_checked": total_rounds,
            "complete_rounds": complete_count,
            "incomplete_rounds": incomplete_rounds,
        },
    )


def check_timing_consistency(events: list[ValoscribeEvent]) -> QualityCheck:
    """Check timestamp consistency and round timing reasonableness.

    Timestamps should be monotonically non-decreasing within rounds.
    Time between consecutive round_start events should be 30-300 seconds.
    """
    issues = []
    warnings = []
    timestamp_regressions = 0
    short_rounds = []
    long_gaps = []

    # Group by round and check timestamp ordering
    rounds: dict[int, list[ValoscribeEvent]] = {}
    for event in events:
        if event.round not in rounds:
            rounds[event.round] = []
        rounds[event.round].append(event)

    # Check within-round timestamp consistency
    for rnd, round_events in rounds.items():
        sorted_events = sorted(round_events, key=lambda e: e.timestamp)
        for i in range(len(sorted_events) - 1):
            if sorted_events[i + 1].timestamp < sorted_events[i].timestamp:
                timestamp_regressions += 1
                issues.append(f"Timestamp regression in round {rnd}: {sorted_events[i].timestamp} -> {sorted_events[i + 1].timestamp}")

    # Check round duration (time between consecutive round_start events)
    round_starts = sorted([e for e in events if e.type == "round_start"], key=lambda e: e.round)
    for i in range(len(round_starts) - 1):
        duration = round_starts[i + 1].timestamp - round_starts[i].timestamp
        round_num = round_starts[i].round

        if duration < 30:
            short_rounds.append(round_num)
            warnings.append(f"Round {round_num} suspiciously short: {duration:.1f}s")
        elif duration > 300:
            long_gaps.append(round_num)
            warnings.append(f"Long gap after round {round_num}: {duration:.1f}s")

    # Score: 1.0 if all checks pass, deduct for violations
    total_checks = len(rounds) + len(round_starts)
    violations = timestamp_regressions + len(short_rounds) + len(long_gaps)
    score = max(0.0, 1.0 - (violations / max(1, total_checks)))

    return QualityCheck(
        name="timing_consistency",
        score=score,
        weight=0.15,
        issues=issues,
        warnings=warnings,
        details={
            "timestamp_regressions": timestamp_regressions,
            "short_rounds": short_rounds,
            "long_gaps": long_gaps,
        },
    )


def score_map_quality(
    events: list[ValoscribeEvent],
    metadata: MapMetadata | None = None,
    map_id: str = "unknown",
) -> QualityScore:
    """Calculate complete quality score for a map with all signals.

    Args:
        events: List of all events for the map
        metadata: Optional metadata containing validation_results
        map_id: Identifier for the map

    Returns:
        QualityScore with overall score, tier, and all check results
    """
    # Run all quality checks
    checks = [
        check_kill_count(events, metadata),
        check_round_progression(events),
        check_round_start_end_balance(events),
        check_event_completeness(events),
        check_timing_consistency(events),
    ]

    # Calculate weighted overall score
    total_weight = sum(c.weight for c in checks)
    overall_score = sum(c.score * c.weight for c in checks) / total_weight

    # Determine tier
    if overall_score >= 0.8:
        tier = "high"
    elif overall_score >= 0.5:
        tier = "medium"
    else:
        tier = "low"

    # Aggregate issues and warnings
    all_issues = []
    all_warnings = []
    for check in checks:
        all_issues.extend(check.issues)
        all_warnings.extend(check.warnings)

    # Cross-check with Valoscribe's validation_results
    cross_check_disagreements = []
    valoscribe_validation = None

    if metadata and metadata.validation_results:
        valoscribe_validation = metadata.validation_results

        # Check for disagreements
        # Valoscribe format is unknown, so we check for common patterns
        valoscribe_pass = False
        if "passed" in valoscribe_validation:
            valoscribe_pass = valoscribe_validation.get("passed", False)
        elif "status" in valoscribe_validation:
            valoscribe_pass = valoscribe_validation.get("status") == "pass"
        elif "valid" in valoscribe_validation:
            valoscribe_pass = valoscribe_validation.get("valid", False)

        # Disagreement detection
        if valoscribe_pass and tier == "low":
            cross_check_disagreements.append(
                f"Valoscribe reports pass but quality score is low ({overall_score:.2f})"
            )
        elif not valoscribe_pass and tier == "high":
            cross_check_disagreements.append(
                f"Valoscribe reports fail but quality score is high ({overall_score:.2f})"
            )

    # Determine if flagged for review
    flagged_for_review = tier == "low" or len(cross_check_disagreements) > 0

    return QualityScore(
        map_id=map_id,
        overall_score=overall_score,
        tier=tier,
        checks=checks,
        valoscribe_validation=valoscribe_validation,
        cross_check_disagreements=cross_check_disagreements,
        all_issues=all_issues,
        all_warnings=all_warnings,
        flagged_for_review=flagged_for_review,
    )
