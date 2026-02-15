# Plan: Per-Map Checkpoint Prediction Experiment

## Goal
Predict map winner from **partial round data** (mid-game checkpoints). At round 6, 12, or 18, given what's happened so far, who wins the map? This is the core live-betting use case.

## Why This Matters
- First experiment showed 100% accuracy but used final scores (data leakage - you already know who won)
- This experiment uses only data available AT that point in the game
- Features like first blood rate, economy, side performance are genuinely predictive from partial data
- Live betting odds shift every round - this is where edge against Polymarket lives

## Key Domain Insight: Side-Adjusted Scoring
Being up 8-4 at halftime means different things depending on map and side:
- Defense on Bind (defense-sided): 8-4 is expected
- Defense on Haven (attack-sided): 8-4 is dominant

We handle this by computing:
1. `map_attack_win_rate` - from our 71 maps, what % of rounds does attack win on each map name?
2. `adjusted_score_diff` - team1's score vs expected score given side and map balance
3. Keep raw features too - model gets both raw state and contextualized state

## File to Create
`scripts/run_checkpoint_prediction.py` (~300 lines)

## Reuse from Existing Code
- All adapter functions from `scripts/run_real_experiment.py`: `discover_series_maps`, `infer_round_numbers`, `compute_sides`, `transform_events`, `transform_metadata`, `load_map_adapted`
- `src/features/extractors/map_features.py`: `extract_map_features()` - works on partial event lists
- `src/modeling/experiment.py`: `run_experiment()` - unchanged
- `src/modeling/config.py`: `ExperimentConfig`, `ModelConfig` - unchanged

## Implementation Steps

### Step 1: Load All Maps
Reuse existing adapter. Load all 71 maps with `load_map_adapted()`. Track `series_id`, `team1`, `map_name` per map.

### Step 2: Compute Map-Level Attack Win Rates
For each of the ~8 map names (ascent, lotus, bind, etc.):
- Collect all round_end events across all maps of that name
- Count attack wins vs defense wins using the `sides` dict
- Compute `attack_win_rate` per map name
- Store as lookup: `{"ascent": 0.52, "bind": 0.45, ...}`

```python
def compute_map_side_stats(all_maps: list[MapData]) -> dict[str, float]:
    """Compute attack win rate per map_name from all available data."""
    from collections import defaultdict
    map_stats = defaultdict(lambda: {"attack_wins": 0, "total_rounds": 0})

    for map_data in all_maps:
        map_name = map_data.metadata.map_name
        for event in map_data.events:
            if isinstance(event, RoundEndEvent):
                if event.sides:
                    # Find which team was on attack
                    for team, side in event.sides.items():
                        if side == "attack":
                            if event.winning_team == team:
                                map_stats[map_name]["attack_wins"] += 1
                            break
                    map_stats[map_name]["total_rounds"] += 1

    return {
        name: stats["attack_wins"] / stats["total_rounds"]
        for name, stats in map_stats.items()
        if stats["total_rounds"] > 0
    }
```

### Step 3: Create Checkpoint Prediction Instances
For each of the 71 maps, at each checkpoint (round 6, 12, 18):

1. **Filter events** to `event.round <= cutoff`
2. **Extract features** using `extract_map_features(filtered_events, map_id, teams)`
   - This gives partial-game features: score at that point, first blood rate so far, streaks so far, etc.
   - `final_score_team1/team2` will actually be the score at the cutoff round (from the last round_end in filtered events)
3. **Add side-context features**:
   - `map_attack_win_rate`: lookup from Step 2
   - `team1_starting_side`: binary (1=attack, 0=defense)
   - `checkpoint_round`: which round cutoff (6, 12, 18) - useful context
   - `expected_score_team1`: `cutoff * (attack_wr if team1 on attack else 1-attack_wr)`
   - `adjusted_score_diff`: `actual_score_team1 - expected_score_team1`
4. **Target**: who actually won the map (from full event data, determined before filtering)
5. **Group**: `series_id` (for LOSO cross-validation)

```python
CHECKPOINTS = [6, 12, 18]

def create_checkpoint_instances(
    all_maps: list[MapData],
    map_side_stats: dict[str, float],
    map_series: dict[str, str],
    map_team1: dict[str, str],
) -> pd.DataFrame:
    rows = []
    for map_data in all_maps:
        teams = map_data.metadata.teams
        team1 = teams[0]
        map_name = map_data.metadata.map_name
        map_atk_wr = map_side_stats.get(map_name, 0.5)

        # Determine actual winner from full data
        actual_winner = determine_map_winner(map_data.events, team1)

        # Get team1's starting side from metadata
        # (already in the sides dict of round events)
        team1_starting_side = get_team1_starting_side(map_data)

        for cutoff in CHECKPOINTS:
            # Filter events to round <= cutoff
            filtered = [e for e in map_data.events if e.round <= cutoff]

            if not has_enough_rounds(filtered, cutoff):
                continue  # Skip if map ended before this checkpoint

            # Extract features from partial data
            features = extract_map_features(filtered, map_data.map_id, teams)

            # Compute side-adjusted features
            if team1_starting_side == "attack":
                t1_side_first_half = "attack"
            else:
                t1_side_first_half = "defense"

            # For rounds 1-12: team1 is on starting side
            # For rounds 13-24: team1 is on opposite side
            if cutoff <= 12:
                expected_t1_wr = map_atk_wr if t1_side_first_half == "attack" else (1 - map_atk_wr)
            else:
                # Mix of first half and second half
                first_half_wr = map_atk_wr if t1_side_first_half == "attack" else (1 - map_atk_wr)
                second_half_wr = (1 - map_atk_wr) if t1_side_first_half == "attack" else map_atk_wr
                rounds_first = min(cutoff, 12)
                rounds_second = cutoff - 12
                expected_t1_wr = (first_half_wr * rounds_first + second_half_wr * rounds_second) / cutoff

            expected_score_t1 = cutoff * expected_t1_wr
            actual_score_t1 = features.get("final_score_team1", 0)

            row = {
                "map_id": map_data.map_id,
                "series_id": map_series[map_data.map_id],
                "checkpoint": cutoff,
                "map_name": map_name,
                # Side context features
                "map_attack_win_rate": map_atk_wr,
                "team1_on_attack_first": 1 if t1_side_first_half == "attack" else 0,
                "adjusted_score_diff": actual_score_t1 - expected_score_t1,
                # All extracted features from partial data
                **features,
                # Target
                "y": 1 if actual_winner == team1 else 0,
            }
            rows.append(row)

    return pd.DataFrame(rows)
```

### Step 4: Preprocess Features
Same as first experiment but with checkpoint-specific handling:
- Convert string features (`pistol_round1_winner`, `pistol_round2_winner`, `map_winner`) to binary
- `pistol_round2_winner` will be 0/missing for checkpoint=6 and checkpoint=12 (R13 hasn't happened)
- Convert bools to int, fill NaN with 0
- Drop metadata columns from X (map_id, series_id, map_name, y, map_winner)

### Step 5: Feature Selection
Use a custom feature list (not the registry, since we have new features):

**Checkpoint features** (~20 total):
- From extract_map_features (partial): `final_score_team1`, `final_score_team2`, `score_differential`, `total_rounds`, `pistol_round1_winner`, `pistol_rounds_won_team1`, `first_half_score_team1`, `first_half_score_team2`, `max_win_streak_team1`, `max_win_streak_team2`, `max_loss_streak_team1`, `max_loss_streak_team2`, `first_blood_rate_team1`, `first_blood_rate_team2`, `attack_win_rate_team1`, `defense_win_rate_team1`
- New side-context: `map_attack_win_rate`, `team1_on_attack_first`, `adjusted_score_diff`, `checkpoint`

Note: `went_to_overtime`, `comeback_from_behind`, second-half features will be 0/False at early checkpoints. That's correct - they haven't happened yet.

### Step 6: Run Experiments
Run with `run_experiment()`:

| Experiment ID | Model | Description |
|---|---|---|
| `checkpoint_lr` | Logistic Regression | All checkpoint features |
| `checkpoint_xgb` | XGBoost | All checkpoint features |

Use LOSO CV with `groups = series_id`.

For the `feature_set` parameter in ModelConfig, use "core" (it's just metadata - the actual features are passed as X).

### Step 7: Per-Checkpoint Analysis
After the main experiments, also analyze accuracy per checkpoint:
- Round 6 accuracy: how well can we predict at 25% of the game?
- Round 12 accuracy: halftime prediction quality?
- Round 18 accuracy: with 75% of game played?

This shows how prediction improves as more game data becomes available.

### Step 8: Print Results
- Comparison table: both experiments vs naive baseline
- SHAP top features: which features drive predictions?
- Per-checkpoint breakdown: accuracy at each round cutoff
- Side adjustment impact: is `adjusted_score_diff` in top features?

## Expected Outcome
- ~213 prediction instances (71 maps x 3 checkpoints)
- Round 18 should be most accurate (most information)
- Round 6 should be hardest (least information)
- `adjusted_score_diff` should be a strong feature (encodes side+map context)
- `score_differential` raw should also be strong
- First blood rate should show up as a secondary signal

## What Success Looks Like
1. Script runs without errors on all 71 maps
2. Log loss < 0.693 (beats naive) - the model learned SOMETHING
3. Clear accuracy gradient: round 18 > round 12 > round 6
4. Side-adjusted features appear in SHAP top 10
5. Results saved to `experiments/checkpoint_lr/` and `experiments/checkpoint_xgb/`

## Important Notes
- The `extract_map_features` function will work on filtered events - it groups by round and processes what's there
- Economy features will be approximate (economy tracker reconstructs from rules, partial data is fine)
- Some features will be 0/None at early checkpoints (e.g., second half scores at round 6) - this is correct behavior, not a bug
- The `run_experiment` function handles SHAP, calibration, thesis validation automatically
- Team ordering is consistent within series (verified from actual data)
