#!/usr/bin/env python
"""Run real VCT data experiments using adapted Valoscribe data.

Bridges the gap between actual Valoscribe data format and the v2 prediction
framework by adapting events/metadata on-the-fly without modifying source code.

Data format differences handled:
  - Nested directory structure (series/map/output/) → flat MapData
  - event_log.jsonl → events.jsonl field remapping
  - killer_name/victim_name → killer/victim
  - winner → winning_team, round_number → round
  - Round number inference for events lacking round_number
  - Side computation from metadata starting_side
  - Metadata teams [{name, starting_side}] → [str]

Usage:
    uv run python scripts/run_real_experiment.py
"""

import json
import sys
import warnings
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.loader import MapData
from src.data.schemas import MapMetadata, parse_event
from src.features.pipeline import FeaturePipeline
from src.features.registry import FeatureRegistry
from src.modeling.config import ExperimentConfig, ModelConfig
from src.modeling.experiment import run_experiment

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
VALOSCRIBE_DATA_DIR = Path("D:/Git/valoscribe/champs2025_processed_vods")
OUTPUT_DIR = Path("experiments")


# ---------------------------------------------------------------------------
# Step 1: Data Discovery
# ---------------------------------------------------------------------------
def discover_series_maps(data_dir: Path) -> dict[str, list[dict]]:
    """Walk nested directory structure to find all series and maps.

    Returns:
        Dict mapping series_id to list of map info dicts, each with:
        - map_dir: Path to map directory
        - map_name: str (e.g., "ascent")
        - map_number: int (from directory name)
    """
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


# ---------------------------------------------------------------------------
# Step 2: Event Transformation
# ---------------------------------------------------------------------------
def infer_round_numbers(raw_events: list[dict]) -> list[dict]:
    """Add round numbers to events that lack them.

    Processes events in timestamp order, tracking current_round from
    round_start events. Events before the first round_start get round=1.
    """
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
    """Transform raw Valoscribe events to JSON strings for parse_event().

    Handles field remapping, round number inference, side computation,
    and weapon null -> "unknown".
    """
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
            # Skip non-essential types: death, revival, ability_used,
            # ability_recharged, match_start, match_end
            continue

        transformed.append(json.dumps(out))

    return transformed


# ---------------------------------------------------------------------------
# Step 3: Metadata Transformation
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Step 4: Map Loading (adapted)
# ---------------------------------------------------------------------------
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
# Step 5: Preprocessing
# ---------------------------------------------------------------------------
def preprocess_features(
    df: pd.DataFrame, map_team1: dict[str, str]
) -> pd.DataFrame:
    """Convert string/bool features to numeric, fill NaN, add binary target."""
    df = df.copy()

    # Track team1 for binary encoding
    df["_team1"] = df["map_id"].map(map_team1)

    # Convert string pistol features to binary (1 = team1 won that pistol)
    for col in ["pistol_round1_winner", "pistol_round2_winner"]:
        if col in df.columns:
            # Handle None/NaN: where map_winner is NaN, keep as 0
            df[col] = df.apply(
                lambda r: 1 if r.get(col) == r.get("_team1") else 0, axis=1
            )

    # Create binary target: 1 if team1 won the map
    df["y"] = (df["map_winner"] == df["_team1"]).astype(int)

    # Convert bools to int
    for col in df.select_dtypes(include=["bool"]).columns:
        df[col] = df[col].astype(int)

    df.drop(columns=["_team1"], inplace=True)

    # Fill NaN with 0 for feature columns
    meta_cols = {"map_id", "map_winner", "series_id", "y"}
    feature_cols = [c for c in df.columns if c not in meta_cols]
    df[feature_cols] = df[feature_cols].fillna(0)

    return df


# ---------------------------------------------------------------------------
# Step 6: Run Experiments
# ---------------------------------------------------------------------------
def run_all_experiments(
    df: pd.DataFrame, feature_sets: dict[str, list[str]]
) -> dict:
    """Run 4 experiments: LR core, LR full, XGB core, XGB full."""
    experiments = {
        "real_lr_core": ("logistic_regression", "core"),
        "real_lr_full": ("logistic_regression", "full"),
        "real_xgb_core": ("xgboost", "core"),
        "real_xgb_full": ("xgboost", "full"),
    }

    y = df["y"]
    groups = df["series_id"]
    results = {}

    for exp_id, (model_type, feat_set) in experiments.items():
        feat_names = feature_sets[feat_set]
        available = [f for f in feat_names if f in df.columns]

        print(f"\n{'='*60}")
        print(f"  Experiment: {exp_id}")
        print(f"  Model: {model_type}, Features: {feat_set} ({len(available)})")
        print(f"{'='*60}")

        X = df[available].astype(float)

        config = ExperimentConfig(
            experiment_id=exp_id,
            model=ModelConfig(
                model_type=model_type,
                feature_set=feat_set,
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


# ---------------------------------------------------------------------------
# Step 7: Analysis Output
# ---------------------------------------------------------------------------
def print_analysis(results: dict, n_maps: int, n_series: int) -> None:
    """Print comprehensive comparison of all experiments."""
    print(f"\n{'='*80}")
    print("EXPERIMENT RESULTS COMPARISON")
    print(f"Dataset: {n_maps} maps across {n_series} series")
    print(f"{'='*80}")

    # Comparison table
    header = (
        f"{'Experiment':<20} {'Log Loss':>10} {'Brier':>10} "
        f"{'Accuracy':>10} {'vs Naive':>10} {'Game%':>8}"
    )
    print(f"\n{header}")
    print("-" * 70)

    print(
        f"{'Naive (0.5)':<20} {'0.6931':>10} {'0.2500':>10} "
        f"{'50.00%':>10} {'---':>10} {'---':>8}"
    )

    for exp_id, result in results.items():
        if "error" in result:
            print(f"{exp_id:<20} {'FAILED':>10}")
            continue

        cv = result["cv_results"]["overall_metrics"]
        gm = result.get("game_mechanics_validation", {})
        gm_pct = gm.get("game_mechanic_pct", 0)  # Already 0-100

        print(
            f"{exp_id:<20} {cv['log_loss']:>10.4f} {cv['brier_score']:>10.4f} "
            f"{cv['accuracy']:>9.2%} "
            f"{'Yes' if result['beats_naive_prior'] else 'No':>10} "
            f"{gm_pct:>7.1f}%"
        )

    # Find best model
    best_exp = None
    best_ll = float("inf")
    for exp_id, result in results.items():
        if "error" not in result:
            ll = result["cv_results"]["overall_metrics"]["log_loss"]
            if ll < best_ll:
                best_ll = ll
                best_exp = exp_id

    if not best_exp:
        print("\nNo successful experiments to analyze.")
        return

    print(f"\n--- Best Model: {best_exp} (log loss = {best_ll:.4f}) ---")
    best = results[best_exp]

    # SHAP top features (feature_importance is a dict: name -> importance)
    shap = best.get("shap_analysis", {})
    importance = shap.get("feature_importance", {})
    if importance:
        print("\nTop 10 Features (SHAP importance):")
        for i, (feat_name, feat_imp) in enumerate(list(importance.items())[:10], 1):
            print(f"  {i:2d}. {feat_name:<35s} {feat_imp:.4f}")

    # Thesis validation
    thesis = best.get("thesis_validation", {})
    if thesis:
        print(f"\nThesis Validation:")
        print(f"  Hierarchy respected: {thesis.get('hierarchy_respected', 'N/A')}")
        print(f"  Game mechanics %:    {thesis.get('game_mechanics_pct', 0):.1f}%")
        print(f"  Interpretation:      {thesis.get('interpretation', 'N/A')}")
        concerns = thesis.get("concerns", [])
        if concerns:
            for c in concerns:
                print(f"  Concern: {c}")

    # Calibration
    cal = best.get("calibration_validation", {})
    if cal:
        print(f"\nCalibration:")
        print(f"  Passes:          {cal.get('passes', 'N/A')}")
        print(f"  Max deviation:   {cal.get('max_deviation', 0):.4f}")
        bins_ok = cal.get("bins_within_tolerance", 0)
        bins_total = cal.get("total_bins", 0)
        print(f"  Bins within 10%: {bins_ok}/{bins_total}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 80)
    print("REAL VCT DATA EXPERIMENT")
    print(f"Data source: {VALOSCRIBE_DATA_DIR}")
    print(f"Output dir:  {OUTPUT_DIR.resolve()}")
    print(f"Started:     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # 1. Discover series/maps
    print("\n--- Step 1: Discovering series and maps ---")
    series_maps = discover_series_maps(VALOSCRIBE_DATA_DIR)
    total_maps = sum(len(maps) for maps in series_maps.values())
    print(f"Found {len(series_maps)} series with {total_maps} total maps")

    for sid, maps in series_maps.items():
        map_names = [m["map_name"] for m in maps]
        print(f"  {sid}: {len(maps)} maps ({', '.join(map_names)})")

    # 2. Load and transform all maps
    print("\n--- Step 2: Loading and transforming maps ---")
    all_maps: list[MapData] = []
    map_series: dict[str, str] = {}
    map_team1: dict[str, str] = {}
    load_failures: list[tuple[str, str, str]] = []

    for series_id, maps_list in series_maps.items():
        for map_info in maps_list:
            try:
                map_data = load_map_adapted(series_id, map_info)
                all_maps.append(map_data)
                map_series[map_data.map_id] = series_id
                map_team1[map_data.map_id] = map_data.metadata.teams[0]

                n_err = len(map_data.parse_errors)
                err_str = f" ({n_err} parse errors)" if n_err > 0 else ""
                print(f"  OK: {map_data.map_id} [{map_data.event_count} events{err_str}]")

            except Exception as e:
                load_failures.append((series_id, map_info["map_dir"].name, str(e)))
                print(f"  FAIL: {series_id}/{map_info['map_dir'].name}: {e}")

    print(f"\nLoaded: {len(all_maps)} maps, Failed: {len(load_failures)}")

    if len(all_maps) < 10:
        print("ERROR: Too few maps loaded to run meaningful experiments. Aborting.")
        return

    # 3. Extract features
    print("\n--- Step 3: Extracting features ---")
    pipeline = FeaturePipeline(feature_set="full")
    df = pipeline.extract_map_dataset(all_maps)
    print(f"Feature matrix: {df.shape[0]} maps x {df.shape[1]} columns")

    if df.empty:
        print("ERROR: Feature extraction produced empty DataFrame. Aborting.")
        return

    # Add series_id
    df["series_id"] = df["map_id"].map(map_series)

    # 4. Preprocess
    print("\n--- Step 4: Preprocessing ---")
    df = preprocess_features(df, map_team1)

    y_dist = df["y"].value_counts().to_dict()
    n_series = df["series_id"].nunique()
    print(f"Target distribution: {y_dist}")
    print(f"Unique series: {n_series}")

    # Sanity check: need both classes
    if len(y_dist) < 2:
        print("ERROR: Only one class in target. Cannot train classifier. Aborting.")
        return

    # Get feature names for both sets
    registry = FeatureRegistry()
    feature_sets = {
        "core": registry.get_feature_names("core"),
        "full": registry.get_feature_names("full"),
    }

    # 5. Run experiments
    print("\n--- Step 5: Running experiments ---")
    results = run_all_experiments(df, feature_sets)

    # 6. Print analysis
    print_analysis(results, n_maps=len(df), n_series=n_series)

    print(f"\n{'='*80}")
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Results saved to: {OUTPUT_DIR.resolve()}")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
