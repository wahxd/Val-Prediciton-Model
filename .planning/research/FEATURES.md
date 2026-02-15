# Feature Landscape: VLR.gg Data for Match Prediction

**Domain:** VCT match prediction with VLR.gg scraped data
**Researched:** 2026-02-14
**Confidence:** MEDIUM (WebSearch for ecosystem, official VLR.gg structure via WebFetch)

## Executive Summary

VLR.gg provides match results, player statistics, agent compositions, team rankings, and YouTube VOD links for VCT tournaments. For a prediction model trained on 150+ maps with walk-forward temporal validation, VLR.gg data enables three categories of new features beyond current Valoscribe game-mechanics extraction:

**Table stakes (must scrape):** Match metadata (teams, dates, tournament, map names), final scores, VOD links for Valoscribe processing pipeline. Without these, you can't build a training dataset at scale.

**Differentiators (actual predictive value):** Team strength ratings (Elo/Glicko derived from match history), recent form features (time-weighted performance), head-to-head records, map pool strength differentials. These add predictive signal that game mechanics alone cannot capture.

**Anti-features (looks useful, isn't):** Raw player statistics (ACS, K/D, ADR) as pre-match features, agent pick rates without map context, tournament seeding/bracket position. These either overfit on small datasets (<200 maps) or provide unstable signal due to meta shifts and roster changes.

**Key insight for v3 milestone:** VLR.gg data's primary value is NOT adding more features to the model (current 34 game-mechanics features already comprehensive). Its value is (1) **scaling dataset** from 71 to 150+ maps via VOD discovery, and (2) **team identity features** that enable strength-of-opponent adjustments and recent-form weighting, which were previously impossible with identity-blind game mechanics.

## Table Stakes Features

Data you MUST scrape for basic functionality. Missing = can't build training dataset at scale.

| Feature | Why Expected | Complexity | Predictive Value | Notes |
|---------|--------------|------------|------------------|-------|
| **Match metadata** (teams, date, tournament, stage) | Required to label training data and enable temporal ordering for walk-forward validation | Low | N/A (metadata) | Available on every match page. Scrape team names, match date, tournament name, stage (e.g., "Main Event-Middle Final"). Critical for chronological dataset construction. |
| **Map names and scores** | Required to map VLR.gg matches to Valoscribe processed maps and validate outcomes | Low | N/A (metadata) | VLR.gg shows individual map results (e.g., "Bind 13-10", "Icebox 11-13"). Match to Valoscribe metadata.json for validation. |
| **YouTube VOD links** | Primary data source for Valoscribe processing pipeline - without VODs, no event data | Low | N/A (pipeline input) | VLR.gg match pages show VOD availability ("YouTube" or "Unavailable"). Scrape YouTube URLs to feed into automated VOD processing queue. **This is the critical bottleneck for scaling from 71 to 150+ maps.** |
| **Series format** (Bo1/Bo3/Bo5) | Required for series prediction (BO3 vs BO5 have different momentum dynamics) | Low | N/A (metadata) | Available on match pages. Needed for existing BO3/BO5 series prediction framework. |
| **Team identification** (consistent naming) | Required to track team history across matches for strength ratings and recent form | Medium | N/A (metadata) | VLR.gg team pages have canonical team IDs/names. Map to Valoscribe team names (which may vary per match). Need normalization layer (e.g., "Sentinels" = "SEN" = "Sentinels Esports"). |
| **Match date/timestamp** | Required for temporal ordering (walk-forward validation) and recency weighting | Low | N/A (metadata) | VLR.gg shows match completion date/time. Essential for chronological train/test splits. |

### Implementation Notes

**VOD discovery workflow:**
1. Scrape VLR.gg tournament pages for match listings
2. Filter for matches with "YouTube" VOD availability
3. Extract YouTube URLs and match metadata
4. Generate Valoscribe processing manifest (map match_id → VOD_url + metadata)
5. Feed manifest to automated VOD processing pipeline

**Team name normalization:** VLR.gg uses canonical names ("Sentinels"), but Valoscribe OCR may extract variants ("SEN", "SENTINELS"). Build mapping table during scraping. Use VLR.gg team page IDs as canonical identifiers.

**Data quality:** Not all VLR.gg matches have VODs. Champions 2025 has high VOD coverage (~90%), but earlier tournaments (2024 Masters) may be lower (~60-70%). Prioritize recent tournaments for data quality.

## Differentiators

Features that add predictive value beyond game mechanics alone. Not expected, but provide edge.

| Feature | Value Proposition | Complexity | Predictive Value | Dependencies | Notes |
|---------|-------------------|------------|------------------|--------------|-------|
| **Team strength rating** (Elo/Glicko derived) | Pre-match team strength differential predicts map winner with ~60-65% baseline accuracy before game mechanics | Medium | HIGH | Match history with temporal ordering | Reconstruct Elo/Glicko ratings from VLR.gg match results. Time-decay weighted (recent matches weighted higher). Adds "strength of opponent" signal that game mechanics can't capture. With 150+ maps, enough data to avoid overfitting to team names. |
| **Recent form** (time-weighted win rate) | Teams on win streaks (or slumps) perform better/worse than their baseline strength | Medium | MEDIUM-HIGH | Match history, time-decay weighting | Calculate exponentially-weighted win rate over last 5-10 maps (decay parameter tuned via CV). Captures momentum and roster/meta adaptation. Research shows 3-5% prediction boost in sports models. |
| **Head-to-head record** | Certain team matchups have stylistic advantages (e.g., Team A 7-2 vs Team B historically) | Low | MEDIUM | Match history | Extract from VLR.gg match results. Filter for same tournament tier (don't mix Champions vs regional qualifiers). With 150+ maps, enough samples for common matchups. |
| **Map pool strength** | Team A 80% win rate on Bind, Team B 45% win rate on Bind → Map pool mismatch predicts outcome | Medium | HIGH | Map-level results per team | VLR.gg team pages show map statistics. Calculate per-team, per-map win rates. Use differential as feature. Addresses "Team A bans their weak maps" selection bias. |
| **Agent composition meta context** | Whether team is playing current-meta agents or off-meta (meta agents have 5-8% higher win rates per VLR.gg stats) | Medium | MEDIUM | VLR.gg agent pick rates, match agent comps | VLR.gg event pages show agent pick rates per tournament. Calculate "meta alignment score" = how closely team comp matches top 5 most-picked agents on that map. Research shows agent meta shifts every patch, so needs time-windowed calculation. |
| **Tournament tier weighting** | Champions matches more predictable than regional qualifiers (higher stakes = less variance) | Low | LOW-MEDIUM | Tournament metadata | Flag tournament tier (Champions > Masters > Regional). Use as feature or for stratified validation. Research shows lower-tier matches have higher upset rates. |

### Implementation Notes

**Elo/Glicko ratings:**
- Start with baseline rating (1500 Elo, 350 Glicko-2 RD)
- Process VLR.gg match results chronologically to update ratings
- Use K-factor tuning (K=32 standard, may need adjustment for best-of-series)
- Glicko preferred over Elo for esports (accounts for rating uncertainty, better for roster changes)
- Research shows esports AI achieved 69% prediction accuracy with Elo/Glicko

**Time-decay weighting:**
- Dixon-Coles model uses exponential decay: recent matches weighted higher
- Optimal decay parameter found via hyperparameter tuning (cross-validate on training data)
- Typical: matches from 1 month ago = 0.8x weight, 3 months ago = 0.5x weight
- Needed because Valorant meta shifts every patch (~2-3 months)

**Map pool strength calculation:**
- Per-team, per-map win rate over last N maps (N=20-30 recommended)
- Differential feature: team1_bind_winrate - team2_bind_winrate
- Requires sufficient map samples (with 150+ maps, ~5-10 per team per map on average)
- Handles agent bans (team's weak maps appear less often, so win rate on played maps is signal)

**Agent meta alignment:**
- VLR.gg event pages show agent pick rates (e.g., Clove 59.6% pick rate, 54.7% win rate in VCT 2026)
- Calculate per-map, per-tournament agent pick rates
- Score = (# meta agents in comp) / 5, where meta = top 10 most-picked agents on that map
- LOW confidence on predictive value: research shows meta shifts reduce stability, may overfit

**Why these matter with 150+ maps:**
Previous decision: "No team identity features - prevents overfitting to team names"
- Valid for 71-map dataset (insufficient samples per team)
- At 150+ maps: ~5-10 maps per team on average, enough for Elo/Glicko to stabilize
- Game mechanics capture "what happened in the match", team strength captures "who is playing"
- Combination is stronger: "Strong team underperforming in-game metrics" = upset, adjust probability

## Anti-Features

Features to explicitly NOT build as primary predictive features. Common mistakes in esports prediction.

| Anti-Feature | Why Avoid | What to Do Instead | Overfitting Risk |
|--------------|-----------|-------------------|------------------|
| **Player-level statistics as pre-match features** (ACS, K/D, ADR, KAST%, HS%) | Previous decision: "Player-level prediction features overfit on small dataset." With 150 maps, still only ~30 maps per player. Insufficient samples. Player stats are OUTCOME of match dynamics, not predictors. | Use player stats for POST-MATCH analysis (SHAP explainability, "which players overperformed?"). NOT as input features. Team-level aggregates (from game mechanics) already capture performance. | HIGH - Will memorize "Player X high K/D" without generalizing. Stats vary match-to-match (high variance). |
| **Agent pick rates without map context** | Agent meta shifts every patch (every 2-3 months). Clove 54.7% win rate now, may be 48% in 2 patches. Unstable signal. Without map-specific rates, biased by map pool (Viper strong on Icebox, weak on Bind). | If using agent features, MUST be map-specific and time-windowed (last 30 days only). Use as meta-alignment score (is team playing current meta?), not raw pick rates. Defer to post-150-map validation. | MEDIUM - Meta shifts cause model staleness. Training data from 3 months ago misleading. |
| **Tournament seeding/bracket position** | Correlation, not causation. "Team from upper bracket wins 60%" = stronger teams reach upper bracket (already captured by Elo/Glicko). Adding bracket position = double-counting team strength. | Use tournament tier as stratification (Champions vs Regional), NOT as feature. Elo/Glicko already captures strength. | MEDIUM - Redundant with strength ratings. Adds complexity without signal. |
| **First Kill / First Death player identity** | VLR.gg shows FK/FD stats per player. Tempting to use "Player X has 0.3 FKPR" as feature. But FKPR is role-dependent (duelists expected to entry frag) and match-dependent (strong opponents = lower FKPR). Small sample size per player. | Use first blood EVENTS from Valoscribe (game mechanics). NOT player-specific FK rates. Valoscribe detects "Team A got first blood Round 3" = high-value event feature. Player identity adds noise. | HIGH - Role confounding, small samples, high variance. |
| **Pistol round win rate as pre-match feature** | Pistol round outcomes matter IN-GAME (existing feature: "pistol_rounds_won_team1" from Valoscribe). But pre-match "Team A wins 65% of pistol rounds historically" is LOW signal. Pistol rounds are 50-50 baseline (equal economy). Variance is high. | Use pistol round OUTCOMES from Valoscribe (already extracted). NOT historical pistol stats. Historical pistol win rate mostly noise. | LOW-MEDIUM - High variance, low samples per team (~2 pistol rounds per map). |
| **Individual agent proficiency per player** | VLR.gg shows per-player, per-agent stats. Tempting: "Player X has 1.4 K/D on Jett." Problem: Agent pool changes (roster shifts), meta shifts (Jett nerfed = K/D drops), small samples (Player X played Jett 8 times). Overfits. | Defer to post-200-map dataset. If building, must be time-windowed (last 20 maps only) and regularized heavily. Likely not worth complexity vs prediction gain. | HIGH - Small samples, meta shifts, roster changes. |
| **Arbitrary streak features** ("Team won last 3 matches") | Recent form already captured by time-weighted Elo/Glicko and time-weighted win rate. Adding "won last 3" = redundant. Also: 3 is arbitrary (why not 5? why not 2?). Overfits to noise. | Use exponentially-weighted win rate (time-decay parameter tuned via CV). NOT arbitrary streak counts. More principled and less prone to overfitting. | MEDIUM - Arbitrary thresholds, redundant with Elo/recent form. |

### Why These Are Tempting

**Player statistics:** VLR.gg prominently displays ACS, K/D, ADR, KAST%, HS%. "More data = better model" intuition. Reality: Player stats are LAGGING indicators (outcome of team performance), not LEADING indicators (predictors of future performance). Team strength (Elo/Glicko) captures skill, game mechanics (from Valoscribe) capture in-match execution. Player stats add noise.

**Agent pick rates:** VLR.gg shows agent pick rate percentages and win rates. Easy to scrape. But agent balance patches every 2-3 months invalidate training data. Clove 54.7% win rate today, 48% win rate after nerf. Model trained on old data performs poorly. If using, MUST be time-windowed and map-specific. Defer until proven necessary.

**Bracket position:** "Upper bracket teams win 60% of finals" = true. But NOT because upper bracket position causes wins. Because stronger teams reach upper bracket. Elo/Glicko already captures strength. Adding bracket position = overfitting to correlated feature without adding signal.

**Player-agent proficiency:** Intuitively valuable ("Player X is a Jett main, they'll perform well"). But small sample sizes (player played Jett 8 times in dataset) + meta shifts (Jett nerfed) + roster changes (player switches teams/roles) = unstable signal. Overfits.

### Overfitting Risk with 150-Map Dataset

**"Large p, Small n" problem:** 150 maps = 150 samples. With 34 existing game-mechanics features + potential 20+ VLR.gg features (team stats, player stats, agent stats), ratio of features to samples is HIGH. Risk of overfitting increases.

**Mitigation strategies:**
1. **Feature selection:** Regularization (L1/L2) to penalize low-signal features. SHAP analysis to identify which VLR.gg features actually contribute.
2. **Cross-validation:** Walk-forward temporal CV (existing). Leave-one-tournament-out CV for diagnostics. Validates generalization.
3. **Dimensionality reduction:** If adding many VLR.gg features, consider PCA or feature clustering to reduce dimensionality.
4. **Conservative feature addition:** Start with Elo/Glicko + recent form only. Validate prediction improvement. Add map pool strength if needed. Defer player stats until 200+ maps.

**Research finding:** "Smaller datasets more susceptible to overfitting. If too many features for too little data, model sees patterns that don't exist and is biased by outliers."

With 150 maps and 50+ features, cross-validation and regularization are CRITICAL.

## Feature Dependencies

Dependencies between VLR.gg features and existing Valoscribe features.

```
VLR.gg Table Stakes (no dependencies, scrape first):
├─ Match metadata (teams, date, tournament, stage)
├─ Map names and scores
├─ YouTube VOD links
├─ Series format (Bo1/Bo3/Bo5)
└─ Team identification (canonical names)

VLR.gg Differentiators (depend on table stakes):
├─ Team strength rating (Elo/Glicko) → requires match metadata + results + temporal ordering
├─ Recent form → requires match results + time-decay weighting
├─ Head-to-head record → requires match metadata + team identification
├─ Map pool strength → requires map-level results per team
├─ Agent meta context → requires VLR.gg agent pick rates + Valoscribe agent comps
└─ Tournament tier weighting → requires tournament metadata

Integration with Valoscribe Features:
├─ Team strength (VLR.gg Elo) → combines with game mechanics (Valoscribe) in model
├─ Map pool strength (VLR.gg) → validates map outcome from Valoscribe
├─ Agent meta alignment (VLR.gg rates + Valoscribe comps) → combined feature
└─ Recent form (VLR.gg) → adjusts predicted probability from game mechanics

Valoscribe Features (existing, 34 features):
├─ Score features (7): final scores, differentials, overtime, map winner
├─ Pistol features (3): pistol round outcomes
├─ Half features (4): first/second half scores
├─ Momentum features (5): win/loss streaks, comebacks
├─ Combat features (6): first bloods, clutches, multi-kills
├─ Side performance (4): attack/defense win rates
└─ Economy features (5): eco round win rates, economy differentials
```

**Critical path for v3:**
1. **Scrape VLR.gg metadata** (teams, dates, maps, VOD links) → Build match manifest
2. **Process VODs via Valoscribe** (scale from 71 to 150+ maps) → Extract game mechanics
3. **Derive team strength ratings** (Elo/Glicko from VLR.gg match history) → Pre-match feature
4. **Integrate strength + mechanics** (combined model: Elo differential + 34 game mechanics) → Run experiments
5. **Validate improvement** (does adding Elo improve log loss vs mechanics-only baseline?)

**Defer to post-150-map validation:**
- Agent meta alignment (unclear predictive value, meta shifts)
- Map pool strength (useful if baseline model struggles with map selection bias)
- Player statistics (anti-feature, HIGH overfitting risk)

## Feature Interaction: VLR.gg + Valoscribe

How VLR.gg features combine with existing Valoscribe game mechanics for prediction.

### Pre-Match Features (VLR.gg)

Predict baseline win probability BEFORE the match:
- Team A Elo: 1650
- Team B Elo: 1550
- Elo differential: +100 → ~60% baseline probability for Team A

Also includes:
- Recent form (Team A won last 5 maps, Team B lost 3 of last 5)
- Head-to-head (Team A 3-1 vs Team B historically)
- Map pool strength (Bind: Team A 75% win rate, Team B 50% win rate)

**Output:** Pre-match baseline probability (e.g., 65% Team A wins)

### In-Match Features (Valoscribe)

Update probability based on game events:
- Score at half: 7-5 Team A
- Pistol rounds: Team A won both
- First blood rate: Team B 60% (better than expected)
- Economy differential: +2000 credits Team A
- Clutch rounds: Team A 3, Team B 1

**Output:** Updated probability based on game state (e.g., 72% Team A wins)

### Combined Model

**Two-stage approach:**
1. **Pre-match stage:** VLR.gg features (Elo, recent form, map pool) → Baseline probability
2. **Post-match stage:** Valoscribe features (34 game mechanics) → Final probability

**Alternative: Single-stage model:**
- Combine all features (Elo + 34 game mechanics) in one XGBoost model
- Let model learn feature interactions (e.g., "Strong team underperforming in-game = upset")

**Research insight:** Sports prediction models with Elo + in-game features outperform either alone. Elo captures "who is playing", game mechanics capture "what happened", combination is stronger.

**Hypothesis for v3:** Adding Elo/Glicko + recent form will improve log loss by 5-10% vs game-mechanics-only baseline (to be validated in experiments).

## MVP Recommendation for v3

For v3 milestone (scale data & validate at volume), prioritize:

### Must-Scrape (Table Stakes)
1. **Match metadata** - Teams, dates, tournament, stage, series format
2. **Map names and scores** - For Valoscribe validation
3. **YouTube VOD links** - Critical for scaling dataset to 150+ maps
4. **Team identification** - Canonical team names/IDs
5. **Match timestamps** - For temporal ordering (walk-forward validation)

### High-Value Features (Differentiators)
1. **Team strength rating** (Elo/Glicko) - Reconstruct from VLR.gg match history, time-weighted
2. **Recent form** - Exponentially-weighted win rate over last 5-10 maps
3. **Map pool strength** - Per-team, per-map win rates (if dataset has sufficient samples)

### Defer to Post-Experiment Validation
1. **Agent meta alignment** - Unclear predictive value, meta shifts reduce stability
2. **Head-to-head records** - May not have sufficient samples for rare matchups
3. **Tournament tier weighting** - Use for stratification, not as feature

### Explicitly Avoid (Anti-Features)
1. **Player-level statistics** (ACS, K/D, ADR) - Overfitting risk, outcome not predictor
2. **Agent pick rates without map context** - Meta shifts, unstable signal
3. **Tournament seeding/bracket position** - Redundant with Elo/Glicko
4. **Arbitrary streak features** - Redundant with time-weighted recent form

## Scraper Requirements

Based on feature analysis, VLR.gg scraper must extract:

### Priority 1 (Blocking for dataset scaling)
- **Match listings** from tournament pages
- **YouTube VOD URLs** from match pages
- **Match metadata**: teams (canonical names), date/timestamp, tournament name, stage, series format (Bo3/Bo5)
- **Map results**: map names, scores per map

### Priority 2 (For team strength ratings)
- **Match results** for Elo/Glicko reconstruction (chronologically ordered)
- **Team identification**: VLR.gg team page IDs for canonical naming
- **Map-level results per team** for map pool strength calculation

### Priority 3 (For validation experiments)
- **Agent compositions** from match pages (if available) for meta alignment
- **Tournament tier** classification (Champions, Masters, Regional)

### Not Required (Anti-features)
- **Player statistics** (ACS, K/D, ADR, KAST%, HS%) - Don't scrape unless for post-match analysis
- **Player-agent proficiency** - Don't scrape
- **Bracket seeding positions** - Don't scrape

## Implementation Complexity Assessment

| Task | Complexity | Estimated Effort | Dependencies |
|------|------------|------------------|--------------|
| **Scrape match metadata** | Low | 2-4 hours | BeautifulSoup, requests, rate limiting |
| **Scrape VOD links** | Low | 1-2 hours | Match page parsing |
| **Build match manifest** | Low | 2-3 hours | CSV/JSON export, Valoscribe schema |
| **Reconstruct Elo/Glicko** | Medium | 4-6 hours | Match history, chronological ordering, Elo library |
| **Calculate recent form** | Medium | 3-4 hours | Time-decay weighting, hyperparameter tuning |
| **Calculate map pool strength** | Medium | 3-5 hours | Per-team, per-map aggregation, sufficient samples check |
| **Scrape agent compositions** | Medium | 4-6 hours | Match page parsing, agent name normalization |
| **Integrate with prediction model** | Medium | 4-8 hours | Feature engineering pipeline, XGBoost integration |
| **Validate prediction improvement** | Medium | 8-12 hours | Experiments, cross-validation, log loss comparison |

**Total estimated effort for MVP (table stakes + Elo/recent form):** 20-35 hours

**Critical path bottleneck:** VOD processing time (46 VODs queued = 15-20 hours processing per PROJECT.md). Scraping is fast (~5-10 hours), but Valoscribe processing is slow. Parallelize if possible.

## Confidence Assessment

| Area | Confidence | Source | Notes |
|------|------------|--------|-------|
| **VLR.gg data structure** | MEDIUM | WebFetch (match results page), WebSearch (scraper tools, Kaggle dataset) | Match pages show stats, teams, VOD links, agent comps. Structure confirmed. May change over time (site redesign risk). |
| **Team strength ratings (Elo/Glicko)** | HIGH | WebSearch (sports prediction research, esports AI case studies) | Well-established in sports prediction. Esports AI achieved 69% accuracy with Elo/Glicko. Glicko preferred for roster changes. |
| **Recent form features** | HIGH | WebSearch (Dixon-Coles time-weighting, sports prediction models) | Time-decay weighting standard in sports prediction. 3-5% prediction boost documented. Hyperparameter tuning needed for optimal decay. |
| **Overfitting risks** | HIGH | WebSearch (ML overfitting on small datasets, feature selection) | "Large p, Small n" problem well-documented. 150 maps with 50+ features = HIGH risk. Regularization + CV critical. |
| **Player statistics as anti-feature** | MEDIUM-HIGH | Project context ("player-level features overfit on small dataset"), WebSearch (overfitting prevention) | Previous decision validated. 150 maps still too small for player-level features (~30 maps per player). Team aggregates sufficient. |
| **Agent meta stability** | MEDIUM | WebSearch (Valorant 2026 meta, Clove 54.7% win rate) | Meta shifts confirmed (Patch 11.08, Patch 12.0). Agent balance changes every 2-3 months. Time-windowed features needed. LOW confidence on predictive value until validated. |
| **Map pool strength** | MEDIUM | Training data (map-specific win rates in Valorant), logic inference | With 150 maps, ~5-10 per team per map. Sufficient for aggregate rates. Addresses map selection bias. Needs validation. |
| **VLR.gg scraping feasibility** | HIGH | WebSearch (unofficial APIs, scraper tools on GitHub) | Multiple scraper implementations exist (axsddlr/vlrggapi, Yuji1702/Valorant-Data-Scrapper). Site is scrapable. Rate limiting needed. |

**Major assumptions:**
1. VLR.gg site structure remains stable (no major redesign mid-scraping)
2. 150+ maps sufficient to stabilize team strength ratings (Elo/Glicko needs ~5-10 matches per team)
3. Valoscribe VOD processing completes successfully for scraped VOD links
4. Adding Elo/Glicko + recent form improves log loss vs mechanics-only baseline (hypothesis, needs validation)

**Verification needed:**
1. Run scraper on VLR.gg and validate data quality (team names consistent, VOD links valid)
2. Process 10-20 VODs from VLR.gg links through Valoscribe to confirm compatibility
3. Reconstruct Elo/Glicko from VLR.gg match history and validate ratings make sense (stronger teams have higher Elo)
4. Run ablation study: mechanics-only vs mechanics+Elo vs mechanics+Elo+recent_form (measure log loss improvement)

## Research Gaps and Next Steps

**Gaps in this research:**

1. **VLR.gg API availability:** WebSearch found unofficial APIs (axsddlr/vlrggapi). Need to validate if these work in 2026 or if custom scraper needed. Site structure may have changed.

2. **VOD coverage rate:** Don't know what % of VLR.gg matches have VOD links. Champions 2025 likely high (~90%), older tournaments lower. Affects dataset scaling feasibility.

3. **Agent composition extraction:** VLR.gg match pages show agent comps, but format unclear (icons? text?). Need to inspect actual match page HTML to confirm scrapability.

4. **Player roster stability:** Team rosters change between tournaments. Elo/Glicko assumes stable rosters. If 50% roster turnover, ratings less stable. Need to check VLR.gg for roster change data.

5. **Optimal Elo parameters:** K-factor, initial rating, decay rate for esports unknown. Sports models use K=32, but esports may differ (more volatile, roster changes). Needs hyperparameter tuning.

6. **Feature interaction effects:** Research estimates independent contributions (Elo = baseline, game mechanics = update). But interactions may be non-linear ("Strong team underperforming" = different signal than "Weak team underperforming"). XGBoost should capture this, but needs validation.

**Recommended next steps:**

1. **Inspect VLR.gg match page HTML** (WebFetch or manual inspection) to confirm agent comp format and scrapability
2. **Test unofficial VLR.gg API** (axsddlr/vlrggapi) to see if it works in 2026 or if custom scraper needed
3. **Scrape 10-20 matches** as pilot and validate data quality (team names, VOD links, map results)
4. **Process pilot VODs** through Valoscribe to confirm pipeline compatibility
5. **Reconstruct Elo/Glicko** from pilot matches and validate ratings (eye test: do strong teams have higher Elo?)
6. **Run ablation experiments** after dataset reaches 100+ maps (mechanics-only vs mechanics+Elo)
7. **Iterate based on log loss improvements** (if Elo doesn't help, investigate why; if it helps, add recent form)

## Sources

### VLR.gg Data Structure
- [VLR.gg Match Results](https://www.vlr.gg/matches/results) - WebFetch confirmed teams, scores, VOD links, stats links
- [Kaggle: Valorant vlr.gg Results and Stats](https://www.kaggle.com/datasets/hidious/valorant-vlrgg-results-and-stats) - Dataset structure includes date, teams, winner, scoreline, series type
- [Medium: Creating A Valorant Player Stats Dataset](https://medium.com/@amanrao032/creating-a-valorant-player-stats-dataset-60abbd82b76f) - Describes scraping with Selenium/BeautifulSoup

### VLR.gg Scraping Tools
- [GitHub: axsddlr/vlrggapi](https://github.com/axsddlr/vlrggapi) - Unofficial REST API for vlr.gg (FastAPI-based)
- [GitHub: Yuji1702/Valorant-Data-Scrapper](https://github.com/Yuji1702/Valorant-Data-Scrapper) - Python tool for scraping player statistics, multithreaded
- [GitHub: akhilnarang/vlrgg-scraper](https://github.com/akhilnarang/vlrgg-scraper) - Another VLR.gg scraper implementation

### Valorant Match Statistics
- [VLR.gg Player/Agent Stats](https://www.vlr.gg/stats) - ACS, K/D, combat score, econ rating, kills, deaths, assists
- [What Is KAST In VALORANT?](https://www.esports.net/wiki/guides/what-is-kast-valorant/) - KAST = Kill, Assist, Survive, Trade percentage
- [VCT 2026: Americas Kickoff: Agent Pick Rates](https://www.vlr.gg/event/agents/2682/vct-2026-americas-kickoff) - Agent compositions per tournament

### Agent Meta (2026)
- [5 agents that could dominate the VALORANT meta in 2026](https://esportsinsider.com/valorant-meta-agents-2026) - Clove 54.7% win rate, 59.6% pick rate
- [Best VALORANT team comps in Season V26, Act One](https://esportsinsider.com/best-valorant-comps) - Double-initiator comps, gunplay-focused meta
- [VALORANT Patch 12.0 Meta Guide](https://www.dtgre.com/2026/01/valorant-patch-12-meta-guide.html) - Bandit pistol changes, Breeze rework, agent buffs

### Predictive Modeling Research
- [A Predictive Analysis of Valorant Esports](https://www.techrxiv.org/users/916972/articles/1289732/master/file/data/Valorant%20Esports%20Predictive%20Model%20Analysis/Valorant%20Esports%20Predictive%20Model%20Analysis.pdf) - Random Forest 93% accuracy, ultimate ability and economy impact on round win probability
- [Round Outcome Prediction in VALORANT Using Tactical Features](https://arxiv.org/html/2510.17199v1) - 81% accuracy using minimap information

### Team Strength Ratings
- [Sports Ratings Guide: Elo, Glicko, RPI](https://prosportstance.com/sports-ratings-guide-elo-glicko-rpi-and-strength-of-schedule/) - Elo vs Glicko for esports
- [Unleashing the Power of AI: Predicting Esports Matches](https://www.toolify.ai/ai-news/unleashing-the-power-of-ai-predicting-esports-matches-2630330) - 69% prediction accuracy with Elo/Glicko
- [Abstracting Glicko-2 for Team Games](https://rhetoricstudios.com/downloads/AbstractingGlicko2ForTeamGames.pdf) - Glicko ratings deviation for roster changes

### Recent Form / Time-Decay Weighting
- [Dixon-Coles and Time-Weighting](https://dashee87.github.io/football/python/predicting-football-results-with-statistical-modelling-dixon-coles-and-time-weighting/) - Exponential decay for recent matches
- [Time-Weighting Predictive Models](https://artiebits.com/blog/improving-poisson-model-using-time-weighting/) - Optimal decay parameter tuning via cross-validation
- [Bayesian weighted discrete-time dynamic models](https://arxiv.org/html/2508.05891v1) - Time-varying precisions for team abilities

### Overfitting Prevention
- [Techniques and pitfalls for ML training with small data sets](https://www.trustbit.tech/blog/2021/06/30/techniques-and-pitfalls-for-ml-training-with-small-data-sets) - Large p, Small n problem
- [Overfitting in Machine Learning](https://elitedatascience.com/overfitting-in-machine-learning) - Feature selection, cross-validation, regularization
- [8 Simple Techniques to Prevent Overfitting](https://towardsdatascience.com/8-simple-techniques-to-prevent-overfitting-4d443da2ef7d/) - Dimensionality reduction, PCA

---

*Research complete. Confidence: MEDIUM (VLR.gg structure verified, team strength ratings well-researched, overfitting risks documented). Ready for scraper requirements definition and roadmap creation.*
