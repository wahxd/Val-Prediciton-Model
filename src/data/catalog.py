"""Data catalog for discovering and documenting Valoscribe output format.

Auto-discovers all event types, fields per type, value ranges, and completeness
stats across the dataset. Handles both known fields and model_extra fields.
"""

from dataclasses import dataclass, field
from typing import Any

from src.data.schemas import ValoscribeEvent


@dataclass
class FieldStats:
    """Statistics for a single field across all events of a type."""

    name: str
    dtype: str  # observed Python type: "str", "int", "float", etc.
    count: int = 0  # how many events have this field
    null_count: int = 0  # how many events have this field as None
    unique_values: set[str] | None = None  # for string fields with < 50 unique values
    min_value: float | None = None  # for numeric fields
    max_value: float | None = None  # for numeric fields
    sample_values: list[Any] = field(default_factory=list)  # first 5 unique values


@dataclass
class CatalogEntry:
    """Catalog entry for a single event type."""

    event_type: str
    count: int = 0
    fields: dict[str, FieldStats] = field(default_factory=dict)


class DataCatalog:
    """Accumulates statistics about Valoscribe data format across the dataset."""

    def __init__(self):
        self.entries: dict[str, CatalogEntry] = {}
        self.total_events: int = 0
        self.total_maps: int = 0

    def add_event(self, event: ValoscribeEvent) -> None:
        """Add a single event to the catalog, accumulating field statistics.

        Args:
            event: Event to process
        """
        self.total_events += 1
        event_type = event.type

        # Create entry if first time seeing this event type
        if event_type not in self.entries:
            self.entries[event_type] = CatalogEntry(event_type=event_type)

        entry = self.entries[event_type]
        entry.count += 1

        # Process all fields: known fields + model_extra fields
        event_dict = event.model_dump()

        for field_name, value in event_dict.items():
            # Initialize field stats if first time seeing this field
            if field_name not in entry.fields:
                entry.fields[field_name] = FieldStats(
                    name=field_name,
                    dtype=type(value).__name__,
                    unique_values=set() if isinstance(value, str) else None,
                )

            field_stat = entry.fields[field_name]
            field_stat.count += 1

            # Track null count
            if value is None:
                field_stat.null_count += 1
                continue

            # Update dtype if we see a more specific type
            value_type = type(value).__name__
            if field_stat.dtype == "NoneType" and value_type != "NoneType":
                field_stat.dtype = value_type

            # Track unique values for strings (up to 50)
            if isinstance(value, str) and field_stat.unique_values is not None:
                if len(field_stat.unique_values) < 50:
                    field_stat.unique_values.add(value)
                elif len(field_stat.unique_values) == 50:
                    # Stop tracking after 50 unique values
                    field_stat.unique_values = None

            # Track min/max for numeric fields
            if isinstance(value, (int, float)):
                if field_stat.min_value is None or value < field_stat.min_value:
                    field_stat.min_value = value
                if field_stat.max_value is None or value > field_stat.max_value:
                    field_stat.max_value = value

            # Add to sample values (first 5 unique)
            if len(field_stat.sample_values) < 5 and value not in field_stat.sample_values:
                field_stat.sample_values.append(value)

    def add_map_events(self, events: list[ValoscribeEvent]) -> None:
        """Bulk add events from a single map.

        Args:
            events: All events from one map
        """
        for event in events:
            self.add_event(event)
        self.total_maps += 1

    def to_dict(self) -> dict[str, Any]:
        """Serialize catalog to dictionary for JSON output.

        Returns:
            Dictionary representation of the catalog
        """
        return {
            "total_events": self.total_events,
            "total_maps": self.total_maps,
            "event_types": {
                event_type: {
                    "count": entry.count,
                    "fields": {
                        field_name: {
                            "dtype": stat.dtype,
                            "count": stat.count,
                            "null_count": stat.null_count,
                            "unique_values": list(stat.unique_values) if stat.unique_values else None,
                            "min_value": stat.min_value,
                            "max_value": stat.max_value,
                            "sample_values": stat.sample_values,
                        }
                        for field_name, stat in entry.fields.items()
                    },
                }
                for event_type, entry in self.entries.items()
            },
        }

    def summary(self) -> str:
        """Generate human-readable summary of catalog.

        Returns:
            Multi-line string summary
        """
        lines = [
            f"Data Catalog Summary",
            f"===================",
            f"",
            f"Total events: {self.total_events:,}",
            f"Total maps: {self.total_maps}",
            f"Event types discovered: {len(self.entries)}",
            f"",
            f"Event Types:",
        ]

        for event_type, entry in sorted(self.entries.items()):
            lines.append(f"  - {event_type}: {entry.count:,} events, {len(entry.fields)} fields")

        return "\n".join(lines)
