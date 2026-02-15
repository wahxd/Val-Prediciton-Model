"""Quality validation for processed Valoscribe output.

Bridges Valoscribe output files (events.jsonl, metadata.json) to the
quality scoring system (src/data/quality.py). Returns a metrics dict
suitable for storage in VODRecord.quality_metrics.
"""

import json
from pathlib import Path

from src.data.quality import score_map_quality
from src.data.schemas import parse_event, MapMetadata


def validate_map_output(output_dir: Path, map_id: str) -> dict:
    """Validate quality of processed Valoscribe output.

    Loads events.jsonl and metadata.json from output_dir, runs quality
    checks via score_map_quality, and returns a metrics dict suitable for
    storage in VODRecord.quality_metrics.

    Args:
        output_dir: Directory containing events.jsonl and metadata.json
        map_id: Identifier for the map (for quality score tracking)

    Returns:
        Quality metrics dict with:
        - overall_score: float (0.0-1.0)
        - tier: str ("high", "medium", "low")
        - flagged_for_review: bool
        - checks: dict of check results
        - total_events: int
        - total_rounds: int
        - cross_check_disagreements: list[str]
        - all_issues: list[str]
        - all_warnings: list[str]
    """
    output_dir = Path(output_dir)
    events_file = output_dir / "events.jsonl"
    metadata_file = output_dir / "metadata.json"

    # Load events
    events = []
    if events_file.exists():
        try:
            with open(events_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            event = parse_event(line)
                            events.append(event)
                        except Exception:
                            # Skip malformed events
                            pass
        except Exception:
            pass

    # Load metadata
    metadata = None
    if metadata_file.exists():
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata_data = json.load(f)
                metadata = MapMetadata(**metadata_data)
        except Exception:
            # Continue without metadata
            pass

    # If no events found, return low quality score
    if not events:
        return {
            "overall_score": 0.0,
            "tier": "low",
            "flagged_for_review": True,
            "checks": {},
            "total_events": 0,
            "total_rounds": 0,
            "cross_check_disagreements": [],
            "all_issues": ["No events found in output"],
            "all_warnings": [],
        }

    # Run quality checks
    quality_score = score_map_quality(events, metadata, map_id)

    # Calculate total rounds from events
    round_numbers = {e.round for e in events if hasattr(e, 'round')}
    total_rounds = max(round_numbers) if round_numbers else 0

    # Convert QualityScore to dict format for storage
    return {
        "overall_score": quality_score.overall_score,
        "tier": quality_score.tier,
        "flagged_for_review": quality_score.flagged_for_review,
        "checks": {
            check.name: {
                "score": check.score,
                "issues": check.issues,
                "warnings": check.warnings,
            }
            for check in quality_score.checks
        },
        "total_events": len(events),
        "total_rounds": total_rounds,
        "cross_check_disagreements": quality_score.cross_check_disagreements,
        "all_issues": quality_score.all_issues,
        "all_warnings": quality_score.all_warnings,
    }


class QualityValidator:
    """Validates quality of processed Valoscribe output."""

    def __init__(self, valoscribe_output_base: Path):
        """Initialize validator.

        Args:
            valoscribe_output_base: Base directory containing processed map dirs
                (e.g., D:/Git/valoscribe/data/processed/)
        """
        self.output_base = Path(valoscribe_output_base)

    def validate(self, map_id: str) -> dict:
        """Validate a single map's output quality.

        Args:
            map_id: Directory name under output_base

        Returns:
            Quality metrics dict for storage in VODRecord.quality_metrics
        """
        output_dir = self.output_base / map_id
        return validate_map_output(output_dir, map_id)
