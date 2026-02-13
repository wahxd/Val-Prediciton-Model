# Architecture: Prediction Model Pipeline

**Domain:** VCT match outcome prediction from Valoscribe event data
**Researched:** 2026-02-13
**Confidence:** HIGH (established ML pipeline patterns applied to known data format)

## Executive Summary

The prediction model pipeline ingests Valoscribe's JSONL event logs and CSV frame states, transforms them into feature vectors at two granularities (round-level and map-level), trains gradient boosting models to predict map and match winners, and evaluates predictions via walk-forward validation that respects temporal ordering. The architecture separates data ingestion, feature engineering, model training, and evaluation into distinct modules under `src/` alongside the existing Phase 1 code.

The critical architectural decision is **two prediction scopes sharing one feature engineering layer**: round-level features aggregate into map-level features, and map-level features aggregate into match-level features. This avoids duplicated feature logic and ensures consistency between the in-game updating model (round-by-round) and the pre-match model (map/series level).

---

## Recommended Architecture

### High-Level Component Diagram

```
Valoscribe Output                    This Project (Val-Prediction-Model)
(D:\Git\valoscribe\)                 (D:\Git\Val-Prediciton-Model\)

champs2025_processed_vods/           src/
  series_XXXX/                         data/
    map_1/                               loader.py        -- Read JSONL/CSV files
      event_log.jsonl  --------+         registry.py      -- Index all available matches
      frame_states.csv --------+         schemas.py       -- Pydantic models for Valoscribe data
      metadata.json  ----------+
                               |       features/
                               +-------> round_features.py -- Round-level feature extraction
                                         map_features.py   -- Map-level aggregation
                                         match_features.py  -- Series-level aggregation
                                         registry.py       -- Feature set definitions
                                         transformers.py   -- sklearn-compatible transformers

                                       models/
                                         trainer.py        -- Train/save models
                                         predictor.py      -- Load model, make predictions
                                         configs.py        -- Model hyperparameter configs

                                       evaluation/
                                         backtester.py     -- Walk-forward validation
                                         metrics.py        -- Accuracy, calibration, log loss
                                         reports.py        -- Generate evaluation reports

                                       pipeline/
                                         orchestrator.py   -- End-to-end train/eval pipeline
                                         experiment.py     -- Experiment tracking (local JSON)
```

### Data Flow

```
1. DATA INGESTION
   loader.py reads Valoscribe output files
   registry.py indexes all available matches with metadata
                    |
                    v
2. FEATURE ENGINEERING (per match)
   round_features.py: JSONL events --> round-level feature vectors
   map_features.py:   round features --> map-level feature vector
   match_features.py: map features --> match/series prediction features
                    |
                    v
3. DATASET CONSTRUCTION
   orchestrator.py combines features across all matches
   Splits by temporal order (not random) for train/test
                    |
                    v
4. MODEL TRAINING
   trainer.py fits model on training set
   Uses sklearn Pipeline with custom transformers
                    |
                    v
5. EVALUATION
   backtester.py runs walk-forward validation
   metrics.py computes accuracy, calibration, log loss
   reports.py generates summary report
```

---

## Component Boundaries

### 1. Data Layer: `src/data/`

**Responsibility:** Read Valoscribe output files, parse into typed Python objects, index available matches.

**New files:**

| File | Purpose |
|------|---------|
| `loader.py` | Load JSONL events, CSV frame states, JSON metadata for a single map |
| `registry.py` | Scan directory tree, build index of all available matches with metadata |
| `schemas.py` | Pydantic models matching Valoscribe's output format |

**Key design: Pydantic schemas match Valoscribe output, not our own event schemas.**

The existing `src/events/schemas.py` defines our Phase 1 event types (KillEvent, RoundEndEvent, etc.) designed for live detection. Valoscribe's JSONL has a different schema with richer fields (killer name, victim name, agent attribution, weapon). The data layer should define schemas matching Valoscribe's actual output format and NOT attempt to force Valoscribe data into our Phase 1 schemas.

```python
# src/data/schemas.py -- matches Valoscribe output format

from pydantic import BaseModel
from typing import Optional, Literal

class ValoscribeEvent(BaseModel):
    """Base event from Valoscribe's event_log.jsonl."""
    event_type: str
    frame_number: int
    timestamp: float           # seconds into video
    round_number: int

class ValoscribeKillEvent(ValoscribeEvent):
    """Kill event with player-level attribution."""
    event_type: Literal["kill"] = "kill"
    killer_agent: Optional[str]
    killer_side: Optional[Literal["attack", "defense"]]
    victim_agent: Optional[str]
    victim_side: Optional[Literal["attack", "defense"]]
    is_headshot: Optional[bool]
    weapon: Optional[str]

class ValoscribeRoundEvent(ValoscribeEvent):
    """Round start/end events."""
    event_type: Literal["round_start", "round_end"]
    score_attack: Optional[int]
    score_defense: Optional[int]
    win_side: Optional[Literal["attack", "defense"]]

class MapMetadata(BaseModel):
    """Metadata for a single map from metadata.json."""
    match_id: str
    map_number: int
    map_name: str
    team_attack: str           # Team starting on attack
    team_defense: str          # Team starting on defense
    final_score_attack: int
    final_score_defense: int
    winner: str                # Team name
    # Agent compositions
    attack_agents: list[str]
    defense_agents: list[str]

class MatchEntry(BaseModel):
    """Registry entry for a match in the dataset."""
    series_id: str
    map_number: int
    map_name: str
    teams: tuple[str, str]
    winner: str
    date: str
    event_log_path: str
    frame_states_path: str
    metadata_path: str
    validation_passed: bool
    event_count: int
```

**Important:** These schemas are preliminary. The actual Valoscribe output format must be verified against real files before implementation. The schemas above are based on the Valoscribe architecture analysis in `.planning/codebase-valoscribe/`. Flag this for Phase 1 validation.

**Integration with existing code:** This module is entirely new. It does NOT modify or depend on any existing `src/state/`, `src/events/`, or `src/quality/` code. The Phase 1 code is preserved for future live stream use.

---

### 2. Feature Engineering Layer: `src/features/`

**Responsibility:** Transform raw event data into numeric feature vectors suitable for ML models.

**New files:**

| File | Purpose |
|------|---------|
| `round_features.py` | Extract features for a single round from events |
| `map_features.py` | Aggregate round features into map-level features |
| `match_features.py` | Aggregate map features into match/series features |
| `registry.py` | Central definition of all feature sets |
| `transformers.py` | sklearn-compatible transformers for pipeline integration |

**Three-tier feature hierarchy:**

```
ROUND FEATURES (per round, within a map)
  |-- first_blood_side: which side got first kill
  |-- alive_diff_at_plant: alive advantage when spike planted
  |-- spike_planted: bool
  |-- round_duration_seconds: time from start to end
  |-- kills_attack / kills_defense: kill counts
  |-- economy_attack / economy_defense: loadout values (if available)
  |-- round_type: pistol / eco / force / full_buy (inferred)
  |-- ult_advantage: count of ults ready (if available)
  |-- side: attack / defense (for the team we're predicting)
  |
  v
MAP FEATURES (per map, aggregated from rounds)
  |-- Pre-match features (known before map starts):
  |     |-- map_name (one-hot or label encoded)
  |     |-- team_elo / team_ranking (if available, external data)
  |     |-- agent_comp_attack / agent_comp_defense (encoded)
  |     |-- historical_h2h_winrate (if enough data)
  |
  |-- Cumulative in-game features (updated as rounds progress):
  |     |-- current_score_diff
  |     |-- rounds_won_attack_side / defense_side
  |     |-- pistol_round_winner (round 1, round 13)
  |     |-- economy_differential_avg
  |     |-- first_blood_rate (% of rounds with first blood)
  |     |-- current_win_streak
  |     |-- half_score (score at side swap, round 12)
  |     |-- attack_round_winrate / defense_round_winrate
  |
  |-- Label:
  |     |-- map_winner: 0 or 1 (did team_attack win?)
  |
  v
MATCH FEATURES (per series, aggregated from maps)
  |-- maps_won_team_a / maps_won_team_b
  |-- series_format: BO1 / BO3 / BO5
  |-- map_scores: list of map results so far
  |-- momentum: did same team win last N maps?
  |
  |-- Label:
  |     |-- match_winner: 0 or 1
```

**Key design: Feature extraction is pure functions, not stateful classes.**

```python
# src/features/round_features.py

import pandas as pd
from src.data.schemas import ValoscribeEvent

def extract_round_features(
    events: list[ValoscribeEvent],
    round_number: int,
    attacking_team: str,
) -> dict:
    """Extract feature dict for a single round.

    Pure function: events in, features out. No side effects.
    Returns dict suitable for pd.DataFrame row construction.
    """
    round_events = [e for e in events if e.round_number == round_number]
    kills = [e for e in round_events if e.event_type == "kill"]

    first_blood_side = None
    if kills:
        first_blood_side = kills[0].killer_side

    spike_events = [e for e in round_events if e.event_type == "spike_plant"]
    spike_planted = len(spike_events) > 0

    return {
        "round_number": round_number,
        "first_blood_attack": 1 if first_blood_side == "attack" else 0,
        "spike_planted": int(spike_planted),
        "kills_attack": sum(1 for k in kills if k.killer_side == "attack"),
        "kills_defense": sum(1 for k in kills if k.killer_side == "defense"),
        # ... more features
    }
```

**sklearn-compatible transformers for pipeline integration:**

```python
# src/features/transformers.py

from sklearn.base import BaseEstimator, TransformerMixin
import pandas as pd
import numpy as np

class MapFeatureTransformer(BaseEstimator, TransformerMixin):
    """Transforms raw round DataFrames into map-level feature vectors.

    Compatible with sklearn Pipeline for cross-validation and
    hyperparameter tuning without data leakage.
    """

    def fit(self, X, y=None):
        # No fitting needed -- feature extraction is deterministic
        return self

    def transform(self, X: list[pd.DataFrame]) -> np.ndarray:
        """Transform list of round DataFrames into feature matrix.

        Each element in X is a DataFrame of round features for one map.
        Returns numpy array where each row is a map's feature vector.
        """
        features = []
        for round_df in X:
            features.append(self._aggregate_rounds(round_df))
        return np.array(features)

    def _aggregate_rounds(self, round_df: pd.DataFrame) -> list:
        """Aggregate round-level features to map-level."""
        return [
            round_df["first_blood_attack"].mean(),
            round_df["spike_planted"].mean(),
            round_df["kills_attack"].sum(),
            round_df["kills_defense"].sum(),
            # ... more aggregations
        ]
```

**Integration with existing code:** Entirely new module. Does not touch Phase 1 code. Uses pandas/numpy which are already in requirements.txt.

---

### 3. Model Layer: `src/models/`

**Responsibility:** Define, train, save, and load prediction models.

**New files:**

| File | Purpose |
|------|---------|
| `trainer.py` | Train model from features, save to disk |
| `predictor.py` | Load trained model, generate predictions |
| `configs.py` | Model hyperparameter configurations |

**Key design: Support multiple model types via configuration, not code changes.**

```python
# src/models/configs.py

from dataclasses import dataclass, field

@dataclass
class ModelConfig:
    """Configuration for a prediction model experiment."""
    name: str
    model_type: str                # "logistic_regression", "gradient_boosting", "xgboost"
    target: str                    # "map_winner" or "match_winner"
    feature_set: str               # name from feature registry
    hyperparams: dict = field(default_factory=dict)

# Pre-defined configs for quick experimentation
BASELINE_MAP = ModelConfig(
    name="baseline_map_lr",
    model_type="logistic_regression",
    target="map_winner",
    feature_set="map_v1",
    hyperparams={"C": 1.0, "max_iter": 1000},
)

GRADIENT_BOOST_MAP = ModelConfig(
    name="gb_map_v1",
    model_type="gradient_boosting",
    target="map_winner",
    feature_set="map_v1",
    hyperparams={
        "n_estimators": 200,
        "max_depth": 4,
        "learning_rate": 0.1,
        "subsample": 0.8,
    },
)
```

```python
# src/models/trainer.py

import joblib
from pathlib import Path
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
from src.models.configs import ModelConfig

MODEL_REGISTRY = {
    "logistic_regression": LogisticRegression,
    "gradient_boosting": GradientBoostingClassifier,
    # "xgboost": xgb.XGBClassifier,  -- add when xgboost installed
}

def train_model(
    config: ModelConfig,
    X_train,
    y_train,
    output_dir: Path,
) -> Pipeline:
    """Train a model from config, save to disk.

    Returns fitted sklearn Pipeline.
    """
    model_cls = MODEL_REGISTRY[config.model_type]
    model = model_cls(**config.hyperparams)

    pipeline = Pipeline([
        # Feature transformers would go here if using sklearn pipeline
        ("classifier", model),
    ])

    pipeline.fit(X_train, y_train)

    # Save model
    model_path = output_dir / f"{config.name}.joblib"
    joblib.dump(pipeline, model_path)

    return pipeline
```

**Model persistence:** Use `joblib` for sklearn model serialization. Models saved to `models/` directory at project root (not under `src/`). Each model file includes the config that produced it for reproducibility.

**Why start with Logistic Regression + Gradient Boosting:**
- Logistic Regression is the interpretable baseline -- outputs calibrated probabilities, easy to debug, reveals which features matter.
- Gradient Boosting (sklearn's HistGradientBoostingClassifier or XGBoost) handles non-linear feature interactions and typically achieves 5-10% better accuracy than LR on tabular data.
- Research on Valorant prediction shows XGBoost achieving 73% accuracy with F1 of 0.73, and logistic regression achieving ~60% on round prediction.
- Start simple, validate the pipeline works end-to-end, then upgrade models.

**Integration with existing code:** Replaces the inline LogisticRegression in `dashboard.py`. The existing dashboard model was trained on synthetic data and will be replaced by a model trained on real Valoscribe data.

---

### 4. Evaluation Layer: `src/evaluation/`

**Responsibility:** Measure model quality with metrics appropriate for prediction markets.

**New files:**

| File | Purpose |
|------|---------|
| `backtester.py` | Walk-forward temporal validation |
| `metrics.py` | Accuracy, log loss, calibration, Brier score |
| `reports.py` | Generate evaluation summary |

**Key design: Walk-forward validation, NOT random train/test split.**

VCT matches are time-ordered. A model trained on January matches should be evaluated on February matches, not randomly shuffled matches. This mimics real-world deployment where you train on past data and predict future matches.

```python
# src/evaluation/backtester.py

from dataclasses import dataclass
from typing import Iterator
import pandas as pd

@dataclass
class BacktestFold:
    """One train/test split in walk-forward validation."""
    fold_number: int
    train_indices: list[int]
    test_indices: list[int]
    train_date_range: tuple[str, str]
    test_date_range: tuple[str, str]

def walk_forward_splits(
    dates: pd.Series,
    min_train_size: int = 30,
    test_size: int = 10,
    step_size: int = 5,
) -> Iterator[BacktestFold]:
    """Generate walk-forward validation splits.

    Expands training window forward through time.
    Each fold trains on all data before the test window.

    Args:
        dates: Series of match dates, sorted ascending.
        min_train_size: Minimum training set size (maps).
        test_size: Number of maps in each test fold.
        step_size: How many maps to advance between folds.

    Yields:
        BacktestFold with train/test indices.
    """
    n = len(dates)
    fold = 0
    start = min_train_size

    while start + test_size <= n:
        train_idx = list(range(0, start))
        test_idx = list(range(start, min(start + test_size, n)))

        yield BacktestFold(
            fold_number=fold,
            train_indices=train_idx,
            test_indices=test_idx,
            train_date_range=(str(dates.iloc[0]), str(dates.iloc[start - 1])),
            test_date_range=(str(dates.iloc[start]), str(dates.iloc[min(start + test_size - 1, n - 1)])),
        )

        fold += 1
        start += step_size
```

**Metrics specific to prediction markets:**

| Metric | Why It Matters | Target |
|--------|----------------|--------|
| **Accuracy** | Basic correctness | >55% (better than coin flip) |
| **Log Loss** | Penalizes confident wrong predictions | <0.68 (better than uninformed prior) |
| **Brier Score** | Calibration of probabilities | <0.25 |
| **Calibration Curve** | "When model says 70%, does team win 70% of the time?" | Diagonal line |
| **ROI at Threshold** | If we only bet when model disagrees with market by X%, what's our return? | Positive at some threshold |

```python
# src/evaluation/metrics.py

from sklearn.metrics import (
    accuracy_score,
    log_loss,
    brier_score_loss,
    calibration_curve,
)
import numpy as np

def evaluate_predictions(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    threshold: float = 0.5,
) -> dict:
    """Compute all evaluation metrics.

    Args:
        y_true: Binary labels (0/1).
        y_prob: Predicted probabilities for class 1.
        threshold: Classification threshold.

    Returns:
        Dict of metric name -> value.
    """
    y_pred = (y_prob >= threshold).astype(int)

    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "log_loss": log_loss(y_true, y_prob),
        "brier_score": brier_score_loss(y_true, y_prob),
        "n_samples": len(y_true),
        "positive_rate": y_true.mean(),
        "predicted_positive_rate": y_pred.mean(),
        "mean_predicted_prob": y_prob.mean(),
    }
```

**Integration with existing code:** Entirely new. No modifications to existing modules.

---

### 5. Pipeline Orchestrator: `src/pipeline/`

**Responsibility:** Wire all components together for end-to-end training and evaluation.

**New files:**

| File | Purpose |
|------|---------|
| `orchestrator.py` | End-to-end train + evaluate pipeline |
| `experiment.py` | Track experiments (configs, results) locally |

```python
# src/pipeline/orchestrator.py

from pathlib import Path
from src.data.registry import MatchRegistry
from src.data.loader import load_match_data
from src.features.map_features import extract_map_features
from src.models.trainer import train_model
from src.models.configs import ModelConfig
from src.evaluation.backtester import walk_forward_splits
from src.evaluation.metrics import evaluate_predictions

def run_experiment(
    config: ModelConfig,
    data_dir: Path,
    output_dir: Path,
) -> dict:
    """Run full experiment: load data, extract features, train, evaluate.

    This is the main entry point for model development.
    """
    # 1. Load all available matches
    registry = MatchRegistry(data_dir)
    matches = registry.get_all_matches(validated_only=True)

    # 2. Extract features for each match
    feature_rows = []
    labels = []
    dates = []
    for match in matches:
        events = load_match_data(match)
        features = extract_map_features(events, match.metadata)
        feature_rows.append(features)
        labels.append(1 if match.metadata.winner == match.metadata.team_attack else 0)
        dates.append(match.metadata.date)

    # 3. Walk-forward evaluation
    X = np.array(feature_rows)
    y = np.array(labels)
    dates = pd.Series(dates)

    all_predictions = []
    all_labels = []

    for fold in walk_forward_splits(dates):
        X_train = X[fold.train_indices]
        y_train = y[fold.train_indices]
        X_test = X[fold.test_indices]
        y_test = y[fold.test_indices]

        model = train_model(config, X_train, y_train, output_dir)
        y_prob = model.predict_proba(X_test)[:, 1]

        all_predictions.extend(y_prob)
        all_labels.extend(y_test)

    # 4. Evaluate
    results = evaluate_predictions(
        np.array(all_labels),
        np.array(all_predictions),
    )
    results["config"] = config.name
    results["n_folds"] = len(list(walk_forward_splits(dates)))

    return results
```

---

## Directory Structure: Complete View

```
Val-Prediction-Model/
  src/
    __init__.py
    state/                    # [EXISTING - Phase 1, preserved]
      __init__.py
      models.py               # GameState frozen dataclass
      tracker.py              # StateTracker
      validator.py            # StateValidator
      ocr_config.py
    events/                   # [EXISTING - Phase 1, preserved]
      __init__.py
      emitter.py              # EventEmitter
      schemas.py              # BaseEvent, KillEvent, etc.
    quality/                  # [EXISTING - Phase 1, preserved]
      __init__.py
      metrics.py              # QualityMetrics
      replay_detector.py      # ReplayDetector

    data/                     # [NEW - v2 milestone]
      __init__.py
      loader.py               # Read Valoscribe JSONL/CSV/JSON
      registry.py             # Index available matches
      schemas.py              # Pydantic models for Valoscribe output

    features/                 # [NEW - v2 milestone]
      __init__.py
      round_features.py       # Round-level feature extraction
      map_features.py         # Map-level feature aggregation
      match_features.py       # Series-level feature aggregation
      registry.py             # Feature set definitions
      transformers.py         # sklearn-compatible transformers

    models/                   # [NEW - v2 milestone]
      __init__.py
      trainer.py              # Train and save models
      predictor.py            # Load and predict
      configs.py              # Model configurations

    evaluation/               # [NEW - v2 milestone]
      __init__.py
      backtester.py           # Walk-forward validation
      metrics.py              # Accuracy, log loss, calibration
      reports.py              # Generate evaluation reports

    pipeline/                 # [NEW - v2 milestone]
      __init__.py
      orchestrator.py         # End-to-end experiment runner
      experiment.py           # Experiment tracking (local JSON)

  data/                       # [NEW - data directory, gitignored]
    raw/                      # Symlink or copy of Valoscribe output
    processed/                # Feature matrices, train/test splits
    models/                   # Saved model files (.joblib)
    experiments/              # Experiment logs (JSON)

  tests/                      # [EXISTING - extend with new tests]
    __init__.py
    test_state_tracker.py     # [EXISTING]
    test_event_emitter.py     # [EXISTING]
    ...
    test_data_loader.py       # [NEW]
    test_round_features.py    # [NEW]
    test_map_features.py      # [NEW]
    test_backtester.py        # [NEW]
    test_orchestrator.py      # [NEW]

  notebooks/                  # [NEW - exploration, not production]
    01_explore_valoscribe_data.ipynb
    02_feature_engineering.ipynb
    03_model_experiments.ipynb

  backend.py                  # [EXISTING - preserved]
  dashboard.py                # [EXISTING - will be updated to use trained model]
  vision_engine.py            # [EXISTING - preserved]
  config.py                   # [EXISTING - preserved]
  requirements.txt            # [EXISTING - will add new dependencies]
```

---

## Handling Two Prediction Scopes

### Pre-Match Prediction (Map Winner)

**When:** Before map starts. Uses only pre-match features.
**Features:** Team names, map name, agent compositions, historical win rates, ELO ratings.
**Target:** Binary -- did team_attack win the map?
**Use case:** Compare pre-match probability against Polymarket opening price.

### In-Game Prediction (Round-by-Round Updating)

**When:** During a map, after each round completes.
**Features:** Pre-match features PLUS cumulative round features (current score, economy, first blood rate, etc.)
**Target:** Same binary -- will team_attack win this map?
**Use case:** Track how win probability shifts during a live match. Compare in-game probability against live Polymarket price.

**Architectural implication:** The in-game model is a superset of the pre-match model. Pre-match features are the baseline; round-by-round features are added incrementally.

```python
# Feature vector at different points in a map:

# Pre-match (round 0):
features = [map_name, team_elo_diff, agent_comp_similarity, ...]

# After round 5 (in-game):
features = [map_name, team_elo_diff, agent_comp_similarity, ...,
            current_score_diff, pistol_winner, economy_diff_avg,
            first_blood_rate, attack_winrate_so_far, ...]

# After round 12 (halftime):
features = [... all above ..., half_score_diff, attack_rounds_won,
            defense_rounds_won, ...]
```

**Implementation approach:** Train a single model that handles variable-length feature vectors using **imputation for missing future features**. At round 0, in-game features are NaN/0. The model learns to rely on pre-match features when in-game features are unavailable.

Alternative: Train two separate models (pre-match and in-game). Simpler to implement but requires maintaining two model pipelines. Recommendation: **Start with two separate models for simplicity**, merge later if needed.

---

## Handling Match/Series Prediction (BO3/BO5)

Match winner prediction operates at a higher level than map winner:

```
Series prediction = f(map_results_so_far, remaining_maps, team_strength)

Example BO3:
  After map 1: Team A wins Bind 13-8
  --> P(Team A wins series) = f(1-0, map_2_prediction, map_3_prediction)

  After map 2: Team B wins Haven 13-11
  --> P(Team A wins series) = f(1-1, map_3_prediction)
```

**Two approaches:**

1. **Analytical:** Given P(win each remaining map), compute series win probability using combinatorics. If P(win map) = 0.6, then P(win BO3 from 1-0) = 0.6 + 0.4 * 0.6 = 0.84.

2. **Learned:** Train a separate model with series-level features (maps won, opponent strength, map pool advantage). Requires more data (series-level, not map-level).

**Recommendation:** Start with approach 1 (analytical) since it requires no additional training data. The map-winner model provides the probability input.

---

## Build Order (Dependency-Driven)

The following build order ensures each phase produces testable, runnable output before the next begins.

### Phase 1: Data Ingestion Layer
**Build:** `src/data/` (loader, registry, schemas)
**Why first:** Everything depends on being able to read Valoscribe data. Until we can load and parse JSONL events, nothing else works.
**Validates:** Valoscribe output format assumptions are correct.
**Depends on:** Nothing in existing codebase. Only depends on Valoscribe output files.
**Tests:** Load a real Valoscribe event log, verify all fields parse correctly.

### Phase 2: Feature Engineering
**Build:** `src/features/` (round_features, map_features, registry)
**Why second:** Features are the input to models. Cannot train without features.
**Validates:** Feature extraction logic produces reasonable values.
**Depends on:** Phase 1 data layer.
**Tests:** Extract features from known match, verify feature values match manual calculation.

### Phase 3: Model Training + Baseline
**Build:** `src/models/` (trainer, predictor, configs)
**Why third:** Need a trained model to evaluate. Start with LogisticRegression baseline.
**Validates:** End-to-end pipeline works: data -> features -> model -> predictions.
**Depends on:** Phase 2 features.
**Tests:** Train on 50+ maps, verify predictions are not random (accuracy > 50%).

### Phase 4: Evaluation + Backtesting
**Build:** `src/evaluation/` (backtester, metrics, reports)
**Why fourth:** Need to measure model quality rigorously before iterating.
**Validates:** Model generalizes to unseen matches (not just memorizing training data).
**Depends on:** Phase 3 model.
**Tests:** Walk-forward validation produces stable metrics across folds.

### Phase 5: Iteration + Advanced Models
**Build:** Gradient boosting models, additional features, feature selection
**Why fifth:** Now that baseline is established, iterate to improve.
**Depends on:** Phase 4 evaluation framework.
**Validates:** Improvements over baseline are statistically significant.

### Phase 6: Match-Level + Series Prediction (optional for v2)
**Build:** `src/features/match_features.py`, analytical series model
**Why last:** Map-level prediction is the core product. Series prediction is an extension.
**Depends on:** Working map-level model from Phase 3-5.

---

## Patterns to Follow

### Pattern 1: Pure Functions for Feature Extraction
**What:** Feature extraction functions take data in, return features out. No side effects, no state.
**Why:** Testable, reproducible, parallelizable. Same input always produces same output.
**Example:**
```python
def extract_round_features(events: list[ValoscribeEvent], round_num: int) -> dict:
    """Pure function: events in, features out."""
    ...
    return {"first_blood_attack": 1, "spike_planted": 0, ...}
```

### Pattern 2: Configuration-Driven Experiments
**What:** Model type, hyperparameters, and feature set defined in config dataclass. Experiments are config changes, not code changes.
**Why:** Reproducible experiments. Can compare results across configs. No code duplication.

### Pattern 3: Temporal Validation Only
**What:** Never use random train/test splits. Always split by date.
**Why:** Real deployment predicts future matches from past data. Random splits leak future information into training, inflating accuracy. Walk-forward validation mimics real-world deployment conditions.

### Pattern 4: Feature Registry
**What:** Central registry maps feature set names to extraction functions.
**Why:** Experiments reference feature sets by name. Easy to add new feature sets without modifying training code.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Notebook-Driven Development
**What:** All feature engineering and model training lives in Jupyter notebooks.
**Why bad:** Notebooks cannot be unit tested, version controlled poorly, and create unreproducible experiments. Code drifts between notebooks.
**Instead:** Notebooks for exploration only. Production code in `src/` modules. Notebooks call `src/` functions.

### Anti-Pattern 2: Feature Leakage
**What:** Using future information as a feature (e.g., "final map score" as input to predict map winner).
**Why bad:** Inflates accuracy to unrealistic levels. Model appears excellent but fails in production.
**Instead:** For in-game prediction, features must only include information available UP TO the current round. For pre-match, only information available before the map starts.

### Anti-Pattern 3: Overengineering Model Infrastructure
**What:** Building MLflow/Weights&Biases/DVC integration before having a working baseline.
**Why bad:** Premature complexity. 71 maps is a small dataset. Local JSON experiment tracking is sufficient.
**Instead:** Start with `joblib` for model persistence and JSON files for experiment logs. Add MLflow later if dataset grows past 500+ maps.

### Anti-Pattern 4: Ignoring Calibration
**What:** Optimizing only for accuracy, ignoring probability calibration.
**Why bad:** For prediction markets, CALIBRATION matters more than accuracy. A model that says "60% win probability" must actually correspond to ~60% win rate in practice. Uncalibrated probabilities lead to incorrect edge calculations against market prices.
**Instead:** Always compute calibration curves and Brier score alongside accuracy. Consider Platt scaling or isotonic regression for probability calibration.

### Anti-Pattern 5: Coupling Feature Engineering to Model Training
**What:** Feature extraction happens inside the training loop.
**Why bad:** Recomputing features every time you retrain wastes time. Cannot inspect features independently. Feature bugs are hidden inside training.
**Instead:** Feature extraction produces a cached DataFrame. Training reads from the cached features. Separate concerns.

---

## Integration Points with Existing Codebase

| Existing Component | Integration Point | What Changes |
|--------------------|-------------------|-------------|
| `dashboard.py` | Model prediction | Replace synthetic LogisticRegression with trained model loaded from `data/models/` |
| `requirements.txt` | Dependencies | Add pandas, xgboost (optional), joblib (already in sklearn) |
| `src/state/models.py` | None | Preserved as-is for future live use |
| `src/events/schemas.py` | None | Preserved as-is. New `src/data/schemas.py` for Valoscribe format |
| `src/quality/` | None | Preserved as-is for future live use |
| `tests/` | Extend | Add new test files for data, features, models, evaluation |

**What does NOT change:**
- All Phase 1 code (`src/state/`, `src/events/`, `src/quality/`) is untouched
- `backend.py`, `vision_engine.py`, `config.py` are untouched
- Existing 65 tests continue to pass

**What gets modified:**
- `requirements.txt`: Add new ML dependencies
- `dashboard.py`: Eventually updated to load trained model instead of synthetic one (Phase 5+, not blocking)

**What is new:**
- `src/data/`, `src/features/`, `src/models/`, `src/evaluation/`, `src/pipeline/`
- `data/` directory (gitignored, for data files)
- `notebooks/` directory (for exploration)

---

## Scalability Considerations

| Concern | At 71 Maps (Current) | At 300 Maps (6 months) | At 1000+ Maps (1 year) |
|---------|----------------------|------------------------|------------------------|
| **Feature extraction** | <1 second total | <5 seconds total | Consider caching features to Parquet |
| **Model training** | <1 second (LR), <10 seconds (GB) | <5 seconds (LR), <30 seconds (GB) | Still fast. Not a bottleneck. |
| **Walk-forward validation** | 3-5 folds, <30 seconds | 10-20 folds, <5 minutes | Add parallel fold evaluation |
| **Data storage** | <10 MB total | <50 MB total | Consider SQLite index for queries |
| **Experiment tracking** | JSON files sufficient | JSON files sufficient | Consider MLflow |

**Verdict:** At 71 maps, everything runs in seconds. No infrastructure needed. Scaling concerns are deferred until dataset grows significantly.

---

## Data Access Pattern

Valoscribe output lives in a separate repo (`D:\Git\valoscribe`). The prediction model should NOT copy data into its own repo. Instead:

**Option A (Recommended): Configuration-based path**
```python
# config.py or .env
VALOSCRIBE_DATA_DIR = "D:/Git/valoscribe/champs2025_processed_vods"
```
The data registry scans this directory to find available matches. No data duplication.

**Option B: Symlink**
```bash
# Create symlink in project
mklink /D "D:\Git\Val-Prediciton-Model\data\raw" "D:\Git\valoscribe\champs2025_processed_vods"
```

**Why not copy:** Data changes as Valoscribe reprocesses VODs or adds new matches. A symlink or config path ensures the prediction model always uses the latest data without manual sync.

---

## Sources

**Architecture patterns:**
- [scikit-learn Pipeline documentation](https://scikit-learn.org/stable/modules/generated/sklearn.pipeline.Pipeline.html)
- [Structuring ML Projects with MLOps](https://towardsdatascience.com/structuring-your-machine-learning-project-with-mlops-in-mind-41a8d65987c9/)
- [ML Pipeline Architecture (OneUpTime)](https://oneuptime.com/blog/post/2026-01-30-ml-pipeline-architecture/view)

**Valorant prediction research:**
- [Round Outcome Prediction in VALORANT Using Tactical Features from Video Analysis (arXiv 2510.17199)](https://arxiv.org/html/2510.17199v1) -- 80.55% accuracy with tactical event features, TimeSformer model
- [Valorant Esports Predictive Model Analysis (TechRxiv)](https://www.techrxiv.org/users/916972/articles/1289732/master/file/data/Valorant%20Esports%20Predictive%20Model%20Analysis/Valorant%20Esports%20Predictive%20Model%20Analysis.pdf) -- Logistic regression 60.61%, loadout value odds ratio 2.2x
- [Valorant Esports Pre-Match Betting Advisory System](https://norma.ncirl.ie/8770/1/abhishekmahendrapawar.pdf) -- Random Forest achieving high accuracy on pre-match prediction

**Evaluation methodology:**
- [Walk-Forward Validation Guide](https://medium.com/@ahmedfahad04/understanding-walk-forward-validation-in-time-series-analysis-a-practical-guide-ea3814015abf)
- [Backtesting ML Models for Time Series](https://machinelearningmastery.com/backtest-machine-learning-models-time-series-forecasting/)

**Model comparison:**
- [Gradient Boosting Comparison: XGBoost vs LightGBM vs CatBoost (Analytics Vidhya)](https://www.analyticsvidhya.com/blog/2026/02/gradient-boosting-vs-adaboost-vs-xgboost-vs-catboost-vs-lightgbm/)
- [XGBoost vs LightGBM (Neptune.ai)](https://neptune.ai/blog/xgboost-vs-lightgbm)

**Existing codebase analysis:**
- `.planning/codebase/ARCHITECTURE.md` -- Current project architecture
- `.planning/codebase-valoscribe/ARCHITECTURE.md` -- Valoscribe architecture
- `.planning/codebase-valoscribe/COMPARISON.md` -- Valoscribe vs this project comparison

**Confidence levels:**
- HIGH: Pipeline architecture patterns (well-established in sklearn ecosystem)
- HIGH: Directory structure and component boundaries (standard ML project layout)
- HIGH: Walk-forward validation approach (established best practice for temporal data)
- MEDIUM: Valoscribe output schema (based on architecture analysis, not verified against actual files)
- MEDIUM: Feature importance estimates (based on Valorant prediction literature)
- LOW: Specific accuracy targets (dependent on data quality and feature engineering)

---

*Architecture research complete: 2026-02-13*
*Ready for roadmap creation.*
