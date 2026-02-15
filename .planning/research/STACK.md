# Technology Stack

**Project:** Val-Prediction-Model v3 Data Scaling
**Researched:** 2026-02-14
**Confidence:** HIGH

## Executive Summary

v3 adds three new capabilities to the existing prediction framework: VLR.gg web scraping, scaled VOD processing (150+ maps), and large-scale experiment orchestration. The stack additions are minimal and focused:

- **Web scraping:** BeautifulSoup4 + lxml + httpx (already have BS4/lxml, add httpx)
- **Rate limiting:** pyrate-limiter for VLR.gg politeness
- **Progress tracking:** tqdm for long-running VOD processing visibility
- **Experiment orchestration:** Built-in concurrent.futures + joblib (already have joblib via sklearn)
- **Local tracking:** SQLite (stdlib) for experiment metadata, no MLflow needed yet

**Anti-recommendation:** Do NOT add heavyweight orchestration (Airflow, Prefect, Metaflow). The scale (150 maps, 4-8 experiments) does not justify orchestration complexity. Use simple Python multiprocessing.

## Recommended Stack Additions

### Web Scraping (VLR.gg)

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| httpx | 0.28.1 | Async HTTP client | Modern requests alternative with async support for concurrent scraping; sync/async APIs |
| pyrate-limiter | 4.0.2 | Rate limiting | Leaky bucket algorithm, prevents request flooding; VLR.gg has no robots.txt but community recommends 1 req/sec |
| tqdm | 4.67.3 | Progress bars | Visual feedback for long VOD processing batches; 60ns overhead, no dependencies |

**Already installed (requirements.txt lines 16-18):**
- beautifulsoup4 >= 4.13 (current: 4.14.3)
- lxml >= 5.0 (current: 6.0.2)
- requests >= 2.32

**Rationale:**
- **httpx over requests:** Async support enables concurrent VLR.gg page fetching (match pages, player stats, VOD links) without blocking. Both sync and async APIs mean gradual migration path.
- **pyrate-limiter over ratelimit:** More recent (Jan 2026 release), production-stable, supports multiple rate limits (e.g., 1/sec + 100/min).
- **BeautifulSoup over Scrapy:** VLR.gg scraping is ~100-200 pages (match results + metadata), not thousands. BS4 simplicity wins over Scrapy's learning curve for this scale.
- **lxml parser:** Already installed. Fastest BS4 parser, recommended for production.

### Progress Tracking

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| tqdm | 4.67.3 | Progress bars | VOD processing runs 15-20 hours; tqdm provides ETA, no dependencies, works with joblib |

**Integration:** Wrap joblib.Parallel with tqdm for per-VOD progress during batch processing.

### Parallel Processing

**No new libraries needed.** Use existing stack:

| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| joblib | 1.5.3 (transitive from sklearn) | Parallel map processing | Already installed via scikit-learn |
| concurrent.futures | stdlib | Experiment orchestration | Built into Python 3.11 |

**Rationale:**
- **joblib for VOD processing:** Already installed. Loky backend bypasses GIL, 6-10x speedup on CPU-bound tasks. Excellent for parallelizing Valoscribe VOD processing (independent map processing).
- **concurrent.futures for experiments:** ThreadPoolExecutor for I/O-bound experiment result aggregation, ProcessPoolExecutor for CPU-bound model training. No external dependencies.
- **Why NOT Metaflow/Airflow/Prefect:** Orchestration overhead unjustified. 150 maps = ~20 hours of embarrassingly parallel processing. 4-8 experiments = simple loop. No DAG complexity, no scheduling, no distributed compute.

### Experiment Tracking

**Use SQLite (stdlib), NOT MLflow.**

| Library | Version | Purpose | Why |
|---------|---------|---------|--------|
| sqlite3 | stdlib (SQLite 3.51.2) | Experiment metadata | Built-in, local-first, 150 maps = ~1MB database |

**Schema:**
```sql
-- experiments table: config, timestamp, status
-- results table: experiment_id, metric, value
-- artifacts table: experiment_id, file_path
```

**Rationale:**
- **SQLite over MLflow:** MLflow adds dependencies (Flask, gunicorn, SQLAlchemy, protobuf). Experiment tracking needs: (1) metadata persistence, (2) comparison queries. SQLite handles both with zero dependencies.
- **When to add MLflow:** If v4 adds live trading and needs model registry + versioning + deployment tracking. Not needed for v3 (validating edge on historical data).
- **DVC:** Deferred. DVC excels at GB+ dataset versioning. Valoscribe JSONL is ~50-100MB total. Git LFS would suffice if versioning needed, but v3 focuses on expanding dataset, not versioning iterations.

## Stack Already Installed

From requirements.txt (validated capabilities, DO NOT change):

### Core ML/Data Science

| Library | Version | Purpose | v3 Usage |
|---------|---------|---------|----------|
| scikit-learn | (installed) | Logistic regression, CV | Existing model pipeline |
| xgboost | >= 3.0 | Gradient boosting | Existing model pipeline |
| optuna | >= 3.0 | Bayesian hyperparameter tuning | Ablation studies |
| pandas | (installed) | DataFrame operations | Feature engineering |
| numpy | (installed) | Numerical computing | Feature engineering |
| scipy | >= 1.11 | Statistical functions | Evaluation metrics |
| shap | >= 0.45.0 | Model explainability | SHAP importance |
| matplotlib | >= 3.8.0 | Visualization | Calibration plots |

### Data Processing

| Library | Version | Purpose | v3 Usage |
|---------|---------|---------|----------|
| pydantic | >= 2.0 | Data validation | Schema validation |
| pyarrow | >= 10.0 | Fast serialization | (unused in v3, can remove) |

### VOD Processing (Valoscribe)

| Library | Version | Purpose | v3 Usage |
|---------|---------|---------|----------|
| streamlink | (installed, latest: 8.2.0) | VOD streaming | Valoscribe VOD download |
| opencv-python | (installed) | Frame extraction | Valoscribe OCR pipeline |
| pytesseract | (installed) | OCR | Valoscribe text detection |

### Utilities

| Library | Version | Purpose | v3 Usage |
|---------|---------|---------|----------|
| tenacity | >= 9.0 | Retry logic | VLR.gg scraping resilience |
| rich | >= 14.0 | Terminal formatting | Already used for logging |
| typer | >= 0.12 | CLI framework | (unused in v3, can remove) |
| structlog | >= 25.0 | Structured logging | Experiment logging |

## Installation

### Additions for v3

```bash
# Web scraping additions
uv pip install httpx==0.28.1
uv pip install pyrate-limiter==4.0.2
uv pip install tqdm==4.67.3

# Update requirements.txt
echo "httpx>=0.28" >> requirements.txt
echo "pyrate-limiter>=4.0" >> requirements.txt
echo "tqdm>=4.67" >> requirements.txt
```

### Optional Cleanup

Remove unused dependencies (pyarrow, typer) if not referenced:

```bash
# Verify usage first
grep -r "import pyarrow" src/ tests/ scripts/
grep -r "import typer" src/ tests/ scripts/

# If no matches, remove from requirements.txt
```

## Integration Architecture

### 1. VLR.gg Scraper (scripts/scrape_vlr.py)

```python
import httpx
from bs4 import BeautifulSoup
from pyrate_limiter import Duration, Limiter, Rate
from pathlib import Path

# Rate limiter: 1 req/sec (VLR.gg politeness)
limiter = Limiter(Rate(1, Duration.SECOND))

async def scrape_match_page(match_url: str) -> dict:
    """Fetch match metadata (teams, map, date, VOD link)."""
    async with limiter.ratelimit("vlr", delay=True):
        async with httpx.AsyncClient() as client:
            response = await client.get(match_url, timeout=10.0)
            soup = BeautifulSoup(response.text, "lxml")
            # Extract teams, map, VOD link
            return {...}

# Sync wrapper for simple usage
def scrape_tournament(tournament_url: str) -> list[dict]:
    """Scrape all matches from tournament page."""
    import asyncio
    return asyncio.run(_scrape_async(tournament_url))
```

**Storage:** JSON manifest at `data/vlr_manifest.json` mapping match_id to VOD URL + metadata.

### 2. Scaled VOD Processing (scripts/process_vods_parallel.py)

```python
from joblib import Parallel, delayed
from tqdm import tqdm
from pathlib import Path

def process_single_vod(vod_url: str, output_dir: Path) -> dict:
    """Process one VOD through Valoscribe, return metadata."""
    # Call Valoscribe processing pipeline
    # Return map_id, event_count, parse_errors
    ...

def process_vod_batch(manifest: list[dict], n_jobs: int = 4):
    """Process VODs in parallel with progress tracking."""
    results = Parallel(n_jobs=n_jobs)(
        delayed(process_single_vod)(item["vod_url"], Path("data/processed"))
        for item in tqdm(manifest, desc="Processing VODs")
    )
    return results
```

**Rationale:**
- joblib handles process pool, automatic error handling
- tqdm wraps input iterable for progress bar
- n_jobs=4 conservative (CPU-bound Valoscribe processing)

### 3. Experiment Orchestration (scripts/run_experiment_batch.py)

```python
import sqlite3
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

# SQLite experiment tracking
def init_experiment_db(db_path: Path):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS experiments (
            id TEXT PRIMARY KEY,
            model_type TEXT,
            feature_set TEXT,
            timestamp TEXT,
            status TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS results (
            experiment_id TEXT,
            metric TEXT,
            value REAL,
            FOREIGN KEY(experiment_id) REFERENCES experiments(id)
        )
    """)
    conn.commit()
    return conn

def run_experiment_tracked(config: dict, db_path: Path):
    """Run single experiment, log to SQLite."""
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO experiments VALUES (?, ?, ?, ?, ?)",
                 (config["id"], config["model"], config["features"],
                  datetime.now().isoformat(), "running"))
    conn.commit()

    try:
        result = run_experiment(config)  # existing function

        for metric, value in result["cv_results"]["overall_metrics"].items():
            conn.execute("INSERT INTO results VALUES (?, ?, ?)",
                        (config["id"], metric, value))

        conn.execute("UPDATE experiments SET status = ? WHERE id = ?",
                    ("complete", config["id"]))
        conn.commit()
        return result
    except Exception as e:
        conn.execute("UPDATE experiments SET status = ? WHERE id = ?",
                    ("failed", config["id"]))
        conn.commit()
        raise

def run_all_experiments(configs: list[dict], max_workers: int = 2):
    """Run experiments in parallel."""
    db_path = Path("experiments/tracking.db")
    init_experiment_db(db_path)

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_experiment_tracked, cfg, db_path): cfg
                   for cfg in configs}

        for future in concurrent.futures.as_completed(futures):
            config = futures[future]
            try:
                result = future.result()
                print(f"✓ {config['id']}: log_loss={result['cv_results']['overall_metrics']['log_loss']:.4f}")
            except Exception as e:
                print(f"✗ {config['id']}: {e}")
```

**Rationale:**
- ProcessPoolExecutor: Separate Python processes for CPU-bound model training
- SQLite: Single-file database, no server, concurrent reads + serial writes
- max_workers=2: Conservative (prevents memory thrashing with XGBoost)

## Anti-Patterns to Avoid

### DO NOT Add Heavy Orchestration

**Avoid:** Airflow, Prefect, Metaflow, Kubeflow

**Why:**
- **Airflow:** Requires webserver, scheduler, database. Overkill for 150 maps + 8 experiments. DAG complexity unjustified (no task dependencies, just parallelism).
- **Prefect:** Similar overhead, designed for complex workflows. v3 workflow is embarrassingly parallel.
- **Metaflow:** Netflix-scale tool. Designed for 1000s of experiments, S3 storage, cloud compute. Local-first Windows environment is antithetical.

**When to reconsider:** If v4+ requires scheduling (daily retraining), complex DAGs (data pipeline → training → backtesting → deployment), or distributed compute (cloud GPUs).

### DO NOT Use requests-html

**Avoid:** requests-html library

**Why:** Unmaintained since 2019 (latest: 0.10.0). No updates for Python 3.8+. Use httpx instead (active development, async support, 0.28.1 released Dec 2024).

### DO NOT Use Playwright/Selenium for VLR.gg

**Avoid:** Browser automation for scraping

**Why:** VLR.gg serves static HTML (verified by community scrapers using BeautifulSoup). Playwright/Selenium adds 100+ MB dependency (browser binary), 10x slower than httpx + BS4. Only needed for JavaScript-rendered SPAs (VLR.gg is not).

**When to reconsider:** If VLR.gg migrates to React/Vue SPA and content becomes client-rendered.

### DO NOT Add MLflow Yet

**Avoid:** MLflow experiment tracking for v3

**Why:**
- Adds 15+ dependencies (Flask, SQLAlchemy, protobuf, gunicorn)
- Requires running UI server (mlflow ui)
- v3 needs: metadata persistence + comparison queries. SQLite handles both with zero dependencies.
- MLflow value: model registry, deployment tracking, team collaboration. All v4+ concerns.

**When to add:** v4 if adding model deployment, versioning, or team collaboration.

## Version Verification Summary

All versions verified against official sources (PyPI, GitHub releases) as of 2026-02-14:

| Library | Recommended | Source | Confidence |
|---------|-------------|--------|------------|
| httpx | 0.28.1 | [PyPI](https://pypi.org/project/httpx/) | HIGH |
| pyrate-limiter | 4.0.2 | [PyPI](https://pypi.org/project/pyrate-limiter/) | HIGH |
| tqdm | 4.67.3 | [PyPI](https://pypi.org/project/tqdm/) | HIGH |
| beautifulsoup4 | 4.14.3 | [PyPI](https://pypi.org/project/beautifulsoup4/) | HIGH |
| lxml | 6.0.2 | [PyPI](https://pypi.org/project/lxml/) | HIGH |
| streamlink | 8.2.0 | [PyPI](https://pypi.org/project/streamlink/) | HIGH |
| joblib | 1.5.3 | [PyPI](https://pypi.org/project/joblib/) | HIGH |
| SQLite | 3.51.2 | [SQLite releases](https://www.sqlite.org/changes.html) | HIGH |

## Constraints Satisfied

- **Local-first:** All libraries run locally, no cloud services
- **Windows 11:** All libraries support Windows (httpx, joblib, SQLite cross-platform)
- **Python 3.11:** All libraries support Python 3.10+ (httpx requires 3.10+, others compatible)
- **uv package manager:** All installable via `uv pip install`
- **No deep dependencies:** httpx (8 deps), pyrate-limiter (1 dep), tqdm (0 deps)

## Sources

### Web Scraping
- [VLR.gg scraper examples](https://github.com/aritropaul/vlr.gg-scraper)
- [VLR.gg scraping discussion](https://www.vlr.gg/30777/is-data-scraping-allowed)
- [Python web scraping libraries comparison](https://www.zenrows.com/blog/python-web-scraping-library)
- [BeautifulSoup documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [httpx documentation](https://www.python-httpx.org/)
- [pyrate-limiter PyPI](https://pypi.org/project/pyrate-limiter/)

### Parallel Processing
- [joblib documentation](https://joblib.readthedocs.io/en/latest/parallel.html)
- [Python multiprocessing comparison](https://www.infoworld.com/article/2257768/the-best-python-libraries-for-parallel-processing.html)
- [concurrent.futures documentation](https://docs.python.org/3/library/concurrent.futures.html)

### Experiment Tracking
- [MLflow vs DVC comparison](https://www.nb-data.com/p/simple-model-experiment-tracking)
- [SQLite Python documentation](https://docs.python.org/3/library/sqlite3.html)
- [MLflow orchestration overview](https://www.prompts.ai/blog/best-orchestration-solutions-machine-learning-projects-2026)

### Package Versions
- [httpx PyPI](https://pypi.org/project/httpx/)
- [pyrate-limiter PyPI](https://pypi.org/project/pyrate-limiter/)
- [tqdm PyPI](https://pypi.org/project/tqdm/)
- [beautifulsoup4 PyPI](https://pypi.org/project/beautifulsoup4/)
- [lxml releases](https://github.com/lxml/lxml/releases)
- [streamlink PyPI](https://pypi.org/project/streamlink/)
- [joblib PyPI](https://pypi.org/project/joblib/)
- [SQLite releases](https://www.sqlite.org/changes.html)
