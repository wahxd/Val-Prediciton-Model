# External Integrations

**Analysis Date:** 2026-02-13

## APIs & External Services

**VLR.gg (vlr.gg):**
- VLR.gg match page scraping - Extract match metadata (teams, players, agents, maps, VOD URLs, starting sides)
  - SDK/Client: requests + beautifulsoup4 + playwright
  - Auth: None (public scraping)
  - Implementation: `src/valoscribe/scraper/vlr_scraper.py`
  - Usage: `valoscribe scrape-vlr <match_url>`

**YouTube:**
- YouTube VOD downloading - Download tournament VODs with optional timestamp ranges
  - SDK/Client: yt-dlp
  - Auth: None (public videos)
  - Implementation: `src/valoscribe/video/youtube.py`
  - Usage: `valoscribe orchestrate download --youtube-url <url>`

## Data Storage

**Databases:**
- None - All data stored as files

**File Storage:**
- Local filesystem only
  - Input: MP4 video files, JSON metadata
  - Output: JSONL event logs (`event_log.jsonl`), CSV frame states (`frame_states.csv`), JSON metadata
  - Config: JSON HUD coordinate configs in `src/valoscribe/config/`
  - Templates: PNG template images in `src/valoscribe/templates/`

**Caching:**
- None

## Authentication & Identity

**Auth Provider:**
- None - No authentication system

## Monitoring & Observability

**Error Tracking:**
- None - Local logging only

**Logs:**
- Python logging module via custom logger (`src/valoscribe/utils/logger.py`)
- Progress bars via tqdm for video processing
- Log levels configurable per module

## CI/CD & Deployment

**Hosting:**
- None - Command-line tool distributed via GitHub

**CI Pipeline:**
- None detected - Manual testing workflow

## Environment Configuration

**Required env vars:**
- None - All configuration via JSON files and CLI arguments

**Secrets location:**
- None required

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## External Binaries

**Tesseract OCR:**
- System binary required for pytesseract
- Installation: `brew install tesseract` (macOS), `apt-get install tesseract-ocr` (Ubuntu), manual installer (Windows)
- Used for: Killfeed text extraction, digit recognition in HUD elements
- Language: English (eng)

## Processing Infrastructure

**Video Processing:**
- OpenCV VideoCapture for local MP4 files
- Frame-by-frame processing at configurable sample rate (default 4 FPS)
- Template matching for agent/HUD element detection
- OCR for text extraction

**Batch Processing:**
- Bash scripts for parallel processing: `scripts/process_all_series_parallel.sh`
- GNU parallel for concurrent job execution
- No cloud infrastructure - local machine processing only

---

*Integration audit: 2026-02-13*
