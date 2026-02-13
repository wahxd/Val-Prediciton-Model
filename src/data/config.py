"""Configuration management for data pipeline using pydantic-settings."""

from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import structlog

logger = structlog.get_logger()


class DataPipelineConfig(BaseSettings):
    """Data pipeline configuration with .env support."""

    valoscribe_data_dir: Path  # Required, no default
    audit_output_dir: Path = Path("data/audit")
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # No prefix - use bare VALOSCRIBE_DATA_DIR as env var name
    )

    @field_validator('valoscribe_data_dir')
    @classmethod
    def validate_data_dir(cls, v: Path) -> Path:
        """Check if Valoscribe data directory exists, warn if not."""
        if not v.exists():
            logger.warning(
                "valoscribe_data_dir_not_found",
                path=str(v),
                message="Directory does not exist. This may be expected during testing."
            )
        return v


def get_config(data_dir_override: Path | None = None) -> DataPipelineConfig:
    """
    Get configuration with optional override.

    Args:
        data_dir_override: Optional path to override VALOSCRIBE_DATA_DIR env var

    Returns:
        DataPipelineConfig instance
    """
    if data_dir_override:
        return DataPipelineConfig(valoscribe_data_dir=data_dir_override)
    return DataPipelineConfig()
