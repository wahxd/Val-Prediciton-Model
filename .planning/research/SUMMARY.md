# Project Research Summary

**Project:** Val-Prediction-Model v3 - Scale Data & Validate at Volume
**Domain:** VCT match prediction with CV-extracted VOD data + VLR.gg metadata
**Researched:** 2026-02-14
**Confidence:** HIGH

## Executive Summary

The v3 milestone scales the prediction dataset from 71 hand-curated maps to 150+ automated maps through VLR.gg scraping integration. Research reveals this is fundamentally a **data discovery and pipeline automation** problem, not a feature engineering or modeling problem. The existing prediction framework (34 game-mechanics features, XGBoost models, walk-forward CV) remains intact; v3 adds a discovery layer (VLR.gg scraping for VOD URLs + match metadata) and a batch processing layer (automated Valoscribe orchestration).

The recommended approach treats VLR.gg as a **match manifest source** that feeds the existing Valoscribe processing pipeline, with team strength features (Elo/Glicko) as the only new predictive capability. Stack additions are minimal and focused: httpx for async scraping, pyrate-limiter for politeness, tqdm for progress visibility, and stdlib SQLite for experiment tracking. No heavyweight orchestration needed - joblib and concurrent.futures handle parallelization at this scale (150 maps, 4-8 experiments).

**Key risk:** VOD availability decay (YouTube videos deleted/privatized) creates non-reproducible datasets. Mitigation is time-based: scrape VLR.gg and process VODs within 48 hours, before deletion windows open. Secondary risk is ReplayDetector validation failure at scale - existing detector validated on Champions 2025 (high-quality 1080p60), but older tournaments may have degraded video quality (lower bitrate/resolution) causing OCR errors and over-suppression. Quality gates (OCR success rate thresholds, replay count distribution validation) required per tournament.

## Key Findings

### Recommended Stack

v3 adds web scraping, rate limiting, and progress tracking capabilities to the existing ML stack. The approach is conservative: add only what's necessary for 150-map scale, defer heavyweight orchestration (Airflow, MLflow, DVC) until proven necessary at 500+ maps.

**Core additions:**
- **httpx (0.28.1):** Async HTTP client for VLR.gg scraping - enables concurrent page fetching without blocking, modern alternative to requests with sync/async APIs
- **pyrate-limiter (4.0.2):** Leaky bucket rate limiting - prevents VLR.gg flooding (1 req/sec community recommendation), supports multiple rate limits (1/sec + 100/min)
- **tqdm (4.67.3):** Progress bars for long-running VOD processing (15-20 hours for 46 VODs) - provides ETA, integrates with joblib, zero dependencies
- **SQLite (stdlib):** Local experiment tracking - zero-dependency metadata persistence, sufficient for 150 maps (~1MB database)

**Existing stack (preserved):**
- scikit-learn, XGBoost, Optuna for ML pipeline
- BeautifulSoup4 + lxml for HTML parsing (already installed)
- joblib for parallel VOD processing (transitive from sklearn)
- concurrent.futures for experiment orchestration (stdlib)
- Valoscribe (D:\Git\valoscribe) for VOD processing (actively developed alongside)

**Anti-recommendations:**
- DO NOT add Airflow/Prefect/Metaflow - orchestration overhead unjustified for embarrassingly parallel processing (150 maps = 20 hours, no DAG complexity)
- DO NOT add MLflow - adds 15+ dependencies (Flask, SQLAlchemy, protobuf) for features not needed until v4 (model registry, deployment tracking)
- DO NOT use Playwright/Selenium - VLR.gg serves static HTML, browser automation adds 100+ MB dependency and 10x slowdown

### Expected Features

VLR.gg data provides two categories of value: **table stakes** (metadata needed to build a training dataset at scale) and **differentiators** (team strength features that add predictive signal beyond game mechanics).

**Must scrape (table stakes):**
- Match metadata (teams, date, tournament, stage, series format) - required for temporal ordering and walk-forward validation
- Map names and scores - required to match VLR.gg matches to Valoscribe processed maps
- YouTube VOD links - primary data source for Valoscribe processing (this is the critical bottleneck for scaling from 71 to 150+ maps)
- Team identification (canonical naming) - required to track team history for strength ratings

**Should add (differentiators):**
- Team strength rating (Elo/Glicko) - pre-match baseline probability (~60-65% accuracy before game mechanics), reconstructed from VLR.gg match history with time-decay weighting
- Recent form (time-weighted win rate) - captures momentum and meta adaptation, research shows 3-5% prediction boost in sports models
- Map pool strength (per-team, per-map win rates) - addresses map selection bias, sufficient samples at 150+ maps (~5-10 per team per map)

**Defer (v2+ or post-validation):**
- Agent meta alignment - unclear predictive value, meta shifts every patch reduce stability
- Head-to-head records - may lack sufficient samples for rare matchups
- Tournament tier weighting - use for stratification, not as feature

**Anti-features (explicitly avoid):**
- Player-level statistics (ACS, K/D, ADR) - overfitting risk HIGH, 150 maps = only ~30 per player, stats are outcome not predictor
- Agent pick rates without map context - meta shifts every 2-3 months invalidate training data
- Tournament seeding/bracket position - redundant with Elo/Glicko, correlation not causation
- Arbitrary streak features - redundant with time-weighted recent form

**Key insight:** VLR.gg data's primary value is NOT adding more features (34 game-mechanics features already comprehensive). Its value is (1) scaling dataset via VOD discovery, and (2) team identity features that enable strength-of-opponent adjustments previously impossible with identity-blind game mechanics.

### Architecture Approach

The architecture adds a **discovery layer** (VLR.gg scraping) and **batch processing layer** (VOD orchestration) while preserving the existing prediction pipeline. Integration strategy: separate output directories (existing 71 maps vs. new scraped maps) until feature engineering, then merge at dataset level.

**New components:**

1. **VLREventScraper** (src/scraping/vlr_events.py) - Discovery layer that extracts match URLs and VOD metadata from VLR.gg tournament pages, calls Valoscribe's scrape_match() for per-match extraction, outputs VODRecords to manifest

2. **ProcessingManifest** (src/scraping/manifest.py) - State tracking for resumable processing, tracks VOD status (pending/downloading/processing/complete/failed), uses atomic JSON writes (temp file + rename) to prevent corruption

3. **VODOrchestrator** (src/scraping/orchestrator.py) - Batch processor that orchestrates: download VOD via Valoscribe -> process through Valoscribe OCR pipeline -> cleanup multi-GB files -> update manifest atomically

4. **ProcessingConfig** (src/scraping/config.py) - Environment-based configuration (Valoscribe repo path, output directories, rate limits, timeouts)

5. **DatasetBuilder** (src/data/builder.py) - Merge layer that combines existing 71 maps + newly scraped maps into unified dataset, thin wrapper over existing loader

**Integration points:**
- Valoscribe CLI (external dependency): download, scrape-vlr, split-metadata, process-vod commands (may need to add some to Valoscribe)
- Existing data loader: DatasetBuilder discovers from multiple directories, calls existing load_map() on merged dict
- Existing feature pipeline: no changes, receives larger map_data_list
- Experiment runner: uses DatasetBuilder instead of manual loading, rest unchanged

**Data flow:**
```
VLR.gg event page -> VLREventScraper -> Manifest (VODRecords) -> VODOrchestrator
                                                                       |
                    Valoscribe (batch) -> JSONL events -> DatasetBuilder -> Feature pipeline -> Model
```

**Separation of concerns:** VLREventScraper knows VLR.gg HTML, not Valoscribe processing. VODOrchestrator knows Valoscribe CLI, not feature extraction. DatasetBuilder knows Valoscribe output format, not scraping. Feature pipeline knows MapData schema, not data sources.

### Critical Pitfalls

Research identified 5 critical pitfalls that cause rewrites, data poisoning, or major infrastructure issues:

1. **VOD Availability Decay (Broken Pipeline)** - YouTube streamers delete VODs after 60/14/7 days (DMCA prevention), tournament organizers privatize videos. Dataset becomes non-reproducible. Prevention: process VODs within 48 hours of scraping, validate all URLs accessible before queueing, track "intended dataset" vs "available dataset" with tombstone records, implement gap-aware walk-forward CV.

2. **Batch Processing Failure Opacity (Silent Corruption)** - Queue 150 VODs overnight, crash at #83, wake to 82 completed maps, assume success, train on partial dataset. Prevention: processing manifest with per-VOD status tracking, atomic completion markers (.SUCCESS files), resumable processing (skip completed VODs), exit non-zero if ANY VOD fails, post-run validation (compare completed vs intended).

3. **ReplayDetector Validation Failure at Scale (Unverified Detector)** - Detector validated on Champions 2025 (1080p60) fails on older tournaments (720p30 lower bitrate), silently over-suppresses live footage or leaks replay events. Prevention: track OCR success rate per map, plot replay_count distribution (outliers = detector failure), tournament-stratified validation, spot-check 5% of maps, quality gate (exclude maps with replay_count outside [p5, p95]).

4. **Temporal Validation Collapse with Small Dataset Expansion (Overfitting Mirage)** - 71 maps shows log loss 0.52, expand to 150 maps shows 0.68, conclude new data is "low quality" and discard. Reality: 71 was too small for reliable CV, 0.52 was overfitted. Prevention: report log loss with bootstrapped 95% CI, document "performance unstable until N>300", plot log loss vs training set size (expect monotonic improvement), hold-out test set (reserve recent tournament, evaluate ONCE), baseline comparison.

5. **Meta Drift Blindness (Stale Model)** - Train on 2024 data (patches 8.0-8.11), deploy for 2025 matches (patch 9.0+), Riot nerfs Jett/buffs Killjoy, model predictions based on outdated meta. Prevention: recency weighting (inverse-time decay for training samples), rolling window training (last 6 months only), patch-aware splits (train pre-patch, test post-patch), performance monitoring (alert if 7-day log loss exceeds training baseline by >0.10).

**Moderate pitfalls** include VLR.gg schema drift (site redesign breaks scraper), match format inconsistency (BO3 vs BO5 confusion), OCR degradation on older VODs (lower bitrate = more errors), ablation study design ambiguity (confounded experiments), and cross-tournament validation misinterpretation (LOTO fallacy).

## Implications for Roadmap

Based on research, v3 should follow a 5-phase structure that prioritizes risk reduction and validates integration points before scaling.

### Phase 1: VLR.gg Scraping Infrastructure
**Rationale:** No dependencies on Valoscribe processing, can validate VLR.gg scraping independently. Builds foundation for all downstream work. Low risk - self-contained, no impact on existing code.

**Delivers:**
- ProcessingManifest with VODRecord schema and atomic persistence
- ProcessingConfig with environment-based paths and rate limits
- VLREventScraper that discovers match URLs and VOD metadata from VLR.gg tournament pages
- Manifest populated with 50-100 VODRecords from 1-2 tournaments

**Addresses features:**
- Table stakes: match metadata, YouTube VOD links, team identification, match timestamps

**Avoids pitfalls:**
- VLR.gg schema drift (Pitfall #6) - schema validation, scraping tests with HTML fixtures, change detection
- Inconsistent map identifiers (Pitfall #12) - canonical ID strategy (VLR.gg match ID primary key)

**Research flag:** STANDARD - VLR.gg scraping well-documented in community scrapers, BeautifulSoup patterns established

### Phase 2: Valoscribe CLI Integration
**Rationale:** Required by orchestrator, may need Valoscribe changes. Validates critical external dependency before scaling. Medium risk - depends on Valoscribe (active development, but external).

**Delivers:**
- Verified/added Valoscribe CLI commands: scrape-vlr, split-metadata, download, process-vod
- Tested download + process pipeline on 1 VOD end-to-end
- Documentation of exact Valoscribe commit hash and CLI interface

**Uses stack:**
- Valoscribe (D:\Git\valoscribe) for VOD processing
- yt-dlp (via Valoscribe) for YouTube downloads

**Implements architecture:**
- VODOrchestrator → Valoscribe CLI interface (subprocess calls)

**Avoids pitfalls:**
- Valoscribe CLI interface changes (Architecture Risk #1) - validate early, document commit hash, pin version

**Research flag:** NEEDS RESEARCH - Valoscribe CLI interface must be verified/extended, integration points not fully documented

### Phase 3: Orchestration Pipeline
**Rationale:** Depends on scraping (Phase 1) + Valoscribe CLI (Phase 2). Validates resumable batch processing before scaling to 150 VODs. Medium risk - integration complexity, but well-isolated from existing code.

**Delivers:**
- VODOrchestrator with download -> process -> cleanup workflow
- scripts/expand_dataset.py CLI entry point for scraping + processing
- scripts/summarize_progress.py for progress monitoring
- Processing pipeline tested on 3-5 VODs, resumability verified (kill + restart)

**Uses stack:**
- httpx for async VLR.gg requests
- pyrate-limiter for rate limiting (1 req/sec)
- tqdm for progress visibility

**Implements architecture:**
- VODOrchestrator batch processing pipeline
- Atomic manifest updates with state transitions

**Avoids pitfalls:**
- VOD availability decay (Pitfall #1) - immediate processing within 48 hours, availability checks before queueing
- Batch processing failure opacity (Pitfall #2) - processing manifest, atomic completion markers, resumable processing, post-run validation
- Duplicate map processing (Pitfall #11) - deduplication check before processing, manifest lookup
- Windows path length limit (Pitfall #13) - short map IDs (date + sequential ID)

**Research flag:** STANDARD - Batch processing patterns well-documented, subprocess orchestration established

### Phase 4: Dataset Merging and Quality Validation
**Rationale:** Can defer until training, doesn't block scraping. Validates data quality before committing to 150-map experiments. Low risk - thin wrapper over existing loader.

**Delivers:**
- DatasetBuilder that merges existing 71 maps + new scraped maps
- Quality validation: OCR success rate per map, replay count distribution analysis, tournament-stratified checks
- Updated experiment scripts to use DatasetBuilder
- Validation on existing 71 maps + 3-5 new maps (verify feature extraction works)

**Uses stack:**
- Existing data loader (src/data/loader.py)
- Existing feature pipeline (src/features/pipeline.py)

**Implements architecture:**
- DatasetBuilder multi-source dataset builder
- Integration with existing experiment runner

**Avoids pitfalls:**
- ReplayDetector validation failure (Pitfall #3) - OCR success rate tracking, replay_count distribution validation, spot-check protocol, quality gates
- OCR degradation on older VODs (Pitfall #8) - quality stratification, OCR error rate per map, adaptive thresholds

**Research flag:** STANDARD - Data merging patterns straightforward, quality metrics well-defined

### Phase 5: Scaled Processing and Experiment Validation
**Rationale:** Validate pipeline at small scale (Phases 1-4) before processing 150 VODs. Operational scale validation, no code changes. Low risk - proven components.

**Delivers:**
- 150+ maps processed through pipeline (existing 71 + 80-100 new from VLR.gg)
- Team strength features (Elo/Glicko, recent form) implemented
- Experiments on combined dataset: mechanics-only vs mechanics+Elo vs mechanics+Elo+recent_form
- Ablation study measuring Elo/recent form contribution to log loss
- SQLite experiment tracking database with results comparison

**Uses stack:**
- joblib for parallel VOD processing (n_jobs=4)
- concurrent.futures for experiment orchestration (max_workers=2)
- SQLite for experiment metadata persistence

**Addresses features:**
- Differentiators: team strength rating (Elo/Glicko), recent form (time-weighted win rate)
- Validation: does adding Elo improve log loss vs mechanics-only baseline?

**Avoids pitfalls:**
- Temporal validation collapse (Pitfall #4) - bootstrapped confidence intervals, convergence testing (plot log loss vs N), hold-out test set, baseline comparison
- Meta drift blindness (Pitfall #5) - recency weighting, rolling window training, patch-aware splits
- Ablation study design ambiguity (Pitfall #9) - pre-registered ablation plans, replacement strategy specification, multiple seeds per ablation
- LOTO misinterpretation (Pitfall #10) - baseline comparison per tournament, stratified analysis by match type

**Research flag:** NEEDS RESEARCH - Team strength rating implementation (Elo vs Glicko, K-factor tuning, time-decay parameters) needs hyperparameter research

### Phase Ordering Rationale

- **Phase 1 before 2:** Scraping is independent of Valoscribe processing, can validate VLR.gg data structure without processing VODs
- **Phase 2 before 3:** Orchestrator depends on Valoscribe CLI, must verify/extend interface before building batch processor
- **Phase 3 before 4:** Can process 3-5 VODs in Phase 3 to test orchestration, full dataset merging deferred until quality validation needed
- **Phase 4 before 5:** Quality gates must be established before committing to 150-VOD processing run (20+ hours)
- **Phase 5 last:** Validates entire pipeline at scale, experiments on full dataset only after proven at small scale

**Dependencies minimized:** Phases 1-2 can run in parallel (scraping while extending Valoscribe CLI). Phases 3-4 can overlap (process first 5 VODs in Phase 3, build DatasetBuilder in Phase 4). Phase 5 strictly depends on 1-4 completion.

### Research Flags

**Needs deeper research during planning:**

- **Phase 2 (Valoscribe CLI Integration):** Valoscribe CLI interface not fully documented, may need to add scrape-vlr and split-metadata commands. Integration points inferred from typical CLI patterns, must verify against actual codebase.

- **Phase 5 (Team Strength Ratings):** Elo vs Glicko decision, optimal K-factor for esports, time-decay parameter tuning, handling roster changes. Research found Glicko preferred (handles rating uncertainty), but implementation details (K-factor, decay rate) need hyperparameter search.

**Standard patterns (skip research-phase):**

- **Phase 1 (VLR.gg Scraping):** BeautifulSoup HTML parsing, rate limiting, manifest persistence all well-documented. Community scrapers (axsddlr/vlrggapi, Yuji1702/Valorant-Data-Scrapper) provide reference implementations.

- **Phase 3 (Orchestration):** Subprocess orchestration, batch processing, resumable pipelines all standard Python patterns. joblib parallelization and atomic file writes well-established.

- **Phase 4 (Dataset Merging):** Multi-source dataset loading straightforward, quality metrics (OCR success rate, replay count distribution) defined in existing Valoscribe validation framework.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All libraries verified against PyPI (httpx 0.28.1, pyrate-limiter 4.0.2, tqdm 4.67.3). Anti-recommendations (Airflow, MLflow) based on scale analysis (150 maps doesn't justify orchestration overhead). |
| Features | HIGH | VLR.gg data structure verified via WebFetch + community scrapers. Team strength ratings (Elo/Glicko) well-researched in sports prediction literature (69% accuracy documented). Overfitting risks (player stats, agent features) validated by "large p, small n" ML research. |
| Architecture | HIGH | Existing v2 codebase (loader.py, pipeline.py, experiment.py) analyzed for integration points. Separation of concerns based on proven patterns (scraping separate from processing, processing separate from feature extraction). |
| Pitfalls | HIGH | VOD availability decay documented in Twitch/YouTube retention policies. Batch processing failure patterns from Microsoft Azure guidance. ReplayDetector validation risks from operational requirements VSCR-03/04 explicitly deferred in v2. Temporal validation collapse from small dataset ML research (N<300 unstable). |

**Overall confidence:** HIGH

All four research dimensions grounded in verified sources (official docs, PyPI, research papers, existing codebase analysis). Medium confidence items (VLR.gg HTML structure stability, Valoscribe CLI interface) flagged as "needs research during planning" for Phase 2.

### Gaps to Address

**VLR.gg API availability:** WebSearch found unofficial APIs (axsddlr/vlrggapi), but last update unknown. Need to validate if these work in 2026 or if custom BeautifulSoup scraper required. Mitigation: build custom scraper using community implementations as reference, defer API usage until proven stable.

**VOD coverage rate:** Unknown what % of VLR.gg matches have VOD links. Champions 2025 likely high (~90%), older tournaments lower. Affects dataset scaling feasibility. Mitigation: scrape 1-2 tournaments in Phase 1, measure VOD availability rate before committing to 150-map target.

**Agent composition extraction:** VLR.gg match pages show agent comps, but format unclear (icons vs text). Need to inspect actual HTML to confirm scrapability. Mitigation: defer agent features to post-150-map validation (anti-feature due to meta instability), prioritize team strength ratings.

**Optimal Elo parameters:** K-factor, initial rating, decay rate for esports unknown. Sports models use K=32, but esports may differ (roster changes, meta volatility). Mitigation: hyperparameter tuning in Phase 5 via Optuna, cross-validate on training data.

**Valoscribe CLI interface:** Assumed commands (scrape-vlr, split-metadata) may not exist, must add to Valoscribe. Mitigation: Phase 2 validates CLI early, we control both repos (Valoscribe actively developed alongside), can add needed commands.

## Sources

### Primary (HIGH confidence)

**Stack research:**
- PyPI official pages: httpx, pyrate-limiter, tqdm, beautifulsoup4, lxml, streamlink, joblib (versions verified 2026-02-14)
- SQLite releases (sqlite.org/changes.html) - SQLite 3.51.2 features
- Python concurrent.futures documentation (docs.python.org) - stdlib ProcessPoolExecutor/ThreadPoolExecutor
- GitHub repositories: axsddlr/vlrggapi, Yuji1702/Valorant-Data-Scrapper (VLR.gg scraping reference implementations)

**Features research:**
- VLR.gg Match Results page (WebFetch) - confirmed teams, scores, VOD links, stats structure
- Kaggle: Valorant vlr.gg Results and Stats dataset - schema includes date, teams, winner, scoreline
- Sports Ratings Guide: Elo, Glicko, RPI (prosportstance.com) - Elo vs Glicko for esports
- Unleashing AI for Esports Prediction (toolify.ai) - 69% accuracy with Elo/Glicko documented
- A Predictive Analysis of Valorant Esports (techrxiv.org) - Random Forest 93% accuracy, economy impact
- Dixon-Coles time-weighting (dashee87.github.io) - exponential decay for recent matches

**Architecture research:**
- Existing v2 codebase: src/data/loader.py, src/features/pipeline.py, src/modeling/experiment.py (direct code analysis)
- Valoscribe integration: D:\Git\valoscribe (active development, we control it)
- Phase 7 research: .planning/phases/07-dataset-expansion/07-RESEARCH.md (yt-dlp, BeautifulSoup patterns)

**Pitfalls research:**
- Twitch/YouTube VOD storage limits (streamrecorder.io) - retention policies 60/14/7 days
- Batch error handling strategies (Microsoft Azure docs) - fatal vs non-fatal errors, recovery
- Evaluation of sample size in ML (pmc.ncbi.nlm.nih.gov) - minimum N=500-1000 to mitigate overfitting
- Data drift detection guide (labelyourdata.com) - concept drift and monitoring
- Time-series cross-validation (Medium) - temporal validation best practices

### Secondary (MEDIUM confidence)

**VLR.gg structure:**
- Medium: Creating A Valorant Player Stats Dataset - describes scraping with Selenium/BeautifulSoup (may be outdated)
- VLR.gg scraping community discussion (vlr.gg/30777) - rate limiting recommendations, ToS (unofficial)

**Agent meta:**
- 5 agents dominating VALORANT 2026 (esportsinsider.com) - Clove 54.7% win rate, 59.6% pick rate
- VALORANT Patch 12.0 Meta Guide (dtgre.com) - Bandit pistol changes, Breeze rework (patch-specific, time-sensitive)

**Experimental design:**
- Ablation study best practices (emergentmind.com) - misalignment, ambiguous boundaries (general guidance)
- ABLATOR framework (MLIR proceedings) - horizontal scaling of ablation experiments (academic framework)

### Tertiary (LOW confidence - needs validation)

None. All research findings validated with primary or secondary sources. Areas with insufficient confidence (VLR.gg HTML stability, Valoscribe CLI interface) flagged as "needs research during planning" rather than included as low-confidence findings.

---
*Research completed: 2026-02-14*
*Ready for roadmap: yes*
