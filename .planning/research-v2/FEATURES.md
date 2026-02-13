# Feature Landscape: VCT Match Prediction Model

**Domain:** Esports match outcome prediction (Valorant VCT) from event log data
**Researched:** 2026-02-13
**Confidence:** MEDIUM-HIGH (academic research + domain knowledge + Valorant game mechanics; limited by 71-map dataset size)

## Executive Summary

This document maps the feature engineering landscape for predicting VCT map winners and match winners from Valoscribe's event log data. The research covers three prediction targets: (1) pre-match map winner, (2) in-game map winner (updating round-by-round), and (3) series winner (BO3/BO5).

**Key finding from academic research:** Team loadout value (economy) is the single strongest predictor of round outcomes, far outweighing ultimate ability status and other features. A TechRxiv study on VCT data found loadout value dominated feature importance in logistic regression, achieving 60.61% round prediction accuracy -- modest but statistically significant. A separate TimeSformer-based approach using minimap tactical features reached ~81% accuracy mid-round, but that approach requires positional data we do not have.

**Key finding for our context:** With only 71 maps (~1,750 rounds), the biggest risk is not missing features but overfitting. The feature set should be deliberately small and high-signal. Academic CS:GO research with 122K round snapshots used ~97 features; we should use 10-20 at most given our sample size. Prioritize features with strong theoretical grounding in Valorant game mechanics over speculative features.

**Practical implication for Polymarket edge:** Pre-match prediction (map winner before the match starts) requires team strength estimation (Elo-like ratings) and map-specific performance -- features derived from historical match results, not in-game events. In-game prediction (updating as rounds progress) uses the event log features. Both are needed: pre-match sets the prior, in-game updates it.

## Table Stakes Features

Features that any competent map/match winner prediction model must include. Without these, the model has no predictive power.

### Pre-Match Features (Map Winner Before Match Starts)

| Feature | Data Source | Complexity | Expected Value | Notes |
|---------|-------------|------------|----------------|-------|
| **Team Elo / Power Rating** | VLR.gg historical match results | Medium | CRITICAL | Riot's GPR uses 80/20 team/league Elo weighting, achieves 65% predictive accuracy. Must build our own from VCT match history. K-factor tuning and recency weighting matter. |
| **Map-specific win rate per team** | VLR.gg match history by map | Low | HIGH | VCT Champions 2025 shows huge map variance: Abyss 57.9% attack-sided, Sunset 60.4% defense-sided. Teams have dramatically different map pools. |
| **Starting side (attack/defense)** | VLR.gg metadata (already scraped) | Low | HIGH | At Champions 2025 pro level, defense wins 50-60% of rounds depending on map. Starting defense on Sunset vs Abyss is very different. |
| **Head-to-head record** | VLR.gg match history | Low | MEDIUM | Direct matchup history. Limited value if teams have few prior meetings. Decays quickly with roster changes. |

**Implementation notes:**

- Team Elo is the single most important pre-match feature. Without it, the model is just guessing. Build a simple Elo system from VCT match history (available via VLR.gg scraper or Kaggle datasets). Start with K=32, tune from there.
- Map-specific ratings are essential because Valorant map pool creates massive asymmetries. A team's overall Elo might be 1600, but their Bind Elo could be 1700 and their Sunset Elo could be 1400.
- Starting side matters because it determines economy flow for the first 12 rounds. On defense-heavy maps, starting defense means banking an early lead.

### In-Game Features (Map Winner Updated Round-by-Round)

| Feature | Data Source | Complexity | Expected Value | Notes |
|---------|-------------|------------|----------------|-------|
| **Current score differential** | Valoscribe `round_end` events | Low | CRITICAL | Most obvious predictor. Team at 10-5 wins more often than 5-10. Non-linear: 12-0 is not proportionally worse than 6-0 because of side swap at round 13. |
| **Round number** | Valoscribe `round_start` events | Low | HIGH | Context for all other features. Round 1 vs round 24 changes the meaning of every other feature. Also indicates half (rounds 1-12 vs 13-24) and overtime. |
| **Current side (attack/defense)** | VLR metadata + round number | Low | HIGH | Derived from starting side + round number. Side swap at round 13. Critical context for interpreting score differential. |
| **Rounds remaining to win** | Derived from score | Low | HIGH | More intuitive than raw score. "Team A needs 3 more rounds, Team B needs 7" directly maps to win probability. |
| **Economy differential (estimated)** | Valoscribe frame states (credits column) or derived from round outcomes | Medium | CRITICAL | Academic research consistently finds loadout value is the strongest round predictor. Can estimate from win/loss history using Valorant economy rules (see Economy Modeling section below). |
| **Round type (pistol/eco/force/full buy)** | Derived from economy estimates | Medium | HIGH | Eco rounds have ~20-25% win rate for the eco team. Full buy vs full buy is ~50-50. Pistol rounds are 50-50 but cascade into 2-3 bonus rounds. |

**Implementation notes:**

- Score differential alone gets you surprisingly far. A simple logistic regression on (score_diff, round_number, side) is a strong baseline.
- Economy is the biggest signal amplifier. The challenge is that Valoscribe's per-round economy data may be noisy (credits visible only during buy phase). See the Economy Modeling section for reconstruction approaches.
- Round type classification creates a categorical feature that captures most of the economy signal in a simpler form.

## Differentiators

Features that provide edge over simple score-based models. These separate a prediction model with Polymarket edge from a toy model.

### High-Value Differentiators

| Feature | Data Source | Complexity | Expected Value | Rationale |
|---------|-------------|------------|----------------|-----------|
| **Pistol round outcomes** | Valoscribe round_end events (rounds 1, 13) | Low | HIGH | Teams winning both pistol rounds have 74% map win rate (2025 VCT data). Pistol wins cascade into 2-3 bonus rounds via economy advantage. Encode as binary features: won_pistol_1, won_pistol_2. |
| **First half score** | Valoscribe round_end events at round 12 | Low | HIGH | Score after first half (before side swap) is highly predictive. A team up 8-4 on attack side of a defense-heavy map is in excellent position. Encodes side advantage + score differential. |
| **Win streak / loss streak (current)** | Derived from round_end sequence | Low | MEDIUM-HIGH | Consecutive round wins reflect momentum and economy snowballing. A 4-round win streak almost always means the winning team has full economy and the losing team is on eco. |
| **Economy state estimation** | Derived from round outcomes + Valorant economy rules | Medium | HIGH | Reconstruct team economy from win/loss sequence, spike plants, and kill counts using Valorant's deterministic economy system. See Economy Modeling section. |
| **Agent composition encoding** | VLR.gg metadata (agent picks per map) | Medium | MEDIUM | Certain compositions have higher win rates on specific maps. Encode as categorical or embedding. Most useful for pre-match prediction. Value decreases in-game because comp is constant. |
| **Spike plant rate** | Valoscribe spike_plant events / total rounds | Low | MEDIUM | Teams that plant spike more often on attack have better map control. Spike plant also grants +300 credits per teammate, affecting economy. |
| **First blood rate (per-round)** | Valoscribe kill events (first kill each round) | Low | MEDIUM-HIGH | Team getting first kill wins the round 65-70% of the time. Track which team gets first blood more consistently as a form indicator. |

### Medium-Value Differentiators

| Feature | Data Source | Complexity | Expected Value | Rationale |
|---------|-------------|------------|----------------|-----------|
| **Post-plant win rate** | spike_plant + round_end events | Low | MEDIUM | Attacking team wins 60-65% post-plant even when outnumbered. Track team-specific post-plant conversion as form indicator. |
| **Round win condition distribution** | Valoscribe round_end.win_condition | Low | MEDIUM | Track % of rounds won by elimination vs spike vs timeout. Teams winning mostly by elimination may be more consistent than teams relying on spike detonation. |
| **Overtime indicator** | Derived from score (both teams >= 12) | Low | MEDIUM | Overtime rounds have different dynamics (alternating economy, high pressure). Flag overtime separately. |
| **Side-specific round win rate** | Valoscribe round_end + side info | Low | MEDIUM | Track attack win rate vs defense win rate within the current map. Strong attack team on defense-heavy map is different from weak attack team on same map. |
| **Kill differential per round** | Valoscribe kill events aggregated | Low | MEDIUM | Average alive differential at round end. Teams winning with 3+ alive vs barely winning 1v0 suggests different dominance levels. |
| **Clutch events (1vN wins)** | Valoscribe kill events + round_end | Medium | LOW-MEDIUM | Track rounds won from disadvantaged alive positions. Clutch rate is somewhat predictive of team composure but high variance with small samples. |

### Pre-Match Only Differentiators

| Feature | Data Source | Complexity | Expected Value | Rationale |
|---------|-------------|------------|----------------|-----------|
| **Recent form (last N matches)** | VLR.gg match history | Low | MEDIUM | Win rate in last 5-10 matches. Teams on hot streaks perform better. Decays Elo lag. |
| **Map pick/ban patterns** | VLR.gg match details | Medium | MEDIUM | Which team picked which map in the veto. Teams pick maps they are confident on. The picked map is likely their stronger map. |
| **Tournament stage** | Match metadata | Low | LOW-MEDIUM | Group stage vs playoffs. Teams may play differently under elimination pressure. Small dataset makes this hard to validate. |
| **Roster recency** | VLR.gg roster data | High | LOW-MEDIUM | How long the current roster has been together. New rosters underperform their individual Elo sum. Hard to quantify with limited data. |

## Anti-Features

Features that seem useful but add noise, cause overfitting, or are not extractable from available data. Explicitly do NOT build these.

| Anti-Feature | Why It Seems Useful | Why It Hurts | What to Do Instead |
|--------------|--------------------|--------------|--------------------|
| **Individual player K/D ratios as model features** | "Star players carry games" | With 71 maps, player-level features massively overfit. A player appearing in 10 maps is not enough data. Also creates dimensionality explosion (10 players x N stats). | Use team-aggregate statistics. Player skill is captured by team Elo. |
| **Per-agent win rates as features** | "Some agents are OP" | Agent meta shifts between patches. Historical agent win rates from 3 months ago may be inverted. Also, composition synergy matters more than individual agent power. | Use agent composition as a categorical feature (comp hash or cluster), not individual agent flags. |
| **Ability usage counts** | "Teams using more abilities win more" | Ability usage is correlated with round length and engagement style, not directly with winning. High ability usage in losing rounds inflates the count. Noise, not signal. | Use ultimate availability count (binary per player: ready/not ready) if available. Simpler, more predictive. |
| **Exact economy values as continuous features** | "More precise economy = better prediction" | Exact credit values have more noise than signal at our sample size. The difference between $4,200 and $4,400 is meaningless. | Categorize economy into tiers: pistol/eco/half-buy/full-buy. Reduces dimensionality, captures the signal. |
| **Player health totals mid-round** | "CSGO models use health" | CS:GO round snapshot datasets (122K snapshots) can support this. We have ~1,750 rounds total. Health mid-round is a within-round predictor, not a map-winner predictor. Useful only for round-level prediction with more data. | For map prediction, use round outcome (win/loss) which integrates all mid-round events. |
| **Weapon inventory per player** | "Knowing who has an Operator matters" | Not reliably extractable from Valoscribe data. Also massively increases feature space. Economy tier captures the same signal (full-buy teams have Operators). | Use economy tier classification. |
| **Map positioning / minimap data** | "Position is everything in FPS" | Not available in our data. The TimeSformer paper achieving 81% accuracy used minimap video frames, not event logs. Different data modality entirely. | Accept that event-log models have a ceiling below positional models. Focus on what we have. |
| **Time-series features with lag > 3 rounds** | "Long-term momentum matters" | With 24 rounds per map and 71 maps, time-series features with long lookbacks have almost no training signal. Overfitting risk is extreme. | Use simple streak length (current consecutive wins/losses) as a proxy. Max lookback of 2-3 rounds. |
| **Cross-map features within a series** | "Winning map 1 gives momentum for map 2" | Theoretically true but with 71 maps across ~24 series, we have ~24 data points for this. Not enough to learn from. | Handle series prediction separately with simple BO3/BO5 probability calculation from per-map probabilities. |

### Why These Seem Tempting But Fail

**The overfitting trap with 71 maps:** Every additional feature requires more data to fit reliably. The rule of thumb is 10-20 samples per feature for logistic regression. With 71 map-level observations, that means 3-7 features maximum for pre-match prediction. For round-level prediction (~1,750 rounds), 80-170 features max -- but this assumes independent rounds, which they are not (rounds within a map are correlated).

**The "more data is better" fallacy:** It is tempting to throw every available signal into the model. But with small datasets, irrelevant features inject noise that degrades performance. A 5-feature model with strong signal outperforms a 50-feature model with mostly noise on 71 samples.

## Feature Dependencies

How features relate to each other and what must be built first.

```
Data Sources:
  VLR.gg metadata (already scraped by Valoscribe)
  ├── Team names, player names, agent compositions
  ├── Map name, starting sides
  └── Historical match results (need to scrape additional)

  Valoscribe JSONL event logs (71 maps)
  ├── kill events (killer, victim, agents, headshot, round)
  ├── round_start / round_end (winner, score, win_condition)
  ├── spike_plant per round
  ├── ability_used / ultimate_used per player
  └── match_start / match_end (final score)

  Valoscribe CSV frame states (71 maps)
  ├── Per-player health, armor, abilities, ultimates, credits
  └── Sampled at 4fps

Feature Engineering Pipeline:

  Tier 0 - Raw Ingestion (no engineering needed):
  ├── Round outcomes (win/loss sequence)
  ├── Final map score
  ├── Map name
  ├── Starting side
  └── Agent compositions

  Tier 1 - Simple Derivations:
  ├── Score differential at each round
  ├── Current side at each round (from starting_side + round_number)
  ├── Rounds remaining to win
  ├── Pistol round outcomes (rounds 1 and 13)
  ├── First half score
  ├── Win/loss streak length
  ├── First blood per round (first kill event)
  └── Spike plant binary per round

  Tier 2 - Moderate Engineering:
  ├── Economy estimation (from win/loss + spike + kills + Valorant rules)
  ├── Round type classification (pistol/eco/half/full from economy)
  ├── Team Elo ratings (from historical match results)
  ├── Map-specific Elo (from map-filtered history)
  ├── Agent composition encoding (hash, cluster, or embedding)
  └── Kill differential per round (alive counts at round end)

  Tier 3 - Complex / External Data:
  ├── Head-to-head record (requires historical scraping)
  ├── Recent form indicator (last N matches)
  ├── Map pick/ban data (which team chose which map)
  └── Roster stability indicator
```

## Economy Modeling

Economy is the single highest-value feature for round prediction. Since exact economy data from Valoscribe may be noisy (credits only visible during buy phase), we should reconstruct economy from game events using Valorant's deterministic economy rules.

### Valorant Economy Rules (for reconstruction)

**Starting credits:** 800 per player (round 1 and round 13)

**Round win reward:** 3,000 per player

**Round loss rewards (loss bonus escalation):**
- 1st consecutive loss: 1,900 per player
- 2nd consecutive loss: 2,400 per player
- 3rd+ consecutive loss: 2,900 per player

**Special case:** Losing while surviving with no spike plant: 1,000 per player

**Kill reward:** 200 per kill

**Spike plant reward:** 300 per teammate (attacking team only, even if round lost)

**Max credits:** 9,000 per player

### Reconstruction Approach

For each round, estimate team economy as:

```
team_credits[round] = sum of:
  - previous round credits remaining (capped at 9000/player)
  - round outcome reward (win: 3000/player, loss: escalating bonus)
  - kill rewards (200 * kills_this_round)
  - spike plant bonus (300/player if attacking team planted)
  - minus loadout cost (estimated from economy tier)
```

**Simplification for modeling:** Rather than tracking exact credits, classify each round's buy state:
- **Pistol round**: Rounds 1 and 13 (always 800 credits, special buy)
- **Eco/save**: 0-1 rounds after a loss streak reset (team has < ~2,500/player)
- **Half-buy/force**: Team has ~2,500-4,000/player (partial equipment)
- **Full buy**: Team has > ~4,000/player (rifles, full armor, abilities)

This classification captures ~80% of the economy signal with zero noise from credit detection errors.

### Economy as Feature

The most useful economy features for map-winner prediction:

1. **Buy differential per round**: Both teams full-buy (neutral), one eco one full (strong predictor), both eco (neutral)
2. **Eco round win rate**: How often does this team win eco rounds? (form indicator)
3. **Economy resets count**: How many times has each team been fully broken (loss bonus back to 1,900)? More resets = worse economy management.
4. **Bonus round conversion**: After winning pistol, how many of the next 2-3 rounds did the team also win? (should be 2-3, anything less means economy advantage wasted)

## Prediction Target Design

### Target 1: Pre-Match Map Winner

**What:** Binary classification -- which team wins this map, before the match starts.

**Features (recommended, ~5-7 total):**
1. Team A Elo - Team B Elo (differential)
2. Team A map-specific win rate - Team B map-specific win rate
3. Starting side advantage (map-specific attack/defense win rate differential)
4. Head-to-head win rate (if available, else drop)
5. Team A recent form - Team B recent form (last 5 match win rate)
6. Map picker indicator (which team picked this map in veto)

**Model:** Logistic regression or gradient-boosted trees with strong regularization. With only 71 training samples at the map level, logistic regression with L2 regularization is safest.

**Evaluation:** Leave-one-out cross-validation (LOOCV) given small sample size. Report log loss and calibration plot, not just accuracy.

**Expected performance:** 55-65% accuracy. This is modest but potentially enough for Polymarket edge if calibration is good and market prices are inefficient on specific matchups.

### Target 2: In-Game Map Winner (Round-by-Round Update)

**What:** After each round completes, update the probability of each team winning the map.

**Features (recommended, ~8-12 per round observation):**
1. Score differential (team_a_score - team_b_score)
2. Round number
3. Current side for team_a (attack=0, defense=1)
4. Rounds team_a needs to win
5. Rounds team_b needs to win
6. Current win streak (positive = team_a streak, negative = team_b streak)
7. Economy state differential (eco/half/full buy classification difference)
8. Pistol round 1 winner (team_a=1, team_b=0)
9. Pistol round 2 winner (if round >= 13)
10. First blood rate differential (team_a first bloods - team_b first bloods, trailing window)
11. Pre-match Elo differential (prior, carried from Target 1)

**Model:** Logistic regression or XGBoost. Each round within each map is one observation (~1,750 total), but rounds within a map are correlated. Use grouped cross-validation (group = match_id) to prevent leakage.

**Evaluation:** Log loss with grouped k-fold CV (k=5 or k=10, grouped by match). Calibration curves. Compare against naive "assume current leader wins" baseline.

**Expected performance:** 65-75% accuracy averaged across all rounds. Should be near 50% at round 1 (no info) and near 95%+ at round 23 (almost decided). The value is in rounds 8-18 where uncertainty is highest and prediction has the most edge.

### Target 3: Series Winner (BO3/BO5)

**What:** Probability of each team winning the series.

**Features:** This is NOT a separate ML model. It is a probability calculation using map-level predictions.

**Formula for BO3 (first to 2 map wins):**
```
P(A wins series) = P(A wins map 1) * P(A wins map 2)                    # 2-0
                 + P(A wins map 1) * P(B wins map 2) * P(A wins map 3)  # 2-1 (A,B,A)
                 + P(B wins map 1) * P(A wins map 2) * P(A wins map 3)  # 2-1 (B,A,A)
```

Each P(A wins map X) comes from Target 1 (pre-match) or Target 2 (in-game, updated as maps are played).

**Key consideration:** Map probabilities should be map-specific (different maps have different Elo differentials). After map 1 is played, update Elo/form for map 2 prediction if desired (momentum effect), though this is hard to validate with limited data.

**After map 1 result is known (in-game series update):**
```
If A won map 1:
  P(A wins series) = P(A wins map 2) + P(B wins map 2) * P(A wins map 3)

If B won map 1:
  P(A wins series) = P(A wins map 2) * P(A wins map 3)
```

## Feature Priority Matrix

Ranked by (expected predictive value) / (implementation complexity), accounting for our 71-map constraint.

```
BUILD FIRST (highest value per effort):
  1. Score differential + round number + side     [Pre-match: N/A; In-game: CRITICAL]
  2. Team Elo from match history                   [Pre-match: CRITICAL; In-game: prior]
  3. Map-specific team win rates                   [Pre-match: HIGH; In-game: prior]
  4. Pistol round outcomes                         [In-game: HIGH; easy to derive]
  5. Economy tier classification (reconstructed)   [In-game: HIGH; medium complexity]
  6. Win/loss streak length                        [In-game: MEDIUM-HIGH; trivial to derive]

BUILD SECOND (meaningful but lower priority):
  7. First blood rate per team                     [In-game: MEDIUM; easy to derive]
  8. First half score                              [In-game: MEDIUM; trivial]
  9. Agent composition encoding                    [Pre-match: MEDIUM; medium complexity]
  10. Starting side + map interaction               [Pre-match: HIGH; trivial]
  11. Spike plant rate                              [In-game: MEDIUM; easy]
  12. Head-to-head record                           [Pre-match: MEDIUM; needs data scraping]

BUILD IF PROVEN NEEDED (validate baseline first):
  13. Round win condition distribution              [In-game: LOW-MEDIUM]
  14. Kill differential per round                   [In-game: MEDIUM; easy]
  15. Post-plant conversion rate                    [In-game: LOW-MEDIUM]
  16. Recent form indicator                         [Pre-match: MEDIUM; needs scraping]
  17. Map veto pick indicator                       [Pre-match: MEDIUM; needs data]
  18. Clutch rate                                   [In-game: LOW; high variance]

DO NOT BUILD:
  - Individual player statistics (overfit with 71 maps)
  - Per-agent win rates (meta shifts, sparse data)
  - Exact economy values (noisy, tier classification better)
  - Ability usage counts (noise, not signal)
  - Time-series features with lag > 3 rounds (overfit)
  - Mid-round features (health, alive counts) for map prediction
```

## Small Dataset Strategy

With 71 maps (~1,750 rounds), feature engineering must be disciplined.

### Rules for Feature Selection

1. **Pre-match model: Maximum 5-7 features.** With 71 observations, even logistic regression overfits at higher dimensionality. Use L2 regularization (ridge) regardless.

2. **In-game model: Maximum 10-15 features.** With ~1,750 round observations (correlated within maps), effective sample size is lower than 1,750. Use grouped cross-validation.

3. **Every feature must have theoretical justification from Valorant game mechanics.** No data-mined features. If you cannot explain why it should predict wins based on game design, do not include it.

4. **Prefer categorical over continuous.** Economy tier (4 categories) is better than exact credits (continuous with noise). Side (binary) is better than attack-round-win-rate (continuous estimated from small sample).

5. **Test each feature addition with CV.** Add one feature at a time. If CV log loss does not improve, the feature is noise. Remove it.

6. **Use regularization always.** L2 penalty for logistic regression. max_depth and min_samples constraints for tree models. Never let the model memorize.

### Expanding the Dataset

71 maps can grow via:

1. **Process more VCT VODs** via Valoscribe. Other VCT 2025 events (Kickoff, Stage 1, Stage 2, Masters) add hundreds of maps with the same format.
2. **Kaggle VCT datasets** (Champions 2025, VCT 2021-2025) provide match-level and map-level data for pre-match features (Elo, win rates). Not event-level, but sufficient for Target 1.
3. **VLR.gg scraping** provides historical match results, agent compositions, and map results going back years. Useful for Elo rating construction.

**Prioritize expanding pre-match data first.** Team Elo requires many historical matches to stabilize. 71 maps from one tournament is not enough to build reliable Elo ratings. Scrape VLR.gg for 1,000+ historical VCT match results to build Elo ratings, then use those Elo ratings as features in the 71-map model.

## Confidence Assessment

| Feature Category | Confidence | Basis |
|-----------------|------------|-------|
| Score differential as predictor | HIGH | Trivially true by game design; supported by all academic research |
| Economy as top predictor | HIGH | TechRxiv study, CS:GO Kaggle research, Riot's GPR system all confirm economy dominance |
| Team Elo as pre-match predictor | HIGH | Riot's GPR achieves 65% accuracy; standard approach in all sports prediction |
| Pistol round impact (74% map win when winning both) | MEDIUM-HIGH | VCT 2025 data from community analysis; consistent with game economics |
| First blood impact (65-70% round win rate) | MEDIUM | Commonly cited in community analysis; not verified with our specific dataset |
| Agent composition value | MEDIUM | Theoretically sound but hard to encode and meta-dependent; value unclear at 71-map scale |
| Feature count discipline (5-7 pre-match, 10-15 in-game) | HIGH | Standard ML practice for small datasets; supported by regularization theory |
| Exact win probability percentages cited | LOW | Estimates from training data and community sources; need validation on our data |

## Sources

### Academic Research (MEDIUM-HIGH confidence)

- [Round Outcome Prediction in VALORANT Using Tactical Features from Video Analysis](https://arxiv.org/html/2510.17199v1) -- TimeSformer model achieving ~81% accuracy using minimap tactical features. 21,229 rounds from 1,376 tournament videos.
- [A Predictive Analysis of Valorant Esports: Win Probability Through Economy and Ultimate Ability](https://www.techrxiv.org/users/916972/articles/1289732-a-predictive-analysis-of-valorant-esports-win-probability-through-economy-and-ultimate-ability) -- Logistic regression, 60.61% accuracy. Key finding: loadout value dominates feature importance over ultimates.
- [Determining Win-Loss Probability and Round Differential in Professional Valorant](https://scholarworks.calstate.edu/concern/projects/pk02cj680) -- CalState thesis. Logistic + linear regression on VCT inaugural season, 1,400+ games.
- [CS:GO Round Winner Classification (Kaggle)](https://www.kaggle.com/datasets/christianlillelund/csgo-round-winner-classification) -- 122K round snapshots, features: time_left, scores, health, armor, money, alive, weapons, grenades. Random Forest 88% accuracy.

### Valorant Game Data (HIGH confidence)

- [VALORANT Champions 2025 Statistics (Liquipedia)](https://liquipedia.net/valorant/VCT/2025/Champions/Statistics) -- Map pick rates, attack/defense win rates by map (Abyss 57.9% attack, Sunset 60.4% defense).
- [Valorant Champions 2025 Paris Kaggle Dataset](https://www.kaggle.com/datasets/piyush86kumar/valorant-champions-tour-2025-paris) -- 10 CSV files: matches, player stats, map stats, agent stats, economy data, performance data.
- [VALORANT Global Power Rankings (GPR)](https://valorantesports.com/gpr) -- Riot's official Elo-based ranking. 80/20 team/league weighting. Tracks buy/eco situation performance and map-specific attack/defense performance.
- [Valorant Economy System](https://www.thespike.gg/valorant/beginner-guides/valorant-economy-guide) -- Win: 3,000/player. Loss bonus: 1,900/2,400/2,900 escalating. Kill: 200. Spike plant: 300/teammate.

### Esports Prediction Domain (MEDIUM confidence)

- [CS2 Match Prediction with AI](https://cieslak.dev/en/blog/2025-07-17-cs2-ai-benchmark) -- Multi-model comparison for CS2 match prediction.
- [Bookmakers' Mistakes in CS2 Line Modeling](https://esportsinsider.com/2024/07/cs2-line-modelling-bookmaker-mistakes) -- Analysis of bookmaker pricing errors in CS2 esports.
- [Pistol Round Impact: VCT Berlin Analysis](https://medium.com/@_SushantJha/importance-of-the-first-pistol-round-a-story-from-vct-berlin-c5935b34f138) -- Community analysis of pistol round cascading economy effects.
- [A Systematic Review of ML in Sports Betting](https://arxiv.org/html/2410.21484v1) -- Comprehensive review of ML approaches, calibration importance.

### Model Evaluation Guidance (MEDIUM-HIGH confidence)

- [Log Loss vs. Brier Score (DRatings)](https://www.dratings.com/log-loss-vs-brier-score/) -- Log loss preferred for sports prediction because it penalizes overconfidence more harshly.
- [AI Model Calibration for Sports Betting](https://www.sports-ai.dev/blog/ai-model-calibration-brier-score) -- Calibration-optimized models generate 69.86% higher returns than accuracy-optimized models.

---

*Feature research complete. Confidence: MEDIUM-HIGH. Ready for roadmap creation.*
*Key recommendation: Start with score + Elo + economy tier baseline. Add features one at a time, validating each with grouped CV log loss. Resist the urge to add all features at once -- 71 maps cannot support it.*
