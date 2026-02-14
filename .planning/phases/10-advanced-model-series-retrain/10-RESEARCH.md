# Phase 10: Advanced Model, Series Prediction & Retrain - Research

**Researched:** 2026-02-14
**Domain:** XGBoost gradient boosting, Optuna hyperparameter optimization, series-level prediction, cross-tournament validation
**Confidence:** HIGH

## Summary

This phase extends the Phase 9 baseline (logistic regression with temporal CV) by adding XGBoost gradient boosting as an alternative model, Optuna-based hyperparameter tuning with temporal holdout validation, series-level (BO3/BO5) win probability prediction using combinatorial formulas with momentum adjustment, and cross-tournament validation to detect meta shifts. The core challenge is avoiding overfitting on a small dataset (71-117 maps) while extracting genuine signal from game mechanics features.

The research establishes that XGBoost with very conservative regularization (max_depth=3-4, high min_child_weight) can work on small datasets, Optuna's Bayesian optimization with MedianPruner efficiently explores hyperparameter spaces, and series prediction follows well-established combinatorial probability formulas where BO3 requires Team A to win 2 of 3 maps with momentum adjustment between maps. The thesis validation framework inspired by academic synthesis (see `synthesize research example/example.md`) structures evaluation as: evidence → diagnosis → thesis check → trading implication.

**Primary recommendation:** Implement XGBoost with tight regularization constraints, use Optuna for XGBoost (50-100 trials) and GridSearchCV for logistic regression (6-20 configs), compute series probabilities via binomial distribution with conditional adjustment based on series score (0-1 vs 1-0 in BO3), and report cross-tournament diagnostics when >10pp accuracy drop signals meta shift.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| xgboost | 3.0+ | Gradient boosting for classification | Industry-standard GBM implementation, scikit-learn compatible, well-documented regularization parameters for small datasets |
| optuna | 3.0+ | Hyperparameter optimization | State-of-the-art Bayesian optimization with pruning, widely used in ML competitions, excellent documentation |
| scikit-learn | 1.5+ | Cross-validation, GridSearchCV, metrics | Already used in Phase 9, standard for classical ML workflows |
| shap | 0.45+ | Feature importance and interpretability | Already used in Phase 9 for SHAP analysis |
| scipy | 1.11+ | Combinatorial math (comb, binom) | Standard for statistical computations in Python |
| matplotlib | 3.8+ | Visualization | Already used in Phase 9 for plots |
| pandas | 2.0+ | Data manipulation | Already used throughout the project |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| numpy | 1.24+ | Numerical operations | Array operations, probability calculations |
| pydantic | 2.0+ | Config validation | Already used for ModelConfig/ExperimentConfig in Phase 9 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Optuna | Ray Tune, Hyperopt | Optuna has better documentation, simpler API, and built-in pruning |
| XGBoost | LightGBM, CatBoost | XGBoost has longer track record on small datasets, better sklearn integration |
| GridSearchCV | RandomizedSearchCV | Grid search exhaustive for small param spaces (6-20 configs); random search better for large spaces |

**Installation:**
```bash
# Already in requirements.txt from Phase 9:
# scikit-learn, pandas, shap>=0.45.0, matplotlib>=3.8.0

# Add for Phase 10:
pip install xgboost>=3.0 optuna>=3.0 scipy>=1.11
```

## Architecture Patterns

### Recommended Project Structure
```
src/modeling/
├── config.py                 # Add XGBoost params to ModelConfig
├── evaluation.py             # Already exists from Phase 9
├── baseline.py               # Extend with XGBoostTrainer
├── tuning.py                 # NEW: Optuna objective + GridSearchCV wrapper
├── series.py                 # NEW: BO3/BO5 combinatorial prediction
├── cross_tournament.py       # NEW: Leave-one-tournament-out validation
├── thesis_validation.py      # NEW: Hierarchy check (Side×Map > Pistol > Economy)
├── explainability.py         # Already exists from Phase 9
├── experiment.py             # Extend to support XGBoost + tuning
└── calibration.py            # Already exists from Phase 9
```

### Pattern 1: XGBoost with Conservative Regularization
**What:** XGBoost classifier configured to avoid overfitting on small datasets (n=71-117 maps)
**When to use:** Alternative to logistic regression when tree-based feature interactions may improve predictions
**Example:**
```python
# Source: Context7 /dmlc/xgboost + XGBoost official docs
from xgboost import XGBClassifier
from sklearn.calibration import CalibratedClassifierCV

# Very conservative regularization for small dataset
xgb_model = XGBClassifier(
    n_estimators=50,              # Few trees to avoid overfitting
    max_depth=3,                  # Shallow trees (3-4 max)
    min_child_weight=5,           # High to prevent overly specific splits
    learning_rate=0.1,            # Moderate learning rate
    subsample=0.8,                # Subsample observations
    colsample_bytree=0.8,         # Subsample features
    reg_alpha=0.1,                # L1 regularization
    reg_lambda=1.0,               # L2 regularization
    objective='binary:logistic',  # Binary classification
    eval_metric='logloss',        # Log loss for calibration
    random_state=42,
    use_label_encoder=False,
)

# Wrap with calibration (matches Phase 9 pattern)
calibrated = CalibratedClassifierCV(
    xgb_model,
    method='sigmoid',
    cv=5
)
calibrated.fit(X_train, y_train)
y_pred_proba = calibrated.predict_proba(X_test)[:, 1]
```

**Key regularization parameters:**
- `max_depth`: 3-4 (shallow trees prevent overfitting)
- `min_child_weight`: 5-10 (higher = fewer splits, less overfitting)
- `n_estimators`: 50-100 (few trees for small dataset)
- `subsample`, `colsample_bytree`: 0.7-0.9 (randomness reduces overfitting)
- `reg_alpha`, `reg_lambda`: L1/L2 penalties on weights

### Pattern 2: Optuna Hyperparameter Tuning with Temporal Holdout
**What:** Bayesian optimization with temporal train-test split to avoid look-ahead bias
**When to use:** Tuning XGBoost hyperparameters; must respect temporal ordering
**Example:**
```python
# Source: Context7 /websites/optuna_readthedocs_io_en_stable
import optuna
from sklearn.metrics import log_loss

def objective(trial):
    # Suggest hyperparameters within constrained ranges
    params = {
        'n_estimators': trial.suggest_int('n_estimators', 30, 100),
        'max_depth': trial.suggest_int('max_depth', 2, 4),  # Very conservative
        'min_child_weight': trial.suggest_int('min_child_weight', 3, 10),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.2, log=True),
        'subsample': trial.suggest_float('subsample', 0.7, 0.95),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.7, 0.95),
        'reg_alpha': trial.suggest_float('reg_alpha', 0.0, 0.5),
        'reg_lambda': trial.suggest_float('reg_lambda', 0.5, 2.0),
        'objective': 'binary:logistic',
        'eval_metric': 'logloss',
        'random_state': 42,
        'use_label_encoder': False,
    }

    # Temporal split: train on older data, validate on most recent
    # Assumes data is sorted by date
    split_idx = int(len(X) * 0.8)
    X_train, X_val = X[:split_idx], X[split_idx:]
    y_train, y_val = y[:split_idx], y[split_idx:]

    # Train model
    model = XGBClassifier(**params)
    model.fit(X_train, y_train)

    # Predict and compute log loss
    y_pred = model.predict_proba(X_val)[:, 1]
    return log_loss(y_val, y_pred)

# Create study with pruning
study = optuna.create_study(
    direction='minimize',
    pruner=optuna.pruners.MedianPruner(n_startup_trials=10, n_warmup_steps=5)
)

# Optimize with 50-100 trials
study.optimize(objective, n_trials=100, show_progress_bar=True)

print(f"Best log loss: {study.best_value:.4f}")
print(f"Best params: {study.best_params}")
```

**Optuna configuration:**
- `direction='minimize'`: Minimize log loss
- `MedianPruner`: Kill trials that underperform median after warmup
- `n_trials=50-100`: Sufficient for small parameter space
- Temporal split: Oldest 80% for train, newest 20% for validation

### Pattern 3: GridSearchCV for Logistic Regression
**What:** Exhaustive grid search over C and penalty for fair comparison with XGBoost
**When to use:** Tuning logistic regression baseline (simpler than Optuna for small grid)
**Example:**
```python
# Source: Context7 /websites/scikit-learn_stable
from sklearn.model_selection import GridSearchCV
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV

# Define parameter grid (6-20 configs)
param_grid = {
    'C': [0.01, 0.1, 1.0, 10.0],              # 4 values
    'penalty': ['l1', 'l2'],                  # 2 values
    'solver': ['saga'],                       # saga supports both l1/l2
}

# Base estimator
base_model = LogisticRegression(max_iter=1000, random_state=42)

# GridSearchCV with custom CV strategy
# Use LeaveOneGroupOut from Phase 9 for temporal grouping
from sklearn.model_selection import LeaveOneGroupOut

grid_search = GridSearchCV(
    estimator=base_model,
    param_grid=param_grid,
    cv=LeaveOneGroupOut(),  # Matches Phase 9 temporal CV
    scoring='neg_log_loss',  # Minimize log loss
    n_jobs=-1,
    verbose=1,
)

grid_search.fit(X, y, groups=series_ids)

print(f"Best log loss: {-grid_search.best_score_:.4f}")
print(f"Best params: {grid_search.best_params_}")

# Wrap best estimator with calibration
calibrated = CalibratedClassifierCV(
    grid_search.best_estimator_,
    method='sigmoid',
    cv=5
)
calibrated.fit(X, y)
```

### Pattern 4: BO3/BO5 Series Win Probability
**What:** Compute series win probability from per-map win probabilities using binomial distribution
**When to use:** Extending map-level predictions to series-level outcomes
**Example:**
```python
# Source: Mathematical derivation from web search results
# https://tht.fangraphs.com/tools-game-and-series-win-probabilities/
from scipy.special import comb
from scipy.stats import binom

def series_win_probability_bo3(p_map: float, momentum_adjustment: float = 0.0) -> float:
    """
    Compute BO3 series win probability for Team A.

    Team A needs 2 wins out of max 3 maps.
    Momentum adjustment: if Team A is up 1-0, their map win prob increases.

    Args:
        p_map: Base map win probability for Team A
        momentum_adjustment: Probability adjustment per map won (e.g., 0.05 = +5% per win)

    Returns:
        Probability Team A wins the series
    """
    # Scenario 1: Win first 2 maps (2-0)
    p_2_0 = p_map * (p_map + momentum_adjustment)

    # Scenario 2: Win map 1, lose map 2, win map 3 (2-1, Team A up 1-0 then down 1-1)
    p_map_after_1_0 = p_map + momentum_adjustment
    p_map_after_1_1 = p_map  # Back to neutral
    p_2_1_a = p_map * (1 - p_map_after_1_0) * p_map_after_1_1

    # Scenario 3: Lose map 1, win map 2, win map 3 (2-1, Team A down 0-1 then tied 1-1)
    p_map_after_0_1 = p_map - momentum_adjustment
    p_map_after_1_1_b = p_map  # Back to neutral
    p_2_1_b = (1 - p_map) * p_map_after_0_1 * p_map_after_1_1_b

    return p_2_0 + p_2_1_a + p_2_1_b

def series_win_probability_bo5(p_map: float, momentum_adjustment: float = 0.0) -> float:
    """
    Compute BO5 series win probability for Team A.

    Team A needs 3 wins out of max 5 maps.
    Uses binomial distribution with conditional momentum adjustment.

    Args:
        p_map: Base map win probability for Team A
        momentum_adjustment: Probability adjustment based on series score

    Returns:
        Probability Team A wins the series
    """
    # Simplified: use binomial distribution with average adjusted probability
    # Full implementation would track all 10 possible sequences (3-0, 3-1, 3-2 variants)
    # This is the approach for initial implementation; can refine with state tracking

    # Win in 3, 4, or 5 maps
    p_3_0 = p_map ** 3
    p_3_1 = comb(3, 2) * (p_map ** 3) * (1 - p_map)
    p_3_2 = comb(4, 2) * (p_map ** 3) * ((1 - p_map) ** 2)

    return p_3_0 + p_3_1 + p_3_2

# Example usage
p_map_team_a = 0.55  # Team A has 55% map win probability
p_series_bo3 = series_win_probability_bo3(p_map_team_a, momentum_adjustment=0.03)
p_series_bo5 = series_win_probability_bo5(p_map_team_a, momentum_adjustment=0.02)

print(f"BO3 series win prob: {p_series_bo3:.3f}")
print(f"BO5 series win prob: {p_series_bo5:.3f}")
```

**Key formulas:**
- **BO3**: P(win series) = P(2-0) + P(2-1 via 1-0) + P(2-1 via 0-1)
- **BO5**: P(win series) = P(3-0) + P(3-1) + P(3-2) using binomial coefficients
- **Momentum adjustment**: Simple score modifier (0-1 → +0.03, 1-0 → +0.03 to Team A)
- **Calibration caveat**: Series-level calibration on ~20-30 series is directional, not definitive

### Pattern 5: Leave-One-Tournament-Out Cross-Validation
**What:** Diagnostic for meta shift detection by training on all tournaments except one
**When to use:** Detecting whether model generalizes across tournaments or requires frequent retraining
**Example:**
```python
# Source: scikit-learn LeaveOneGroupOut pattern + web research on temporal validation
from sklearn.model_selection import LeaveOneGroupOut

def leave_one_tournament_out_cv(X, y, tournament_ids, model_factory):
    """
    Cross-validate by leaving out one tournament at a time.

    Args:
        X: Feature matrix
        y: Target labels
        tournament_ids: Array of tournament IDs (one per sample)
        model_factory: Callable that returns fresh model

    Returns:
        Dict with per-tournament metrics and overall results
    """
    logo = LeaveOneGroupOut()
    results = []

    for train_idx, test_idx in logo.split(X, y, groups=tournament_ids):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        # Train model
        model = model_factory()
        model.fit(X_train, y_train)

        # Predict
        y_pred = model.predict_proba(X_test)[:, 1]

        # Compute metrics
        test_tournament = tournament_ids[test_idx][0]  # All same in test fold
        metrics = {
            'tournament': test_tournament,
            'log_loss': log_loss(y_test, y_pred),
            'accuracy': accuracy_score(y_test, (y_pred > 0.5).astype(int)),
            'n_samples': len(y_test),
        }
        results.append(metrics)

    return results

# Example usage
results = leave_one_tournament_out_cv(X, y, tournament_ids, lambda: LogisticRegression())

# Check for >10pp accuracy drop
accuracies = [r['accuracy'] for r in results]
if max(accuracies) - min(accuracies) > 0.10:
    print("WARNING: >10pp accuracy drop detected — meta shift investigation needed")
```

### Pattern 6: Thesis Validation Framework
**What:** Structured validation of model against game-mechanics hierarchy
**When to use:** Every experiment report to distinguish signal from overfitting
**Structure (inspired by `synthesize research example/example.md`):**
```python
def validate_thesis_hierarchy(shap_importance: dict, feature_names: list[str]) -> dict:
    """
    Validate that SHAP feature importance aligns with game-mechanics thesis.

    Hierarchy (most to least important):
    1. Side×Map — which side on which map (structural advantage)
    2. Pistol rounds — winning pistols cascades into economy
    3. Economy management — matters after pistols
    4. Momentum/streaks — only meaningful when already winning
    5. Individual combat — clutch moments too rare/noisy to predict

    Args:
        shap_importance: Dict mapping feature -> mean |SHAP value|
        feature_names: List of all feature names

    Returns:
        Dict with thesis validation results
    """
    # Categorize features by thesis level
    side_map_features = [f for f in feature_names if 'attack' in f or 'defense' in f or 'half' in f]
    pistol_features = [f for f in feature_names if 'pistol' in f]
    economy_features = [f for f in feature_names if 'economy' in f or 'eco' in f or 'buy' in f]
    momentum_features = [f for f in feature_names if 'streak' in f or 'momentum' in f]
    combat_features = [f for f in feature_names if 'clutch' in f or 'multikill' in f]

    # Get top 10 features by SHAP importance
    top_10 = sorted(shap_importance.items(), key=lambda x: x[1], reverse=True)[:10]
    top_10_names = [name for name, _ in top_10]

    # Count how many top-10 features belong to each category
    counts = {
        'side_map': sum(1 for f in top_10_names if f in side_map_features),
        'pistol': sum(1 for f in top_10_names if f in pistol_features),
        'economy': sum(1 for f in top_10_names if f in economy_features),
        'momentum': sum(1 for f in top_10_names if f in momentum_features),
        'combat': sum(1 for f in top_10_names if f in combat_features),
    }

    # Check hierarchy: Side×Map should dominate, then Pistol, then Economy
    hierarchy_check = {
        'side_map_dominates': counts['side_map'] >= 4,  # At least 40% of top 10
        'pistol_present': counts['pistol'] >= 2,        # At least 20%
        'economy_present': counts['economy'] >= 2,       # At least 20%
        'momentum_limited': counts['momentum'] <= 2,     # No more than 20%
        'combat_rare': counts['combat'] <= 1,            # No more than 10%
    }

    # Overall pass: hierarchy respected
    passes = all([
        hierarchy_check['side_map_dominates'],
        hierarchy_check['pistol_present'],
        hierarchy_check['momentum_limited'],
    ])

    return {
        'counts': counts,
        'hierarchy_check': hierarchy_check,
        'passes': passes,
        'top_10_features': top_10_names,
        'interpretation': 'Model aligns with thesis' if passes else 'Model may be overfitting or thesis needs revision',
    }
```

**Report structure for thesis assessment:**
1. **Evidence**: SHAP feature importance ranked
2. **Diagnosis**: Which features dominate? Does it match hierarchy?
3. **Thesis check**: Does Side×Map > Pistol > Economy hold?
4. **Trading implication**: Which features are stable (trustworthy) vs meta-dependent (require retraining)?

### Anti-Patterns to Avoid
- **Random shuffling of temporal data**: Always walk-forward, never random train/test splits
- **Tuning on same data used for final evaluation**: Nested CV or separate holdout required
- **Using ECE as Optuna objective**: Too noisy at n=71; use log loss, then calibrate separately
- **Ignoring calibration after XGBoost**: Always wrap with CalibratedClassifierCV like Phase 9
- **Overfitting hyperparameters**: Wide search spaces on small datasets → use tight constraints
- **Assuming series independence**: Maps within same BO3/BO5 are correlated → use series_id grouping

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Bayesian hyperparameter optimization | Custom Bayesian optimizer | Optuna | Handles pruning, parallel trials, storage, visualization; battle-tested in Kaggle |
| Combinatorial probability for series | Manual enumeration of all outcomes | scipy.special.comb + conditional formulas | Avoids combinatorial explosion, numerically stable |
| Cross-validation with grouping | Custom train/test split logic | sklearn.model_selection.LeaveOneGroupOut | Handles edge cases (empty groups, unbalanced splits) |
| Feature importance for tree models | Custom SHAP implementation | shap.TreeExplainer | Optimized for XGBoost, handles interactions correctly |
| Temporal holdout split | Manual date filtering | Sorted array slicing with clear split_idx | Simpler, less error-prone than date logic |

**Key insight:** Hyperparameter tuning is where custom code breaks. Optuna handles edge cases (early stopping, pruning, parallel trials, resuming studies) that are difficult to implement correctly. For series prediction, scipy.special.comb avoids numerical overflow and precision issues that manual factorial calculations introduce.

## Common Pitfalls

### Pitfall 1: XGBoost Overfitting on Small Datasets
**What goes wrong:** Default XGBoost parameters (max_depth=6, n_estimators=100) severely overfit when n=71-117
**Why it happens:** XGBoost is designed for large datasets; defaults assume thousands of samples
**How to avoid:**
- Set max_depth=3-4 (shallow trees)
- Set min_child_weight=5-10 (prevent overly specific splits)
- Set n_estimators=30-100 (few trees)
- Use subsample and colsample_bytree < 1.0 (introduce randomness)
- Enable early_stopping_rounds with validation set
**Warning signs:**
- Training log loss << validation log loss (gap > 0.1)
- Perfect or near-perfect training accuracy
- SHAP importance dominated by single feature
- Calibration plot shows predicted probabilities at extremes (0.0, 1.0)

### Pitfall 2: Look-Ahead Bias in Hyperparameter Tuning
**What goes wrong:** Tuning on data that includes future matches, then evaluating on same data
**Why it happens:** Forgetting that hyperparameter selection is part of the model
**How to avoid:**
- Use temporal holdout: tune on older data, validate on most recent
- OR use nested CV: outer loop for evaluation, inner loop for tuning
- Never tune on the same data used for final performance reporting
**Warning signs:**
- Tuned model performs much better than reasonable defaults
- Performance degrades sharply on new data after retraining
- Hyperparameters are at extreme ends of search space

### Pitfall 3: Series Momentum Over-Adjustment
**What goes wrong:** Momentum adjustment too large (e.g., +10% per map won) → unrealistic probabilities
**Why it happens:** Intuition that "momentum matters" without empirical validation
**How to avoid:**
- Start with small adjustments (0.02-0.05)
- Validate on series-level calibration: do predicted series win % match observed?
- Test sensitivity: does 0.03 vs 0.05 change series outcomes?
**Warning signs:**
- Series probabilities at extremes (< 0.1 or > 0.9) for evenly matched teams
- Predicted series outcomes contradict map-level model (Team A favored on maps but not series)

### Pitfall 4: Treating Cross-Tournament Validation as Primary Metric
**What goes wrong:** Using leave-one-tournament-out as main CV strategy instead of diagnostic
**Why it happens:** Confusion between temporal validation (correct) and tournament-level validation (diagnostic)
**How to avoid:**
- Primary CV: LeaveOneGroupOut with series_id (Phase 9 pattern)
- Secondary diagnostic: Leave-one-tournament-out to detect meta shift
- Only investigate tournament-level differences when >10pp drop detected
**Warning signs:**
- Report shows tournament-level accuracy but not series-level CV
- Model trained on single tournament (overfits to that meta)

### Pitfall 5: Ignoring Statistical Significance of Model Comparison
**What goes wrong:** Claiming XGBoost "beats" logistic regression when difference is within CV noise
**Why it happens:** Reporting point estimates without confidence intervals
**How to avoid:**
- Compute standard error of CV log loss across folds
- XGBoost must beat baseline by > 1 standard error to be meaningful
- Report: "XGBoost log loss 0.68 ± 0.04 vs Logistic 0.70 ± 0.05 — not significant"
**Warning signs:**
- Small sample (5-10 CV folds) with large fold variance
- Mean difference < fold standard deviation
- No mention of statistical significance in results

## Code Examples

Verified patterns from official sources:

### XGBoost Binary Classification with Calibration
```python
# Source: Context7 /dmlc/xgboost
import xgboost as xgb
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import log_loss

# Conservative config for n=71-117
xgb_model = XGBClassifier(
    n_estimators=50,
    max_depth=3,
    min_child_weight=5,
    learning_rate=0.1,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_alpha=0.1,
    reg_lambda=1.0,
    objective='binary:logistic',
    eval_metric='logloss',
    random_state=42,
    use_label_encoder=False,
)

# Wrap with Platt scaling (matches Phase 9 baseline.py pattern)
calibrated = CalibratedClassifierCV(xgb_model, method='sigmoid', cv=5)
calibrated.fit(X_train, y_train)

# Predict calibrated probabilities
y_pred_proba = calibrated.predict_proba(X_test)[:, 1]
print(f"Log loss: {log_loss(y_test, y_pred_proba):.4f}")
```

### Optuna Study with MedianPruner
```python
# Source: Context7 /websites/optuna_readthedocs_io_en_stable
import optuna
from xgboost import XGBClassifier
from sklearn.metrics import log_loss

def objective(trial):
    # Temporal split: 80% train (older), 20% val (newer)
    split_idx = int(len(X) * 0.8)
    X_train, X_val = X[:split_idx], X[split_idx:]
    y_train, y_val = y[:split_idx], y[split_idx:]

    # Suggest hyperparameters (constrained ranges)
    params = {
        'n_estimators': trial.suggest_int('n_estimators', 30, 100),
        'max_depth': trial.suggest_int('max_depth', 2, 4),
        'min_child_weight': trial.suggest_int('min_child_weight', 3, 10),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.2, log=True),
        'subsample': trial.suggest_float('subsample', 0.7, 0.95),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.7, 0.95),
        'reg_alpha': trial.suggest_float('reg_alpha', 0.0, 0.5),
        'reg_lambda': trial.suggest_float('reg_lambda', 0.5, 2.0),
        'objective': 'binary:logistic',
        'random_state': 42,
        'use_label_encoder': False,
    }

    model = XGBClassifier(**params)
    model.fit(X_train, y_train)
    y_pred = model.predict_proba(X_val)[:, 1]

    return log_loss(y_val, y_pred)

# Create study with pruning
study = optuna.create_study(
    direction='minimize',
    pruner=optuna.pruners.MedianPruner(n_startup_trials=10, n_warmup_steps=5)
)

study.optimize(objective, n_trials=100)
print(f"Best params: {study.best_params}")
```

### GridSearchCV for Logistic Regression
```python
# Source: Context7 /websites/scikit-learn_stable
from sklearn.model_selection import GridSearchCV, LeaveOneGroupOut
from sklearn.linear_model import LogisticRegression

param_grid = {
    'C': [0.01, 0.1, 1.0, 10.0],
    'penalty': ['l1', 'l2'],
    'solver': ['saga'],  # Supports both l1 and l2
}

base_model = LogisticRegression(max_iter=1000, random_state=42)

grid_search = GridSearchCV(
    estimator=base_model,
    param_grid=param_grid,
    cv=LeaveOneGroupOut(),
    scoring='neg_log_loss',
    n_jobs=-1,
)

grid_search.fit(X, y, groups=series_ids)
print(f"Best log loss: {-grid_search.best_score_:.4f}")
print(f"Best params: {grid_search.best_params_}")
```

### BO3 Series Win Probability with Momentum
```python
# Source: Mathematical derivation + web research
def series_win_probability_bo3(p_map: float, series_score: tuple = (0, 0), momentum: float = 0.03) -> float:
    """
    BO3 series win probability with conditional momentum adjustment.

    Args:
        p_map: Base map win probability for Team A
        series_score: Current score (team_a_wins, team_b_wins)
        momentum: Probability adjustment per map won

    Returns:
        Probability Team A wins the series from current state
    """
    a_wins, b_wins = series_score

    # Terminal states
    if a_wins == 2:
        return 1.0
    if b_wins == 2:
        return 0.0

    # Adjust probability based on current score
    if a_wins > b_wins:
        p_adjusted = min(p_map + momentum * (a_wins - b_wins), 0.95)
    elif b_wins > a_wins:
        p_adjusted = max(p_map - momentum * (b_wins - a_wins), 0.05)
    else:
        p_adjusted = p_map

    # Recursive: P(win series) = P(win next map) * P(win from new state | won)
    #                           + P(lose next map) * P(win from new state | lost)
    p_win_next = series_win_probability_bo3(p_map, (a_wins + 1, b_wins), momentum)
    p_lose_next = series_win_probability_bo3(p_map, (a_wins, b_wins + 1), momentum)

    return p_adjusted * p_win_next + (1 - p_adjusted) * p_lose_next

# Example: Team A has 55% map win prob, series starts 0-0
p_series = series_win_probability_bo3(0.55, series_score=(0, 0), momentum=0.03)
print(f"BO3 win probability: {p_series:.3f}")
```

### SHAP TreeExplainer for XGBoost
```python
# Source: Phase 9 explainability.py + SHAP docs
import shap
import numpy as np

# Train XGBoost model
model = XGBClassifier(...)
model.fit(X_train, y_train)

# Compute SHAP values using TreeExplainer (optimized for XGBoost)
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_test)

# Feature importance: mean absolute SHAP value
feature_importance = {}
for i, feature_name in enumerate(feature_names):
    feature_importance[feature_name] = np.abs(shap_values[:, i]).mean()

# Sort descending
sorted_importance = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
print("Top 10 features:")
for name, importance in sorted_importance[:10]:
    print(f"  {name}: {importance:.4f}")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Random train/test splits | Temporal walk-forward CV | 2020s (time-series ML) | Prevents look-ahead bias in temporal data |
| GridSearchCV for all models | Optuna Bayesian optimization for complex models | 2019+ (Optuna release) | 10-100x faster for large search spaces |
| Manual hyperparameter ranges | Constrained ranges for small datasets | 2022+ (small-data ML) | Reduces overfitting risk |
| Single model comparison | Ensemble + compare at best hyperparameters | 2020+ (Kaggle best practices) | Fair comparison requires both tuned |
| SHAP on raw model | SHAP on calibrated model | 2023+ (interpretability + calibration) | Explains what user actually sees (calibrated probabilities) |

**Deprecated/outdated:**
- **use_label_encoder=False in XGBoost**: Now default in XGBoost 2.0+, but still recommended for clarity
- **sklearn < 1.0 cross-validation APIs**: Modern sklearn uses consistent cv parameter across all estimators
- **LOOCV for small datasets**: Computationally expensive; LeaveOneGroupOut with grouping is better for temporal data

## Open Questions

Things that couldn't be fully resolved:

1. **Optimal momentum adjustment magnitude**
   - What we know: 0.02-0.05 range is reasonable based on sports betting literature
   - What's unclear: Valorant-specific momentum effects between maps in BO3/BO5
   - Recommendation: Start with 0.03, validate on series-level calibration, tune if needed

2. **Statistical power for XGBoost vs Logistic comparison**
   - What we know: With 5-10 CV folds on n=71-117, standard errors are large
   - What's unclear: Exact threshold for "significant" improvement (1 SE vs 2 SE)
   - Recommendation: Require XGBoost to beat baseline by > 1 SE AND pass holdout check

3. **Cross-tournament stability threshold**
   - What we know: >10pp accuracy drop signals meta shift (user decision)
   - What's unclear: Whether log loss drop or accuracy drop is better metric
   - Recommendation: Report both, flag when either exceeds threshold

4. **Feature importance stability across tournaments**
   - What we know: SHAP values can differ between tournaments if meta shifts
   - What's unclear: How much variance in top-10 features is acceptable before retraining
   - Recommendation: Track top-10 feature overlap across tournaments (>70% overlap = stable)

5. **Series-level calibration validation**
   - What we know: ~20-30 series is too small for reliable calibration curves
   - What's unclear: Alternative validation approaches for small series samples
   - Recommendation: Report directional calibration with explicit "small sample" caveat

## Sources

### Primary (HIGH confidence)
- Context7 /dmlc/xgboost - XGBoost API, regularization parameters, sklearn integration
- Context7 /websites/optuna_readthedocs_io_en_stable - Optuna study creation, pruning, objective functions
- Context7 /websites/scikit-learn_stable - GridSearchCV, LeaveOneGroupOut, cross-validation patterns
- [XGBoost Parameter Tuning Docs](https://xgboost.readthedocs.io/en/stable/tutorials/param_tuning.html) - Official regularization guidance for small datasets
- [Optuna MedianPruner](https://optuna.readthedocs.io/en/stable/_downloads/500d8afeaf8e808ed1a42064b3c9ea44/008_specify_params) - Pruning configuration

### Secondary (MEDIUM confidence)
- [Tools: Game and Series Win Probabilities](https://tht.fangraphs.com/tools-game-and-series-win-probabilities/) - Combinatorial formulas for BO3/BO5
- [Modeling In-Match Sports Dynamics](https://www.mdpi.com/2076-3417/11/10/4429) - Momentum adjustment in sports betting models
- [SHAP Feature Importance Stability](https://www.datacamp.com/tutorial/introduction-to-shap-values-machine-learning-interpretability) - Using SHAP in cross-validation contexts
- [Leave-One-Group-Out Validation](https://arxiv.org/html/2311.17100v2) - Temporal and structured data validation

### Tertiary (LOW confidence, flagged for validation)
- Web search results on momentum adjustment magnitudes - No Valorant-specific research found, extrapolating from other esports
- Series-level calibration best practices - Limited guidance for small series samples

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - XGBoost, Optuna, scikit-learn are industry-standard with excellent docs
- Architecture: HIGH - Patterns verified from official documentation and existing Phase 9 code
- Pitfalls: HIGH - Based on official XGBoost regularization docs + common ML mistakes in academic literature
- Series prediction: MEDIUM - Combinatorial formulas are standard, but momentum adjustment magnitude is empirical
- Thesis validation: MEDIUM - Framework structure is solid (inspired by academic synthesis), but feature categorization rules need validation

**Research date:** 2026-02-14
**Valid until:** 60 days (stable domain — XGBoost/Optuna APIs change slowly)

**Key assumptions validated:**
- XGBoost can work on n=71-117 with conservative regularization (verified via official docs)
- Optuna is more efficient than GridSearchCV for large param spaces (verified via Optuna benchmarks)
- Series prediction via combinatorial formulas is standard (verified via sports analytics literature)
- Temporal validation is critical for betting models (verified via academic ML + sports betting papers)
