# Architecture Patterns: VLR.gg Scraping and Scaled Processing

**Domain:** Data pipeline scaling for VCT match prediction
**Researched:** 2026-02-14
**Confidence:** HIGH

## Executive Summary

The v3 data scaling pipeline integrates VLR.gg scraping with existing Valoscribe processing and prediction infrastructure. The architecture adds 5 new components while preserving existing data flows. Key insight: treat VLR.gg scraping as **discovery layer** (what to process) and Valoscribe as **transformation layer** (VOD → events), with the existing prediction pipeline remaining unchanged downstream.

**Integration strategy:** Separate output directories (existing 71 maps vs. new scraped maps) until feature engineering, then merge at dataset level. This preserves existing experiments while scaling.

## Current Architecture (v2 Baseline)

### Data Flow
```
Valoscribe VOD → JSONL events → Data loader → Feature pipeline → Model → Predictions
                  (manual)        (src/data)    (src/features)   (src/modeling)
```

### Component Inventory
| Component | Location | Responsibility | Inputs | Outputs |
|-----------|----------|---------------|--------|---------|
| **Valoscribe** | D:\Git\valoscribe | VOD processing (CV + OCR) | YouTube URL, metadata.json | events.jsonl, frames.csv, metadata.json |
| **Data Loader** | src/data/loader.py | Discover and load maps | Valoscribe output dir | MapData objects |
| **Feature Pipeline** | src/features/pipeline.py | Extract features | MapData list | DataFrame (features + target) |
| **Feature Registry** | src/features/registry.py | Named feature sets | YAML config | Feature name lists |
| **Model Trainer** | src/modeling/baseline.py | Train models | X, y, groups | Trained model + metrics |
| **Experiment Runner** | src/modeling/experiment.py | Full pipeline orchestration | Config, data | Experiment results |
| **Series Predictor** | src/modeling/series.py | BO3/BO5 predictions | Map probabilities | Series probabilities |

### Data Formats
```
Valoscribe output:
  {map_id}/
    events.jsonl      # One event per line (JSON objects)
    frames.csv        # Per-frame state snapshots
    metadata.json     # Teams, map name, date, validation results

Feature pipeline:
  DataFrame columns: map_id, [34 features], map_winner, series_id

Experiment results:
  JSON: cv_results, shap_analysis, thesis_validation, calibration_validation
```

## New Architecture (v3 Extension)

### Enhanced Data Flow
```
VLR.gg event page → VLREventScraper → Manifest (VODRecords) → VODOrchestrator
                     (discover)         (state tracking)       (batch process)
                                                                     ↓
                    ┌────────────────────────────────────────────────┘
                    ↓
        Valoscribe (batch) → JSONL events → DatasetBuilder → Feature pipeline → Model
         (process VODs)       (per map)       (merge sources)   (existing)      (existing)
```

### New Components

#### 1. VLREventScraper (Discovery Layer)
**File:** `src/scraping/vlr_events.py`
**Responsibility:** Discover match URLs and VOD metadata from VLR.gg tournament pages

**Key methods:**
- `discover_match_urls(event_url)` → List of match URLs
- `discover_vods(event_url, manifest, tournament_name)` → Count of new VODs added

**Integration point:** Calls Valoscribe's `scrape_match()` to extract per-match metadata (teams, maps, YouTube URLs)

**Data flow:**
```
VLR.gg event URL → BeautifulSoup scraping → Match URLs
                                                ↓
                    Valoscribe scrape_match() → Match metadata (teams, maps, VOD URLs)
                                                ↓
                                      VODRecord creation → Manifest
```

**Rate limiting:** 1.5 seconds between requests (polite to VLR.gg servers)

#### 2. ProcessingManifest (State Management)
**File:** `src/scraping/manifest.py`
**Responsibility:** Track VOD processing state across runs (resumable)

**Key structures:**
```python
@dataclass
class VODRecord:
    vod_id: str                  # "{vlr_match_id}_map{N}"
    youtube_url: str
    vlr_match_url: str
    teams: list[str]
    map_name: str
    map_number: int
    tournament: str
    date: str
    patch_version: str | None
    status: StatusType           # pending/downloading/processing/complete/failed/skipped
    map_id: str | None           # Valoscribe output directory name
    error_message: str | None
    retry_count: int
    # Timestamps for progress tracking
    created_at: str
    started_at: str | None
    completed_at: str | None
    processing_time_seconds: float | None
```

**Persistence:** Atomic JSON writes (temp file + rename) to prevent corruption on crash

**Integration point:** Updated by VODOrchestrator after each status change (downloading → processing → complete)

#### 3. VODOrchestrator (Batch Processor)
**File:** `src/scraping/orchestrator.py`
**Responsibility:** Orchestrate VOD downloading → Valoscribe processing → cleanup

**Pipeline stages:**
1. **Discovery:** Call VLREventScraper to populate manifest
2. **Download:** Call Valoscribe download command (wraps yt-dlp)
3. **Process:** Call Valoscribe orchestrate process-vod
4. **Cleanup:** Delete downloaded VOD files (multi-GB)

**Key method:**
```python
process_single_vod(record: VODRecord) -> bool:
    1. Update manifest: status = "downloading"
    2. Scrape series metadata from VLR.gg (if not cached)
    3. Download VOD via Valoscribe download command
    4. Update manifest: status = "processing"
    5. Process VOD through Valoscribe orchestrate process-vod
    6. Update manifest: status = "complete", map_id = output_dir_name
    7. Delete VOD file (save disk space)
    8. Rate limit delay before next VOD
```

**Error handling:** Retry with exponential backoff, skip after max retries, atomic manifest saves

**Integration point:** Calls Valoscribe CLI as subprocess, outputs to separate directory (`data/processing/processed/`)

#### 4. ProcessingConfig (Configuration)
**File:** `src/scraping/config.py`
**Responsibility:** Environment-based configuration for pipeline

**Key settings:**
```python
valoscribe_repo: Path = "D:/Git/valoscribe"
output_dir: Path = "data/processing/processed"  # Separate from existing 71 maps
download_dir: Path = "data/processing/downloads"
manifest_path: Path = "data/processing/manifest.json"
metadata_dir: Path = "data/processing/metadata"

download_delay_seconds: float = 10.0        # YouTube rate limiting
processing_timeout_seconds: int = 7200      # 2 hours per VOD
max_retries: int = 2
delete_vod_after_processing: bool = True
```

**Integration point:** Loaded by orchestrator and scraper for paths and timeouts

#### 5. DatasetBuilder (Merge Layer)
**File:** `src/data/builder.py` (NEW - to be created in v3)
**Responsibility:** Merge existing maps + newly scraped maps into unified dataset

**Proposed interface:**
```python
class DatasetBuilder:
    def __init__(self,
                 existing_maps_dir: Path,      # D:\Git\valoscribe\data\processed (71 maps)
                 new_maps_dir: Path,           # data/processing/processed (scraped maps)
                 manifest: ProcessingManifest):
        """Discover maps from multiple sources."""

    def build_combined_dataset(self,
                               feature_set: str,
                               quality_threshold: float = 0.8) -> pd.DataFrame:
        """Load all maps, filter by quality, extract features."""
        # 1. Discover maps from both directories
        # 2. Load with existing loader (src/data/loader.py)
        # 3. Filter by quality score
        # 4. Extract features via FeaturePipeline
        # 5. Add metadata: source (existing vs. scraped), tournament, date
        # 6. Return unified DataFrame ready for experiments
```

**Integration point:** Called by experiment runners to get training data

**Why separate from existing loader:** Existing loader assumes single directory, minimal changes preserves v2 experiments

## Integration Points

### 1. Valoscribe Integration (External Dependency)

**Current interface:**
- Valoscribe lives at `D:\Git\valoscribe`
- Actively developed alongside this repo
- Provides VLRScraper for match page scraping

**New interface requirements:**
```bash
# 1. Download VOD (wraps yt-dlp)
python -m valoscribe download <YOUTUBE_URL> --output <DIR> --overwrite

# 2. Scrape match metadata (NEW in v3 - may need to add)
python -m valoscribe scrape-vlr <VLR_MATCH_URL> --output <METADATA_FILE>

# 3. Split series metadata into per-map files (NEW in v3)
python -m valoscribe split-metadata <SERIES_JSON> --output-dir <MAP_METADATA_DIR>

# 4. Process single VOD with metadata
python -m valoscribe orchestrate process-vod <VOD_FILE> <MAP_METADATA_FILE> --output <DIR> --quiet
```

**What exists:** Commands 1 and 4 likely exist (download + process-vod)
**What needs verification:** Commands 2 and 3 (scraping + splitting) may need to be added to Valoscribe CLI

**Risk mitigation:** Valoscribe is actively developed alongside this repo. If CLI commands don't exist, we add them to Valoscribe (single source of truth for VOD processing).

### 2. Data Loader Integration (Minimal Changes)

**Current behavior:**
- `discover_maps(data_dir)` scans single directory
- Returns `{map_id: Path}` dict
- `load_all_maps(data_dir)` loads from discovered maps

**New behavior (proposed in DatasetBuilder):**
```python
# Load from multiple directories
existing_maps = discover_maps(Path("D:/Git/valoscribe/data/processed"))
new_maps = discover_maps(Path("data/processing/processed"))
all_maps = {**existing_maps, **new_maps}  # Merge dicts

# Load with existing loader (no changes needed)
results = load_all_maps_from_dict(all_maps)  # Pass pre-discovered map dict
```

**Why minimal change:** Existing loader has `load_map(map_dir)` that works on single map. Just call it on merged dict.

### 3. Feature Pipeline Integration (No Changes)

**Current behavior:**
- `FeaturePipeline.extract_map_dataset(map_data_list)` → DataFrame
- Works on list of MapData objects (agnostic to source)

**New behavior:**
- Same interface, just receives larger `map_data_list` (existing 71 + new scraped maps)

**Why no change:** Feature pipeline is already decoupled from data source

### 4. Experiment Runner Integration (Minor Config Change)

**Current behavior:**
- Experiments read from single data directory via environment variable
- Scripts like `run_real_experiment.py` hardcode `VALOSCRIBE_DATA_DIR`

**New behavior:**
```python
# In experiment script
from src.data.builder import DatasetBuilder

builder = DatasetBuilder(
    existing_maps_dir=Path("D:/Git/valoscribe/data/processed"),
    new_maps_dir=Path("data/processing/processed"),
    manifest=ProcessingManifest(Path("data/processing/manifest.json"))
)

df = builder.build_combined_dataset(
    feature_set="full",
    quality_threshold=0.8
)

# Rest of experiment unchanged
```

**Why minor change:** DatasetBuilder encapsulates multi-source loading, experiment runner just calls it instead of manual loading

## Directory Structure

### Before (v2)
```
D:\Git\
├── Val-Prediciton-Model\
│   ├── src/
│   │   ├── data/         # Loader for Valoscribe output
│   │   ├── features/     # Feature extraction
│   │   ├── modeling/     # Models and experiments
│   ├── scripts/
│   │   └── run_real_experiment.py
│   └── experiments/      # Experiment results
│
└── valoscribe\
    ├── data/
    │   └── processed/    # 71 maps (existing)
    │       ├── {map_id_1}/
    │       │   ├── events.jsonl
    │       │   ├── frames.csv
    │       │   └── metadata.json
    │       └── {map_id_2}/
    │           └── ...
    └── src/
        └── scraper/
            └── vlr_scraper.py  # Match page scraping
```

### After (v3)
```
D:\Git\
├── Val-Prediciton-Model\
│   ├── src/
│   │   ├── data/
│   │   │   ├── loader.py       # Existing (unchanged)
│   │   │   ├── builder.py      # NEW - multi-source dataset builder
│   │   │   └── ...
│   │   ├── features/           # Existing (unchanged)
│   │   ├── modeling/           # Existing (unchanged)
│   │   ├── scraping/           # NEW
│   │   │   ├── __init__.py
│   │   │   ├── vlr_events.py   # VLR.gg event page scraper
│   │   │   ├── manifest.py     # State tracking
│   │   │   ├── orchestrator.py # Batch processor
│   │   │   └── config.py       # Configuration
│   │   └── ...
│   ├── scripts/
│   │   ├── run_real_experiment.py  # Updated to use DatasetBuilder
│   │   ├── expand_dataset.py       # NEW - CLI for scraping + processing
│   │   └── summarize_progress.py   # NEW - Read manifest and print stats
│   ├── data/
│   │   └── processing/         # NEW - separate from existing maps
│   │       ├── manifest.json   # VOD processing state
│   │       ├── downloads/      # Temporary VOD files (deleted after)
│   │       ├── metadata/       # VLR.gg match metadata cache
│   │       └── processed/      # Valoscribe output (new maps)
│   │           ├── {vod_id_1}/ # Format: "{match_id}_map{N}"
│   │           │   ├── events.jsonl
│   │           │   ├── frames.csv
│   │           │   └── metadata.json
│   │           └── {vod_id_2}/
│   │               └── ...
│   └── experiments/
│
└── valoscribe\
    ├── data/
    │   └── processed/    # 71 maps (existing, preserved)
    │       └── ...
    └── src/
        └── scraper/
            └── vlr_scraper.py  # Used by Val-Prediction-Model scraping
```

## Data Flow Diagrams

### Discovery Flow (New)
```
User specifies VLR.gg event URL
        ↓
VLREventScraper.discover_match_urls()
        ↓
For each match URL:
    ↓
    Valoscribe scrape_match()  [external call]
        ↓
    Extract: teams, maps, VOD URLs, tournament
        ↓
    Create VODRecord for each map with VOD
        ↓
    Add to ProcessingManifest
        ↓
    Manifest.save() [atomic JSON write]
```

### Processing Flow (New)
```
VODOrchestrator.run_pipeline()
        ↓
For each pending VOD in manifest:
    ↓
    1. Update status: "downloading"
    ↓
    2. Valoscribe download (YouTube URL → .mp4)
    ↓
    3. Update status: "processing"
    ↓
    4. Valoscribe orchestrate process-vod (.mp4 + metadata → events.jsonl)
    ↓
    5. Update status: "complete", set map_id
    ↓
    6. Delete .mp4 file (save disk)
    ↓
    7. Manifest.save() [atomic]
        ↓
        Continue to next VOD
```

### Training Flow (Modified)
```
Experiment runner
        ↓
DatasetBuilder.build_combined_dataset()  [NEW component]
        ↓
    Discover maps from:
        - D:\Git\valoscribe\data\processed (existing 71)
        - data/processing/processed (new scraped)
        ↓
    Load all maps via existing loader
        ↓
    Filter by quality score (existing quality module)
        ↓
    Extract features via existing FeaturePipeline
        ↓
    Return unified DataFrame
        ↓
Existing experiment pipeline (unchanged)
    ↓
Train model, evaluate, calibrate, explain
```

## Build Order Recommendation

Based on dependencies and risk, suggested phase structure:

### Phase 1: Scraping Infrastructure
**Why first:** No dependencies, can validate VLR.gg scraping independently

**Components:**
- `src/scraping/manifest.py` - State tracking (standalone, testable)
- `src/scraping/config.py` - Configuration (simple, no dependencies)
- `src/scraping/vlr_events.py` - VLR.gg scraper (depends on Valoscribe scrape_match)

**Validation:** Scrape 1-2 VLR.gg events, verify manifest persists correctly

**Risk:** LOW - self-contained, no impact on existing code

### Phase 2: Valoscribe CLI Integration
**Why second:** Required by orchestrator, may need Valoscribe changes

**Components:**
- Verify/add Valoscribe CLI commands: `scrape-vlr`, `split-metadata`, `download`, `process-vod`
- Test download + process pipeline on 1 VOD

**Validation:** Manually call Valoscribe commands, verify output format matches expectations

**Risk:** MEDIUM - depends on Valoscribe changes (active development, but external)

### Phase 3: Orchestration Pipeline
**Why third:** Depends on scraping + Valoscribe CLI

**Components:**
- `src/scraping/orchestrator.py` - Batch processor
- `scripts/expand_dataset.py` - CLI entry point
- `scripts/summarize_progress.py` - Progress monitoring

**Validation:** Process 3-5 VODs end-to-end, verify resumability (kill + restart)

**Risk:** MEDIUM - integration complexity, but well-isolated from existing code

### Phase 4: Dataset Merging
**Why fourth:** Can defer until training, doesn't block scraping

**Components:**
- `src/data/builder.py` - Multi-source dataset builder
- Update experiment scripts to use DatasetBuilder

**Validation:** Load existing 71 maps + 3-5 new maps, verify feature extraction works

**Risk:** LOW - thin wrapper over existing loader

### Phase 5: Scaled Processing
**Why last:** Validate pipeline at small scale first

**Components:**
- Process 50+ VODs through pipeline
- Monitor for failures, disk space, rate limits

**Validation:** Process 150+ maps, run experiments on combined dataset (71 existing + 150 new)

**Risk:** LOW - operational scale, no code changes

## Suggested Component Boundaries

### Clean Interfaces

**VLREventScraper → Manifest:**
```python
# Discovery returns list of VODRecords
vod_records = scraper.discover_vods(event_url, manifest, tournament_name)
# Scraper is read-only, manifest handles persistence
```

**Manifest → VODOrchestrator:**
```python
# Orchestrator queries manifest for work
pending_vods = manifest.get_pending()
# Orchestrator updates status after each step
manifest.update_status(vod_id, "processing", started_at=timestamp)
```

**VODOrchestrator → Valoscribe:**
```python
# Orchestrator calls Valoscribe via subprocess
subprocess.run(["python", "-m", "valoscribe", "download", url, "--output", dir])
# Output: Valoscribe writes to disk, orchestrator reads output path
```

**DatasetBuilder → Existing Pipeline:**
```python
# Builder provides unified DataFrame
df = builder.build_combined_dataset(feature_set="full")
# Experiment runner receives same interface as before (just bigger DataFrame)
```

### Separation of Concerns

| Component | Knows About | Does NOT Know About |
|-----------|-------------|---------------------|
| VLREventScraper | VLR.gg HTML, Valoscribe scrape_match | Valoscribe processing, feature extraction |
| Manifest | VOD metadata, processing status | Valoscribe CLI, feature engineering |
| VODOrchestrator | Valoscribe CLI, manifest state | Feature extraction, model training |
| DatasetBuilder | Valoscribe output format, quality filtering | Scraping, downloading |
| Feature Pipeline | MapData schema | VLR.gg, manifest, scraping |
| Model Trainer | DataFrame format | Valoscribe, scraping, data sources |

### Anti-Pattern: Tight Coupling

**Bad (don't do this):**
```python
# VODOrchestrator directly importing FeaturePipeline
class VODOrchestrator:
    def process_vod(self, record):
        # ... download and process ...
        features = FeaturePipeline().extract_features(...)  # WRONG - too coupled
```

**Good (separation):**
```python
# VODOrchestrator focuses on processing
class VODOrchestrator:
    def process_vod(self, record):
        # ... download and process ...
        return map_id  # Just return output location

# Feature extraction happens separately in experiment runner
builder = DatasetBuilder(...)
df = builder.build_combined_dataset(...)  # Reads processed maps, extracts features
```

## Scalability Considerations

### At 100 Maps (Current + Immediate)
- **Storage:** ~500MB (events.jsonl + metadata), negligible
- **Processing time:** ~2 hours per VOD × 30 VODs = 60 hours (2.5 days continuous)
- **Approach:** Sequential processing, single output directory, existing loader works

### At 500 Maps (v3 Target)
- **Storage:** ~2.5GB events, manageable
- **Processing time:** ~150 hours (6 days continuous)
- **Approach:** Still sequential, may batch-process overnight, manifest enables resume
- **New concern:** Feature extraction time increases (500 maps × 0.1s = 50s, still fast)

### At 2000 Maps (Future v4+)
- **Storage:** ~10GB events, still local-friendly
- **Processing time:** ~600 hours (25 days continuous)
- **Approach:** Consider parallel Valoscribe processing (multiple GPUs), multi-machine
- **New concern:** Feature extraction may need Parquet caching, incremental updates

**Current architecture supports up to 500 maps without changes.** Beyond that, consider:
- Parallel Valoscribe processing (requires GPU coordination)
- Incremental feature extraction (cache features per map, update on new data)
- Distributed storage (S3/GCS for processed maps)

## Risk Areas and Mitigation

### Risk 1: Valoscribe CLI Interface Changes
**What:** Valoscribe is actively developed, CLI may not match assumptions

**Mitigation:**
- Phase 2 validates Valoscribe CLI early
- Document exact Valoscribe commit hash used
- Pin Valoscribe version in requirements or use git submodule
- If commands don't exist, add them to Valoscribe (we control both repos)

### Risk 2: VLR.gg HTML Structure Changes
**What:** VLR.gg updates site, scraper breaks

**Mitigation:**
- VLREventScraper includes error handling for missing elements
- Manifest tracks scraping failures separately from processing failures
- Build test suite with saved HTML snapshots
- Monitor error rates in manifest (spike = site changed)

### Risk 3: Manifest Corruption
**What:** Python crashes during JSON write, manifest corrupted

**Mitigation:**
- Atomic write pattern (temp file + rename)
- Daily backups of manifest (copy to `manifest.YYYYMMDD.json`)
- Validate JSON on load, fallback to backup if corrupt

### Risk 4: Disk Space Exhaustion
**What:** VODs are multi-GB, processing 100+ fills disk

**Mitigation:**
- Delete VOD immediately after successful processing
- `try/finally` ensures cleanup even on errors
- Check free disk space before download (refuse if <50GB)
- Log disk usage in manifest summary

### Risk 5: YouTube Rate Limiting
**What:** YouTube detects bot, throttles or blocks

**Mitigation:**
- 10-second delay between downloads (configured in ProcessingConfig)
- Use Valoscribe's yt-dlp wrapper (handles anti-bot measures)
- Process overnight to spread requests over time
- Monitor for HTTP 429 errors, increase delay if detected

## Testing Strategy

### Unit Tests
- `manifest.py`: Atomic saves, status updates, query methods
- `vlr_events.py`: Match URL parsing (with saved HTML fixtures)
- `config.py`: Environment variable loading

### Integration Tests
- `orchestrator.py`: Mock Valoscribe subprocess calls, verify state transitions
- `builder.py`: Load from multiple directories, merge datasets

### End-to-End Tests
- Process 1 VOD through full pipeline (scrape → download → process → load)
- Verify output matches Valoscribe format
- Kill orchestrator mid-processing, verify resume works

### Operational Validation
- Process 3-5 VODs, check manifest status
- Run experiment on combined dataset (existing + new)
- Verify log loss doesn't degrade (sanity check on data quality)

## Sources

**HIGH confidence (architecture patterns validated):**
- Existing v2 codebase: src/data/loader.py, src/features/pipeline.py, src/modeling/experiment.py
- Valoscribe integration: D:\Git\valoscribe (active development, we control it)
- Phase 7 research: .planning/phases/07-dataset-expansion/07-RESEARCH.md (yt-dlp, BeautifulSoup, subprocess patterns)

**MEDIUM confidence (integration points inferred):**
- Valoscribe CLI commands: Assumed based on typical CLI patterns, must verify in Phase 2
- VLR.gg scraping: HTML structure must be validated against live pages

**No LOW confidence items** - all architectural decisions based on existing code or verified patterns.
