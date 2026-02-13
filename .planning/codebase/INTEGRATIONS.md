# External Integrations

**Analysis Date:** 2026-02-12

## APIs & External Services

**Video Streaming Platforms:**
- YouTube/Twitch VODs - Live and recorded gameplay footage
  - SDK/Client: streamlink
  - Usage: Extract best-quality stream URL from public VOD links
  - Example: `https://www.youtube.com/watch?v=GoLVlVZAk6E` (`d:\Git\Val-Prediciton-Model\backend.py` line 105)

**Valorant Esports:**
- No direct official API integration
- Relies on screen scraping of VCT broadcast overlay (OCR-based)
- Reads game state from broadcast video (scores, player counts, spike status)

## Data Storage

**Databases:**
- None detected - No persistent database

**File Storage:**
- Local filesystem only
- JSON output file: `game_state.json` (`d:\Git\Val-Prediciton-Model\backend.py` line 14)
- Temporary files: System temp directory for uploaded VOD files (`d:\Git\Val-Prediciton-Model\dashboard.py` line 181)

**Caching:**
- Streamlit @st.cache_resource decorator for ML model (`d:\Git\Val-Prediciton-Model\dashboard.py` line 117)
- Streamlit caches loaded models in session state

## Authentication & Identity

**Auth Provider:**
- None - No user authentication or identity system
- Public video links only (YouTube, Twitch)
- Streamlink handles stream resolution without API keys for VOD access

## Monitoring & Observability

**Error Tracking:**
- None detected - No error tracking service (Sentry, DataDog, etc.)

**Logs:**
- Console print statements only (`d:\Git\Val-Prediciton-Model\backend.py` lines 20, 23, 97, 100)
- No structured logging framework

## CI/CD & Deployment

**Hosting:**
- None currently deployed - Local development only
- Can be deployed to Streamlit Cloud or Docker container

**CI Pipeline:**
- None detected - No GitHub Actions, GitLab CI, or similar

**Deployment Target:**
- Local machine (Windows 11 Pro)
- Potential targets: Streamlit Cloud, Docker, standalone Python executable

## Environment Configuration

**Required env vars:**
- None detected - No environment variables configured
- All settings hardcoded or provided via Streamlit UI inputs

**Secrets location:**
- No secrets management - No API keys, tokens, or credentials in use
- Stream URLs are public (no authentication needed)

**Configuration Files:**
- `d:\Git\Val-Prediciton-Model\config.py` - Game HUD coordinates and color thresholds

## Webhooks & Callbacks

**Incoming:**
- None detected

**Outgoing:**
- None detected

## System Dependencies & External Tools

**Tesseract-OCR:**
- External binary dependency (not Python package)
- Used for OCR text recognition from game interface
- Path: `C:\Program Files\Tesseract-OCR\tesseract.exe` (Windows)
- Configuration: `d:\Git\Val-Prediciton-Model\config.py` line 5

**OpenCV Video Codecs:**
- System video codec support (FFmpeg-based)
- OpenCV delegates to system libraries for stream decoding

## Data Flow

**Prediction Pipeline:**

1. User uploads VOD or live stream URL (Streamlit UI)
2. Streamlink extracts best-quality stream URL from platform
3. OpenCV reads video frames from stream
4. VCTVisionEngine analyzes frame:
   - OCR extracts scores using Tesseract
   - Color analysis detects spike status
   - Pixel sampling determines alive player counts
5. LogisticRegression model predicts win probability
6. Results displayed in Streamlit dashboard
7. JSON output written to `game_state.json`

## Broadcast Data Extraction

**Source:** VCT broadcast overlay (1920x1080 resolution)

**Extracted Via:**
- OCR (Tesseract): Scores, timers, credits
- Color detection (HSV): Spike planted indicator
- Pixel sampling: Player alive/dead status

**Coordinates (Hardcoded):**
- Score left: `[20:90, 830:890]`
- Score right: `[20:90, 1030:1090]`
- Timer: `[20:100, 930:990]`
- Spike area: `[80:120, 940:980]`
- Left team health bars: X=260
- Right team health bars: X=1660
- See `d:\Git\Val-Prediciton-Model\config.py` for complete coordinates

---

*Integration audit: 2026-02-12*
