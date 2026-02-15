"""Typer CLI for Valoscribe data pipeline operations.

Provides convenient access to load, audit, and catalog commands
with Rich progress display and formatted output.
"""

from pathlib import Path

import structlog
import typer
from rich.console import Console
from rich.progress import track
from rich.table import Table

from src.data.audit import generate_audit
from src.data.catalog import DataCatalog
from src.config.data import get_config
from src.data.loader import load_all_maps

logger = structlog.get_logger()
console = Console()
app = typer.Typer(help="Valoscribe data pipeline CLI")


@app.command()
def load(
    data_dir: Path = typer.Option(
        None, "--data-dir", help="Override VALOSCRIBE_DATA_DIR"
    ),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Verbose output"),
):
    """Load all maps and display summary."""
    # Configure logging
    if verbose:
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(min_level=10)
        )

    # Get config
    config = get_config(data_dir_override=data_dir)

    console.print(f"[bold]Loading maps from:[/bold] {config.valoscribe_data_dir}")

    # Load all maps
    results = load_all_maps(config.valoscribe_data_dir)

    # Summary stats
    total = len(results)
    success = sum(1 for r in results.values() if r.success)
    failed = total - success

    console.print(
        f"\n[bold green]✓ Loaded {success}/{total} maps[/bold green] ({failed} failures)"
    )

    # Display map index table
    if success > 0:
        table = Table(title="Map Index")
        table.add_column("Map ID", style="cyan")
        table.add_column("Teams", style="yellow")
        table.add_column("Map", style="magenta")
        table.add_column("Events", justify="right")

        for map_id, result in sorted(results.items()):
            if result.success and result.data:
                teams_str = (
                    " vs ".join(result.data.metadata.teams)
                    if result.data.metadata
                    else "unknown"
                )
                map_name = (
                    result.data.metadata.map_name
                    if result.data.metadata
                    else "unknown"
                )
                event_count = result.data.event_count

                table.add_row(map_id, teams_str, map_name, str(event_count))

        console.print(table)

    # Display failures if any
    if failed > 0:
        console.print(f"\n[bold red]Failed Maps:[/bold red]")
        for map_id, result in sorted(results.items()):
            if not result.success:
                console.print(f"  - {map_id}: {result.error}")


@app.command()
def audit(
    data_dir: Path = typer.Option(
        None, "--data-dir", help="Override VALOSCRIBE_DATA_DIR"
    ),
    output_dir: Path = typer.Option(
        Path("data/audit"), "--output-dir", help="Audit report output directory"
    ),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Verbose output"),
):
    """Load all maps, run quality audit, and generate reports."""
    # Configure logging
    if verbose:
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(min_level=10)
        )

    # Get config
    config = get_config(data_dir_override=data_dir)

    console.print(f"[bold]Loading maps from:[/bold] {config.valoscribe_data_dir}")

    # Load all maps with progress
    results = load_all_maps(config.valoscribe_data_dir)

    total = len(results)
    success = sum(1 for r in results.values() if r.success)
    failed = total - success

    console.print(
        f"[bold green]✓ Loaded {success}/{total} maps[/bold green] ({failed} failures)\n"
    )

    # Generate audit reports
    console.print(f"[bold]Generating audit reports...[/bold]")
    json_path, md_path = generate_audit(results, output_dir)

    console.print(f"\n[bold green]✓ Audit complete![/bold green]")
    console.print(f"  - JSON report: {json_path}")
    console.print(f"  - Markdown report: {md_path}")

    # Display executive summary
    from src.data.audit import run_audit

    audit_result = run_audit(results)

    console.print(f"\n[bold]Executive Summary:[/bold]")
    console.print(f"  Total maps: {audit_result.total_maps}")
    console.print(f"  Loaded: {audit_result.maps_loaded}")
    console.print(f"  Failed: {audit_result.maps_failed}")
    console.print(f"\n[bold]Quality Tiers:[/bold]")
    console.print(f"  High: {audit_result.tier_summary['high']} maps")
    console.print(f"  Medium: {audit_result.tier_summary['medium']} maps")
    console.print(f"  Low: {audit_result.tier_summary['low']} maps")

    total_usable = (
        audit_result.tier_summary["high"] + audit_result.tier_summary["medium"]
    )
    if audit_result.maps_loaded > 0:
        usable_pct = total_usable / audit_result.maps_loaded * 100
        console.print(
            f"\n[bold]Dataset Readiness:[/bold] {total_usable} usable maps ({usable_pct:.1f}%)"
        )


@app.command()
def catalog(
    data_dir: Path = typer.Option(
        None, "--data-dir", help="Override VALOSCRIBE_DATA_DIR"
    ),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Verbose output"),
):
    """Load all maps and display data catalog summary."""
    # Configure logging
    if verbose:
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(min_level=10)
        )

    # Get config
    config = get_config(data_dir_override=data_dir)

    console.print(f"[bold]Loading maps from:[/bold] {config.valoscribe_data_dir}")

    # Load all maps
    results = load_all_maps(config.valoscribe_data_dir)

    # Build catalog
    data_catalog = DataCatalog()
    for result in results.values():
        if result.success and result.data:
            data_catalog.add_map_events(result.data.events)

    # Display summary
    console.print(f"\n{data_catalog.summary()}")

    # Display event type table
    table = Table(title="Event Types")
    table.add_column("Event Type", style="cyan")
    table.add_column("Count", justify="right", style="green")
    table.add_column("Fields", justify="right")

    for event_type, entry in sorted(data_catalog.entries.items()):
        table.add_row(event_type, f"{entry.count:,}", str(len(entry.fields)))

    console.print(table)


@app.command()
def run(
    data_dir: Path = typer.Option(
        None, "--data-dir", help="Override VALOSCRIBE_DATA_DIR"
    ),
    output_dir: Path = typer.Option(
        Path("data/audit"), "--output-dir", help="Audit report output directory"
    ),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Verbose output"),
):
    """Convenience command: load + audit combined."""
    # Just call audit command (which does both)
    audit(data_dir=data_dir, output_dir=output_dir, verbose=verbose)


if __name__ == "__main__":
    app()
