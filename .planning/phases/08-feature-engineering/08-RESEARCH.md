# Phase 8: Feature Engineering - Research

**Researched:** 2026-02-14
**Domain:** Feature engineering for time-series event data with pandas and scikit-learn
**Confidence:** HIGH

## Summary

Feature engineering for time-series event data requires specialized tools and patterns to avoid common pitfalls (particularly data leakage) while building reproducible, maintainable pipelines. The standard Python stack combines pandas for aggregation/windowing operations, scikit-learn for pipeline architecture, and YAML for configuration management.

For this phase's requirements—transforming Valoscribe JSONL events into predictive features at round/map/match levels with economy reconstruction and a feature registry—the established approach is:

1. **Custom scikit-learn transformers** for domain-specific feature extraction (economy tracking, combat metrics, side performance)
2. **Pandas groupby/rolling operations** for temporal aggregations (streaks, rates, differentials)
3. **YAML-based feature registry** with Pydantic validation for experiment reproducibility
4. **Walk-forward temporal validation** via scikit-learn's TimeSeriesSplit to prevent data leakage

**Primary recommendation:** Build custom transformers inheriting from `BaseEstimator` and `TransformerMixin`, organize features into composable YAML sets, and use pandas' built-in aggregation methods (not `.apply()`) for performance.

## Standard Stack

The established libraries/tools for time-series feature engineering:

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pandas | 2.x+ | Time-series aggregation, groupby operations, rolling windows | De facto standard for temporal data manipulation in Python; optimized C-based operations for performance ([pandas documentation](https://pandas.pydata.org/docs/)) |
| scikit-learn | 1.7+ | Pipeline architecture, custom transformers, TimeSeriesSplit | Industry standard for ML pipelines; prevents data leakage via fit/transform separation ([scikit-learn docs](https://scikit-learn.org/stable/)) |
| PyYAML | 6.x | Configuration file parsing | Lightweight, well-maintained YAML parser for Python ([PyYAML GitHub](https://github.com/yaml/pyyaml)) |
| Pydantic | 2.x | Configuration validation | Type-safe parsing with automatic validation; already in project stack ([Pydantic docs](https://pydantic.dev/)) |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic-yaml | 1.x+ | YAML ↔ Pydantic model serialization | When you want type-safe YAML parsing with validation (combines PyYAML + Pydantic) ([pydantic-yaml docs](https://pydantic-yaml.readthedocs.io/)) |
| tsfresh | 0.20+ | Automated time-series feature extraction | For exploration: generates 794 statistical features automatically, useful for discovering non-obvious patterns ([tsfresh GitHub](https://github.com/blue-yonder/tsfresh)) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pandas groupby | NumPy vectorized ops | NumPy is faster for pure computation but pandas provides labeled data structures critical for feature naming/debugging |
| Custom transformers | Feature-engine library | Feature-engine provides pre-built transformers but custom transformers give full control for domain-specific logic (economy tracking, game mechanics) |
| YAML config | Hydra/OmegaConf | Hydra adds hierarchical config composition but introduces complexity; YAML + Pydantic is simpler for this project's scope |
| Manual registry | Feast feature store | Feast is production-grade feature serving but overkill for offline batch model training; adds infrastructure complexity |

**Installation:**
```bash
# Core dependencies (likely already in project)
uv add pandas scikit-learn pyyaml pydantic

# Optional: for exploration/validation
uv add pydantic-yaml  # Type-safe YAML parsing
uv add tsfresh        # Automated feature discovery (exploration only)
```

## Architecture Patterns

### Recommended Project Structure

```
src/
├── features/              # Feature engineering module
│   ├── __init__.py
│   ├── registry.py        # Feature registry loader (YAML → Python)
│   ├── transformers/      # Custom sklearn transformers
│   │   ├── __init__.py
│   │   ├── base.py        # Base classes, shared utilities
│   │   ├── economy.py     # Economy reconstruction transformer
│   │   ├── combat.py      # Combat metrics (first blood, K/D, clutch rate)
│   │   ├── momentum.py    # Streaks, win/loss sequences
│   │   └── aggregators.py # Round → map → match aggregation
│   ├── extractors/        # Per-level feature extraction functions
│   │   ├── round_features.py
│   │   ├── map_features.py
│   │   └── match_features.py
│   └── config/            # Feature set definitions
│       ├── feature_sets.yaml  # Feature registry (YAML)
│       └── schemas.py         # Pydantic models for config validation
└── data/                  # Existing data module
    └── loader.py          # Already loads Valoscribe events
```

### Pattern 1: Custom Transformer for Domain Logic

**What:** Encapsulate domain-specific feature engineering (e.g., economy tracking) in scikit-learn transformers

**When to use:** For stateful transformations that need to be part of a reproducible pipeline

**Example:**
```python
# Source: scikit-learn docs + best practices from research
from sklearn.base import BaseEstimator, TransformerMixin
import pandas as pd

class EconomyReconstructorTransformer(BaseEstimator, TransformerMixin):
    """Reconstructs team economy per round from round outcomes.

    Uses Valorant's deterministic economy rules:
    - Pistol round: 800 credits
    - Win bonus: 3000 credits
    - Loss bonus: 1900 → 2400 → 2900 (max)
    - Spike plant: +300 credits
    """

    def __init__(self, starting_credits=800):
        self.starting_credits = starting_credits

    def fit(self, X, y=None):
        # Stateless transformer - no fitting needed
        return self

    def transform(self, X):
        """
        Args:
            X: DataFrame with round_end events (winning_team, spike_planted, round number)

        Returns:
            DataFrame with added columns: team1_credits, team2_credits, team1_eco_tier, team2_eco_tier
        """
        X = X.copy()

        # Initialize economy tracking
        credits = {team: self.starting_credits for team in X['teams'].iloc[0]}
        loss_streak = {team: 0 for team in credits}

        eco_tiers = []
        credit_values = []

        for idx, row in X.iterrows():
            # Update credits based on previous round outcome
            winner = row['winning_team']
            loser = [t for t in credits if t != winner][0]

            # Win bonus
            credits[winner] += 3000
            loss_streak[winner] = 0

            # Loss bonus (escalating)
            loss_streak[loser] += 1
            loss_bonus = min(1900 + (loss_streak[loser] - 1) * 500, 2900)
            credits[loser] += loss_bonus

            # Spike plant bonus
            if row.get('spike_planted', False):
                attacking_team = row['attacking_team']
                credits[attacking_team] += 300

            # Classify economy tier
            eco_tiers.append({
                'team1_eco_tier': self._classify_tier(credits[row['teams'][0]]),
                'team2_eco_tier': self._classify_tier(credits[row['teams'][1]]),
            })
            credit_values.append({
                'team1_credits': credits[row['teams'][0]],
                'team2_credits': credits[row['teams'][1]],
            })

        # Add to DataFrame
        X = pd.concat([X, pd.DataFrame(eco_tiers), pd.DataFrame(credit_values)], axis=1)
        return X

    def _classify_tier(self, credits):
        """Classify economy tier from credit estimate."""
        if credits < 2500:
            return 'eco'
        elif credits < 3500:
            return 'light_buy'
        else:
            return 'full_buy'
```

### Pattern 2: Pandas Groupby for Temporal Aggregation

**What:** Use pandas' built-in aggregation methods for performance-critical operations

**When to use:** Computing streaks, rates, differentials across rounds/maps

**Example:**
```python
# Source: pandas documentation on groupby operations
import pandas as pd

def compute_combat_features(events_df):
    """Aggregate kill events into map-level combat features.

    Args:
        events_df: DataFrame of kill events with killer, victim, killer_team, timestamp

    Returns:
        DataFrame with combat features per team per map
    """
    # First blood detection (first kill of each round)
    first_bloods = (
        events_df[events_df['type'] == 'kill']
        .groupby(['map_id', 'round'])
        .first()
        .groupby(['map_id', 'killer_team'])
        .size()
    )

    # Multi-kill detection (2+ kills within 5 seconds)
    events_df['time_since_last'] = events_df.groupby(['map_id', 'round', 'killer'])['timestamp'].diff()
    multi_kills = (
        events_df[events_df['time_since_last'] < 5.0]
        .groupby(['map_id', 'killer_team'])
        .size()
    )

    # Aggregate to map level
    combat_features = pd.DataFrame({
        'first_blood_rate': first_bloods / events_df.groupby('map_id')['round'].nunique(),
        'multi_kill_rate': multi_kills / events_df.groupby('map_id')['round'].nunique(),
    })

    return combat_features
```

### Pattern 3: YAML Feature Registry with Pydantic Validation

**What:** Define feature sets in YAML, validate with Pydantic for type safety

**When to use:** Managing multiple feature set configurations for experiments

**Example:**
```python
# Source: pydantic-yaml documentation + ML best practices
from pydantic import BaseModel, Field
from pydantic_yaml import parse_yaml_file_as
from typing import List, Optional

class FeatureSetConfig(BaseModel):
    """Configuration for a named feature set."""

    name: str = Field(..., description="Unique identifier for feature set")
    description: str = Field(..., description="Human-readable description")
    extends: Optional[str] = Field(None, description="Parent feature set to extend")
    features: List[str] = Field(..., description="List of feature names to include")

    class Config:
        extra = 'forbid'  # Strict validation - no unknown fields

# YAML file: config/feature_sets.yaml
"""
feature_sets:
  - name: baseline
    description: Minimal feature set for initial model
    features:
      - score_differential
      - pistol_round_wins
      - first_half_score
      - attack_win_rate
      - defense_win_rate

  - name: economy_extended
    description: Baseline + economy features
    extends: baseline
    features:
      - eco_round_win_rate
      - economy_differential
      - force_buy_success_rate
      - save_round_frequency
"""

# Loading and validation
class FeatureRegistry:
    def __init__(self, config_path: str):
        self.config = parse_yaml_file_as(List[FeatureSetConfig], config_path)
        self._resolve_inheritance()

    def _resolve_inheritance(self):
        """Expand 'extends' to include parent features."""
        feature_sets = {fs.name: fs for fs in self.config}

        for fs in self.config:
            if fs.extends:
                parent = feature_sets[fs.extends]
                fs.features = parent.features + fs.features

    def get_features(self, set_name: str) -> List[str]:
        """Get feature list for a named set."""
        for fs in self.config:
            if fs.name == set_name:
                return fs.features
        raise ValueError(f"Feature set '{set_name}' not found")
```

### Pattern 4: Walk-Forward Temporal Validation

**What:** Use scikit-learn's TimeSeriesSplit for temporal cross-validation

**When to use:** Always - prevents data leakage for time-ordered data

**Example:**
```python
# Source: scikit-learn documentation on TimeSeriesSplit
from sklearn.model_selection import TimeSeriesSplit
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
import numpy as np

# Assume X is map-level features sorted by date, y is map winner
X_sorted = X.sort_values('date')
y_sorted = y[X_sorted.index]

# TimeSeriesSplit creates expanding training windows
tscv = TimeSeriesSplit(n_splits=5)

scores = []
for train_idx, test_idx in tscv.split(X_sorted):
    X_train, X_test = X_sorted.iloc[train_idx], X_sorted.iloc[test_idx]
    y_train, y_test = y_sorted.iloc[train_idx], y_sorted.iloc[test_idx]

    # Fit on training fold (never future data)
    pipeline.fit(X_train, y_train)
    score = pipeline.score(X_test, y_test)
    scores.append(score)

print(f"Mean CV score: {np.mean(scores):.3f} (+/- {np.std(scores):.3f})")
```

### Anti-Patterns to Avoid

- **Using `.apply()` for aggregations:** Slow Python loops instead of vectorized operations. Use built-in methods (`.sum()`, `.mean()`, `.count()`) instead ([source](https://medium.com/@2nick2patel2/pandas-groupby-at-speed-pitfalls-and-power-moves-8b27ca7ccc5a))
- **Fitting transformers on full dataset:** Causes data leakage. Always fit only on training folds inside cross-validation ([source](https://scikit-learn.org/stable/common_pitfalls.html))
- **String-based group keys:** Use categorical dtype for repeated labels (team names, map names) to reduce memory and improve performance ([source](https://pandas.pydata.org/docs/user_guide/groupby.html))
- **Over-engineering features:** Start with broad categories, let model regularization select important features rather than manual feature selection upfront ([source](https://www.kdnuggets.com/5-critical-feature-engineering-mistakes-that-kill-machine-learning-projects))

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Time-series cross-validation | Custom train/test splitter with date filtering | `sklearn.model_selection.TimeSeriesSplit` | Handles expanding windows, fold indices, and prevents future data leakage automatically ([docs](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)) |
| YAML parsing with validation | `yaml.load()` + manual dict validation | `pydantic-yaml` with Pydantic models | Type-safe parsing, automatic validation, clear error messages for config issues ([docs](https://pydantic-yaml.readthedocs.io/)) |
| Feature pipeline composition | Chaining transform functions manually | `sklearn.pipeline.Pipeline` with custom transformers | Prevents data leakage (fit/transform separation), enables grid search, guarantees reproducibility ([docs](https://scikit-learn.org/stable/modules/compose.html)) |
| Categorical encoding for teams/maps | Manual label encoding or one-hot | pandas categorical dtype + sklearn's `OrdinalEncoder` | Memory-efficient, preserves unknown categories, faster groupby operations ([docs](https://pandas.pydata.org/docs/user_guide/categorical.html)) |

**Key insight:** Time-series feature engineering has subtle data leakage risks (fitting scalers on test data, using future information in features). sklearn's pipeline architecture forces proper train/test separation by design - use it religiously.

## Common Pitfalls

### Pitfall 1: Data Leakage from Global Statistics

**What goes wrong:** Computing aggregations (mean, std, min, max) across the entire dataset before train/test split, then using these as features. Model learns from test set statistics during training.

**Why it happens:** Natural instinct to normalize/standardize features, but computing statistics on full dataset leaks information about test distribution to training.

**How to avoid:**
- Always split data first (by date for temporal data)
- Fit transformers (scalers, encoders, aggregators) only on training fold
- Use sklearn Pipeline to enforce fit/transform separation automatically

**Warning signs:**
- Perfect or near-perfect validation accuracy that crashes in production
- Feature statistics computed before cross-validation loop
- Transforms applied directly to full DataFrame before splitting

**Source:** [MachineLearningMastery: Data Leakage](https://machinelearningmastery.com/data-preparation-without-data-leakage/), [scikit-learn common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html)

### Pitfall 2: Using `.apply()` for Performance-Critical Aggregations

**What goes wrong:** Using pandas `.apply()` with lambda functions for aggregations runs slow Python loops instead of optimized C code. Can be 10-100x slower than built-in methods.

**Why it happens:** `.apply()` is flexible and intuitive, but operates on Python objects rather than NumPy arrays.

**How to avoid:**
- Use built-in aggregation methods: `.sum()`, `.mean()`, `.count()`, `.std()`, `.min()`, `.max()`
- For custom aggregations, use `.agg()` with named functions
- Only use `.apply()` when no built-in method exists

**Warning signs:**
- Aggregation code taking minutes on 100-1000 rows
- Lambda functions inside `.groupby().apply()`
- Profiling shows most time spent in `.apply()` calls

**Example of fix:**
```python
# SLOW (Python loop)
df.groupby('team').apply(lambda x: x['kills'].sum())

# FAST (vectorized C code)
df.groupby('team')['kills'].sum()
```

**Source:** [Pandas GroupBy Performance](https://medium.com/@2nick2patel2/pandas-groupby-at-speed-pitfalls-and-power-moves-8b27ca7ccc5a), [pandas documentation](https://pandas.pydata.org/docs/user_guide/groupby.html)

### Pitfall 3: Breaking Temporal Order in Validation

**What goes wrong:** Using random train/test split or k-fold cross-validation on time-series data. Model trains on future data and validates on past data, giving falsely optimistic results.

**Why it happens:** Default sklearn cross-validation methods (KFold, train_test_split) don't respect temporal ordering.

**How to avoid:**
- Always use `TimeSeriesSplit` for time-ordered data
- Sort data by date before splitting
- Verify test dates are always after training dates
- Document temporal ordering in code comments

**Warning signs:**
- Using `train_test_split(shuffle=True)` on event data
- KFold cross-validation on maps sorted by date
- Test set contains matches from before training set

**Source:** [Time Series Cross-Validation Best Practices](https://medium.com/@pacosun/respect-the-order-cross-validation-in-time-series-7d12beab79a1), [Understanding Walk-Forward Validation](https://medium.com/@ahmedfahad04/understanding-walk-forward-validation-in-time-series-analysis-a-practical-guide-ea3814015abf)

### Pitfall 4: Overfitting with Correlated Features

**What goes wrong:** Creating many highly correlated features (e.g., `team1_kills`, `team2_kills`, `kill_differential`, `kill_ratio`) without regularization. Model becomes unstable and overfits.

**Why it happens:** Intuition suggests "more features = better model" but correlated features increase dimensionality without adding information.

**How to avoid:**
- Start broad but use L1/L2 regularization (Logistic Regression with `penalty='l1'`)
- Monitor feature importance/coefficients for redundancy
- Document feature correlations in exploration phase
- Let model regularization handle feature selection

**Warning signs:**
- Large positive and negative coefficients for related features
- Model performance degrades when adding "obviously useful" features
- High variance between cross-validation folds

**Source:** [5 Critical Feature Engineering Mistakes](https://www.kdnuggets.com/5-critical-feature-engineering-mistakes-that-kill-machine-learning-projects), [Feature Engineering Pitfalls](https://www.statsig.com/perspectives/feature-engineering-pitfalls)

### Pitfall 5: Approximating Game State Without Validation

**What goes wrong:** Reconstructing game economy using approximate rules without validating against ground truth. Errors compound over rounds, making features unreliable.

**Why it happens:** Perfect economy tracking requires kill rewards per weapon, ability purchases, etc. - data not always available. Tempting to use simplified approximations.

**How to avoid:**
- Start with simplest approximation (standard loadout, average kill reward)
- Validate against buy_phase events where OCR succeeded
- Document assumptions explicitly in code
- Include "confidence" metadata (% of rounds with OCR validation)
- Flag maps with low OCR coverage for review

**Warning signs:**
- Economy estimates diverging wildly from OCR detections
- Features show no predictive power despite strong domain theory
- Missing handling of edge cases (overtime economy, force buys)

**Source:** Domain knowledge (Valorant economy mechanics), [Valorant Economy Guide](https://mobalytics.gg/blog/valorant/ultimate-economy-guide/)

## Code Examples

Verified patterns from official sources:

### Pandas Groupby with Rolling Windows (Time-Based)

```python
# Source: pandas documentation - time-series groupby operations
import pandas as pd

# Events with DatetimeIndex
events = pd.DataFrame({
    'timestamp': pd.date_range('2025-01-01', periods=100, freq='5s'),
    'team': ['A', 'B'] * 50,
    'kills': range(100)
})
events.set_index('timestamp', inplace=True)

# Rolling window by team (last 30 seconds of kills)
rolling_kills = (
    events.groupby('team')
    .rolling(window='30s')['kills']
    .sum()
)

# Expanding window (cumulative from start of map)
cumulative_kills = (
    events.groupby('team')
    .expanding()['kills']
    .sum()
)
```

### Custom Transformer with DataFrame Output

```python
# Source: scikit-learn 1.2+ set_output API
from sklearn.base import BaseEstimator, TransformerMixin
import pandas as pd

class TeamSideFeatureExtractor(BaseEstimator, TransformerMixin):
    """Extract attack/defense performance per team from round events."""

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        """
        Args:
            X: DataFrame with round_end events (winning_team, sides)

        Returns:
            DataFrame with attack_win_rate, defense_win_rate per team
        """
        features = []

        for map_id in X['map_id'].unique():
            map_rounds = X[X['map_id'] == map_id]

            for team in map_rounds['teams'].iloc[0]:
                # Filter rounds where team was attacking
                attack_rounds = map_rounds[map_rounds['sides'].apply(lambda s: s.get(team) == 'attack')]
                attack_wins = (attack_rounds['winning_team'] == team).sum()
                attack_rate = attack_wins / len(attack_rounds) if len(attack_rounds) > 0 else 0.5

                # Filter rounds where team was defending
                defense_rounds = map_rounds[map_rounds['sides'].apply(lambda s: s.get(team) == 'defense')]
                defense_wins = (defense_rounds['winning_team'] == team).sum()
                defense_rate = defense_wins / len(defense_rounds) if len(defense_rounds) > 0 else 0.5

                features.append({
                    'map_id': map_id,
                    'team': team,
                    'attack_win_rate': attack_rate,
                    'defense_win_rate': defense_rate,
                })

        return pd.DataFrame(features)

    def get_feature_names_out(self, input_features=None):
        """Enable pipeline feature name tracking."""
        return ['attack_win_rate', 'defense_win_rate']

# Use set_output to preserve DataFrame through pipeline
transformer = TeamSideFeatureExtractor()
transformer.set_output(transform="pandas")
```

### Safe YAML Loading with Error Handling

```python
# Source: PyYAML documentation
import yaml
from yaml import YAMLError
from pathlib import Path

def load_feature_registry(config_path: Path) -> dict:
    """Load feature registry YAML with error handling."""

    try:
        with config_path.open('r') as f:
            config = yaml.safe_load(f)  # Never use yaml.load() - security risk
        return config

    except yaml.scanner.ScannerError as e:
        print(f"YAML syntax error: {e.problem}")
        print(f"Line {e.problem_mark.line + 1}, column {e.problem_mark.column + 1}")
        raise

    except yaml.parser.ParserError as e:
        print(f"YAML structure error: {e.problem}")
        raise

    except YAMLError as e:
        print(f"YAML error: {e}")
        raise

    except FileNotFoundError:
        print(f"Config file not found: {config_path}")
        raise
```

### TimeSeriesSplit with Expanding Windows

```python
# Source: scikit-learn documentation
from sklearn.model_selection import TimeSeriesSplit
import numpy as np

# Maps sorted by date (critical - must be pre-sorted)
n_maps = 71
tscv = TimeSeriesSplit(n_splits=5)

for fold, (train_idx, test_idx) in enumerate(tscv.split(X), start=1):
    print(f"Fold {fold}:")
    print(f"  Train: maps {train_idx[0]}-{train_idx[-1]} ({len(train_idx)} maps)")
    print(f"  Test:  maps {test_idx[0]}-{test_idx[-1]} ({len(test_idx)} maps)")

    # Each fold: train on ALL data up to test_idx[0]
    # Test on next chunk
    # Training window expands each fold (walk-forward)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual feature aggregation in loops | pandas built-in aggregations (`.sum()`, `.mean()`, `.agg()`) | pandas 0.20+ (2017) | 10-100x performance improvement for groupby operations |
| Manual train/test temporal splits | `TimeSeriesSplit` for walk-forward validation | scikit-learn 0.18+ (2016) | Standardized temporal CV, prevents accidental future data leakage |
| Chaining transform functions | sklearn Pipeline with `fit`/`transform` separation | scikit-learn 0.16+ (2015) | Automatic prevention of data leakage, enables grid search over full pipeline |
| `yaml.load()` for parsing | `yaml.safe_load()` for untrusted input | PyYAML 5.1+ (2019) | Prevents arbitrary code execution via malicious YAML |
| Transformers return NumPy arrays | `set_output(transform="pandas")` preserves DataFrames | scikit-learn 1.2+ (2022) | Better debugging, feature name tracking through pipelines |

**Deprecated/outdated:**
- **tsfresh for production features**: Generates 794 features automatically but most are irrelevant for sports prediction. Use for exploration only, not production ([tsfresh docs](https://tsfresh.readthedocs.io/))
- **Hydra/OmegaConf for simple configs**: Adds complexity (hierarchical composition, interpolation) unnecessary for flat feature set definitions. YAML + Pydantic is sufficient
- **Feast feature store for offline training**: Designed for online serving with feature staleness requirements. Overkill for batch model training ([Feast docs](https://feast.dev/))

## Open Questions

Things that couldn't be fully resolved:

1. **Economy reconstruction accuracy without full OCR data**
   - What we know: buy_phase events have ~75% coverage (3/5 players detected threshold), Valorant economy is deterministic
   - What's unclear: Best strategy for missing data - interpolate from OCR successes, or use pure rule-based approximation?
   - Recommendation: Start with pure rule-based (simpler, more predictable), validate against buy_phase events where available, flag low-coverage maps for review

2. **Handling the 3500-3900 credit gap in economy tiers**
   - What we know: User defined eco (0-2500), light buy (2500-3500), full buy (3900+) based on Valorant knowledge
   - What's unclear: How to classify 3500-3900 range (typically "half-buy" in competitive meta)
   - Recommendation: Add fourth tier "half_buy" (3500-3900) OR merge with light_buy. Test both in exploration, choose based on feature importance

3. **Optimal feature granularity for series momentum**
   - What we know: Match-level features should include series momentum (score differentials, overtime flags, win/loss sequence)
   - What's unclear: How much map-level detail to preserve vs. aggregate (per-map features vs. summary statistics)
   - Recommendation: Start with summary statistics (mean map score differential, % maps to OT, comeback indicator), add per-map vectors only if summary insufficient

4. **Feature registry metadata level**
   - What we know: Registry should track feature names and composition (which sets extend which)
   - What's unclear: How much metadata to include (description, date created, data coverage requirements, validation rules)
   - Recommendation: Minimal for MVP (name, description, features list, optional extends), add metadata fields as needed during iteration

## Sources

### Primary (HIGH confidence)

- [pandas documentation](https://pandas.pydata.org/docs/) - Time-series aggregation, groupby operations, rolling windows
- [scikit-learn documentation](https://scikit-learn.org/stable/) - Pipeline architecture, custom transformers, TimeSeriesSplit
- [PyYAML GitHub](https://github.com/yaml/pyyaml) - Safe YAML parsing with error handling
- [Pydantic documentation](https://pydantic.dev/) - Type-safe configuration validation
- [pydantic-yaml documentation](https://pydantic-yaml.readthedocs.io/) - YAML to Pydantic model serialization

### Secondary (MEDIUM confidence)

- [Time-related feature engineering - scikit-learn](https://scikit-learn.org/stable/auto_examples/applications/plot_cyclical_feature_engineering.html) - Cyclical feature handling
- [6 Powerful Feature Engineering Techniques For Time Series Data](https://www.analyticsvidhya.com/blog/2019/12/6-powerful-feature-engineering-techniques-time-series/) - Lag features, rolling windows, time deltas
- [Custom Transformers in scikit-learn Pipelines - GeeksforGeeks](https://www.geeksforgeeks.org/data-science/custom-transformers-in-scikit-learn-pipelines/) - BaseEstimator/TransformerMixin patterns
- [Pandas GroupBy: Your Guide to Grouping Data in Python - Real Python](https://realpython.com/pandas-groupby/) - Aggregation best practices
- [TimeSeriesSplit - scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html) - Walk-forward validation
- [Valorant Economy Guide - Mobalytics](https://mobalytics.gg/blog/valorant/ultimate-economy-guide/) - Loss bonus formula, credit mechanics

### Tertiary (LOW confidence - exploration only)

- [tsfresh GitHub](https://github.com/blue-yonder/tsfresh) - Automated feature extraction (794 statistical features, use for exploration)
- [Feast feature store](https://feast.dev/) - Production feature serving (overkill for offline training)
- [Azure ML Feature Registry](https://learn.microsoft.com/en-us/azure/machine-learning/reference-yaml-registry?view=azureml-api-2) - Enterprise feature store patterns (informational, not applicable)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pandas, scikit-learn, PyYAML, Pydantic are mature, well-documented, verified via Context7 and official docs
- Architecture: HIGH - Custom transformer pattern, pipeline architecture, TimeSeriesSplit are established best practices with official examples
- Pitfalls: HIGH - Data leakage, performance anti-patterns well-documented in official scikit-learn and pandas guides

**Research date:** 2026-02-14
**Valid until:** 60 days (stable ecosystem, slow-moving best practices)
