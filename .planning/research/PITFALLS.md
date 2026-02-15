# Domain Pitfalls: Esports Prediction System Scaling

**Domain:** VCT match prediction from CV-extracted VOD data + VLR.gg metadata
**Researched:** 2026-02-14
**Context:** Scaling from 71 hand-curated Champions 2025 maps to 150+ automated dataset

---

## Critical Pitfalls

Mistakes that cause rewrites, data poisoning, or major infrastructure issues.

### Pitfall 1: VOD Availability Decay (The "Broken Pipeline" Problem)

**What goes wrong:** You scrape VLR.gg for 200 match URLs pointing to YouTube VODs. Three months later, when reprocessing or validating, 30% of those VODs are private, deleted, or DMCA-taken-down. Your dataset silently degrades and becomes non-reproducible.

**Why it happens:**
- YouTube streamers delete VODs after 60 days (partners), 14 days (affiliates), or 7 days (regular users) to avoid DMCA strikes
- Tournament organizers make VODs private after contract expiration
- Copyright claims remove individual videos without warning
- URL structure changes (playlist reorganization, channel moves)

**Consequences:**
- Dataset becomes non-reproducible (can't reprocess with new detectors)
- Temporal validation breaks if missing VODs create gaps in chronological data
- Ablation studies fail when reference dataset cannot be regenerated
- Silent data loss goes undetected until reprocessing attempt

**Prevention:**
1. **Immediate processing:** Process VODs within 48 hours of scraping VLR.gg links (before deletion window)
2. **Availability checks:** Before queueing 150 VODs for 30-hour processing run, validate ALL YouTube URLs are accessible (`yt-dlp --check-formats`)
3. **Tombstone tracking:** Track "intended dataset" vs "available dataset" separately — record which VLR.gg matches had inaccessible VODs
4. **Graceful degradation:** When VOD unavailable, log to manifest with reason (deleted/private/unavailable) and continue with remaining VODs
5. **Downstream awareness:** Training pipeline must handle missing maps in temporal sequence (gap-aware walk-forward CV)

**Detection:**
- YouTube API returns 404 or "This video is private"
- `streamlink` fails with "No playable streams found"
- VLR.gg lists match but YouTube link returns 410 Gone
- Processing queue shows lower completion rate than expected (e.g., 142/150 instead of 150/150)

**Phase impact:** Phase 1 (VLR.gg scraping), Phase 2 (VOD processing pipeline)

---

### Pitfall 2: Batch Processing Failure Opacity (The "Silent Corruption" Problem)

**What goes wrong:** You queue 150 VODs for overnight processing (20+ hours). Processing crashes at VOD #83 due to OCR timeout. You wake up to 82 completed maps and assume the run finished successfully. Train model on partial dataset. Model evaluation shows poor results but you can't tell if it's model quality or data quality.

**Why it happens:**
- Batch video processing pipelines fail partially (per-VOD errors don't halt entire batch)
- Windows environment masks errors (PowerShell continues on exception, Python scripts may catch-and-continue)
- Processing time variability (15-30 min/VOD) makes "expected completion time" unreliable
- No centralized error aggregation for 150-item batch

**Consequences:**
- Train on incomplete dataset without realizing it
- Temporal validation corrupted (missing maps create unintended gaps)
- Ablation studies non-reproducible (rerun produces different dataset)
- Waste compute re-running entire 20-hour batch to identify which VODs failed

**Prevention:**
1. **Processing manifest:** Create `.processing_manifest.json` with status tracking per VOD:
   ```json
   {
     "vlr_match_12345": {
       "status": "completed|failed|skipped",
       "youtube_url": "...",
       "map_id": "...",
       "processing_time_sec": 1823,
       "error": null,
       "timestamp": "2026-02-14T15:23:00Z"
     }
   }
   ```
2. **Atomic completion markers:** Write `.SUCCESS` file only after ALL processing steps complete for a VOD
3. **Resumable processing:** Before reprocessing entire batch, check manifest and skip VODs with `.SUCCESS` marker
4. **Exit code discipline:** Processing script must exit non-zero if ANY VOD fails (enable strict error handling)
5. **Progress monitoring:** Write processing state to manifest after each VOD (enables mid-run inspection)
6. **Post-run validation:** Compare completed maps against intended dataset — fail loudly if mismatch

**Detection:**
- Expected 150 processed map directories, `ls data/processed/ | wc -l` shows 127
- Manifest shows `"status": "failed"` for subset of VODs
- Training dataset has unexpected date gaps (2024-11-03, 2024-11-05, missing 2024-11-04)
- Reprocessing same batch produces different number of maps

**Phase impact:** Phase 2 (VOD processing pipeline), Phase 3 (data ingestion)

---

### Pitfall 3: ReplayDetector Validation Failure at Scale (The "Unverified Detector" Problem)

**What goes wrong:** ReplayDetector works perfectly on 71 Champions maps. You scale to 150 maps including older tournaments (Masters Bangkok 2024, VCT Americas 2024) which use different broadcast layouts or timer formats. ReplayDetector silently fails to detect replays (false negatives) or over-suppresses live footage (false positives). Training data becomes poisoned with phantom duplicate events or missing critical rounds.

**Why it happens:**
- Broadcast layout changes between tournaments (different OCR ROI coordinates for timer)
- Timer format variations (some broadcasts show "1:30", others show "01:30" or "90s")
- Overtime rounds use different timer logic (alternating 2-round segments in Valorant OT)
- OCR quality degrades on older/lower-bitrate VODs (more `None` timer readings)
- Operational requirements VSCR-03/04 explicitly deferred in v2 (detection rate and regression check)

**Consequences:**
- False negatives: Replay events leak into training data → model learns from duplicate/phantom rounds
- False positives: Live footage suppressed → model trained on incomplete maps (missing critical comeback rounds)
- Silent corruption: No error thrown, just bad training data
- Non-reproducible experiments: Same VOD reprocessed with different detector settings produces different feature values

**Prevention:**
1. **Validation metrics per map:** Track `replay_count` and `frames_suppressed` in metadata.json (already implemented)
2. **Distribution validation:** Before training, plot histogram of `replay_count` across all maps — outliers indicate detector failure
3. **Regression flagging:** If map has `replay_count=0` but duration >60 min (typical VCT map with replays), flag for manual inspection
4. **Tournament-stratified validation:** Validate detector performance separately for each tournament (Champions 2025, Masters Bangkok 2024, VCT Americas 2024)
5. **Spot-check protocol:** Manually verify 5% of maps (randomly sampled, stratified by tournament) by watching VOD segments flagged as replays
6. **Quality gate:** Exclude maps with `replay_count` outside [5th percentile, 95th percentile] from training (likely detector failures)

**Detection:**
- Map metadata shows `replay_count: 0` for 90-minute VOD (expected ~10-15 replays for long map)
- Map metadata shows `replay_count: 47` for 35-minute VOD (likely over-suppression)
- Feature engineering shows negative economy values (impossible) → indicates suppressed buy rounds
- Manual spot-check reveals timer in replay segment but not suppressed

**Phase impact:** Phase 2 (VOD processing pipeline), Phase 5 (data quality validation)

---

### Pitfall 4: Temporal Validation Collapse with Small Dataset Expansion (The "Overfitting Mirage" Problem)

**What goes wrong:** You train on 71 maps with leave-one-series-out CV and get promising log loss (0.52). You expand to 150 maps and log loss degrades to 0.68. You conclude the new data is "low quality" and discard it. In reality, 71 maps was too small for reliable CV — the original 0.52 was overfitted, and 0.68 is closer to true generalization performance.

**Why it happens:**
- Small datasets (N < 100-300) overestimate predictive power due to high variance in CV splits
- Temporal validation requires contiguous chronological sequences — missing maps break walk-forward folds
- Performance doesn't converge until N = 750-1500 for many ML tasks (you're at N=71→150, still in high-variance zone)
- "Single lucky fold" effect: One particularly predictable series (e.g., stomp matches) inflates metrics

**Consequences:**
- Mistakenly discard valuable training data as "low quality"
- False confidence in model edge (think you have 0.52 log loss, actually 0.68)
- Downstream betting decisions based on inflated performance estimates
- Waste research effort debugging "data quality issues" that are actually sample size issues

**Prevention:**
1. **Confidence intervals:** Report log loss with bootstrapped 95% CI, not point estimates (expect wide intervals at N=71)
2. **Sample size awareness:** Document "performance will be unstable until N>300" in evaluation framework
3. **Convergence testing:** Plot log loss vs training set size (50, 75, 100, 125, 150 maps) — expect monotonic improvement
4. **Hold-out test set:** Reserve most recent tournament (20-30 maps) as untouched test set — only evaluate on this ONCE at end
5. **Cross-tournament validation:** Compare LOTO performance across tournaments — high variance indicates sample size issues
6. **Baseline comparison:** Track "predict home team always" baseline — improvement over baseline matters more than absolute log loss

**Detection:**
- Log loss confidence interval spans >0.15 (e.g., [0.45, 0.63])
- Adding 50% more data degrades performance (non-monotonic learning curve)
- One tournament dominates LOTO performance (e.g., removing Champions improves log loss by 0.10)
- Performance on most recent 10 maps wildly different from training performance

**Phase impact:** Phase 4 (model evaluation), Phase 5 (model iteration)

---

### Pitfall 5: Meta Drift Blindness (The "Stale Model" Problem)

**What goes wrong:** You train on VCT 2024 data (patches 8.0-8.11) and deploy for VCT 2025 matches (patch 9.0+). Riot nerfs Jett dash and buffs Killjoy turret. Your model still predicts based on 2024 agent meta. Duelist-heavy compositions underperform your predictions. Log loss degrades from 0.55 to 0.72 in production.

**Why it happens:**
- Valorant patches every 2 weeks with agent balance changes
- Meta shifts make historical feature distributions non-stationary (concept drift)
- Your feature set excludes per-agent features (per PROJECT.md: "meta shifts between patches, unstable signal")
- Game mechanics features (economy, score, momentum) are stable, but agent-comp interactions are not
- Training data from 6+ months ago has different "ground truth" relationship to outcomes

**Consequences:**
- Model degrades silently in production (no agent features = no drift detection signal)
- Predictions miscalibrated for current meta (overconfident on outdated patterns)
- Waste compute retraining on stale data (need recency weighting or data pruning)
- Miss profitable betting opportunities (model underestimates new meta compositions)

**Prevention:**
1. **Recency weighting:** Implement inverse-time decay weighting for training samples (already in v2 framework)
2. **Rolling window training:** Train only on last 6 months of data (1-2 major patches in Valorant)
3. **Patch-aware splits:** Validate across patch boundaries (train pre-patch, test post-patch) to measure drift
4. **Performance monitoring:** Track production log loss over time — alert if 7-day moving average exceeds training baseline by >0.10
5. **Graceful fallback:** When production log loss degrades, fall back to simpler model or widen confidence intervals
6. **Meta features (optional):** If adding agent features, use patch-relative encoding (e.g., "picked in >30% of matches this patch") not absolute pick rates

**Detection:**
- Production log loss trends upward over time (concept drift)
- Model overconfident on recent matches (predicted 0.75 win prob, actual outcome 50/50 over 20 matches)
- VLR.gg shows meta shift (Jett pick rate drops from 60% to 30% in last 50 matches) but model predictions unchanged
- Cross-tournament validation shows newer tournaments have worse performance

**Phase impact:** Phase 4 (model evaluation), Phase 5 (model iteration), Phase 6 (production monitoring — out of scope for v3)

---

## Moderate Pitfalls

Mistakes that cause delays, technical debt, or experimental design flaws.

### Pitfall 6: VLR.gg Schema Drift (The "Scraper Breakage" Problem)

**What goes wrong:** You build a scraper for VLR.gg's current HTML structure (`.match-item > .team-name`). VLR.gg redesigns their site. Your scraper silently fails or returns malformed data. You don't notice for 2 weeks. By then, 30 new matches are missing from your dataset.

**Why it happens:**
- VLR.gg has no official API (community scrapers are fragile)
- HTML structure changes without notice (class names, nesting, pagination)
- Anti-scraping measures (rate limiting, IP blocks, Cloudflare challenges)
- Tournament page format varies (regular season vs playoffs vs international events)

**Prevention:**
- **Schema validation:** Assert expected fields present after scraping (team names, map name, YouTube URL)
- **Scraping tests:** Store 2-3 example HTML pages in `tests/fixtures/`, write unit tests for scraper
- **Change detection:** Hash scraped HTML structure (tag hierarchy), alert if structure changes
- **Graceful degradation:** If parsing fails, log raw HTML and continue with partial data
- **Manual review:** After initial scrape of 150 matches, manually inspect 10 random entries for correctness
- **Rate limiting:** 1 request/sec to avoid IP blocks (VLR.gg community recommendation)

**Detection:**
- Scraper returns empty list or missing fields (team names are `None`)
- VLR.gg returns 429 Too Many Requests or Cloudflare challenge page
- YouTube URLs point to wrong videos (wrong tournament, wrong date)

**Phase impact:** Phase 1 (VLR.gg scraping)

---

### Pitfall 7: Match Format Metadata Inconsistency (The "BO3 vs BO5" Problem)

**What goes wrong:** You scrape match results from VLR.gg and assume all matches are BO3. Some playoff matches are BO5. Your series prediction model trained on BO3 data predicts BO5 matches incorrectly (momentum adjustment wrong, map count expectations wrong).

**Why it happens:**
- Tournament formats vary (group stage BO3, playoffs BO5, grand finals BO5)
- VLR.gg doesn't always clearly label match format in consistent location
- Overtime rule variations (some tournaments use different OT formats)
- Tiebreaker maps (some tournaments have unique tiebreaker rules)

**Prevention:**
- **Format field in manifest:** Scraper must extract `match_format: "BO3" | "BO5"` from VLR.gg
- **Validation check:** Count maps per series in scraped data — flag if BO3 match has 4+ maps
- **Format-specific models:** Train separate models for BO3 and BO5 if sample sizes permit
- **Graceful handling:** If format unknown, use conservative prediction (wider confidence intervals)

**Detection:**
- Series prediction shows 4 maps for "BO3" match
- Model predicts match winner after map 2 (assumes BO3) but match continues to map 4

**Phase impact:** Phase 1 (VLR.gg scraping), Phase 4 (series prediction)

---

### Pitfall 8: OCR Degradation on Older VODs (The "Bitrate Trap" Problem)

**What goes wrong:** Champions 2025 VODs are 1080p60 high-bitrate. Masters Bangkok 2024 VODs are 720p30 lower-bitrate (uploaded before YouTube quality improvements). Your OCR detectors (timer, score) trained/validated on Champions data have higher error rates on Bangkok data. Timer reads as `None` more frequently, triggering ReplayDetector's "maintain current state" logic, causing over-suppression.

**Why it happens:**
- Older tournaments have lower video quality (bitrate, resolution, frame rate)
- YouTube compression artifacts more severe on older uploads
- Broadcast production quality varies by region/tournament tier
- OCR confidence thresholds tuned for high-quality VODs fail on degraded video

**Prevention:**
- **Quality stratification:** Track OCR error rate per map in metadata (`timer_ocr_success_rate`, `score_ocr_success_rate`)
- **Quality gates:** Exclude maps with OCR success rate <85% from training (too unreliable)
- **Adaptive thresholds:** Use more lenient OCR confidence thresholds for known low-quality tournaments
- **Bitrate check:** Log YouTube video bitrate in manifest, flag if <2 Mbps (likely degraded quality)
- **Manual spot-check:** Validate OCR accuracy on 3 random maps per tournament (stratified sampling)

**Detection:**
- Map metadata shows `timer_ocr_success_rate: 0.62` (vs 0.95 for Champions maps)
- ReplayDetector shows unusually high `frames_suppressed` for older tournament maps
- Feature engineering produces many `None` or default values for economy features (requires timer for round detection)

**Phase impact:** Phase 2 (VOD processing), Phase 5 (data quality validation)

---

### Pitfall 9: Ablation Study Design Ambiguity (The "Confounded Ablation" Problem)

**What goes wrong:** You want to measure contribution of "economy features" via ablation. You remove 4 economy features and retrain. Log loss degrades 0.03. You conclude economy features are valuable. But you didn't control for feature count — removing 4 features also reduces model complexity, which might independently affect performance.

**Why it happens:**
- Ablation design doesn't isolate the component being tested
- Removing features changes both signal AND model complexity
- Incomplete specification: ablation should specify "replace with what?" (zeros, mean imputation, exclusion, random noise)
- Statistical thresholds not pre-registered (post-hoc p-hacking on ablation results)

**Prevention:**
- **Replacement strategy:** Specify whether ablation is "removal" (exclude from training) or "corruption" (replace with noise/zeros)
- **Complexity control:** If removing features, also run ablation removing random features (same count) as control
- **Pre-registration:** Document ablation plan BEFORE running experiments (which features, how many runs, statistical test)
- **Multiple ablations:** Run 3+ random seeds per ablation, report mean + CI (single run is high-variance)
- **Holdout evaluation:** Evaluate all ablations on same hold-out set (not CV, which has variance across folds)

**Detection:**
- Removing any 4 random features degrades performance by similar amount (not specific to economy features)
- Ablation results flip when rerun with different random seed
- Statistical significance test shows p=0.12 (not significant) but claimed as "valuable"

**Phase impact:** Phase 5 (model iteration, ablation studies)

---

### Pitfall 10: Cross-Tournament Validation Misinterpretation (The "LOTO Fallacy" Problem)

**What goes wrong:** You run leave-one-tournament-out (LOTO) CV. Champions 2025 held-out shows log loss 0.48. Masters Bangkok held-out shows log loss 0.72. You conclude "Masters data is low quality, exclude it." In reality, Masters has fewer stomps (more competitive matches = harder to predict), which is GOOD for generalization.

**Why it happens:**
- Confusing "harder to predict" with "lower quality"
- Tournament difficulty varies (group stage has stomps, playoffs have close matches)
- LOTO conflates temporal effects, tournament tier, and match competitiveness
- No baseline comparison (is 0.72 good or bad for competitive matches?)

**Prevention:**
- **Baseline comparison:** Compare model log loss to "predict 50/50" baseline per tournament
- **Stratified analysis:** Break down LOTO by match type (group stage vs playoffs) and score margin
- **Competitiveness metrics:** Track average score margin per tournament (narrow margins = harder prediction)
- **Diagnostic only:** Per PROJECT.md, LOTO is "diagnostic only" — default to mixed temporal training
- **Combine tournaments:** Don't exclude tournaments unless validation proves they harm generalization

**Detection:**
- Tournament with worst LOTO log loss also has smallest average score margin (most competitive)
- Removing "low quality" tournament from training degrades performance on hold-out set

**Phase impact:** Phase 4 (model evaluation), Phase 5 (model iteration)

---

## Minor Pitfalls

Mistakes that cause annoyance, wasted time, or minor inefficiencies.

### Pitfall 11: Duplicate Map Processing (The "Wasted Compute" Problem)

**What goes wrong:** You scrape VLR.gg and find 180 match results. Some matches have 3 maps, some have 5 maps. You generate 180 "map processing jobs" but 60 of them are duplicates (same YouTube URL, same timestamp). You waste 10 hours reprocessing maps you already have.

**Prevention:**
- **Deduplication check:** Before processing, check if `map_id` already exists in `data/processed/`
- **Manifest lookup:** Query processing manifest for existing entries with same YouTube URL + timestamp
- **Dry-run mode:** Scraper outputs "would process 142 new maps, skip 38 existing" before starting 20-hour job

**Detection:**
- Processing log shows "Processing map_12345... already exists, skipping"
- Two map directories have identical YouTube URL in metadata

**Phase impact:** Phase 2 (VOD processing pipeline)

---

### Pitfall 12: Inconsistent Map Identifiers (The "Join Key Hell" Problem)

**What goes wrong:** VLR.gg uses match ID `vlr-12345`. YouTube URL is `youtube.com/watch?v=abc123`. Valoscribe generates map ID `map_20241103_TL_vs_FNC_Haven`. Your manifest tries to join these three identifiers and fails because there's no consistent key.

**Prevention:**
- **Canonical ID strategy:** Use VLR.gg match ID as primary key, store YouTube URL and Valoscribe map_id as fields
- **Bidirectional mapping:** Manifest includes both `vlr_match_id → map_id` and `map_id → vlr_match_id`
- **ID validation:** Assert all three IDs present before marking processing as complete

**Detection:**
- Training pipeline can't match VLR.gg metadata to Valoscribe features
- Manual joins require string matching on team names (fragile)

**Phase impact:** Phase 1 (scraping), Phase 2 (processing), Phase 3 (data ingestion)

---

### Pitfall 13: Windows Path Length Limit (The "MAX_PATH" Problem)

**What goes wrong:** You generate map IDs like `20241103_Team_Liquid_vs_Fnatic_Haven_Map3_VCT_Champions_2025`. Full path is `D:\Git\valoscribe\data\processed\20241103_Team_Liquid_vs_Fnatic_Haven_Map3_VCT_Champions_2025\events.jsonl` which exceeds Windows MAX_PATH (260 characters). Processing fails with cryptic error.

**Prevention:**
- **Short map IDs:** Use date + sequential ID (`20241103_001`, `20241103_002`) instead of descriptive names
- **Path length check:** Validate generated path <240 characters before processing
- **Enable long paths:** Set Windows registry `LongPathsEnabled=1` (requires admin)

**Detection:**
- File operations fail with "path too long" or "system cannot find the path"
- `os.path.exists()` returns False for path that should exist

**Phase impact:** Phase 2 (VOD processing)

---

### Pitfall 14: Agent Composition Data Temptation (The "Feature Creep" Problem)

**What goes wrong:** VLR.gg provides agent composition data (which agents each player picked). You're tempted to add "agent pick rate" features. You add 10 agent features. Model performance improves on CV. You deploy. Next patch nerfs Jett. Model degrades catastrophically.

**Prevention:**
- **Stick to game mechanics:** Per PROJECT.md decision, exclude agent features due to meta instability
- **Deferred decision:** Mark agent features as "v4 research topic" after validating game mechanics approach
- **Meta stability check:** IF adding agent features, use patch-relative encoding and validate across patch boundaries

**Detection:**
- Model performance degrades after game patch
- Feature importance shows agent features dominate (unstable signal)

**Phase impact:** Phase 3 (feature engineering), Phase 5 (model iteration)

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| VLR.gg scraping | VOD availability decay (#1), schema drift (#6) | Validate URLs before processing, scrape + process within 48hr |
| VOD processing pipeline | Batch failure opacity (#2), OCR degradation (#8) | Processing manifest with atomic completion markers, quality metrics per map |
| Data quality validation | ReplayDetector failure (#3), duplicate maps (#11) | Distribution validation, spot-check protocol, deduplication check |
| Feature engineering | Agent composition temptation (#14), identifier inconsistency (#12) | Stick to game mechanics, canonical ID strategy |
| Model evaluation | Temporal validation collapse (#4), LOTO misinterpretation (#10) | Confidence intervals, baseline comparison, diagnostic-only LOTO |
| Model iteration | Meta drift blindness (#5), ablation ambiguity (#9) | Recency weighting, rolling window training, pre-registered ablation plans |
| Match format handling | BO3 vs BO5 inconsistency (#7) | Extract format from VLR.gg, validate map counts |
| Infrastructure | Windows path limit (#13) | Short map IDs, long paths enabled |

---

## Sources

### Data Quality & Scaling
- [Evaluation of decided sample size in ML applications](https://pmc.ncbi.nlm.nih.gov/articles/PMC9926644/) — Minimum N=500-1000 to mitigate overfitting
- [Techniques for ML with small datasets](https://www.trustbit.tech/blog/2021/06/30/techniques-and-pitfalls-for-ml-training-with-small-data-sets) — Small dataset pitfalls
- [Data drift detection guide](https://labelyourdata.com/articles/machine-learning/data-drift) — Concept drift and monitoring
- [Model drift in ML systems](https://www.evidentlyai.com/ml-in-production/data-drift) — Data vs concept drift

### Batch Processing & Infrastructure
- [Batch error handling strategies](https://learn.microsoft.com/en-us/azure/batch/error-handling) — Fatal vs non-fatal errors, recovery
- [Handling batch failures](https://www.linkedin.com/advice/1/how-can-you-handle-batch-processing-failures-ouoke) — Resumable processing, checkpointing

### Video & OCR Processing
- [OCR bottlenecks and VLM solutions](https://dzone.com/articles/from-ocr-bottlenecks-to-structured-understanding) — Token explosion, scalability
- [Video OCR optimization](https://www.mdpi.com/2227-7390/12/7/1036) — Image quality impact on OCR
- [Twitch/YouTube VOD storage limits](https://streamrecorder.io/blog/your-ultimate-guide-to-twitch-vods) — VOD retention policies

### Esports & Web Scraping
- [VLR.gg scraping community discussion](https://www.vlr.gg/30777/is-data-scraping-allowed) — Rate limiting, ToS
- [Esports data scraping pitfalls](https://esportsinsider.com/2023/12/data-scraping-odds-esports-bayes-esports) — Legal, quality, maintenance issues
- [Game patches impact on predictions](https://iwantmedia.com/the-role-of-game-patches-and-updates-in-esports-betting-decisions/) — Meta shifts and prediction decay
- [Esports match formats](https://www.esports.net/wiki/guides/esports-tournament-formats/) — BO3, BO5, tournament structures

### Experimental Design
- [Ablation study best practices](https://www.emergentmind.com/topics/controlled-ablation-study) — Misalignment, ambiguous boundaries
- [ABLATOR framework](https://proceedings.mlr.press/v224/fostiropoulos23a/fostiropoulos23a.pdf) — Horizontal scaling of ablation experiments
- [Time-series cross-validation](https://medium.com/@pacosun/respect-the-order-cross-validation-in-time-series-7d12beab79a1) — Temporal validation best practices

### Metadata & Sports Data
- [Sports metadata problems](https://www.metabroadcast.com/2025/07/16/sports-programming-has-a-metadata-problem/) — Inconsistent identifiers, schema
- [Esports tournament formats 2026](https://escharts.com/news/match-formats-are-used-esports) — BO1, BO3, BO5 prevalence
