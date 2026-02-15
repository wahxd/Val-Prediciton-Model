"""VOD processing orchestrator that wires together Valoscribe CLI commands.

Provides VODOrchestrator class that:
- Downloads VODs via Valoscribe download command
- Processes VODs via Valoscribe orchestrate process-vod command
- Tracks state in ProcessingManifest
- Provides resumable batch processing loop
"""

import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import structlog

from src.config.processing import ProcessingConfig
from src.pipeline.manifest import ProcessingManifest, VODRecord

log = structlog.get_logger(__name__)


class VODOrchestrator:
    """Orchestrates VOD downloading and processing through Valoscribe CLI.

    Manages the full pipeline:
    1. Discovery: Scrape VLR.gg event pages for match URLs
    2. Download: Call Valoscribe download command for each VOD
    3. Process: Call Valoscribe orchestrate process-vod for each VOD
    4. Cleanup: Delete downloaded VOD files after successful processing
    """

    def __init__(self, config: ProcessingConfig, manifest: ProcessingManifest):
        """Initialize orchestrator.

        Args:
            config: Processing configuration
            manifest: Processing manifest for state tracking
        """
        self.config = config
        self.manifest = manifest

    def _run_valoscribe_cmd(
        self,
        args: list[str],
        timeout: int | None = None,
        cwd: Path | None = None
    ) -> subprocess.CompletedProcess:
        """Run a Valoscribe CLI command.

        Args:
            args: Command arguments (e.g., ['download', 'URL', '--output', 'path'])
            timeout: Timeout in seconds (None = no timeout)
            cwd: Working directory (default: config.valoscribe_repo)

        Returns:
            CompletedProcess with stdout/stderr captured

        Raises:
            subprocess.CalledProcessError: If command fails
            subprocess.TimeoutExpired: If command times out
        """
        if cwd is None:
            cwd = self.config.valoscribe_repo

        cmd = ["python", "-m", "valoscribe"] + args

        log.debug("Running Valoscribe command", cmd=" ".join(cmd), cwd=str(cwd))

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd
            )
            log.debug("Valoscribe command succeeded", exit_code=result.returncode)
            return result

        except subprocess.CalledProcessError as e:
            log.error(
                "Valoscribe command failed",
                cmd=" ".join(cmd),
                exit_code=e.returncode,
                stderr=e.stderr[:500] if e.stderr else None
            )
            raise

        except subprocess.TimeoutExpired as e:
            log.error(
                "Valoscribe command timed out",
                cmd=" ".join(cmd),
                timeout=timeout
            )
            raise

    def scrape_and_populate(
        self,
        event_url: str,
        tournament_name: str
    ) -> int:
        """DEPRECATED: Use TournamentScraper directly instead.

        This method uses the old scraping workflow. For new code, use:

        ```python
        from src.scraping.tournament_scraper import TournamentScraper
        import asyncio

        scraper = TournamentScraper(manifest, youtube_api_key=...)
        stats = asyncio.run(scraper.scrape_tournament(event_url, tournament_name))
        ```

        Args:
            event_url: VLR.gg event/tournament URL
            tournament_name: Tournament name for metadata

        Returns:
            Count of new VODs added to manifest
        """
        log.warning(
            "deprecated_method",
            method="scrape_and_populate",
            suggestion="Use TournamentScraper directly for new scraping workflows"
        )

        # For backward compatibility, could implement wrapper here
        # But better to force migration to new TournamentScraper
        raise NotImplementedError(
            "scrape_and_populate() is deprecated. Use TournamentScraper instead. "
            "See src/scraping/tournament_scraper.py and scripts/scrape_tournaments.py"
        )

    def process_single_vod(self, record: VODRecord) -> bool:
        """Process a single VOD: download, process through Valoscribe, cleanup.

        Args:
            record: VODRecord to process

        Returns:
            True on success, False on failure
        """
        start_time = datetime.now(timezone.utc)
        vod_file = None
        series_metadata_file = None
        download_phase = True  # Track which phase we're in for granular failure status

        try:
            # Step 1: Update status to downloading
            log.info(
                "Starting VOD processing",
                vod_id=record.vod_id,
                teams=record.teams,
                map_name=record.map_name
            )

            self.manifest.update_status(
                record.vod_id,
                "downloading",
                started_at=start_time.isoformat()
            )

            # Step 2: Download series metadata (if not already done)
            # Extract match ID from vod_id (format: "{match_id}_map{N}")
            match_id = record.vod_id.rsplit('_', 1)[0]
            series_metadata_file = self.config.metadata_dir / f"{match_id}_series.json"

            if not series_metadata_file.exists():
                log.info("Scraping series metadata", match_url=record.vlr_match_url)

                # Create metadata directory
                self.config.metadata_dir.mkdir(parents=True, exist_ok=True)

                # Scrape series metadata
                self._run_valoscribe_cmd([
                    "scrape-vlr",
                    record.vlr_match_url,
                    "--output", str(series_metadata_file)
                ])

                # Split into per-map metadata files
                map_metadata_dir = self.config.metadata_dir / f"{match_id}_maps"
                self._run_valoscribe_cmd([
                    "split-metadata",
                    str(series_metadata_file),
                    "--output-dir", str(map_metadata_dir)
                ])
            else:
                log.debug("Series metadata already exists", file=str(series_metadata_file))

            # Step 3: Download VOD
            log.info("Downloading VOD", url=record.youtube_url)

            # Create download directory
            self.config.download_dir.mkdir(parents=True, exist_ok=True)

            # Download to specific filename
            vod_file = self.config.download_dir / f"{record.vod_id}.mp4"

            self._run_valoscribe_cmd(
                [
                    "download",
                    record.youtube_url,
                    "--output", str(self.config.download_dir),
                    "--overwrite"
                ],
                timeout=self.config.download_timeout_seconds
            )

            # Find the downloaded file (Valoscribe names it based on video title)
            # Look for the most recently created .mp4 file in download_dir
            mp4_files = list(self.config.download_dir.glob("*.mp4"))
            if not mp4_files:
                raise RuntimeError(f"No .mp4 file found after download in {self.config.download_dir}")

            # Use the most recently modified file
            downloaded_file = max(mp4_files, key=lambda p: p.stat().st_mtime)

            # Rename to standard name if different
            if downloaded_file != vod_file:
                downloaded_file.rename(vod_file)

            log.info("VOD downloaded", file=str(vod_file))

            # Download phase complete -- switch to processing phase
            download_phase = False

            # Step 4: Update status to processing
            self.manifest.update_status(record.vod_id, "processing")

            # Step 5: Get per-map metadata
            map_metadata_dir = self.config.metadata_dir / f"{match_id}_maps"
            map_metadata_file = map_metadata_dir / f"map{record.map_number}.json"

            if not map_metadata_file.exists():
                raise RuntimeError(
                    f"Map metadata not found: {map_metadata_file}. "
                    f"Expected from split-metadata output."
                )

            log.info("Processing VOD through Valoscribe", metadata=str(map_metadata_file))

            # Step 6: Process through Valoscribe
            # Output to: output_dir/{vod_id}/
            output_dir = self.config.output_dir / record.vod_id
            output_dir.mkdir(parents=True, exist_ok=True)

            self._run_valoscribe_cmd(
                [
                    "orchestrate", "process-vod",
                    str(vod_file),
                    str(map_metadata_file),
                    "--output", str(output_dir),
                    "--quiet"
                ],
                timeout=self.config.processing_timeout_seconds
            )

            # Step 7: Mark complete
            end_time = datetime.now(timezone.utc)
            processing_time = (end_time - start_time).total_seconds()

            self.manifest.update_status(
                record.vod_id,
                "complete",
                map_id=record.vod_id,  # Use vod_id as map_id
                completed_at=end_time.isoformat(),
                processing_time_seconds=processing_time
            )

            log.info(
                "VOD processing complete",
                vod_id=record.vod_id,
                processing_time=f"{processing_time:.1f}s"
            )

            # Step 8: Rate limit (delay before next download)
            time.sleep(self.config.download_delay_seconds)

            return True

        except subprocess.TimeoutExpired as e:
            # Timeout - determine which phase timed out
            if download_phase:
                error_msg = f"Download timeout after {self.config.download_timeout_seconds}s"
                status = "download_failed"
            else:
                error_msg = f"Processing timeout after {self.config.processing_timeout_seconds}s"
                status = "processing_failed"

            log.error("VOD processing timeout", vod_id=record.vod_id, error=error_msg, phase="download" if download_phase else "processing")

            self.manifest.update_status(
                record.vod_id,
                status,
                error_message=error_msg,
                retry_count=record.retry_count + 1
            )

            return False

        except Exception as e:
            # Any other failure - use granular status based on phase
            error_msg = str(e)
            status = "download_failed" if download_phase else "processing_failed"

            log.error("VOD processing failed", vod_id=record.vod_id, error=error_msg, phase="download" if download_phase else "processing")

            self.manifest.update_status(
                record.vod_id,
                status,
                error_message=error_msg,
                retry_count=record.retry_count + 1
            )

            return False

        finally:
            # Always clean up VOD file
            if vod_file and vod_file.exists() and self.config.delete_vod_after_processing:
                try:
                    vod_file.unlink()
                    log.debug("Deleted VOD file", file=str(vod_file))
                except Exception as e:
                    log.warning("Failed to delete VOD file", file=str(vod_file), error=str(e))

    def run_pipeline(self) -> dict:
        """Run the full processing pipeline for all pending VODs.

        Returns:
            Summary dict with processing statistics
        """
        pending = self.manifest.get_pending()

        log.info(
            "Pipeline starting",
            total_vods=len(self.manifest.records),
            pending=len(pending)
        )

        completed_count = 0
        failed_count = 0
        skipped_count = 0

        for i, record in enumerate(pending, 1):
            # Skip VODs that have exceeded max retries
            if record.retry_count >= self.config.max_retries:
                log.warning(
                    "Skipping VOD (max retries exceeded)",
                    vod_id=record.vod_id,
                    retry_count=record.retry_count
                )
                self.manifest.update_status(record.vod_id, "skipped")
                skipped_count += 1
                continue

            # Log progress
            log.info(
                "Processing VOD",
                index=i,
                total=len(pending),
                vod_id=record.vod_id,
                teams=f"{record.teams[0]} vs {record.teams[1]}" if len(record.teams) >= 2 else str(record.teams)
            )

            # Process VOD
            success = self.process_single_vod(record)

            if success:
                completed_count += 1
            else:
                failed_count += 1

            # Log running progress
            summary_so_far = self.manifest.get_summary()
            log.info(
                "Progress update",
                processed=f"{i}/{len(pending)}",
                complete=summary_so_far['by_status'].get('complete', 0),
                failed=summary_so_far['by_status'].get('failed', 0)
            )

        # Final summary
        final_summary = self.manifest.get_summary()
        log.info(
            "Pipeline complete",
            total=final_summary['total'],
            complete=final_summary['by_status'].get('complete', 0),
            failed=final_summary['by_status'].get('failed', 0),
            skipped=final_summary['by_status'].get('skipped', 0),
            pending=final_summary['by_status'].get('pending', 0)
        )

        return final_summary
