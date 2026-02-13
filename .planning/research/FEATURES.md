# Feature Landscape: Valorant Esports Event Data Collection

**Domain:** Esports data collection and match prediction (Valorant VCT)
**Researched:** 2026-02-12
**Confidence:** MEDIUM (based on training data about Valorant mechanics, esports prediction systems, and CV capabilities; WebSearch unavailable for 2026 verification)

## Executive Summary

Valorant prediction systems divide into three feature tiers: **table stakes** (events any system must capture to be minimally viable), **differentiators** (events that separate sophisticated models from basic ones), and **anti-features** (tempting but low-value or impractical for CV-based broadcast extraction).

**Key insight for prediction markets:** Events that create **irreversible advantages** (round wins, economy damage) matter far more than momentary micro-events (individual kills). A team winning pistol round shifts win probability ~8-12%; a single kill mid-round shifts it ~2-5% depending on context.

**CV extraction reality check:** Broadcast overlays expose scores, alive counts, economy, and spike status reliably. Agent icons, ultimate orbs, and map names are visible but require template matching. Individual player stats, ability cooldowns, and positioning are NOT visible in standard VCT broadcasts.

## Table Stakes Features

Events users expect. Missing = system is incomplete for prediction modeling.

| Feature | Why Expected | CV Difficulty | Prediction Value | Dependencies | Notes |
|---------|--------------|---------------|------------------|--------------|-------|
| **Round results** | Foundation of match outcome; every round shifts series score | Easy | CRITICAL | Score extraction (existing) | Detectable via score increment. Need state machine to emit discrete "round_end" events. |
| **Kills per round** | Core mechanic affecting alive differential and round outcome | Medium | HIGH | Alive count tracking (existing) | Detect via alive_count decrements. Cannot identify WHO killed WHO from broadcast (no killfeed OCR yet). |
| **Spike plant detection** | Major economy/tactical shift; planted rounds worth more credits | Easy | HIGH | Spike status (existing) | Already extracted. Need event emission when status changes from "not planted" → "planted". |
| **Spike defuse/detonation** | Determines round winner and economy outcomes | Medium | HIGH | Spike status + round timer | Combine spike status with round end. If spike planted + timer expires = detonation. If spike planted + round ends early = defuse. |
| **Round timer** | Context for evaluating alive differential and spike status | Easy | Medium | OCR (existing) | Already extracted. Used as event timestamp and tactical context (10s left = high pressure). |
| **Economy per team** | Predicts buy types (eco/force/full) which shift win probability 15-25% | Medium | CRITICAL | OCR on economy UI (existing) | VCT shows total team economy during buy phase. Need to detect buy phase and log economy snapshots. Currently extracted but not logged persistently. |
| **Match score** | Series context (Bo3/Bo5); map score affects team psychology and strategy | Easy | HIGH | Score extraction (existing) | Already extracted. Need to differentiate map score vs round score in event logs. |
| **Team identification** | Match event logs to specific teams for training data labeling | Medium | N/A (metadata) | OCR on team name overlay | VCT shows team names/logos top center. Template matching or OCR required. Critical for labeling training data. |
| **Map identification** | Different maps have different defender/attacker win rates (45-55% variance) | Medium | HIGH | OCR or template matching on map name | VCT shows map name during buy phase and round start. Affects baseline win probabilities. |

### Implementation Notes

**Round result detection:** Requires state machine tracking previous score. When `score_left` or `score_right` increments, emit `round_end` event with winner, final alive counts, spike status, and round duration.

**Kill detection:** Track alive count per team. When count decrements, emit `kill` event. Limitation: Cannot identify attacker/victim from broadcast without killfeed OCR (complex, low priority).

**Economy events:** VCT broadcast shows total team economy during buy phase (~45 seconds at round start). Detect buy phase (timer = 0:45 or score unchanged for 45s), OCR economy, classify buy type:
- Eco: <16,000 total (0-3 rifles)
- Force: 16,000-22,000 (mixed rifles/SMGs)
- Full buy: >22,000 (full rifles, utilities, armor)

Emit `buy_phase` event with economy snapshot and buy type classification.

## Differentiators

Features that separate sophisticated prediction models from basic ones. Not expected, but provide edge.

| Feature | Value Proposition | CV Difficulty | Prediction Value | Dependencies | Notes |
|---------|-------------------|---------------|------------------|--------------|-------|
| **Agent compositions** | Certain agent combos (e.g., Viper+Astra) have 5-8% higher win rates on specific maps | Medium | MEDIUM | Template matching on agent icons | VCT shows agent portraits top of screen. ~22 agents, need template library. Affects baseline map win rates. |
| **Ultimate status** | Team with 3+ ults ready has ~10-15% higher round win rate | Hard | MEDIUM-HIGH | Template matching on ultimate orbs | VCT shows ult orbs under agent portraits. Green = ready. Difficult: Small icons, requires per-agent tracking. High value for mid-round prediction. |
| **First blood** | Team getting first kill wins round 65-70% of time (significant predictor) | Easy | HIGH | Kill event detection | Derived from kill events. First kill in round = first blood. Requires kill event detection (table stakes). |
| **Alive differential over time** | Tracking 5v4 → 5v3 progression reveals momentum and round-win confidence | Easy | MEDIUM | Alive count tracking (existing) | Calculate `alive_left - alive_right` per frame. Emit when differential changes. Temporal feature for prediction model. |
| **Round type** (Pistol/Eco/Gun) | Pistol rounds have 50-50 base rates; eco rounds 20-80 favoring full-buy team | Medium | HIGH | Economy classification | Classify based on economy snapshot. Pistol = rounds 1, 13. Eco/Force/Full = economy-based. Adjusts baseline win probability. |
| **Side** (Attack/Defense) | Defender win rate varies 45-55% by map; critical for probability calibration | Easy | HIGH | Map detection + round number | VCT broadcasts show attacker/defender icons. Or infer: rounds 1-12 one side, 13-24 other (swap at half). |
| **Comeback potential** | Trailing team behavior differs (force buys, risky plays); affects prediction volatility | Easy | MEDIUM | Score differential + economy | Derived feature. If `score_diff >= 3` and `trailing_team_economy < 20k`, flag high-variance round. |
| **Post-plant situations** | After plant, attacking team wins 60-65% even if outnumbered (time pressure on defenders) | Easy | MEDIUM-HIGH | Spike plant + alive differential + timer | Combine existing features. If spike planted + defenders have alive advantage, win rate still favors attackers. |
| **Momentum streaks** | Team winning 3+ consecutive rounds has psychological edge (~5% win rate boost) | Easy | MEDIUM | Round result history | Track round winners. Emit `momentum_shift` when 3+ round streak starts/ends. |

### Implementation Notes

**Agent compositions:** VCT overlay shows agent portraits (128x128 approx) at top of screen. Extract during agent select or buy phase. Use template matching with stored agent icon library (~22 agents as of training data). Low priority for MVP—agent meta changes seasonally.

**Ultimate tracking:** Most complex differentiator. VCT shows ultimate orbs (small circles) under each agent portrait. Green filled = ready, empty = charging. Requires:
1. Locate 10 agent portraits (5 per team)
2. Sample pixels below each portrait for ult orb
3. Classify green (ready) vs gray (not ready)
4. Aggregate to team-level: "Team A has 3 ults ready"

High value but high complexity. Defer to post-MVP unless ult tracking proves critical for prediction edge.

**First blood:** Derived from kill detection. Emit special `first_blood` event for first kill of each round. Simple once kill events work.

**Side detection:** VCT shows attacker/defender icons OR can infer from round number (rounds 1-12 = one side, 13+ = swapped). Essential for map-specific prediction calibration.

## Anti-Features

Features to explicitly NOT build. Common mistakes in this domain.

| Anti-Feature | Why Avoid | What to Do Instead | CV Feasibility |
|--------------|-----------|-------------------|----------------|
| **Player-level stats** (individual K/D/A, ADR, headshot %) | Not visible in broadcast; would require game API access or killfeed OCR. High complexity, low prediction value (team aggregates sufficient). | Focus on team-level aggregates (total kills, alive counts). Defer player-level to post-MVP only if prediction model shows need. | Hard (killfeed OCR unreliable; player names often obscured) |
| **Ability cooldown tracking** | Not shown in VCT broadcast. Would require frame-perfect tracking of ability usage, impossible from spectator view. | Use ultimate status (visible) as proxy for ability availability. | Impossible from broadcast |
| **Real-time price integration** | Out of scope for data collection milestone. Adds complexity without improving data quality. | Log event timestamps. Manually align with Polymarket/Kalshi price data in post-processing. Add price API later. | N/A (not CV problem) |
| **Positioning/map control** | VCT broadcast rarely shows minimap clearly; spectator camera focuses on action. Unreliable extraction. | Infer from alive counts and spike status. "Spike planted + 5v3 alive advantage" implies map control. | Very Hard (minimap too small, inconsistently shown) |
| **Weapon inventory per player** | Partially visible but requires per-player tracking. Low prediction value—economy is better proxy. | Use team economy total to infer buy quality. Full buy ($22k+) = rifles assumed. | Hard (requires player tracking) |
| **Specific ability usage** (e.g., "Sova dart detected site A") | Not visible in broadcast overlay. Would need game log access. Prediction value unclear. | Track ultimate availability only (visible). Defer ability-level granularity. | Impossible from broadcast |
| **VOD scrubbing for historical data** | Tempting to batch-process old VODs, but VCT overlay formats change between seasons. ROI coordinates break. | Focus on live/recent matches with current overlay. Accept smaller dataset with consistent format over large dataset requiring constant recalibration. | Hard (format drift over time) |
| **Cross-platform price arbitrage signals** | Out of scope. This is trading logic, not data collection. Premature. | Build clean event logs first. Prediction model second. Trading signals third (future milestone). | N/A |

### Why These Are Tempting

**Player-level stats:** Feels like "more data = better model." Reality: Team aggregates (alive counts, economy) capture 90% of predictive signal. Individual K/D ratios matter in player evaluation, not round outcome prediction.

**Positioning:** Intuitively important (map control = win). But broadcast doesn't expose minimap reliably. Attempting to extract it wastes CV effort on noisy data. Better to infer: "5v3 alive advantage + spike planted + 30s left" implies attackers have site control.

**VOD scrubbing:** Tempting to build "5 years of VCT data." But:
1. Overlay formats change seasonally (ROI coordinates break)
2. Historical matches don't reflect current agent meta or team rosters
3. Fresh data from current season > stale data from 2021

Focus on live data collection for current season. Accept smaller, higher-quality dataset.

## Feature Dependencies

Dependencies between features (some features require others to be implemented first).

```
Foundational (no dependencies):
├─ Score extraction (OCR) [EXISTING]
├─ Alive count tracking (color detection) [EXISTING]
├─ Spike status (color detection) [EXISTING]
├─ Round timer (OCR) [EXISTING]
└─ Economy extraction (OCR) [EXISTING]

Tier 1 (depends on foundational):
├─ Round result detection → requires score tracking (state machine)
├─ Kill events → requires alive count deltas (state machine)
├─ Spike plant/defuse events → requires spike status deltas (state machine)
├─ Team identification → requires OCR on team name overlay (new CV)
└─ Map identification → requires OCR or template matching (new CV)

Tier 2 (depends on Tier 1):
├─ First blood → requires kill events
├─ Round type classification → requires economy + round number
├─ Side detection → requires map + round number OR icon detection
├─ Buy phase events → requires economy + round timer
├─ Alive differential → requires alive count tracking (already exists)
└─ Momentum tracking → requires round result history

Tier 3 (differentiators, optional):
├─ Agent compositions → requires template matching (new CV, independent)
├─ Ultimate tracking → requires agent tracking + template matching (complex)
├─ Post-plant analysis → requires spike plant events + alive differential
└─ Comeback flags → requires score differential + economy
```

**Critical path for MVP:**
1. Implement state machine for event detection (score/alive/spike deltas)
2. Persistent event logging (replace overwritten game_state.json)
3. Team/map auto-detection (metadata for training data labeling)
4. Economy event logging during buy phase

**Defer to post-MVP:**
- Agent compositions (meta shifts, requires template library)
- Ultimate tracking (high complexity, marginal prediction gain over economy)
- Player-level tracking (not visible in broadcast)

## Feature Priority Matrix

Ranked by prediction value vs CV extraction difficulty.

```
HIGH VALUE, EASY EXTRACTION (implement first):
- Round results (score delta detection)
- Spike plant/defuse (status change detection)
- Economy snapshots (existing OCR, add event emission)
- First blood (derived from kill events)
- Side detection (icon detection or round-based inference)
- Alive differential (existing data, add trending)

HIGH VALUE, MEDIUM EXTRACTION (implement second):
- Kill events (alive count delta detection)
- Team identification (OCR or template matching)
- Map identification (OCR during buy phase)
- Round type classification (economy-based)
- Post-plant analysis (combined features)

MEDIUM VALUE, MEDIUM EXTRACTION (implement if time allows):
- Agent compositions (template matching, 22 agents)
- Momentum tracking (round streak detection)
- Buy phase classification (eco/force/full)

MEDIUM VALUE, HARD EXTRACTION (defer or deprioritize):
- Ultimate tracking (10 player ult orbs, pixel sampling)
- Comeback potential flags (derived logic)

LOW VALUE or IMPOSSIBLE (skip):
- Player-level stats (not in broadcast)
- Ability cooldowns (not shown)
- Positioning/map control (unreliable)
- Weapon inventory per player (marginal value)
```

## MVP Feature Recommendation

For initial milestone (event detection + persistent logging), prioritize:

### Must-Have (Table Stakes)
1. **Round result events** - Win/loss per round with metadata (alive counts, spike status, economy)
2. **Kill events** - Alive count deltas (cannot identify who killed who, team-level only)
3. **Spike plant/defuse/detonate events** - Critical economy/tactical shifts
4. **Economy snapshots** - Total team economy during buy phase
5. **Team identification** - OCR team names for training data labeling
6. **Map identification** - OCR map name for baseline win rate calibration
7. **Match session management** - Start/stop, metadata, multi-map series support

### Nice-to-Have (Quick Wins)
1. **First blood detection** - Derived from kill events (flag first kill per round)
2. **Side detection** - Attacker/defender identification (icon or round-based)
3. **Alive differential tracking** - Emit events when differential changes
4. **Round type classification** - Pistol/eco/force/full based on economy

### Defer to Post-MVP
1. **Agent compositions** - Requires building 22-agent template library
2. **Ultimate tracking** - Complex, requires per-player pixel sampling
3. **Momentum streaks** - Derived feature, lower priority
4. **Player-level stats** - Not feasible from broadcast (no killfeed OCR)

## Event Schema Recommendations

Based on feature analysis, recommended event types for persistent logging:

```json
{
  "event_type": "round_end",
  "timestamp": "2024-03-15T18:42:33.123Z",
  "round_number": 13,
  "winner": "team_a",
  "score": {"team_a": 7, "team_b": 6},
  "alive_counts": {"team_a": 3, "team_b": 0},
  "spike_status": "detonated",
  "round_duration": 87.5,
  "economy_snapshot": {"team_a": 24500, "team_b": 18200},
  "round_type": "full_buy",
  "first_blood": "team_b"
}
```

```json
{
  "event_type": "kill",
  "timestamp": "2024-03-15T18:41:28.456Z",
  "round_number": 13,
  "alive_before": {"team_a": 5, "team_b": 4},
  "alive_after": {"team_a": 5, "team_b": 3},
  "team_killed": "team_b"
}
```

```json
{
  "event_type": "spike_plant",
  "timestamp": "2024-03-15T18:41:45.789Z",
  "round_number": 13,
  "round_timer_remaining": 32.5,
  "alive_counts": {"team_a": 5, "team_b": 3}
}
```

```json
{
  "event_type": "match_start",
  "timestamp": "2024-03-15T18:30:00.000Z",
  "teams": {"team_a": "Sentinels", "team_b": "LOUD"},
  "map": "Bind",
  "series_format": "Bo3",
  "map_number": 1
}
```

## CV Extraction Feasibility Assessment

| Feature | Broadcast Visibility | Extraction Method | Reliability | Notes |
|---------|---------------------|-------------------|-------------|-------|
| **Scores** | Always visible top center | OCR | HIGH | Already implemented. Tesseract reliable on clean digits. |
| **Alive counts** | Player portraits always visible | Color detection on health bars | MEDIUM-HIGH | Already implemented. Fails if overlay obscured. Brightness-based detection fragile (see CONCERNS.md). |
| **Spike status** | Icon visible top center when planted | HSV color detection (red) | MEDIUM | Already implemented. Threshold-dependent (lighting variations). |
| **Round timer** | Always visible top center | OCR | HIGH | Already implemented. Clean font, high contrast. |
| **Economy** | Visible during buy phase only (~45s) | OCR | MEDIUM | Already implemented. Only extractable during buy phase; hidden during combat. Need phase detection. |
| **Team names** | Visible top center (small text) | OCR or template matching | MEDIUM | Not implemented. Tesseract on small text less reliable. May need template matching on team logos instead. |
| **Map name** | Visible during buy phase (large text) | OCR | HIGH | Not implemented. Shown clearly during buy phase, clean font. |
| **Agent icons** | Portraits visible top of screen | Template matching | MEDIUM | Not implemented. Requires 22-agent template library. Icons are ~64x64px, consistent across matches. |
| **Ultimate orbs** | Small circles under agent portraits | Pixel sampling (green = ready) | MEDIUM-LOW | Not implemented. Very small (~10x10px), requires precise ROI. Color detection fragile. |
| **Side (attack/def)** | Icon visible OR inferable from round # | Icon detection or logic | HIGH | Not implemented. Simple logic: rounds 1-12 one side, 13+ swapped. |
| **Killfeed** | Scrolling text bottom-right | OCR on dynamic text | LOW | Not implemented. Text scrolls quickly, overlaps with other UI. OCR challenging. Defer. |

**Key takeaway:** Table stakes features (scores, alive counts, economy, spike) are reliably extractable from VCT broadcasts. Differentiators (agents, ultimates) require additional CV work with medium reliability. Player-level stats require killfeed OCR (low reliability) or game API (unavailable).

## Prediction Value by Feature Category

Based on training data about tactical FPS mechanics and betting market efficiency:

| Feature Category | Win Probability Impact | Reasoning |
|------------------|------------------------|-----------|
| **Round wins** | 8-12% per round | Each round won = 1 step closer to map victory. Pistol rounds ~10%, normal rounds ~8%. |
| **Economy advantage** | 15-25% | Full buy vs eco round = massive firepower gap. $30k vs $15k economy = 70-30 win rate. |
| **Alive differential** | 2-5% per player | 5v4 = slight edge. 5v3 = major advantage. Non-linear: 5v1 nearly guaranteed round win. |
| **Spike plant** | 10-15% | Attackers win ~60-65% post-plant even if outnumbered (defenders must push into crossfire + time pressure). |
| **First blood** | 8-12% | Team with first kill wins round 65-70% of time. Removes utility + creates man advantage. |
| **Ultimate availability** | 5-8% per ult ready | Team with 3+ ults has ~10-15% higher win rate (game-changing abilities like Brimstone orbital strike). |
| **Map/side** | 5-10% baseline | Defender advantage on most maps (55-45 split). Bind/Haven slightly attacker-favored. |
| **Agent composition** | 3-7% | Certain comps counter others. Meta shifts seasonally. Viper+Astra ~5% higher win rate on Icebox. |
| **Momentum** | 3-5% | Psychological edge. 5-round win streak team has higher confidence, forcing opponents into desperate plays. |

**Most impactful for prediction markets:**
1. Economy (15-25%) - Separates eco rounds from gun rounds
2. Spike plant (10-15%) - Post-plant situations drastically shift odds
3. Round wins (8-12%) - Series score progress
4. First blood (8-12%) - Early round indicator
5. Alive differential (2-5%) - Compounds with other factors

**Why economy matters most:** Valorant economy is deterministic. Team with $30k buys rifles + full armor + utilities. Team with $15k buys pistols + light armor. Firepower gap creates 70-30 win probability. This is visible in broadcast and highly predictive.

**Why player-level stats matter less:** Individual K/D or ADR reflects skill over many rounds, but doesn't shift single-round win probability as much as structural advantages (economy, alive counts, spike status). Team aggregates capture 90% of signal.

## Domain-Specific Considerations

### Valorant Game Mechanics Impact on Features

**Economy reset on round loss:** Losing team loses equipment but gains loss bonus ($1900-2900). Creates force-buy decisions. Prediction models must track loss streaks to estimate economy recovery.

**Ultimate point accumulation:** Ultimates charge via kills, orbs, and spike plants. Not time-based. Tracking ult status requires knowing charge rate per agent (varies 5-8 orbs). Complex. May not justify CV effort.

**Pistol round importance:** Rounds 1 and 13 (pistol rounds) have ~10% impact on map outcome. Winning pistol → likely win round 2 (economy advantage) → 2-0 or 1-1 start. Flag pistol rounds in event logs.

**Side swap at half (round 13):** Valorant maps favor defense (55-45 on average). Prediction models must know which side each team is playing. Extract from broadcast icon or infer from round number.

**Spike plant credit reward:** Planting spike grants attacker team +300 credits each, even if round lost. This affects next-round economy. Models should track "spike planted but round lost" scenarios.

### VCT Broadcast Overlay Specifics

**Buy phase economy visibility:** Total team economy shown only during buy phase (~45 seconds at round start). Hidden during combat. CV pipeline must detect buy phase (timer = 0:45 or score unchanged for 45s) and extract economy before combat starts.

**Agent portraits always visible:** Unlike player cams or minimap (shown intermittently), agent portraits remain top of screen throughout match. Reliable extraction target for agent composition.

**Scoreboard overlay inconsistency:** VCT production sometimes overlays stats (K/D/A board) during timeouts or between rounds. This occludes vision ROIs. CV pipeline must detect scoreboard overlay and skip frame processing during those periods (or handle gracefully).

**Resolution consistency:** VCT broadcasts are 1920x1080 (1080p60). Existing ROI coordinates assume this. If Riot upgrades to 4K broadcasts, all coordinates break. Document this assumption in concerns.

### Training Data Requirements

**Match outcome labels:** Each event log must be labeled with final match winner. Requires watching match to completion (or scraping result from Liquipedia/VLR.gg).

**Minimum viable dataset:** Estimating based on training data about ML sample sizes:
- Minimum: 50-100 maps (5,000-10,000 rounds) for basic logistic regression
- Ideal: 200+ maps (20,000+ rounds) for robust predictions across agent metas, maps, and teams

**Data staleness:** Agent balance patches every 2-3 months. Meta shifts. Training data from 6+ months ago less relevant. Continuous data collection required.

**Class imbalance:** VCT matches often feature top teams vs lower-tier teams (70-30 win rates). Dataset may be imbalanced. Stratified sampling or reweighting required during model training.

## Confidence Assessment

| Area | Confidence Level | Source | Notes |
|------|------------------|--------|-------|
| **Valorant game mechanics** | HIGH | Training data (game design, competitive rules) | Mechanics unlikely to change drastically. Economy/spike/round structure is core. |
| **VCT broadcast overlay** | MEDIUM | Training data + existing codebase analysis | Overlay format may change between seasons. ROI coordinates break on UI refresh. |
| **Prediction market value** | MEDIUM | Training data (esports betting, FPS mechanics) | Win probability shifts are estimates based on general FPS principles, not Valorant-specific studies. |
| **CV extraction feasibility** | HIGH | Existing codebase + OpenCV capabilities | Scores, alive counts, economy, spike status are already extracted. New features (teams, map, agents) feasible with template matching. |
| **Feature priority** | MEDIUM-HIGH | Training data + project context | Prioritization based on prediction value and CV difficulty is sound, but lacks real-world validation with trained models. |
| **2026 current state** | LOW | WebSearch unavailable | Cannot verify if VCT broadcast overlay changed in 2025-2026, if agent roster expanded, or if new game mechanics introduced. Assume training data (Jan 2025) is current. |

**Major assumption:** VCT broadcast overlay format has not changed significantly since training data cutoff (Jan 2025). If Riot redesigned overlay in 2025-2026, ROI coordinates and feature extraction approach may need recalibration.

**Verification needed:**
- WebSearch for "VCT 2026 broadcast overlay changes" (unavailable currently)
- Test extraction pipeline against live VCT match from 2026 to verify ROI coordinates still valid
- Validate agent roster (training data shows ~22 agents; more may have been added in 2025-2026)

## Research Gaps and Next Steps

**Gaps in this research:**

1. **2026 VCT broadcast format verification:** Cannot confirm overlay layout unchanged since training data cutoff. Risk: ROI coordinates may be stale.

2. **Agent meta current state:** Training data from Jan 2025. Agent balance patches since then may shift composition importance. New agents released?

3. **Prediction market liquidity:** Don't know if Polymarket/Kalshi have liquid VCT markets in 2026. If markets are thin, prediction edge may not translate to profitable trades.

4. **Competitor analysis:** No data on what features other Valorant prediction systems use. Are we over-engineering (ultimate tracking) or under-engineering (missing critical features)?

5. **Feature interaction effects:** Research estimates individual feature impact (economy = 15-25%, first blood = 8-12%) but doesn't model interactions. Reality: "First blood + economy advantage + spike plant" compounds non-linearly.

**Recommended next steps:**

1. **Validate against live 2026 VCT match:** Run existing CV pipeline against current VCT broadcast. Verify ROI coordinates still accurate.

2. **Phase-specific research during implementation:** When implementing agent compositions, research current agent roster and meta (may have changed since Jan 2025).

3. **Prediction model validation:** After collecting initial event logs, train basic model and measure calibration. If predictions are poorly calibrated, revisit feature priorities.

4. **Competitor research (if time allows):** Search for "Valorant prediction models" or "VCT betting systems" to see what features others prioritize. May reveal overlooked high-value features.

5. **Iterate based on data collection:** Features that seem high-value theoretically may be unreliable in practice (e.g., ultimate tracking may be too noisy from broadcast). Be ready to deprioritize.

## Sources and Methodology

**Research sources (training data only; WebSearch unavailable):**

- **Valorant game mechanics:** Training data about tactical FPS economy systems, round-based gameplay, agent abilities (as of Jan 2025 knowledge cutoff)
- **VCT broadcast analysis:** Existing codebase analysis (vision_engine.py, config.py, PROJECT.md, ARCHITECTURE.md, CONCERNS.md)
- **Esports prediction systems:** Training data about feature engineering for match outcome prediction, betting market efficiency, event impact on win probability
- **Computer vision feasibility:** Training data about OCR (Tesseract) capabilities, template matching, color detection, limitations of broadcast analysis

**Methodology:**

1. **Domain analysis:** Identified Valorant-specific mechanics (economy resets, spike plant rewards, pistol round importance) that affect feature priorities
2. **CV constraint mapping:** Cross-referenced VCT broadcast overlay visibility (what's shown on screen) with CV extraction techniques (OCR, template matching, color detection)
3. **Prediction value estimation:** Applied FPS game theory (alive differential impact, economy gap impact) to estimate win probability shifts per feature
4. **Feasibility assessment:** Categorized features by CV extraction difficulty (easy/medium/hard) based on existing codebase capabilities and overlay visibility
5. **Priority matrix:** Ranked features by prediction value vs implementation difficulty to guide MVP scope

**Limitations:**

- No access to 2026 VCT broadcasts for verification (WebSearch blocked)
- No competitor analysis (cannot research existing Valorant prediction systems)
- Win probability estimates based on general FPS principles, not Valorant-specific empirical studies
- Feature interaction effects not modeled (assumes independent contributions, which is oversimplification)

---

*Feature research complete. Confidence: MEDIUM (training data-based; 2026 verification pending). Ready for roadmap creation.*
