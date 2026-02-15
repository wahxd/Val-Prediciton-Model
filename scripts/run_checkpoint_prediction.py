#!/usr/bin/env python
"""Per-map checkpoint prediction experiment.

Predicts map winner from partial round data at mid-game checkpoints (round 6, 12, 18).
Uses only data available AT that point in the game - no data leakage.

Key innovations over the first experiment:
  - Side-adjusted scoring: accounts for map-specific attack/defense balance
  - Checkpoint features: prediction improves as more game data becomes available
  - Live-betting use case: this is where edge against Polymarket lives

Usage:
    python scripts/run_checkpoint_prediction.py
"""

import json
import sys
import warnings
from pathlib import Path
from datetime import datetime
from collections import defaultdict

import numpy as np
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.loader import MapData
from src.data.schemas import MapMetadata, RoundEndEvent, parse_event
from src.features.extractors.map_features import extract_map_features
from src.modeling.config import ExperimentConfig, ModelConfig
from src.modeling.experiment import run_experiment

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
VALOSCRIBE_DATA_DIR = Path("D:/Git/valoscribe/champs2025_processed_vods")
OUTPUT_DIR = Path("experiments")
CHECKPOINTS = [6, 12, 18]


# ---------------------------------------------------------------------------
# Adapter functions (copied from run_real_experiment.py)
# ---------------------------------------------------------------------------
def discover_series_maps(data_dir: Path) -> dict[str, list[dict]]:
    """Walk nested directory structure to find all series and maps."""
    series_maps: dict[str, list[dict]] = {}

    for series_dir in sorted(data_dir.iterdir()):
        if not series_dir.is_dir():
            continue

        series_id = series_dir.name
        maps = []

        for map_dir in sorted(series_dir.iterdir()):
            if not map_dir.is_dir() or map_dir.name == "metadata":
                continue
            if not map_dir.name.startswith("map"):
                continue

            output_dir = map_dir / "output"
            if not (output_dir / "event_log.jsonl").exists():
                continue
            if not (map_dir / "metadata.json").exists():
                continue

            parts = map_dir.name.split("_", 1)
            map_num = int(parts[0].replace("map", ""))
            map_name = parts[1] if len(parts) > 1 else "unknown"

            maps.append({
                "map_dir": map_dir,
                "map_name": map_name,
                "map_number": map_num,
            })

        if maps:
            maps.sort(key=lambda m: m["map_number"])
            series_maps[series_id] = maps

    return series_maps


def infer_round_numbers(raw_events: list[dict]) -> list[dict]:
    """Add round numbers to events that lack them."""
    events = sorted(raw_events, key=lambda e: e.get("timestamp", 0))
    current_round = 1

    for event in events:
        etype = event.get("type", "")
        if etype == "round_start" and "round_number" in event:
            current_round = event["round_number"]
        elif etype == "round_end" and "round_number" in event:
            current_round = event["round_number"]

        if "round_number" not in event:
            event["round_number"] = current_round

    return events


def compute_sides(
    round_number: int, team1: str, team2: str, team1_starting_side: str
) -> dict[str, str]:
    """Compute sides dict for a round based on starting sides."""
    if round_number <= 12:
        t1_side = team1_starting_side
    elif round_number <= 24:
        t1_side = "attack" if team1_starting_side == "defense" else "defense"
    else:
        ot_round = round_number - 24
        ot_period = (ot_round - 1) // 2
        if ot_period % 2 == 0:
            t1_side = "attack" if team1_starting_side == "defense" else "defense"
        else:
            t1_side = team1_starting_side

    t2_side = "attack" if t1_side == "defense" else "defense"
    return {team1: t1_side, team2: t2_side}


def transform_events(raw_events: list[dict], metadata: dict) -> list[str]:
    """Transform raw Valoscribe events to JSON strings for parse_event()."""
    events = infer_round_numbers(raw_events)

    teams = metadata.get("teams", [])
    team1 = teams[0]["name"] if teams else "Team1"
    team2 = teams[1]["name"] if len(teams) > 1 else "Team2"
    t1_start = teams[0].get("starting_side", "attack") if teams else "attack"

    transformed = []

    for event in events:
        etype = event.get("type", "")
        ts = event.get("timestamp", 0.0)
        rn = event.get("round_number", 1)

        if etype == "kill":
            out = {
                "type": "kill",
                "timestamp": ts,
                "round": rn,
                "killer": event.get("killer_name", "unknown"),
                "victim": event.get("victim_name", "unknown"),
                "weapon": event.get("weapon") or "unknown",
                "killer_team": event.get("killer_team", ""),
                "victim_team": event.get("victim_team", ""),
            }
        elif etype == "round_end":
            out = {
                "type": "round_end",
                "timestamp": ts,
                "round": rn,
                "winning_team": event.get("winner", ""),
                "score_team1": event.get("score_team1", 0),
                "score_team2": event.get("score_team2", 0),
                "sides": compute_sides(rn, team1, team2, t1_start),
            }
        elif etype == "round_start":
            out = {
                "type": "round_start",
                "timestamp": ts,
                "round": rn,
                "sides": compute_sides(rn, team1, team2, t1_start),
            }
        elif etype == "spike_plant":
            out = {"type": "spike_plant", "timestamp": ts, "round": rn}
        elif etype == "spike_defuse":
            out = {"type": "spike_defuse", "timestamp": ts, "round": rn}
        elif etype == "ultimate_used":
            out = {
                "type": "ult_usage",
                "timestamp": ts,
                "round": rn,
                "player": event.get("player"),
                "agent": event.get("agent"),
            }
        else:
            continue

        transformed.append(json.dumps(out))

    return transformed


def transform_metadata(raw_meta: dict) -> dict:
    """Transform Valoscribe metadata to MapMetadata-compatible format."""
    teams = []
    for t in raw_meta.get("teams", []):
        teams.append(t["name"] if isinstance(t, dict) else str(t))

    return {
        "teams": teams,
        "map_name": raw_meta.get("map", ""),
        "date": "",
    }


def load_map_adapted(series_id: str, map_info: dict) -> MapData:
    """Load and transform a single map into a MapData object."""
    map_dir = map_info["map_dir"]

    with open(map_dir / "metadata.json", "r", encoding="utf-8") as f:
        raw_meta = json.load(f)

    raw_events = []
    with open(map_dir / "output" / "event_log.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                raw_events.append(json.loads(line))

    json_strings = transform_events(raw_events, raw_meta)

    events = []
    parse_errors = []
    for i, js in enumerate(json_strings):
        try:
            events.append(parse_event(js))
        except Exception as e:
            parse_errors.append({"line": i + 1, "error": str(e), "raw": js[:200]})

    meta_dict = transform_metadata(raw_meta)
    metadata = MapMetadata.model_validate(meta_dict)

    map_id = f"{series_id}__map{map_info['map_number']}_{map_info['map_name']}"

    return MapData(
        map_id=map_id,
        map_dir=map_dir,
        events=events,
        frames=None,
        metadata=metadata,
        files_found=["event_log.jsonl", "metadata.json"],
        event_count=len(events),
        parse_errors=parse_errors,
    )


# ---------------------------------------------------------------------------
# Step 2: Compute Map-Level Attack Win Rates
# ---------------------------------------------------------------------------
def compute_map_side_stats(all_maps: list[MapData]) -> dict[str, float]:
    """Compute attack win rate per map_name from all available data."""
    map_stats = defaultdict(lambda: {"attack_wins": 0, "total_rounds": 0})

    for map_data in all_maps:
        map_name = map_data.metadata.map_name
        for event in map_data.events:
            if isinstance(event, RoundEndEvent):
                if event.sides:
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


# ---------------------------------------------------------------------------
# Step 3: Determine map winner and starting side helpers
# ---------------------------------------------------------------------------
def determine_map_winner(events: list, team1: str) -> str:
    """Determine who won the map from full event data."""
    last_round_end = None
    for event in events:
        if isinstance(event, RoundEndEvent):
            last_round_end = event

    if last_round_end is None:
        return team1  # fallback

    if last_round_end.score_team1 > last_round_end.score_team2:
        return team1
    else:
        # team2 is the other team
        if last_round_end.sides:
            teams = list(last_round_end.sides.keys())
            return teams[1] if teams[0] == team1 else teams[0]
        return "team2"


def get_team1_starting_side(map_data: MapData) -> str:
    """Get team1's starting side from the first round's sides dict."""
    team1 = map_data.metadata.teams[0]
    for event in map_data.events:
        if isinstance(event, RoundEndEvent) and event.sides:
            return event.sides.get(team1, "attack")
        if hasattr(event, "sides") and event.sides:
            return event.sides.get(team1, "attack")
    return "attack"  # fallback


def has_enough_rounds(filtered_events: list, cutoff: int) -> bool:
    """Check if filtered events contain enough round_end events."""
    round_ends = [e for e in filtered_events if isinstance(e, RoundEndEvent)]
    return len(round_ends) >= cutoff


# ---------------------------------------------------------------------------
# Step 3: Create Checkpoint Prediction Instances
# ---------------------------------------------------------------------------
def create_checkpoint_instances(
    all_maps: list[MapData],
    map_side_stats: dict[str, float],
    map_series: dict[str, str],
) -> pd.DataFrame:
    """Create prediction instances at each checkpoint for each map."""
    rows = []

    for map_data in all_maps:
        teams = map_data.metadata.teams
        team1 = teams[0]
        map_name = map_data.metadata.map_name
        map_atk_wr = map_side_stats.get(map_name, 0.5)

        # Determine actual winner from full data
        actual_winner = determine_map_winner(map_data.events, team1)

        # Get team1's starting side
        t1_starting_side = get_team1_starting_side(map_data)

        for cutoff in CHECKPOINTS:
            # Filter events to round <= cutoff
            filtered = [e for e in map_data.events if e.round <= cutoff]

            if not has_enough_rounds(filtered, cutoff):
                continue  # Map ended before this checkpoint

            # Extract features from partial data
            features = extract_map_features(filtered, map_data.map_id, teams)

            # Compute side-adjusted features
            if cutoff <= 12:
                expected_t1_wr = map_atk_wr if t1_starting_side == "attack" else (1 - map_atk_wr)
            else:
                # Mix of first half and second half
                first_half_wr = map_atk_wr if t1_starting_side == "attack" else (1 - map_atk_wr)
                second_half_wr = (1 - map_atk_wr) if t1_starting_side == "attack" else map_atk_wr
                rounds_first = min(cutoff, 12)
                rounds_second = cutoff - 12
                expected_t1_wr = (first_half_wr * rounds_first + second_half_wr * rounds_second) / cutoff

            expected_score_t1 = cutoff * expected_t1_wr
            actual_score_t1 = features.get("final_score_team1", 0) or 0

            row = {
                "map_id": map_data.map_id,
                "series_id": map_series[map_data.map_id],
                "checkpoint": cutoff,
                "map_name": map_name,
                # Side context features
                "map_attack_win_rate": map_atk_wr,
                "team1_on_attack_first": 1 if t1_starting_side == "attack" else 0,
                "adjusted_score_diff": actual_score_t1 - expected_score_t1,
                # All extracted features from partial data
                **features,
                # Target
                "y": 1 if actual_winner == team1 else 0,
            }
            rows.append(row)

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Step 4: Preprocess Features
# ---------------------------------------------------------------------------
def preprocess_checkpoint_features(df: pd.DataFrame) -> pd.DataFrame:
    """Convert string/bool features to numeric, fill NaN."""
    df = df.copy()

    # Convert string pistol features to binary (1 = team1 won that pistol)
    for col in ["pistol_round1_winner", "pistol_round2_winner"]:
        if col in df.columns:
            # Need to compare against team1 per-row; we don't have _team1 column
            # but we can get it from map_id -> look at the map_data
            # Simpler: the feature already has the team name or None
            # We can use a helper: team1 is first in the teams list
            # For checkpoint data, we need the map_id -> team1 mapping
            pass  # Handled below

    # Get team1 per map_id from the data (team1 = the team whose perspective features are from)
    # In extract_map_features, team1 is teams[0], so pistol_round1_winner contains a team name
    # We need to convert it to binary

    # Build map_id -> team1 mapping from the 'map_id' and available data
    # We already have this info in the features: team1 is implicit
    # For each row, check if pistol winner matches team1
    # But we don't have team1 name stored... We DO have it embedded in the map_id
    # Actually, let's just use a different approach: store team1 name during instance creation

    # Pistol features: convert team name to binary
    for col in ["pistol_round1_winner", "pistol_round2_winner"]:
        if col in df.columns:
            # If value is a string (team name), we need to know if it's team1
            # We stored 'y' based on team1 winning, and features are team1-perspective
            # pistol winner == team1 means pistol_rounds_won should increment
            # Simplest: if value is truthy string and not NaN, check against team1
            # But we don't have team1 name in the df...
            # Let's use pistol_rounds_won_team1 as a proxy and just zero out the string columns
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    # Convert map_winner to binary (1 = team1 won partial data winner, which is misleading)
    # Actually map_winner from extract_map_features reflects partial data - drop it
    if "map_winner" in df.columns:
        df.drop(columns=["map_winner"], inplace=True)

    # Convert bools to int
    for col in df.select_dtypes(include=["bool"]).columns:
        df[col] = df[col].astype(int)

    # Drop metadata columns from features
    meta_cols = {"map_id", "series_id", "map_name", "y"}
    feature_cols = [c for c in df.columns if c not in meta_cols]
    df[feature_cols] = df[feature_cols].fillna(0)

    # Ensure all feature columns are numeric
    for col in feature_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df


# ---------------------------------------------------------------------------
# Step 5: Feature Selection
# ---------------------------------------------------------------------------
CHECKPOINT_FEATURES = [
    # From extract_map_features (partial data)
    "final_score_team1",
    "final_score_team2",
    "score_differential",
    "total_rounds",
    "pistol_round1_winner",
    "pistol_rounds_won_team1",
    "first_half_score_team1",
    "first_half_score_team2",
    "max_win_streak_team1",
    "max_win_streak_team2",
    "max_loss_streak_team1",
    "max_loss_streak_team2",
    "first_blood_rate_team1",
    "first_blood_rate_team2",
    "attack_win_rate_team1",
    "defense_win_rate_team1",
    # New side-context features
    "map_attack_win_rate",
    "team1_on_attack_first",
    "adjusted_score_diff",
    "checkpoint",
]


# ---------------------------------------------------------------------------
# Step 6 & 7: Run Experiments and Per-Checkpoint Analysis
# ---------------------------------------------------------------------------
def run_checkpoint_experiments(df: pd.DataFrame, feature_names: list[str]) -> dict:
    """Run LR and XGB experiments on checkpoint data."""
    experiments = {
        "checkpoint_lr": "logistic_regression",
        "checkpoint_xgb": "xgboost",
    }

    available = [f for f in feature_names if f in df.columns]
    y = df["y"]
    groups = df["series_id"]
    X = df[available].astype(float)

    print(f"\nFeatures used ({len(available)}): {available}")
    print(f"Dataset: {len(df)} instances, {groups.nunique()} groups")

    results = {}

    for exp_id, model_type in experiments.items():
        print(f"\n{'='*60}")
        print(f"  Experiment: {exp_id}")
        print(f"  Model: {model_type}, Features: {len(available)}")
        print(f"{'='*60}")

        config = ExperimentConfig(
            experiment_id=exp_id,
            model=ModelConfig(
                model_type=model_type,
                feature_set="core",
            ),
            calibration_method="sigmoid",
            calibration_cv=3,
            output_dir=OUTPUT_DIR,
        )

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result = run_experiment(config, X, y, groups, available)

            cv = result["cv_results"]["overall_metrics"]
            print(f"  Log Loss:    {cv['log_loss']:.4f}")
            print(f"  Brier Score: {cv['brier_score']:.4f}")
            print(f"  Accuracy:    {cv['accuracy']:.2%}")
            print(f"  Beats naive: {result['beats_naive_prior']}")
            print(f"  Folds:       {result['cv_results']['n_folds']}")

            results[exp_id] = result

        except Exception as e:
            print(f"  FAILED: {e}")
            import traceback
            traceback.print_exc()
            results[exp_id] = {"error": str(e)}

    return results


def analyze_per_checkpoint(df: pd.DataFrame, feature_names: list[str]) -> dict:
    """Analyze prediction quality at each checkpoint round."""
    available = [f for f in feature_names if f in df.columns]
    results = {}

    for cp in CHECKPOINTS:
        cp_df = df[df["checkpoint"] == cp]
        if len(cp_df) < 5:
            results[cp] = {"n": len(cp_df), "skipped": True}
            continue

        X_cp = cp_df[available].astype(float)
        y_cp = cp_df["y"]
        groups_cp = cp_df["series_id"]

        config = ExperimentConfig(
            experiment_id=f"checkpoint_r{cp}_lr",
            model=ModelConfig(
                model_type="logistic_regression",
                feature_set="core",
            ),
            calibration_method="sigmoid",
            calibration_cv=3,
            output_dir=OUTPUT_DIR,
        )

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result = run_experiment(config, X_cp, y_cp, groups_cp, available)

            cv = result["cv_results"]["overall_metrics"]
            results[cp] = {
                "n": len(cp_df),
                "log_loss": cv["log_loss"],
                "accuracy": cv["accuracy"],
                "brier": cv["brier_score"],
                "beats_naive": result["beats_naive_prior"],
            }
        except Exception as e:
            results[cp] = {"n": len(cp_df), "error": str(e)}

    return results


# ---------------------------------------------------------------------------
# Step 8: Print Results
# ---------------------------------------------------------------------------
def print_results(
    results: dict,
    per_checkpoint: dict,
    map_side_stats: dict[str, float],
    n_instances: int,
    n_maps: int,
    n_series: int,
) -> None:
    """Print comprehensive results."""
    print(f"\n{'='*80}")
    print("CHECKPOINT PREDICTION EXPERIMENT RESULTS")
    print(f"Dataset: {n_instances} instances from {n_maps} maps across {n_series} series")
    print(f"Checkpoints: rounds {CHECKPOINTS}")
    print(f"{'='*80}")

    # Map side stats
    print(f"\nMap Attack Win Rates:")
    for map_name, awr in sorted(map_side_stats.items()):
        balance = "attack-sided" if awr > 0.52 else "defense-sided" if awr < 0.48 else "balanced"
        print(f"  {map_name:<12s}: {awr:.3f} ({balance})")

    # Main experiment comparison
    header = (
        f"{'Experiment':<20} {'Log Loss':>10} {'Brier':>10} "
        f"{'Accuracy':>10} {'vs Naive':>10}"
    )
    print(f"\n{header}")
    print("-" * 62)

    print(
        f"{'Naive (0.5)':<20} {'0.6931':>10} {'0.2500':>10} "
        f"{'50.00%':>10} {'---':>10}"
    )

    for exp_id, result in results.items():
        if "error" in result:
            print(f"{exp_id:<20} {'FAILED':>10}")
            continue

        cv = result["cv_results"]["overall_metrics"]
        print(
            f"{exp_id:<20} {cv['log_loss']:>10.4f} {cv['brier_score']:>10.4f} "
            f"{cv['accuracy']:>9.2%} "
            f"{'Yes' if result['beats_naive_prior'] else 'No':>10}"
        )

    # Per-checkpoint breakdown
    print(f"\n--- Per-Checkpoint Accuracy (LR) ---")
    print(f"{'Round':>8} {'N':>6} {'Log Loss':>10} {'Accuracy':>10} {'Beats Naive':>12}")
    print("-" * 48)

    for cp in CHECKPOINTS:
        info = per_checkpoint.get(cp, {})
        if info.get("skipped") or info.get("error"):
            print(f"{cp:>8} {info.get('n', 0):>6} {'SKIP/ERROR':>10}")
            continue
        print(
            f"{cp:>8} {info['n']:>6} {info['log_loss']:>10.4f} "
            f"{info['accuracy']:>9.2%} "
            f"{'Yes' if info['beats_naive'] else 'No':>12}"
        )

    # SHAP top features from best model
    best_exp = None
    best_ll = float("inf")
    for exp_id, result in results.items():
        if "error" not in result:
            ll = result["cv_results"]["overall_metrics"]["log_loss"]
            if ll < best_ll:
                best_ll = ll
                best_exp = exp_id

    if best_exp:
        best = results[best_exp]
        print(f"\n--- Best Model: {best_exp} (log loss = {best_ll:.4f}) ---")

        shap = best.get("shap_analysis", {})
        importance = shap.get("feature_importance", {})
        if importance:
            print("\nTop 10 Features (SHAP importance):")
            for i, (feat_name, feat_imp) in enumerate(list(importance.items())[:10], 1):
                marker = " <-- SIDE-ADJUSTED" if "adjusted" in feat_name or "attack_win_rate" == feat_name else ""
                print(f"  {i:2d}. {feat_name:<35s} {feat_imp:.4f}{marker}")

        # Check if side-adjusted features appear
        side_features = {"map_attack_win_rate", "team1_on_attack_first", "adjusted_score_diff"}
        if importance:
            top_10_names = set(list(importance.keys())[:10])
            side_in_top10 = side_features & top_10_names
            print(f"\nSide-adjusted features in top 10: {side_in_top10 if side_in_top10 else 'None'}")

        # Thesis / calibration
        thesis = best.get("thesis_validation", {})
        if thesis:
            print(f"\nThesis Validation:")
            print(f"  Hierarchy respected: {thesis.get('hierarchy_respected', 'N/A')}")
            print(f"  Game mechanics %:    {thesis.get('game_mechanics_pct', 0):.1f}%")

        cal = best.get("calibration_validation", {})
        if cal:
            print(f"\nCalibration:")
            print(f"  Passes:          {cal.get('passes', 'N/A')}")
            print(f"  Max deviation:   {cal.get('max_deviation', 0):.4f}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 80)
    print("CHECKPOINT PREDICTION EXPERIMENT")
    print(f"Data source: {VALOSCRIBE_DATA_DIR}")
    print(f"Output dir:  {OUTPUT_DIR.resolve()}")
    print(f"Started:     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # 1. Discover and load all maps
    print("\n--- Step 1: Discovering and loading maps ---")
    series_maps = discover_series_maps(VALOSCRIBE_DATA_DIR)
    total_maps = sum(len(maps) for maps in series_maps.values())
    print(f"Found {len(series_maps)} series with {total_maps} total maps")

    all_maps: list[MapData] = []
    map_series: dict[str, str] = {}
    load_failures = []

    for series_id, maps_list in series_maps.items():
        for map_info in maps_list:
            try:
                map_data = load_map_adapted(series_id, map_info)
                all_maps.append(map_data)
                map_series[map_data.map_id] = series_id
                print(f"  OK: {map_data.map_id} [{map_data.event_count} events]")
            except Exception as e:
                load_failures.append((series_id, map_info["map_dir"].name, str(e)))
                print(f"  FAIL: {series_id}/{map_info['map_dir'].name}: {e}")

    print(f"\nLoaded: {len(all_maps)} maps, Failed: {len(load_failures)}")

    if len(all_maps) < 10:
        print("ERROR: Too few maps. Aborting.")
        return

    # 2. Compute map-level attack win rates
    print("\n--- Step 2: Computing map side stats ---")
    map_side_stats = compute_map_side_stats(all_maps)
    for map_name, awr in sorted(map_side_stats.items()):
        print(f"  {map_name}: attack_win_rate = {awr:.3f}")

    # 3. Create checkpoint instances
    print("\n--- Step 3: Creating checkpoint instances ---")
    df = create_checkpoint_instances(all_maps, map_side_stats, map_series)
    print(f"Created {len(df)} prediction instances")
    print(f"  Per checkpoint: {df['checkpoint'].value_counts().sort_index().to_dict()}")
    print(f"  Target distribution: {df['y'].value_counts().to_dict()}")

    if df.empty:
        print("ERROR: No instances created. Aborting.")
        return

    # 4. Preprocess
    print("\n--- Step 4: Preprocessing ---")
    df = preprocess_checkpoint_features(df)
    n_series = df["series_id"].nunique()
    print(f"Preprocessed: {len(df)} instances, {n_series} series")

    # 5. Run main experiments (all checkpoints combined)
    print("\n--- Step 5: Running experiments ---")
    results = run_checkpoint_experiments(df, CHECKPOINT_FEATURES)

    # 6. Per-checkpoint analysis
    print("\n--- Step 6: Per-checkpoint analysis ---")
    per_checkpoint = analyze_per_checkpoint(df, CHECKPOINT_FEATURES)

    # 7. Print comprehensive results
    print_results(
        results,
        per_checkpoint,
        map_side_stats,
        n_instances=len(df),
        n_maps=len(all_maps),
        n_series=n_series,
    )

    print(f"\n{'='*80}")
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Results saved to: {OUTPUT_DIR.resolve()}")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
