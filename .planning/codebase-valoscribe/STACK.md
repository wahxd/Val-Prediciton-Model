# Technology Stack

**Analysis Date:** 2026-02-13

## Languages

**Primary:**
- Python 3.10+ - All source code, detectors, orchestration, CLI

**Secondary:**
- Bash - Batch processing scripts in `scripts/` directory
- JSON - Configuration files for HUD coordinates

## Runtime

**Environment:**
- Python 3.10+ (tested on 3.10, 3.11, 3.12, 3.13)

**Package Manager:**
- uv (recommended) - Fast Python package manager from Astral
- pip (alternative) - Standard Python package manager
- Lockfile: `uv.lock` present

## Frameworks

**Core:**
- OpenCV (opencv-python >=4.8.0) - Computer vision and image processing
- NumPy (>=1.24.0) - Array operations and numerical processing
- Pydantic (>=2.0.0) - Data validation and type definitions
- Typer (>=0.9.0) - CLI framework with command groups

**Testing:**
- pytest (>=7.4.0) - Test framework

**Build/Dev:**
- Hatchling - Build backend
- Ruff (>=0.1.0) - Fast linter and formatter (Astral)
- mypy (>=1.5.0) - Static type checking

## Key Dependencies

**Critical:**
- pytesseract (>=0.3.10) - OCR for killfeed and text extraction (requires Tesseract binary)
- opencv-python (>=4.8.0) - Template matching, image cropping, frame processing
- yt-dlp (>=2023.0.0) - YouTube VOD downloading
- requests (>=2.31.0) - HTTP requests for VLR.gg scraper
- beautifulsoup4 (>=4.12.0) - HTML parsing for VLR.gg metadata extraction
- playwright (>=1.40.0) - Browser automation for VLR.gg scraping

**Infrastructure:**
- Pillow (>=10.0.0) - Image processing utilities
- tqdm (>=4.66.0) - Progress bars for video processing

## Configuration

**Environment:**
- No environment variables required for core functionality
- Tesseract OCR binary must be installed separately (not via pip)
- HUD coordinates configured via JSON files in `src/valoscribe/config/`

**Build:**
- `pyproject.toml` - Python project configuration (PEP 621)
- `uv.lock` - Dependency lockfile
- Ruff config in `pyproject.toml` (line length 100, Python 3.10 target)
- mypy config in `pyproject.toml` (lenient settings)

## Platform Requirements

**Development:**
- Python 3.10 or higher
- Tesseract OCR binary (brew/apt/manual install)
- 1080p video files for processing

**Production:**
- Command-line tool (no server/deployment infrastructure)
- Processes videos locally or via batch scripts
- Output: JSONL event logs and CSV frame states

---

*Stack analysis: 2026-02-13*
