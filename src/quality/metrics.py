"""QualityMetrics: structured logging and degradation tracking for OCR quality.

Tracks per-field OCR confidence averages, consecutive failure counts, debounce
statistics, replay detection counts, and per-event-type emission counts.
Uses structlog for JSON-formatted structured logging.

Warning thresholds (per user decisions):
- 10+ consecutive failures: structlog WARNING
- 50+ consecutive failures: console print (significant issue)
- 180+ consecutive failures (~30s at 6fps): structlog ERROR (check ROI/stream)
"""

from __future__ import annotations

from collections import defaultdict

import structlog

# Configure structlog for JSON-formatted structured logging at module level.
# This runs once on import, establishing the logging pipeline.
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

# OCR fields tracked for per-field confidence metrics
_OCR_FIELDS: tuple[str, ...] = (
    "timer",
    "score_left",
    "score_right",
    "alive_left",
    "alive_right",
)

# Warning thresholds for consecutive OCR failures
WARN_THRESHOLD: int = 10
CONSOLE_THRESHOLD: int = 50
PAUSE_THRESHOLD: int = 180  # ~30 seconds at 6fps


class QualityMetrics:
    """Tracks OCR quality and system health metrics with structured logging.

    Provides observability for the event detection pipeline: OCR confidence
    tracking, degradation warnings, replay metrics, and event counts.

    Usage:
        metrics = QualityMetrics()
        metrics.log_ocr_result("timer", 0.92, True)
        metrics.log_frame_processed(True)
        metrics.log_event_emitted("kill")
        summary = metrics.get_summary()
    """

    def __init__(self) -> None:
        self.logger = structlog.get_logger("quality_metrics")

        # Frame counters
        self.total_frames: int = 0
        self.frames_with_valid_ocr: int = 0
        self.frames_skipped_low_confidence: int = 0
        self.frames_skipped_invalid_value: int = 0

        # OCR confidence tracking per field
        self.consecutive_failures: int = 0
        self.ocr_confidence_sum: dict[str, float] = {f: 0.0 for f in _OCR_FIELDS}
        self.ocr_confidence_count: dict[str, int] = {f: 0 for f in _OCR_FIELDS}

        # Debounce and replay tracking
        self.debounce_rejects: int = 0
        self.replay_detections: int = 0
        self.replay_frames_suppressed: int = 0

        # Event tracking
        self.events_emitted: dict[str, int] = defaultdict(int)

        # Validation warnings
        self.validation_warnings: list[str] = []

    def log_ocr_result(self, field: str, confidence: float, is_valid: bool) -> None:
        """Track OCR quality for a specific field.

        If valid with confidence >= 0.7, adds to running average and resets
        failure counter. If invalid, increments failure counter and triggers
        warnings at configured thresholds.

        Args:
            field: OCR field name (e.g., "timer", "score_left").
            confidence: OCR confidence score (0.0-1.0).
            is_valid: Whether the extracted value passed validation.
        """
        if is_valid and confidence >= 0.7:
            if field in self.ocr_confidence_sum:
                self.ocr_confidence_sum[field] += confidence
                self.ocr_confidence_count[field] += 1
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1

            if not is_valid:
                self.frames_skipped_invalid_value += 1
            elif confidence < 0.7:
                self.frames_skipped_low_confidence += 1

            # Warning thresholds
            if self.consecutive_failures >= PAUSE_THRESHOLD:
                self.logger.error(
                    "ocr_degradation_critical",
                    field=field,
                    consecutive_failures=self.consecutive_failures,
                    recommendation="Check ROI alignment or stream quality",
                )
            elif self.consecutive_failures >= CONSOLE_THRESHOLD:
                self.logger.warning(
                    "ocr_degradation_significant",
                    field=field,
                    consecutive_failures=self.consecutive_failures,
                )
                print(
                    f"WARNING: {self.consecutive_failures} consecutive OCR failures "
                    f"on field '{field}'. Check stream quality."
                )
            elif self.consecutive_failures >= WARN_THRESHOLD:
                self.logger.warning(
                    "ocr_degradation_warning",
                    field=field,
                    consecutive_failures=self.consecutive_failures,
                )

    def log_frame_processed(self, valid: bool) -> None:
        """Record a processed frame.

        Args:
            valid: Whether the frame produced a valid GameState.
        """
        self.total_frames += 1
        if valid:
            self.frames_with_valid_ocr += 1

    def log_debounce_reject(self) -> None:
        """Record a debounce rejection (value changed but no 3-frame consensus)."""
        self.debounce_rejects += 1

    def log_replay_detected(
        self, timer_regression: str, current_score: tuple[int, int]
    ) -> None:
        """Record a replay segment detection.

        Args:
            timer_regression: Description of the timer regression (e.g., "0:30 -> 1:15").
            current_score: Current score as (left, right) for context.
        """
        self.replay_detections += 1
        self.logger.info(
            "replay_detected",
            timer_regression=timer_regression,
            score_left=current_score[0],
            score_right=current_score[1],
            total_replays=self.replay_detections,
        )

    def log_replay_frame_suppressed(self) -> None:
        """Record a frame suppressed due to ongoing replay."""
        self.replay_frames_suppressed += 1

    def log_event_emitted(self, event_type: str) -> None:
        """Record an emitted event by type.

        Args:
            event_type: The event type string (e.g., "kill", "round_end").
        """
        self.events_emitted[event_type] += 1
        self.logger.debug(
            "event_emitted",
            event_type=event_type,
            total_of_type=self.events_emitted[event_type],
        )

    def log_validation_warning(self, warning: str) -> None:
        """Record a state coherence validation warning.

        Args:
            warning: Description of the coherence violation.
        """
        self.validation_warnings.append(warning)
        self.logger.warning("validation_warning", warning=warning)

    def get_summary(self) -> dict:
        """Return comprehensive metrics summary for post-stream analysis.

        Returns:
            Dict with all tracked metrics including OCR success rate,
            per-field confidence averages, event counts, and quality stats.
        """
        avg_confidence: dict[str, float] = {}
        for field in _OCR_FIELDS:
            count = self.ocr_confidence_count[field]
            if count > 0:
                avg_confidence[field] = round(
                    self.ocr_confidence_sum[field] / count, 4
                )
            else:
                avg_confidence[field] = 0.0

        ocr_success_rate = 0.0
        if self.total_frames > 0:
            ocr_success_rate = round(
                self.frames_with_valid_ocr / self.total_frames, 4
            )

        return {
            "total_frames": self.total_frames,
            "frames_with_valid_ocr": self.frames_with_valid_ocr,
            "frames_skipped_low_confidence": self.frames_skipped_low_confidence,
            "frames_skipped_invalid_value": self.frames_skipped_invalid_value,
            "ocr_success_rate": ocr_success_rate,
            "avg_confidence": avg_confidence,
            "debounce_rejects": self.debounce_rejects,
            "replay_detections": self.replay_detections,
            "replay_frames_suppressed": self.replay_frames_suppressed,
            "events_emitted": dict(self.events_emitted),
            "total_events": sum(self.events_emitted.values()),
            "validation_warnings_count": len(self.validation_warnings),
        }

    def reset(self) -> None:
        """Reset all counters for a new match."""
        self.total_frames = 0
        self.frames_with_valid_ocr = 0
        self.frames_skipped_low_confidence = 0
        self.frames_skipped_invalid_value = 0
        self.consecutive_failures = 0
        self.ocr_confidence_sum = {f: 0.0 for f in _OCR_FIELDS}
        self.ocr_confidence_count = {f: 0 for f in _OCR_FIELDS}
        self.debounce_rejects = 0
        self.replay_detections = 0
        self.replay_frames_suppressed = 0
        self.events_emitted = defaultdict(int)
        self.validation_warnings = []
