# Technology Stack

**Project:** Valorant VCT Event Detection & Logging
**Researched:** 2026-02-12
**Research Mode:** Stack dimension (subsequent milestone)
**Overall Confidence:** MEDIUM (based on training data; verification needed with Context7/official docs)

## Executive Summary

This stack extends the existing Python CV pipeline (OpenCV + pytesseract + streamlink) with event detection, persistent storage, and enhanced OCR capabilities. Recommendations prioritize:
- **Incremental adoption** - extend existing stack, don't replace
- **Windows 11 compatibility** - avoid Unix-only dependencies
- **Local-first storage** - SQLite for structured events, no cloud dependencies
- **Training data collection focus** - storage optimized for ML pipeline consumption

**Critical recommendation:** Replace pytesseract with EasyOCR for better accuracy on game overlay text without Tesseract installation complexity on Windows.

---

## Recommended Stack

### OCR Engine (CRITICAL UPGRADE)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **EasyOCR** | 1.7.x+ | Game overlay text extraction (team names, agent names, map names) | Better accuracy than pytesseract on stylized game fonts, GPU-accelerated, no external Tesseract binary needed on Windows |

**Rationale:**
- pytesseract requires separate Tesseract installation (friction on Windows)
- Game overlays use custom fonts that Tesseract struggles with
- EasyOCR trained on synthetic data, handles stylized text better
- GPU acceleration via PyTorch (critical for real-time processing)
- Better bounding box detection for multi-region extraction

**Confidence:** MEDIUM (requires verification of current version and Windows GPU support)

**Installation:**
```bash
pip install easyocr
```

**Alternative considered:**
- **PaddleOCR**: Strong accuracy but heavier dependencies, less Windows-friendly
- **pytesseract**: Already in stack, but insufficient for game overlay text

---

### Event Storage & Logging

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **SQLite** | 3.40+ (via Python stdlib) | Primary event storage | Zero-config, ACID transactions, excellent query performance for training data retrieval |
| **SQLAlchemy** | 2.0.x+ | ORM & schema migration | Type-safe models, migration support via Alembic, simplifies event schema evolution |
| **Alembic** | 1.13.x+ | Database migrations | Schema versioning as features evolve |

**Rationale:**
- SQLite is built into Python, no server setup
- ACID guarantees prevent data loss during stream interruptions
- Indexing on timestamps enables efficient temporal queries for ML training
- SQLAlchemy provides migration path if scaling to PostgreSQL later
- Local-first aligns with project constraints

**Confidence:** HIGH (SQLite is stable, well-documented, proven for this use case)

**Schema suggestion:**
```python
# events table
- id (int, primary key)
- event_type (str) # 'round_start', 'team_win', 'agent_select', etc.
- timestamp (float) # epoch time
- stream_timestamp (str) # VOD timestamp for debugging
- confidence (float) # CV detection confidence
- data (JSON) # event-specific payload
- frame_hash (str) # for deduplication
```

**Why NOT Parquet:**
- Parquet is columnar, optimized for batch analytics
- Poor for incremental writes (live stream scenario)
- No transaction safety
- Use case: export to Parquet for ML training, store in SQLite

**Why NOT JSONL:**
- No query capabilities (must read entire file)
- No indexing
- No schema enforcement
- Use case: debugging/logging, not primary storage

---

### State Change Detection

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **python-statemachine** | 2.1.x+ | State machine for game phases | Explicit state transitions (menu → agent_select → in_game → post_round), prevents invalid state changes |
| **deepdiff** | 6.7.x+ | State diffing for complex objects | Detect changes in agent compositions, team rosters without manual field comparison |

**Rationale:**
- **python-statemachine**: Game state follows predictable FSM (finite state machine)
  - Prevents logging impossible transitions (e.g., post_round → agent_select without round_end)
  - Built-in event callbacks for state entry/exit
  - Visualizable state diagrams for debugging

- **deepdiff**: OCR results are nested dicts (teams, agents, scores)
  - Computes semantic diffs, not just `==` comparison
  - Returns what changed, simplifies event payload construction
  - Handles missing keys gracefully (OCR might fail on some frames)

**Confidence:** MEDIUM (requires verification of Windows compatibility and current API)

**Alternative pattern:**
Simple dict hashing for lightweight state tracking:
```python
import hashlib
import json

def state_hash(state_dict):
    return hashlib.md5(json.dumps(state_dict, sort_keys=True).encode()).hexdigest()
```
Use when full state machine overhead isn't needed.

---

### Timestamp Synchronization

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **Built-in time module** | stdlib | System timestamps | Sufficient for single-stream processing |
| **timecode** | 1.4.x+ | SMPTE timecode parsing | If stream provides timecodes, convert to frame-accurate timestamps |

**Rationale:**
- VCT broadcasts don't provide embedded timecodes, use system time
- Store both epoch timestamp (for sorting/querying) and stream offset (for VOD replay)
- `timecode` library useful if parsing VOD metadata later

**Confidence:** HIGH (standard practice for stream processing)

**Timestamp strategy:**
```python
import time

event = {
    'timestamp': time.time(),  # epoch, for DB queries
    'stream_offset': current_frame / fps,  # relative to stream start
    'frame_number': current_frame  # for debugging
}
```

---

### Frame Processing Pipeline

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **OpenCV (cv2)** | 4.9.x+ | Frame capture & preprocessing | Already in stack, keep |
| **NumPy** | 1.26.x+ | Array operations | Already in stack, keep |
| **scikit-image** | 0.22.x+ | Advanced preprocessing (denoising, contrast) | Better than OpenCV for adaptive preprocessing before OCR |
| **imutils** | 0.5.x+ | Convenience wrappers for OpenCV | Simplifies common operations (resize, rotate, etc.) |

**Rationale:**
- Keep existing OpenCV pipeline
- Add scikit-image for OCR preprocessing (CLAHE, bilateral filtering improve text detection)
- imutils reduces boilerplate

**Confidence:** HIGH (well-established Python CV ecosystem)

**Preprocessing pipeline for OCR:**
```python
import cv2
from skimage import exposure

def preprocess_for_ocr(frame, region):
    roi = frame[region[1]:region[3], region[0]:region[2]]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    # Adaptive histogram equalization
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    # Denoise
    denoised = cv2.fastNlMeansDenoising(enhanced)
    return denoised
```

---

### Configuration Management

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **pydantic** | 2.5.x+ | Settings validation | Type-safe config, validation at startup, env var support |
| **python-dotenv** | 1.0.x+ | Environment variables | Local config without hardcoding |

**Rationale:**
- Regions of interest (ROIs) for OCR are config, not code
- Pydantic validates on load, prevents runtime errors from bad config
- `.env` for local overrides (different stream URLs, debug modes)

**Confidence:** HIGH (standard Python practice)

**Config example:**
```python
from pydantic import BaseModel
from pydantic_settings import BaseSettings

class OCRRegion(BaseModel):
    name: str
    x: int
    y: int
    width: int
    height: int

class Settings(BaseSettings):
    stream_url: str
    database_path: str = "events.db"
    ocr_regions: list[OCRRegion]

    class Config:
        env_file = ".env"
```

---

### Deduplication & Caching

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **diskcache** | 5.6.x+ | Frame result caching | Avoid re-OCR-ing identical frames (stream buffering causes duplicates) |
| **imagehash** | 4.3.x+ | Perceptual hashing | Detect near-duplicate frames (compression artifacts) |

**Rationale:**
- Streams have buffering/keyframe repeats
- OCR is expensive (100-200ms/frame with GPU)
- Cache OCR results keyed by perceptual hash
- `diskcache` persists across runs, unlike `functools.lru_cache`

**Confidence:** MEDIUM (requires validation of current versions)

**Usage:**
```python
import imagehash
from PIL import Image
from diskcache import Cache

cache = Cache('.cache')

def get_cached_ocr(frame):
    pil_img = Image.fromarray(frame)
    hash_key = str(imagehash.phash(pil_img))

    if hash_key in cache:
        return cache[hash_key]

    result = perform_ocr(frame)
    cache[hash_key] = result
    return result
```

---

### Logging & Monitoring

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **loguru** | 0.7.x+ | Application logging | Better DX than stdlib logging, automatic rotation, colored output |
| **tqdm** | 4.66.x+ | Progress bars | Visual feedback during live processing |

**Rationale:**
- `loguru` simplifies logging setup, handles file rotation automatically
- `tqdm` shows frames/sec, events/sec for monitoring pipeline health

**Confidence:** HIGH (widely used)

---

## Installation

```bash
# Core dependencies (extend existing requirements.txt)

# OCR upgrade
pip install easyocr

# Event storage
pip install sqlalchemy alembic

# State management
pip install python-statemachine deepdiff

# Frame processing enhancements
pip install scikit-image imutils

# Configuration
pip install pydantic pydantic-settings python-dotenv

# Deduplication
pip install diskcache imagehash pillow

# Logging
pip install loguru tqdm

# Timestamp utilities (optional)
pip install timecode
```

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| OCR | EasyOCR | PaddleOCR | Heavier dependencies, less Windows support |
| OCR | EasyOCR | pytesseract | Poor accuracy on game fonts, Windows install friction |
| Storage | SQLite + SQLAlchemy | PostgreSQL | Overkill for local-first, requires server setup |
| Storage | SQLite | Parquet | No incremental writes, no ACID |
| Storage | SQLite | JSONL | No queries, no indexes |
| State Diffing | deepdiff | Manual comparison | Brittle, hard to maintain |
| State Machine | python-statemachine | Manual FSM | Reinventing wheel, no validation |
| Caching | diskcache | Redis | Requires server, overkill for single-node |
| Config | pydantic | ConfigParser | No validation, no type safety |

---

## Architecture Notes

### Data Flow

```
Stream (streamlink)
  ↓
Frame Buffer (OpenCV)
  ↓
ROI Extraction (config-driven)
  ↓
Preprocessing (scikit-image)
  ↓
OCR (EasyOCR) → Cache (diskcache + imagehash)
  ↓
State Diffing (deepdiff)
  ↓
State Machine (python-statemachine)
  ↓
Event Logging (SQLite via SQLAlchemy)
```

### Storage Schema

**events table:**
```sql
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    timestamp REAL NOT NULL,
    stream_offset REAL,
    frame_number INTEGER,
    confidence REAL,
    data JSON,
    frame_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_event_type ON events(event_type);
CREATE INDEX idx_timestamp ON events(timestamp);
CREATE INDEX idx_frame_hash ON events(frame_hash);
```

**ocr_cache table (optional, if not using diskcache):**
```sql
CREATE TABLE ocr_cache (
    frame_hash TEXT PRIMARY KEY,
    result JSON,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Windows 11 Compatibility Notes

**EasyOCR GPU support:**
- Requires CUDA-compatible GPU + PyTorch with CUDA support
- Install: `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118`
- Fallback: CPU mode works but slower (300-500ms/frame vs 100-200ms)

**SQLite:**
- Built into Python, no issues

**Path handling:**
- Use `pathlib.Path` for cross-platform paths
- SQLite connection strings: `sqlite:///C:/path/to/db.sqlite` (forward slashes work on Windows)

---

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Frame processing | 30 FPS | Match stream rate (1920x1080 @ 30fps typical for VCT) |
| OCR latency | <200ms/frame | GPU-accelerated EasyOCR |
| Event write latency | <10ms | SQLite local writes |
| Cache hit rate | >80% | With perceptual hashing |

---

## Migration Path

**From current stack:**
1. Add SQLAlchemy models alongside existing code
2. Initialize SQLite database with Alembic
3. Wrap pytesseract calls with EasyOCR (same interface)
4. Add state machine for phase transitions
5. Integrate deepdiff for state change detection
6. Add diskcache for OCR results

**Backward compatibility:**
- Keep existing streamlink + OpenCV pipeline
- SQLite files are portable (copy for backup)
- Configuration via pydantic won't break existing code

---

## Critical Dependencies

**Must verify versions (MEDIUM confidence):**
- EasyOCR 1.7.x (check Windows GPU support)
- SQLAlchemy 2.0.x (verify migration guide from 1.4)
- python-statemachine 2.1.x (check API stability)
- deepdiff 6.7.x (verify performance on large state dicts)

**Verification needed:**
- Context7 for EasyOCR, SQLAlchemy current versions
- Official docs for Windows GPU setup (PyTorch + CUDA)
- Benchmark EasyOCR vs pytesseract on actual VCT screenshots

---

## Anti-Patterns to Avoid

**Do NOT:**
- Use MongoDB/NoSQL for events (overkill, worse query performance than SQLite)
- Use Pandas for real-time event storage (memory overhead, not transactional)
- Use multiprocessing for OCR (GPU contention, diminishing returns)
- Use asyncio unless proven bottleneck (adds complexity, OpenCV is sync)
- Store raw frames in database (use frame hashes, reference video files separately)
- Use ORMs other than SQLAlchemy (less migration support)

**Do:**
- Batch OCR requests if EasyOCR supports it (reduces GPU overhead)
- Use connection pooling if processing multiple streams (not needed for single stream)
- Validate OCR results before logging events (confidence thresholding)
- Write unit tests for state machine transitions
- Export to Parquet for ML training (after collection in SQLite)

---

## Open Questions (require phase-specific research)

1. **EasyOCR model selection:** Which pre-trained model works best for Valorant UI? (requires testing on actual frames)
2. **OCR ROI optimization:** Exact bounding boxes for team names, agent icons, map name (requires frame analysis)
3. **State machine complexity:** How many states needed? (requires domain analysis of VCT match phases)
4. **Event taxonomy:** Complete list of event types (requires VCT broadcast structure research)
5. **GPU memory limits:** Can EasyOCR + OpenCV coexist on consumer GPU? (requires hardware testing)

---

## Sources

**Confidence levels:**
- HIGH: Standard Python ecosystem (SQLite, NumPy, OpenCV)
- MEDIUM: Library-specific recommendations based on training data (requires Context7 verification)
- LOW: Performance claims (require benchmarking on actual VCT streams)

**Verification needed (Context7 or official docs):**
- EasyOCR: https://github.com/JaidedAI/EasyOCR
- SQLAlchemy 2.0: https://docs.sqlalchemy.org/
- python-statemachine: https://python-statemachine.readthedocs.io/
- deepdiff: https://zepworks.com/deepdiff/
- diskcache: http://www.grantjenks.com/docs/diskcache/

**Critical:** All version numbers and API claims must be verified before implementation.
