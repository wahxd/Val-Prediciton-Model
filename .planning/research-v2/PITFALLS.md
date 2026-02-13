# Domain Pitfalls: VCT Match Prediction Model

**Domain:** Esports match outcome prediction from CV-extracted event data, targeting prediction market edge
**Researched:** 2026-02-13
**Confidence:** MEDIUM-HIGH (cross-referenced academic research, betting model literature, and project-specific data characteristics)

---

## Critical Pitfalls

Mistakes that produce a model that looks good in development but loses money in production, or that require fundamental rework to fix.

---

### Pitfall 1: Overfitting on 71 Maps Masquerading as Predictive Skill

**What goes wrong:** With only 71 maps (~35 series), your model memorizes team-specific patterns rather than learning generalizable prediction rules. A gradient boosting model with 20+ features and no regularization achieves 80%+ accuracy on cross-validation but performs at coin-flip level on new tournaments. You believe you have edge; you do not.

**Why it happens:**
- 71 maps is an extremely small dataset for ML. Even logistic regression with 10 features has ~1 effective parameter per 7 samples -- well below the recommended 10-20 samples per parameter
- Champions 2025 features a fixed set of ~16 teams. The model learns "Team X beats Team Y" rather than "teams with these characteristics tend to win"
- Standard k-fold cross-validation leaks information when multiple maps from the same series appear in both train and test folds
- Feature engineering creates combinatorial explosion: 20 features from 71 samples is textbook overfitting territory
- Validation accuracy on held-out data from the same tournament is not evidence of generalization to future tournaments

**Consequences:**
- False confidence in model edge leads to real money losses on Polymarket
- Kelly criterion amplifies damage: if your "60% confidence" prediction is actually 50%, Kelly sizes you for a bet that has negative expected value
- Wasted time iterating on feature engineering that appears to improve in-sample metrics but does not generalize
- Entire model may need to be thrown out and rebuilt with different approach (Elo/Glicko ratings, Bayesian methods)

**Warning signs:**
- Large gap between training accuracy and test accuracy (>10 percentage points)
- Model accuracy drops significantly when evaluated on a different tournament's data
- Feature importance is dominated by team identity features rather than gameplay features
- Adding more features consistently "improves" cross-validation scores
- Model assigns extreme probabilities (>80% or <20%) frequently -- genuine models on small datasets should be uncertain

**Prevention:**
1. **Start with the simplest possible model.** Logistic regression with 3-5 features maximum. On 71 samples, this is not a handicap -- it is discipline. Research on Valorant prediction (CSU thesis, 2024) showed logistic regression achieving 60.6% accuracy on 1301 rounds with just loadout value and ultimate features; simpler models are competitive
2. **Use leave-one-series-out cross-validation.** Never split maps from the same BO3/BO5 across train and test. Each fold holds out an entire series (all 2-3 maps), preserving the dependency structure
3. **Impose strong regularization.** L1 (Lasso) regularization for logistic regression aggressively zeros out weak features. For tree models, limit max_depth to 2-3 and min_samples_leaf to 10+
4. **Establish a naive baseline.** Before any ML: what accuracy does "always pick the higher-ranked team" or "always pick 50/50" achieve? Your model must beat this baseline on held-out data, not just in aggregate
5. **Consider Elo/Glicko rating systems instead of ML.** Bayesian Elo systems (like the Valorant-specific one by BDepanfilis) are explicitly designed for small samples -- they start with priors and update incrementally. They naturally express uncertainty through rating deviation. For 71 maps, Elo may outperform any ML model
6. **Plan for dataset expansion as the real solution.** 71 maps is a starting point, not an endpoint. Prioritize processing more VODs via Valoscribe. Target 200+ maps across multiple tournaments before trusting any model for real money

**Phase mapping:** Phase 1 (initial model). This is the single most important pitfall. The model architecture and evaluation strategy must account for this from day one.

**Confidence:** HIGH -- this is well-established ML theory applied to our specific sample size.

---

### Pitfall 2: Random Train/Test Splits Causing Temporal Data Leakage

**What goes wrong:** You randomly shuffle 71 maps and split 80/20 for train/test. Maps from Day 4 of Champions appear in training while maps from Day 2 appear in testing. Your model implicitly learns from "future" information -- roster changes, team form shifts, meta evolution that happened between those days. Test accuracy is inflated by 5-15 percentage points.

**Why it happens:**
- Default scikit-learn `train_test_split` shuffles randomly by default
- Team strength evolves over a tournament (teams improve through bracket, fatigue accumulates, meta adapts)
- Champions 2025 spans group stage through grand finals -- teams that reach finals have different characteristics than group-stage teams
- Maps within a single series share correlated features (same teams, same day, same momentum)

**Consequences:**
- Model appears better than it is because it "saw the future" during training
- Calibration is off -- probabilities trained on leaked data are systematically overconfident
- When deployed on genuinely future matches (new tournaments), performance drops to or below baseline
- You cannot distinguish between "model has skill" and "model memorized temporal patterns"

**Warning signs:**
- Model performance degrades when you switch from random split to chronological split
- Performance is suspiciously high (>70% accuracy on a binary prediction with 71 samples)
- Model performs well on later rounds of tournament but poorly on early rounds when evaluated chronologically

**Prevention:**
1. **Always use chronological splits.** Sort all maps by date/time. Training set = first N matches chronologically. Test set = last M matches. Never look forward
2. **Use expanding window validation.** Train on matches 1-20, test on 21-25. Train on 1-25, test on 26-30. Average across windows. This simulates real deployment
3. **Group series together.** Maps from the same BO3 must all be in train or all in test. Use scikit-learn's `GroupKFold` with series_id as the group
4. **Include a temporal gap.** If possible, leave a gap between train and test (e.g., skip 1 series between train end and test start) to prevent short-range autocorrelation leaking through
5. **Treat tournament stages as regimes.** Group stage, playoffs, and grand finals may have different dynamics. Validate across stages, not within them

**Phase mapping:** Phase 1 (model evaluation setup). Must be established before any model evaluation occurs. Retroactively fixing evaluation methodology is worthless -- you can never trust results from a leaked evaluation.

**Confidence:** HIGH -- temporal leakage in sports prediction is well-documented and our dataset has clear temporal structure (tournament progression).

---

### Pitfall 3: Optimizing for Accuracy Instead of Calibration, Then Losing Money

**What goes wrong:** You optimize your model for classification accuracy ("did the model predict the winner correctly?"). It achieves 65% accuracy. You deploy it for Kelly criterion betting. The model says "Team A wins with 70% probability" but Team A actually wins 55% of the time in that scenario. Your bets are sized for a 20% edge that does not exist. You lose money systematically despite being "65% accurate."

**Why it happens:**
- Accuracy is the default metric in ML tutorials and scikit-learn defaults
- Accuracy rewards correct binary predictions, not probability quality
- A model can be 65% accurate but terribly calibrated -- it might predict 70% for everything, getting credit when the correct answer is "yes" and being wrong about the margin when the answer is "no"
- Walsh and Joshi (2024) demonstrated that calibration-optimized models generate 69.86% higher average returns than accuracy-optimized models
- Log loss and Brier score measure probability quality, but most ML pipelines do not optimize for them by default

**Consequences:**
- Kelly criterion requires accurate probabilities, not just correct classifications. Overconfident probabilities lead to oversized bets; underconfident probabilities lead to missed opportunities
- Edge calculation depends on probability accuracy: `edge = (odds * p) - 1`. If p is miscalibrated, edge estimates are garbage
- Full Kelly with overestimated edge leads to bankruptcy in 100% of scenarios (Wharton study, Beggy 2023)
- Even fractional Kelly cannot save a fundamentally miscalibrated model -- it just loses money more slowly

**Warning signs:**
- Reliability diagram shows systematic deviation from the diagonal (predicted probability vs actual frequency)
- Model rarely outputs probabilities in the 45-55% range -- overconfident predictions cluster at extremes
- Log loss is high even when accuracy is acceptable
- Brier score does not improve when you add features that improve accuracy

**Prevention:**
1. **Use log loss as primary evaluation metric, not accuracy.** Log loss penalizes overconfident wrong predictions exponentially. For betting models, this is the correct loss function (DRatings analysis confirms: "log loss greatly outperforms the Brier Score" for sports prediction)
2. **Build reliability diagrams from day one.** Bin predictions into buckets (0.5-0.55, 0.55-0.60, etc.), plot predicted vs actual frequency. Deviation from diagonal = miscalibration
3. **Apply Platt scaling or isotonic regression as post-hoc calibration.** Platt scaling fits a logistic regression on top of model outputs. Isotonic regression is non-parametric but overfits on small datasets -- use Platt scaling with 71 maps
4. **Use Brier score as secondary metric.** Brier score = mean squared error of probabilities. More robust to calibration issues than log loss. Use both
5. **Compare model calibration against market prices.** If Polymarket says 60% and your model says 65%, you need your 65% to actually mean 65% for the 5% edge to be real. Plot your model's historical calibration at each probability bucket
6. **Never use full Kelly.** Even with perfect calibration, use 0.25x-0.50x Kelly to account for estimation uncertainty. With 71-map calibration, use 0.10x-0.25x Kelly at most

**Phase mapping:** Phase 2 (model evaluation and calibration). Calibration assessment must happen before any discussion of deployment or betting. This is a hard gate.

**Confidence:** HIGH -- supported by multiple academic sources and betting model literature. Walsh & Joshi (2024) and the Wharton study provide direct evidence.

---

### Pitfall 4: Treating Noisy CV-Extracted Data as Ground Truth

**What goes wrong:** Valoscribe has an 87% validation rate -- meaning 13% of maps (~9 maps) have known data quality issues. But even the 87% "validated" maps have noise: phantom kills from undetected replays, misattributed killfeed entries (killer agent mismatch bug documented in Valoscribe), and round start/end count mismatches. You treat all event data as perfect ground truth and engineer features from it. Your features are built on noise. Garbage in, garbage out.

**Why it happens:**
- Valoscribe's validation checks are necessary but not sufficient. A map can pass all automated checks and still have subtle errors (e.g., 2 phantom kills that happen to not violate monotonicity checks)
- No replay detection in Valoscribe (confirmed as single biggest error source -- 9/71 map failures)
- Killfeed agent attribution has a documented bug where killer agent does not match victim's recorded killer
- Kill events from broadcast replays are indistinguishable from real kills in the JSONL output
- Per-player ability and ultimate data is fragile (hardcoded charge counts, agent-specific HUD quirks for Astra/Neon/Chamber/Jett/Viper)

**Consequences:**
- Feature engineering on noisy data amplifies noise. "Kill differential" includes phantom kills. "First blood rate" includes kills from replays
- Model learns to predict noise patterns rather than game mechanics
- With only 71 maps, a few corrupted maps can shift feature distributions significantly (1 bad map = 1.4% of your dataset)
- Cannot trust feature importance rankings when features are measured with error
- Unknown error rate in the "validated" 87% means you cannot bound your noise floor

**Warning signs:**
- Maps with >15 kills per round (mathematically impossible in 5v5)
- Round event counts that do not match score progression
- Kill timestamps that cluster unnaturally (multiple kills at exact same frame from replay)
- Feature distributions with suspicious outliers (one map shows 40 kills when average is 22)
- Model performance improves when you remove specific maps (indicating those maps are corrupting training)

**Prevention:**
1. **Build a data quality scoring system for each map.** Score each map on: round start/end count match, total kills vs expected kills (score * ~4.5 average), kill timing plausibility, score progression consistency. Weight maps by quality score during training, or exclude maps below threshold
2. **Audit the 9 failed maps manually.** Determine failure modes. Are they salvageable (minor issues, usable with caveats) or trash (fundamental corruption)?
3. **Spot-check 5-10 "passing" maps against VOD footage.** Verify kill counts, round outcomes, and key events against the actual video. This establishes your true validation rate on passing maps
4. **Use robust features that degrade gracefully with noise.** Round-level features (who won the round, final score) are more reliable than event-level features (specific kill timing, ability usage). Aggregate heavily: "team's overall kill rate" is more robust than "first blood rate in pistol rounds"
5. **Implement noise-aware feature engineering.** For any feature computed from kill events, add uncertainty: if kill count has +/- 2 noise, propagate that uncertainty into features. Or use features that are inherently noise-resistant: final map score (almost never wrong), round win/loss sequence (reliable from score progression alone)
6. **Do not use ability/ultimate features initially.** These have the lowest reliability in Valoscribe (hardcoded charge counts, agent-specific bugs). Stick to kills, scores, and round outcomes

**Phase mapping:** Phase 0 (data ingestion and cleaning). Data quality assessment must happen before feature engineering begins. You cannot engineer features you do not trust.

**Confidence:** HIGH -- specific to our data source. Error modes are documented in Valoscribe's codebase analysis (CONCERNS.md) and README.

---

### Pitfall 5: Single-Tournament Bias (Champions 2025 Is Not All of Valorant)

**What goes wrong:** Your entire dataset is VCT Champions 2025. This is one tournament, one meta, one patch, one set of teams at one point in time. You train a model that learns "Champions 2025 patterns" and deploy it on VCT 2026 Kickoff. The meta has shifted (new agent, balance patch, map pool change). Teams have made roster swaps. Your model's learned relationships no longer hold. It performs at or below baseline.

**Why it happens:**
- Valorant patches change agent balance 4-6 times per year. Champions 2025 was played on a specific patch; future tournaments will be on different patches
- Map pool rotates: Riot adds/removes maps between tournaments. Champions 2025 map pool may not match 2026 map pool
- Teams make roster changes between tournaments (player transfers, coach changes). A team at Champions may be fundamentally different at Kickoff
- Meta evolves even within a patch as teams discover new strategies. Double initiator was meta; now teams are moving away from it on some maps
- Agent compositions that dominated Champions 2025 may be nerfed or countered by the time you deploy

**Consequences:**
- Features based on agent composition become obsolete when agents are rebalanced
- Map-specific features become irrelevant when maps rotate out of the pool
- Team-level features (e.g., team Elo from Champions) do not reflect roster changes
- Model calibration trained on one meta does not transfer to a different meta
- You think you are betting on a model's prediction, but you are really betting that the meta has not changed

**Warning signs:**
- Model features include agent-specific or map-specific encodings that are patch-dependent
- No mechanism to decay or update feature weights over time
- Model performs well on Champions 2025 holdout but poorly on any other tournament data
- Agent pick rates in new tournament differ significantly from training data

**Prevention:**
1. **Prioritize meta-stable features.** Features that transcend specific metas: round-level economy (teams always need money), first blood advantage (always matters), side advantage (attack/defense win rates), raw kill differential. These are less patch-dependent than agent composition features
2. **Expand dataset across tournaments as soon as possible.** Process VODs from Kickoff 2025, Masters 2025, Champions Tour regionals. Even 30 more maps from a different tournament dramatically improves generalization
3. **Build a "tournament context" feature set.** Instead of encoding specific agents, encode team comp archetypes: "double controller", "triple duelist", "rush comp". These transfer better across patches
4. **Implement time decay on training data.** Older matches should have less weight than recent matches. Exponential decay with half-life of ~3 months reflects typical meta shift frequency
5. **Monitor for distribution shift.** Before deploying on a new tournament, compare feature distributions (kill rates, round win rates, economy patterns) between training data and the new tournament's early matches. If distributions diverge significantly, retrain before betting
6. **Use Elo/Glicko ratings that update continuously.** Elo ratings naturally handle meta shifts because they update after every match. A team that is strong in one meta and weak in another will see their Elo adjust. This is more robust than static ML features trained on one snapshot

**Phase mapping:** Phase 3 (dataset expansion and model robustness). The initial model on Champions 2025 only is a prototype. Never deploy it with real money until cross-tournament validation is performed.

**Confidence:** MEDIUM-HIGH -- meta shifts are well-documented in Valorant (patch notes, agent tier list changes), but the exact magnitude of impact on prediction is not empirically quantified for our specific features.

---

## Moderate Pitfalls

Mistakes that cause degraded performance, wasted effort, or require significant rework.

---

### Pitfall 6: Ignoring Map-Level Heterogeneity in a Map-Winner Model

**What goes wrong:** You build one model that treats all maps identically. But Valorant maps have vastly different dynamics: Breeze is attacker-sided, Bind is defender-sided, map-specific agent compositions vary wildly. Your model learns "average" patterns that do not apply to any specific map. Performance is mediocre everywhere.

**Why it happens:**
- 71 maps across 7 maps in the pool means ~10 maps per map name. Far too few to train map-specific models
- Temptation to pool all data for statistical power
- Map identity as a one-hot feature creates sparse encoding that the model cannot leverage with so few samples

**Prevention:**
1. **Use map as a stratification variable, not a feature.** Evaluate model performance per map to understand where it succeeds and fails, but do not try to build map-specific models with 10 samples each
2. **Engineer map-relative features.** Instead of raw attack-side win rate, use "attack-side win rate relative to map average." This normalizes for map-specific imbalances
3. **Incorporate published map statistics as priors.** VLR.gg and thespike.gg publish map-specific attack/defense win rates from hundreds of matches. Use these as Bayesian priors, then update with your data
4. **Defer map-specific modeling until 30+ maps per map.** This requires ~210+ total maps across the pool

**Warning signs:**
- Model performs very differently on different maps but treats them all the same
- Residual analysis shows map-correlated errors

**Phase mapping:** Phase 1 (feature engineering). Use map-relative features from the start rather than trying to add map-specificity later.

**Confidence:** HIGH -- Valorant's map asymmetry is well-documented and significant.

---

### Pitfall 7: Feature Leakage from Post-Game Aggregates

**What goes wrong:** You engineer features like "total kills by Team A" or "ACS (Average Combat Score) of star player" -- but these are full-match aggregates that are only known after the match ends. You train on these features. Your model "predicts" that the team with more kills wins. Of course it does -- the team with more kills almost always wins. But you do not know total kills before the match starts.

**Why it happens:**
- Valoscribe's JSONL contains all events for a completed map. It is trivially easy to compute post-hoc aggregates
- The line between "pre-game knowledge" and "in-game outcome" is blurry for some features: agent composition is pre-game, but kill data is in-game
- In feature engineering, it is natural to compute everything available and let the model sort it out
- No automated check prevents you from using future information as features

**Consequences:**
- Model achieves 85%+ accuracy in development (because it is using outcome-correlated features as inputs)
- When deployed for pre-match prediction, those features are unavailable. Model collapses to baseline
- If you use partial-match features (e.g., "kills in first 5 rounds"), you still have leakage for pre-match prediction but useful signal for live in-match prediction. Must be clear about which use case you are building for

**Warning signs:**
- Any feature that cannot be computed before the match starts should not be in a pre-match model
- Suspiciously high model accuracy (>75% on pre-match prediction with small dataset = almost certainly leaking)
- Feature importance shows "total_kills" or "round_differential" as top features

**Prevention:**
1. **Strictly categorize features by availability time.** Create three buckets:
   - **Pre-match** (available before map starts): historical team stats, Elo ratings, agent compositions (from pre-game draft), map pick history
   - **In-match** (available during map, for live prediction): current score, economy state, kills so far
   - **Post-match** (only available after map ends): total kills, final score, ACS. NEVER use these for prediction
2. **Enforce availability constraints in code.** Build a feature registry that tags each feature with its availability time. The training pipeline should refuse to include post-match features in pre-match models
3. **Use historical aggregates, not current-match aggregates.** "Team A's average kills per map across their last 10 maps" is pre-match knowledge. "Team A's kills in this map" is leakage
4. **Separate pre-match and in-match models explicitly.** If you want both use cases, build two distinct models with different feature sets

**Phase mapping:** Phase 1 (feature engineering). Must establish the feature availability framework before any features are engineered.

**Confidence:** HIGH -- data leakage is the most common ML mistake, and Valoscribe's complete-match JSONL format makes it especially easy to commit.

---

### Pitfall 8: Multicollinearity and Feature Redundancy Inflating Apparent Complexity

**What goes wrong:** You engineer 20 features from Valoscribe data: total kills, kill differential, first blood rate, headshot percentage, ACS, clutch rate, multi-kill rate... Many of these are highly correlated (kill differential and total kills share 90%+ variance). Your model has 20 features but effectively 5-7 independent signals. The apparent feature count suggests you need more data than you actually do for the redundant features, but it also means your model is fitting noise in the correlated dimensions.

**Why it happens:**
- Valorant events are inherently correlated: teams that get more kills win more rounds, teams that win more rounds have better economy, teams with better economy get more kills
- It feels productive to engineer many features
- Tree-based models handle multicollinearity better than logistic regression, but with 71 samples they still overfit on redundant features
- No penalty for adding features in many ML workflows until you notice overfitting

**Prevention:**
1. **Start with uncorrelated feature groups.** Pick one feature per concept: one economy feature, one kill feature, one round feature, one composition feature. Maximum 5-7 features total for 71 samples
2. **Compute VIF (Variance Inflation Factor) or correlation matrix before training.** Drop features with VIF > 5 or pairwise correlation > 0.7
3. **Use L1 regularization (Lasso) to automatically select features.** Lasso zeros out redundant features. With strong regularization, it will select 3-5 features from your 20
4. **For interpretability, prefer logistic regression with manual feature selection over tree ensembles.** With 71 samples, you need to understand what the model is doing. Black-box models that perform similarly are strictly worse because you cannot diagnose problems

**Phase mapping:** Phase 1 (feature engineering and selection). Establish feature budget before engineering features.

**Confidence:** HIGH -- standard ML guidance, directly applicable to our feature set.

---

### Pitfall 9: Ignoring Series-Level Dynamics When Predicting Match Winners

**What goes wrong:** You build a map-winner model and then naively combine map predictions to predict series (BO3/BO5) winners. You assume map outcomes are independent. They are not: the team that wins map 1 has momentum, teams adapt strategies between maps, map vetoes create correlated map selections. Your series prediction is worse than if you had modeled the series directly.

**Why it happens:**
- Map-level prediction feels like the natural unit because each map has a clear winner
- Independence assumption makes series prediction simple: P(win BO3) = P(win map)^2 * (3 - 2*P(win map)) for identical maps
- Momentum effects, tactical adaptation, and fatigue are hard to quantify
- Map veto creates non-random map selection -- teams pick their strong maps and ban their weak maps

**Consequences:**
- Series predictions are miscalibrated even if map predictions are well-calibrated
- Momentum effects (map 1 winner wins map 2 at higher rate than baseline) are ignored
- Map veto information is wasted (which maps a team bans reveals information about their strengths)
- Correlation between maps in a series means the variance of series outcome is higher than the independence model suggests

**Prevention:**
1. **Model series outcome directly as a separate model.** Use team-level features (historical series win rate, map pool depth, veto patterns) rather than combining map probabilities
2. **If combining map models, add a correlation term.** Estimate the correlation between map outcomes within a series from historical data. Even a simple "map 1 winner gets +5% on map 2" adjustment improves calibration
3. **Use map veto data as features.** VLR.gg tracks map picks and bans. Which maps a team bans reveals information about their map pool depth and current comfort level
4. **Validate series predictions separately from map predictions.** A good map model does not automatically make a good series model

**Warning signs:**
- Series predictions are systematically overconfident for the favorite (because independence assumption underestimates upset probability in series)
- Map veto data is available but unused

**Phase mapping:** Phase 2 (series-level modeling). Build map model first, then series model as a separate concern.

**Confidence:** MEDIUM -- momentum effects in esports series are discussed anecdotally but not well-quantified in academic literature for Valorant specifically.

---

### Pitfall 10: Building a Model Before Understanding Polymarket's Pricing Efficiency

**What goes wrong:** You spend months building a prediction model. You compare it against Polymarket prices. Polymarket prices are already well-calibrated (prediction markets aggregate information efficiently). Your model's edge, if any, is smaller than Polymarket's bid-ask spread. You have a model with no profitable deployment path.

**Why it happens:**
- Assumption that prediction markets are inefficient without evidence
- Esports markets on Polymarket may be less liquid than major sports, but they are still information-aggregating
- Arbitrage bots already operate on Polymarket, extracting mispricings worth $40M+ (2024-2025 study). The easy edges are already taken
- Your model has a 71-map training set; market participants collectively have far more information (team scrims, insider knowledge, historical data APIs)

**Consequences:**
- Model that is slightly better than random but not better than market prices has zero value for betting
- Transaction costs (spread, gas fees) eat whatever tiny edge exists
- Time investment in model building produces no return if the market is already efficient for this asset class

**Warning signs:**
- Polymarket prices for VCT matches consistently match actual outcomes at stated probabilities (market is well-calibrated)
- Your model's predictions closely track Polymarket prices (your model has no unique information)
- Profitable-looking backtests do not survive transaction cost adjustment

**Prevention:**
1. **Assess market efficiency first, before building the model.** Collect Polymarket prices for VCT matches. Calculate Brier score and calibration of raw market prices. If the market is already well-calibrated, your bar is much higher
2. **Identify specific market inefficiencies to exploit.** Possible edges:
   - **Speed**: Your model processes data faster than the market adjusts (requires live in-match prediction, not pre-match)
   - **Niche knowledge**: CV-extracted tactical data (agent compositions, ability usage patterns) that market participants do not systematically track
   - **Structural mispricing**: Esports markets may be less efficient than mainstream sports. Low liquidity = more noise = more opportunity
   - **Map-level vs series-level**: If Polymarket only offers series-level contracts, but map-level dynamics create edge, you might see structural mispricing
3. **Calculate minimum required edge.** Account for Polymarket spread, gas fees, and Kelly fraction. If minimum profitable edge is 5%, your model needs to be 5% better than market prices, not just better than random
4. **Start with paper trading.** Deploy model alongside Polymarket for one full tournament without betting real money. Measure realized edge after accounting for all costs

**Phase mapping:** Phase 3 (deployment and validation). But the market efficiency assessment should happen early (Phase 1) to calibrate expectations and potentially redirect the modeling approach.

**Confidence:** MEDIUM -- Polymarket esports market efficiency has not been formally studied, but the general prediction market efficiency literature and the arbitrage bot findings suggest the bar is high.

---

## Minor Pitfalls

Mistakes that cause delays or require adjustments but are recoverable.

---

### Pitfall 11: Agent Composition Features That Do Not Generalize

**What goes wrong:** You one-hot encode each agent and create "team composition" features. With 24 agents, you add 24 binary features per team (48 total). On 71 maps, this is catastrophically overfit. Even simpler encoding (composition hash) creates too many unique values.

**Prevention:**
1. Encode agent roles (duelist count, controller count, sentinel count, initiator count) instead of specific agents. This reduces 24 features to 4 per team
2. Better yet: use established composition archetypes (rush comp, default, double controller) as 3-5 categorical features
3. Best: defer agent composition features entirely until dataset is large enough (200+ maps)

**Phase mapping:** Phase 1 (feature engineering). Use role-based encoding or skip agent features entirely.

**Confidence:** HIGH.

---

### Pitfall 12: Not Accounting for Map Veto Selection Bias in Win Rates

**What goes wrong:** You compute "Team A's win rate on Bind = 80%" from 5 matches on Bind. But Team A only played Bind when they chose it (via map pick) -- meaning they play it because it is their strong map. Their true strength on Bind is lower than 80% because the sample is biased by self-selection. Conversely, when they play a map the opponent picked, their win rate is lower.

**Prevention:**
1. Track whether each map was the team's pick, opponent's pick, or decider (leftover)
2. Separate win rates by map selection context: pick, opponent pick, decider
3. Use veto data from VLR.gg to determine map selection context for each map in the dataset

**Phase mapping:** Phase 2 (feature refinement). Requires veto data integration from VLR.gg scraper.

**Confidence:** MEDIUM -- map veto data is available via VLR.gg but may not be present in Valoscribe's current output.

---

### Pitfall 13: Ignoring Side Selection (Attacker/Defender First) Impact

**What goes wrong:** You predict map winner without considering which side each team starts on. On attacker-sided maps like Breeze, starting on attack provides a meaningful advantage (more rounds won in first half = better economy entering second half). Ignoring this throws away easy predictive signal.

**Prevention:**
1. Include starting side as a feature
2. Use map-specific side win rates from VLR.gg as context features
3. Valoscribe tracks starting sides via VLR.gg metadata scraping -- ensure this is in the ingested data

**Phase mapping:** Phase 1 (feature engineering). Starting side should be one of the first features included.

**Confidence:** HIGH -- side advantage is a known, significant factor in Valorant competitive play.

---

### Pitfall 14: Probability Outputs That Do Not Sum Correctly for Series

**What goes wrong:** Your map model outputs P(Team A wins this map). You combine three independent map predictions for a BO3. But if your map probabilities are biased (e.g., always slight overconfidence for the favorite), the error compounds across maps. A 3% calibration error per map becomes a 7-9% calibration error for the series.

**Prevention:**
1. Calibrate at the map level first, then propagate through series calculation
2. Simulate series outcomes via Monte Carlo rather than analytical formulas, especially if map outcomes are correlated
3. Validate series-level calibration independently of map-level calibration

**Phase mapping:** Phase 2 (series-level prediction). Calibration error propagation must be understood before combining map predictions.

**Confidence:** HIGH -- basic probability theory, directly applicable.

---

### Pitfall 15: Overcomplicating the Initial Model Before Validating the Data Pipeline

**What goes wrong:** You jump to gradient boosting, neural networks, or ensemble methods before confirming that your data ingestion pipeline correctly loads Valoscribe's JSONL, that your feature engineering produces sensible values, and that your evaluation framework is sound. You debug model architecture when the actual bug is in data parsing. Weeks wasted.

**Prevention:**
1. **Phase 0 sanity checks.** Before any model: load all 71 maps, print summary statistics per map (total kills, rounds, score, side win rates). Manually verify 3 maps against known results
2. **Start with a constant model.** Predict the base rate (home team wins 52% or whatever the distribution is). This is your floor. Any model that cannot beat this is useless
3. **Then logistic regression with 1 feature.** Team Elo difference, or historical head-to-head record. Does it beat the constant? Good. Now you have a baseline
4. **Only then consider complexity.** Add features one at a time, measuring improvement on held-out data at each step. Stop when adding features no longer improves test performance

**Phase mapping:** Phase 0 (data pipeline validation) and Phase 1 (baseline model). Resist the urge to jump to complex models.

**Confidence:** HIGH -- this is universal ML advice, especially critical for small datasets.

---

## Phase-Specific Warnings

| Phase | Likely Pitfall | Severity | Mitigation |
|-------|---------------|----------|------------|
| Phase 0: Data Ingestion | Treating CV-extracted data as ground truth (P4) | Critical | Build data quality scoring, audit failed maps, spot-check passing maps |
| Phase 0: Data Ingestion | Feature leakage from post-game aggregates (P7) | Critical | Establish feature availability framework before any feature engineering |
| Phase 1: Initial Model | Overfitting on 71 maps (P1) | Critical | Start with logistic regression, 3-5 features max, leave-one-series-out CV |
| Phase 1: Initial Model | Random train/test splits (P2) | Critical | Chronological splits only, group by series |
| Phase 1: Initial Model | Agent composition over-encoding (P11) | Moderate | Role counts only, or skip agent features entirely |
| Phase 1: Initial Model | Overcomplicating before validating pipeline (P15) | Moderate | Constant baseline -> 1-feature model -> add incrementally |
| Phase 2: Model Calibration | Optimizing accuracy instead of calibration (P3) | Critical | Log loss primary metric, reliability diagrams, Platt scaling |
| Phase 2: Series Model | Ignoring series dynamics (P9) | Moderate | Model series directly, add correlation term, use veto data |
| Phase 2: Series Model | Probability compounding errors (P14) | Moderate | Monte Carlo simulation, series-level calibration validation |
| Phase 3: Deployment | Single-tournament bias (P5) | Critical | Expand dataset across tournaments, time-decay training weights |
| Phase 3: Deployment | Market already efficient (P10) | Critical | Assess Polymarket calibration first, calculate minimum required edge |
| Phase 3: Deployment | Map selection bias in win rates (P12) | Minor | Separate pick/opponent-pick/decider contexts |

---

## Anti-Pattern Summary: The Overconfident Small-Dataset Pipeline

The most dangerous failure mode for this project combines multiple pitfalls into a single pipeline that looks good but is worthless:

1. Random train/test split (P2) inflates accuracy
2. Post-game features leak into pre-match model (P7) further inflating accuracy
3. Accuracy used as metric instead of calibration (P3) hides probability quality issues
4. 20+ correlated features on 71 samples (P1, P8) overfit the noise
5. Single-tournament data generalizes poorly (P5) to new events
6. Full Kelly sizing on overconfident probabilities (P3) maximizes losses

**The correct pipeline is the boring one:**

1. Chronological split with series-level grouping
2. Strict feature availability enforcement (pre-match only for pre-match model)
3. Log loss as primary metric, reliability diagrams for calibration
4. 3-5 uncorrelated features, logistic regression with L1 regularization
5. Cross-tournament validation before any real money
6. 0.10x-0.25x fractional Kelly with EV threshold of 3%+

---

## Sources

**HIGH confidence (academic papers and official documentation):**
- [Round Outcome Prediction in VALORANT Using Tactical Features from Video Analysis](https://arxiv.org/html/2510.17199v1) -- 81% round accuracy with tactical features, dataset of 29,506 rounds
- [Machine learning for sports betting: Should model selection be based on accuracy or calibration?](https://www.sciencedirect.com/science/article/pii/S266682702400015X) -- Walsh & Joshi (2024), calibration-optimized models generate 69.86% higher returns
- [An Investigation of Sports Betting Selection and Sizing](https://wsb.wharton.upenn.edu/wp-content/uploads/2023/05/Beggy_2023__Betting_Kelly.pdf) -- Wharton study, full Kelly leads to bankruptcy in 100% of realistic scenarios
- [A Predictive Analysis of Valorant Esports: Win Probability Through Economy and Ultimate Ability](https://www.techrxiv.org/users/916972/articles/1289732-a-predictive-analysis-of-valorant-esports-win-probability-through-economy-and-ultimate-ability) -- Logistic regression on 1301 rounds, 60.6% accuracy with economy + ultimate features
- [Log Loss vs. Brier Score](https://www.dratings.com/log-loss-vs-brier-score/) -- Log loss superior for sports prediction models

**MEDIUM confidence (industry analysis and community research):**
- [AI Model Calibration for Sports Betting: Brier Score & Reliability](https://www.sports-ai.dev/blog/ai-model-calibration-brier-score) -- Practical calibration guidance, Platt scaling and reliability diagrams
- [Valorant Bayesian Elo System](https://github.com/BDepanfilis/Valorant-Bayesian-Elo-System) -- Bayesian priors, time decay, regional bias for Valorant Elo
- [Bot-like bettors exploited mispriced wagers on Polymarket](https://www.mitrade.com/insights/news/live-news/article-3-1063250-20250823) -- $40M+ arbitrage profits 2024-2025
- [Polymarket Strategies: 2026 Guide](https://cryptonews.com/cryptocurrency/polymarket-strategies/) -- Market efficiency and trading strategies
- [Kelly criterion - Wikipedia](https://en.wikipedia.org/wiki/Kelly_criterion) -- Half Kelly reduces 80% drawdown probability from 1/5 to 1/213

**Project-specific (HIGH confidence for our codebase):**
- Valoscribe CONCERNS.md -- 87% validation rate, killfeed agent attribution bug, 9/71 map failures
- Valoscribe ARCHITECTURE.md -- No replay detection, phase detection limitations
- Valoscribe COMPARISON.md -- Data characteristics, existing capabilities

---

*Pitfalls research: 2026-02-13*
*Overall confidence: MEDIUM-HIGH*
*Next action: Inform roadmap phase structure, especially Phase 0 data validation and Phase 1 baseline model approach*
