# Phase 8: Feature Engineering - Context

**Gathered:** 2026-02-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Transform Valoscribe event data into predictive features at three levels (round, map, match) with a feature registry for reproducible experiments. Features are purely game-mechanics-based -- no team identity features. Post-hoc features only (completed maps), not live/in-play.

</domain>

<decisions>
## Implementation Decisions

### Economy Reconstruction
- Use estimated credit tracking: reconstruct approximate team credits per round using Valorant's deterministic economy rules (loss bonus escalation, win bonus, plant bonus)
- Derive economy tiers from credit estimates per player:
  - Eco: 0-2500
  - Light buy: 2500-3500
  - Full buy: 3900+
  - Pistol rounds tagged separately
- Include round-over-round economy trends: loss bonus streak length, consecutive eco rounds, consecutive full-buys
- Handle unknowns with standard loadout assumption: use average kill reward (~200), ignore ability-related credits. Simple approximation over precision

### Feature Scope & Baseline
- Start broad: include features from all categories (economy, combat, side performance) rather than a minimal baseline
- All categories equally important -- let the model determine what's predictive
- Feature categories to build:
  - Economy & resource management: eco round win rate, economy differential, save frequency, force-buy success rate
  - Combat & momentum: first blood rate, clutch rate, multi-kill frequency, win streaks, anti-eco conversion rate
  - Side performance: attack vs defense win rates, pistol round outcomes per side, side-specific first blood rate
- Organize feature sets by data coverage: "core" (always available on all maps) and "extended" (includes features with sparse coverage)
- Post-hoc features only -- compute from completed maps for map/match winner prediction. Live/in-play features deferred
- Round-level features aggregate into map-level vectors only -- no round-winner prediction target
- No team identity features at all -- model predicts purely from in-game mechanics

### Feature Registry Structure
- YAML/JSON config file for feature set definitions
- Composable sets: feature sets can extend others (e.g., "economy_extended" = baseline + [eco_streak, force_buy_rate, ...])
- Registry = names only: YAML lists feature names and composition. Computation logic lives in Python code
- Metadata level: Claude's discretion (description, date created -- decided during implementation)

### Match-Level & Series Features
- No Elo ratings -- dropped entirely. No team strength signal, no historical VCT result scraping needed
- Match-level features = per-map aggregation + series momentum
- Series momentum features include:
  - Score differentials across maps (how decisive each win/loss was)
  - Win/loss sequence (comeback from 0-1 vs leading 1-0)
  - Whether previous maps went to overtime
- No tournament context, no map-pool features -- series momentum is sufficient
- Success criterion #4 (Elo ratings) will be updated to reflect this decision

### Claude's Discretion
- Feature registry metadata level (minimal vs descriptive)
- Exact feature names and computation approach
- How to handle the 3500-3900 gap in economy tiers (likely "half-buy" or merge with light buy)
- Specific missing-data defaults for extended feature set
- Loading skeleton for economy reconstruction (which round events to use)

</decisions>

<specifics>
## Specific Ideas

- Economy tiers based on user's Valorant knowledge: eco (0-2500), light buy (2500-3500), full buy (3900+) -- not standard analytics thresholds
- Philosophy: "let the model determine what's predictive" -- build comprehensive features, let regularization handle selection
- Pure game-mechanics approach: if the model can't predict from what happened in the game, it shouldn't predict at all

</specifics>

<deferred>
## Deferred Ideas

- Live/in-play prediction features (predicting at round X) -- future capability, v3 scope
- Map name as categorical feature -- could be useful but deferred per user preference
- Tournament stage context features -- deferred
- Elo rating system -- explicitly dropped, not deferred. Could reconsider if pure mechanics model underperforms

</deferred>

---

*Phase: 08-feature-engineering*
*Context gathered: 2026-02-14*
