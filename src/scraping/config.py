"""Configuration for dataset expansion processing pipeline.

Loads settings from environment variables with EXPANSION_ prefix.
Uses pydantic-settings for validation and defaults.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


class ProcessingConfig(BaseSettings):
    """Configuration for VOD processing pipeline.

    Environment variables:
        EXPANSION_VALOSCRIBE_REPO: Path to Valoscribe repository
        EXPANSION_OUTPUT_DIR: Output directory for processed data
        EXPANSION_DOWNLOAD_DIR: Temporary directory for downloaded VODs
        EXPANSION_MANIFEST_PATH: Path to manifest.json
        EXPANSION_METADATA_DIR: Directory for VLR metadata files
    """

    # Paths
    valoscribe_repo: Path = Path("D:/Git/valoscribe")
    output_dir: Path = Path("data/processing/processed")
    download_dir: Path = Path("data/processing/downloads")
    manifest_path: Path = Path("data/processing/manifest.json")
    metadata_dir: Path = Path("data/processing/metadata")

    # Processing behavior
    download_delay_seconds: float = 10.0  # Delay between YouTube downloads
    processing_timeout_seconds: int = 7200  # 2 hours per VOD
    max_retries: int = 2
    delete_vod_after_processing: bool = True

    class Config:
        env_prefix = "EXPANSION_"
        case_sensitive = False

    def __init__(self, **kwargs):
        """Initialize config, loading from environment variables."""
        super().__init__(**kwargs)

        # Convert to Path objects if loaded as strings
        self.valoscribe_repo = Path(self.valoscribe_repo)
        self.output_dir = Path(self.output_dir)
        self.download_dir = Path(self.download_dir)
        self.manifest_path = Path(self.manifest_path)
        self.metadata_dir = Path(self.metadata_dir)
