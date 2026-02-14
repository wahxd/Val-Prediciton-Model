# Phase 9: Baseline Model & Evaluation - Research

**Researched:** 2026-02-14
**Domain:** Machine learning model training, evaluation, and calibration for sports betting prediction
**Confidence:** HIGH

## Summary

Phase 9 establishes the baseline prediction model and evaluation framework for VCT match outcome prediction. This phase is critical: it proves predictive signal exists in the engineered features and sets the standards all future models must meet.

The standard approach uses **logistic regression with L2 regularization** as the baseline, validated via **walk-forward temporal cross-validation** with **leave-one-series-out** splits. The evaluation framework prioritizes **log loss** (calibrated probability quality) over accuracy, since betting edge depends on well-calibrated probabilities, not just binary correctness. **Platt scaling via CalibratedClassifierCV** ensures predicted probabilities match observed frequencies. **SHAP feature importance analysis** validates that the model learns game mechanics (economy, momentum, side advantage) rather than memorizing team identities.

With only 71 Champions 2025 maps available (growing to 117+ as Phase 7 VODs process), **regularization is critical** to prevent overfitting. The small n means L2 penalty strength becomes a key hyperparameter. Evaluation reports (JSON metrics + matplotlib plots) provide reproducible documentation of model performance for future comparison.

**Primary recommendation:** Start with scikit-learn's LogisticRegression + CalibratedClassifierCV + LeaveOneGroupOut for temporal validation, measure log loss as primary metric, and use SHAP LinearExplainer for feature importance. Keep configuration simple (Pydantic for model config, JSON for experiment results), and establish the evaluation framework that Phase 10's XGBoost model will inherit.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| scikit-learn | 1.7.1+ | ML training, calibration, evaluation | Industry-standard for classical ML, excellent documentation, stable API |
| pandas | Latest | Feature DataFrames, data manipulation | Already used in Phase 8 pipeline, natural scikit-learn integration |
| numpy | Latest | Numerical operations, array handling | Dependency of scikit-learn, universal in ML stack |
| matplotlib | Latest | Calibration plots, reliability diagrams | Standard plotting for ML evaluation, proven for scientific figures |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| shap | Latest | Feature importance analysis | Validating model learns game mechanics, not team identity |
| Pydantic | 2.0+ (already in project) | Model configuration schemas | Type-safe experiment configs, validation, serialization |
| structlog | 25.0+ (already in project) | Structured logging | Tracking experiments, debugging, audit trail |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| LogisticRegression | statsmodels GLM | statsmodels provides p-values and statistical tests, but scikit-learn has better CV integration and calibration support |
| CalibratedClassifierCV | Manual Platt scaling | Manual implementation gives more control but is error-prone; scikit-learn's implementation is well-tested |
| matplotlib | seaborn | seaborn has nicer defaults but matplotlib gives finer control for publication-quality plots |
| JSON serialization | XGBoost native JSON | For baseline logistic regression, standard JSON is simpler; XGBoost native format needed in Phase 10 |

**Installation:**
Already in requirements.txt: `scikit-learn`, `pandas`, `numpy`, `structlog`, `pydantic>=2.0`

Missing: `shap`, `matplotlib` (matplotlib likely exists as transitive dep, verify)

```bash
# Add to requirements.txt if missing:
echo "shap>=0.45.0" >> requirements.txt
echo "matplotlib>=3.8.0" >> requirements.txt  # If not already present
```

## Architecture Patterns

### Recommended Project Structure
```
src/
├── modeling/              # New module for Phase 9
│   ├── __init__.py
│   ├── config.py          # ModelConfig, ExperimentConfig Pydantic schemas
│   ├── baseline.py        # LogisticRegression baseline trainer
│   ├── calibration.py     # CalibratedClassifierCV wrapper
│   ├── evaluation.py      # Metrics, cross-validation, report generation
│   └── explainability.py  # SHAP feature importance
├── features/              # Phase 8 - already exists
│   ├── pipeline.py        # FeaturePipeline (Phase 8)
│   └── registry.py        # FeatureRegistry (Phase 8)
└── data/                  # Phase 5 - already exists
    └── loader.py          # load_all_maps (Phase 5)

experiments/               # New directory for experiment outputs
├── {experiment_id}/
│   ├── config.json        # Experiment configuration
│   ├── metrics.json       # Log loss, Brier, accuracy, etc.
│   ├── model.json         # Serialized model (if sklearn supports, else .pkl)
│   ├── calibration_curve.png
│   ├── feature_importance.png
│   └── shap_summary.png

tests/
└── modeling/              # New test module
    ├── test_baseline.py
    ├── test_calibration.py
    ├── test_evaluation.py
    └── test_explainability.py
```

### Pattern 1: Configuration-Driven Experiments

**What:** Use Pydantic models to define experiment configuration, separating hyperparameters from code

**When to use:** Every experiment run (baseline logistic regression now, XGBoost in Phase 10)

**Example:**
```python
# Source: Project conventions (Phase 8 uses Pydantic extensively)
from pydantic import BaseModel, Field

class ModelConfig(BaseModel):
    """Configuration for model training."""
    model_type: str = Field(..., description="Model type: 'logistic_regression' or 'xgboost'")
    feature_set: str = Field(..., description="Feature set name from registry")
    regularization_c: float = Field(1.0, description="Inverse of regularization strength (sklearn C parameter)")
    solver: str = Field("lbfgs", description="Optimization solver")
    max_iter: int = Field(1000, description="Maximum iterations for solver")
    random_state: int = Field(42, description="Random seed for reproducibility")

class ExperimentConfig(BaseModel):
    """Full experiment configuration."""
    experiment_id: str = Field(..., description="Unique experiment identifier")
    model: ModelConfig
    calibration_method: str = Field("sigmoid", description="Platt scaling method")
    cv_strategy: str = Field("leave_one_series_out", description="Cross-validation strategy")
    output_dir: str = Field("experiments", description="Directory for experiment outputs")
```

**Rationale:** Type-safe configs prevent runtime errors, enable reproducibility, and document hyperparameters explicitly

### Pattern 2: Walk-Forward Temporal Validation

**What:** Leave-one-series-out cross-validation with chronological ordering enforced by series_id grouping

**When to use:** All model evaluation (prevents data leakage, respects temporal causality)

**Example:**
```python
# Source: https://github.com/scikit-learn/scikit-learn (Context7)
from sklearn.model_selection import LeaveOneGroupOut
import numpy as np

def temporal_cross_validate(X, y, groups, model, calibrator):
    """
    Walk-forward cross-validation with series-level grouping.

    Args:
        X: Feature matrix (pandas DataFrame)
        y: Target labels (map_winner, 1 if team1 wins, 0 if team2 wins)
        groups: Series IDs (ensure no series appears in both train and test)
        model: Base estimator (LogisticRegression)
        calibrator: CalibratedClassifierCV wrapper

    Returns:
        metrics: Dict of log_loss, brier_score, accuracy per fold
    """
    logo = LeaveOneGroupOut()
    fold_metrics = []

    for train_idx, test_idx in logo.split(X, y, groups=groups):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

        # Train calibrated model
        calibrator.fit(X_train, y_train)

        # Predict probabilities
        y_pred_proba = calibrator.predict_proba(X_test)[:, 1]

        # Compute metrics
        from sklearn.metrics import log_loss, brier_score_loss, accuracy_score
        fold_metrics.append({
            "log_loss": log_loss(y_test, y_pred_proba),
            "brier_score": brier_score_loss(y_test, y_pred_proba),
            "accuracy": accuracy_score(y_test, (y_pred_proba > 0.5).astype(int)),
        })

    return fold_metrics
```

**Rationale:** LeaveOneGroupOut ensures no series leakage, chronological ordering prevents look-ahead bias

### Pattern 3: Calibration with Platt Scaling

**What:** Wrap base model in CalibratedClassifierCV to ensure predicted probabilities match observed frequencies

**When to use:** Always for probabilistic prediction (especially for betting applications)

**Example:**
```python
# Source: https://github.com/scikit-learn/scikit-learn (Context7)
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV

# Base model with L2 regularization
base_model = LogisticRegression(
    penalty='l2',
    C=1.0,  # Inverse regularization strength
    solver='lbfgs',
    max_iter=1000,
    random_state=42
)

# Wrap in calibration layer (uses cross-validation internally)
calibrated_model = CalibratedClassifierCV(
    estimator=base_model,
    method='sigmoid',  # Platt scaling
    cv=5,  # Internal CV for calibration
    ensemble=True  # Average predictions from CV folds
)

# Train on data
calibrated_model.fit(X_train, y_train)

# Get calibrated probabilities
proba = calibrated_model.predict_proba(X_test)[:, 1]
```

**Rationale:** LogisticRegression is naturally calibrated when unpenalized, but L2 regularization can distort probabilities; Platt scaling corrects this

### Pattern 4: SHAP Feature Importance

**What:** Use SHAP values to explain feature contributions, validating model learns game mechanics

**When to use:** Model interpretation, feature selection, debugging unexpected predictions

**Example:**
```python
# Source: https://shap.readthedocs.io/ (WebFetch verified)
import shap

# For logistic regression, use LinearExplainer (fast and exact)
explainer = shap.LinearExplainer(base_model, X_train)

# Compute SHAP values for test set
shap_values = explainer.shap_values(X_test)

# Summary plot showing feature importance
shap.summary_plot(shap_values, X_test, plot_type="bar")

# Validate: Top features should be game mechanics (economy, momentum, side advantage)
# NOT team identity (which isn't in feature set per Phase 8 decisions)
```

**Rationale:** SHAP provides model-agnostic explanations, handles feature interactions, and gives both global and local interpretability

### Pattern 5: Evaluation Report Generation

**What:** Structured experiment outputs with JSON metrics + matplotlib plots

**When to use:** Every experiment run (enables comparison across experiments)

**Example:**
```python
# Source: Project conventions + scikit-learn calibration docs
import json
from pathlib import Path
import matplotlib.pyplot as plt
from sklearn.calibration import calibration_curve

def generate_evaluation_report(
    experiment_id: str,
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    metrics: dict,
    output_dir: Path,
):
    """
    Generate evaluation report with JSON metrics and plots.

    Args:
        experiment_id: Unique experiment identifier
        y_true: True labels
        y_pred_proba: Predicted probabilities
        metrics: Dict of computed metrics (log_loss, brier_score, accuracy)
        output_dir: Directory to save outputs
    """
    exp_dir = output_dir / experiment_id
    exp_dir.mkdir(parents=True, exist_ok=True)

    # Save metrics as JSON
    with open(exp_dir / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    # Generate calibration curve (reliability diagram)
    prob_true, prob_pred = calibration_curve(y_true, y_pred_proba, n_bins=10)

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot([0, 1], [0, 1], 'k--', label='Perfect calibration')
    ax.plot(prob_pred, prob_true, marker='o', label='Model calibration')
    ax.set_xlabel('Mean predicted probability')
    ax.set_ylabel('Fraction of positives')
    ax.set_title('Calibration Curve (Reliability Diagram)')
    ax.legend()
    ax.grid(True, alpha=0.3)

    fig.savefig(exp_dir / "calibration_curve.png", dpi=150, bbox_inches='tight')
    plt.close(fig)
```

**Rationale:** JSON enables programmatic comparison, plots enable human inspection, consistent structure aids reproducibility

### Anti-Patterns to Avoid

- **Random train/test splits on time series data:** Violates temporal causality, creates data leakage. Always use walk-forward or leave-one-group-out with chronological grouping.
- **Evaluating on accuracy alone:** Betting edge depends on calibrated probabilities. A model with 60% accuracy but poor calibration is worse than 58% accuracy with perfect calibration.
- **Forgetting to exclude series from both train and test:** If maps from the same series appear in both sets, the model learns series-specific patterns that don't generalize.
- **Using pickle for long-term model storage:** Pickle is fragile across Python versions. Use model-native formats (sklearn's joblib is better, XGBoost native JSON in Phase 10).
- **Training on all data before cross-validation:** Fit model inside CV loop, not outside. Otherwise you're validating on training data.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Probability calibration | Manual sigmoid fit on validation set | `CalibratedClassifierCV` | Edge cases (empty bins, numerical stability), ensemble averaging, internal CV |
| Cross-validation with groups | Custom train/test splitting logic | `LeaveOneGroupOut` or `GroupKFold` | Guarantees no group leakage, handles edge cases (single-sample groups) |
| Log loss calculation | Manual `-(y*log(p) + (1-y)*log(1-p))` | `sklearn.metrics.log_loss` | Handles clipping (avoid log(0)), multi-class extension, averaging |
| Calibration curves | Manual binning and frequency calculation | `sklearn.calibration.calibration_curve` | Optimal bin edges, uniform mass bins, edge case handling |
| SHAP values for linear models | Manual coefficient × (x - mean) | `shap.LinearExplainer` | Handles intercept correctly, provides visualization, supports interactions |
| Model configuration validation | Manual type checking and defaults | `Pydantic BaseModel` | Type coercion, validation errors, JSON serialization, documentation |

**Key insight:** Evaluation infrastructure has subtle edge cases (numerical stability, empty bins, group leakage). Use battle-tested libraries to avoid silent bugs that corrupt experimental results.

## Common Pitfalls

### Pitfall 1: Data Leakage via Series Splitting

**What goes wrong:** A series (BO3 or BO5) has multiple maps. If some maps from a series are in training and others in testing, the model learns series-specific patterns (team matchups, meta, form) that inflate validation performance but fail on truly unseen series.

**Why it happens:** Naively splitting on map_id treats each map as independent. But maps within a series are highly correlated (same teams, same day, momentum effects).

**How to avoid:**
- Use `LeaveOneGroupOut` with `groups=series_id` parameter
- Ensure `series_id` is tracked in the feature DataFrame (from Phase 8 pipeline)
- Verify in tests that no series appears in both train and test sets

**Warning signs:**
- Validation log loss is suspiciously low (< 0.4) on a 71-map dataset
- Test performance degrades significantly when evaluating on new tournament data
- Feature importance shows unexpected reliance on map-specific features

### Pitfall 2: Ignoring Temporal Ordering in Cross-Validation

**What goes wrong:** Even with leave-one-series-out, if the series are randomly ordered, the model can train on future data and test on past data, violating causality and creating subtle leakage.

**Why it happens:** `LeaveOneGroupOut` doesn't enforce chronological order by default. It only ensures series don't overlap between train and test.

**How to avoid:**
- Sort data by match date before splitting (requires metadata.date field)
- For initial baseline with limited date metadata, acknowledge this limitation and note that true temporal validation requires Phase 7 expanded dataset with diverse dates
- Document assumption: "71 Champions 2025 maps are from single tournament (limited temporal diversity), true walk-forward validation requires Phase 7 multi-tournament data"

**Warning signs:**
- Model performs well on Champions data but fails on Masters data (different time period)
- Feature importance shifts dramatically when adding older tournament data
- Calibration degrades on out-of-time test sets

### Pitfall 3: Over-Regularization on Small Dataset

**What goes wrong:** With only 71 maps, strong L2 regularization (small C) can shrink coefficients so aggressively that the model becomes nearly constant, losing all predictive signal.

**Why it happens:** Default `C=1.0` may be too small for n=71. The penalty dominates the likelihood term, forcing coefficients toward zero.

**How to avoid:**
- Tune `C` hyperparameter via nested cross-validation (outer loop: performance estimation, inner loop: hyperparameter selection)
- Start with grid search over `C=[0.01, 0.1, 1.0, 10.0, 100.0]`
- Monitor coefficient magnitudes: if all coefficients are near zero, regularization is too strong
- Compare against unregularized baseline (C=1e10) to verify regularization is helping, not hurting

**Warning signs:**
- Log loss approaches 0.693 (naive prior of always predicting 0.5)
- All predicted probabilities cluster around 0.5
- SHAP values show negligible feature importance
- Model coefficients are all < 0.01 in absolute value

### Pitfall 4: Miscalibration Despite CalibratedClassifierCV

**What goes wrong:** Predicted probabilities don't match observed frequencies even after Platt scaling, failing the ±10% calibration criterion.

**Why it happens:**
- Insufficient calibration data (internal CV splits too small)
- Platt scaling assumes sigmoid relationship, which may not hold if base model is poorly calibrated
- Overfitting in the calibration layer itself

**How to avoid:**
- Use `cv=5` or `cv=10` in CalibratedClassifierCV (default is 5, increase if data allows)
- Try isotonic regression (`method='isotonic'`) if sigmoid assumption fails (requires more data)
- Inspect reliability diagram visually: points should be near diagonal
- If calibration fails, consider simpler base model (reduce regularization, fewer features)

**Warning signs:**
- Reliability diagram shows systematic deviation from diagonal
- Predicted probabilities are poorly distributed (e.g., all between 0.4-0.6)
- Brier score is good but log loss is poor (suggests bias in probability estimates)

### Pitfall 5: Confusing Model Serialization Formats

**What goes wrong:** Saving scikit-learn models with pickle/joblib, then failing to load in different Python version or scikit-learn version.

**Why it happens:** Pickle serializes Python object state, which is fragile across versions. Scikit-learn doesn't have a stable native JSON format like XGBoost.

**How to avoid:**
- For Phase 9 baseline: Use `joblib` (more stable than pickle for numpy arrays)
- Save `model.coef_` and `model.intercept_` explicitly as JSON for long-term archival
- For Phase 10 XGBoost: Use native JSON format (`save_model('model.json')`)
- Document serialization method in experiment config

**Warning signs:**
- Models fail to load after upgrading scikit-learn
- Models trained on Windows fail to load on Linux (joblib is cross-platform, but pickle can have issues)
- Experiment reproducibility breaks after environment changes

## Code Examples

Verified patterns from official sources:

### Logistic Regression with L2 Regularization

```python
# Source: https://github.com/scikit-learn/scikit-learn (Context7)
from sklearn.linear_model import LogisticRegression

# L2 regularization with customizable strength
model = LogisticRegression(
    penalty='l2',              # L2 (Ridge) regularization
    C=1.0,                     # Inverse regularization strength (larger C = less regularization)
    solver='lbfgs',            # Recommended for L2, handles multicollinearity well
    max_iter=1000,             # Sufficient for convergence on small datasets
    random_state=42,           # Reproducibility
    class_weight='balanced',   # Optional: handle class imbalance if exists
)

model.fit(X_train, y_train)
y_pred_proba = model.predict_proba(X_test)[:, 1]
```

### Leave-One-Group-Out Cross-Validation

```python
# Source: https://github.com/scikit-learn/scikit-learn (Context7)
from sklearn.model_selection import LeaveOneGroupOut

# groups = series_id for each map
# Ensures no series appears in both train and test
logo = LeaveOneGroupOut()

for train_idx, test_idx in logo.split(X, y, groups=series_ids):
    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

    # Train and evaluate
    model.fit(X_train, y_train)
    predictions = model.predict_proba(X_test)[:, 1]
```

### Calibration with CalibratedClassifierCV

```python
# Source: https://github.com/scikit-learn/scikit-learn (Context7)
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression

# Base model
base = LogisticRegression(penalty='l2', C=1.0, solver='lbfgs')

# Calibrated wrapper (uses internal CV)
calibrated = CalibratedClassifierCV(
    estimator=base,
    method='sigmoid',    # Platt scaling (fits sigmoid to scores)
    cv=5,                # 5-fold internal CV for calibration
    ensemble=True        # Average predictions from all CV folds
)

calibrated.fit(X_train, y_train)
calibrated_proba = calibrated.predict_proba(X_test)[:, 1]
```

### Computing Evaluation Metrics

```python
# Source: https://github.com/scikit-learn/scikit-learn (Context7)
from sklearn.metrics import log_loss, brier_score_loss, accuracy_score

# Primary metric: log loss (lower is better, 0.693 is random baseline)
ll = log_loss(y_true, y_pred_proba)

# Secondary metric: Brier score (MSE of probabilities)
brier = brier_score_loss(y_true, y_pred_proba)

# Tertiary metric: accuracy (not primary for betting)
acc = accuracy_score(y_true, (y_pred_proba > 0.5).astype(int))

print(f"Log Loss: {ll:.4f} (target: < 0.693)")
print(f"Brier Score: {brier:.4f}")
print(f"Accuracy: {acc:.2%}")
```

### Calibration Curve (Reliability Diagram)

```python
# Source: https://github.com/scikit-learn/scikit-learn (Context7)
from sklearn.calibration import calibration_curve
import matplotlib.pyplot as plt

# Compute calibration curve
prob_true, prob_pred = calibration_curve(
    y_true,
    y_pred_proba,
    n_bins=10,      # 10 bins for small datasets
    strategy='uniform'  # Equal-width bins
)

# Plot reliability diagram
fig, ax = plt.subplots(figsize=(8, 6))
ax.plot([0, 1], [0, 1], 'k--', label='Perfect calibration')
ax.plot(prob_pred, prob_true, marker='o', label='Model')
ax.set_xlabel('Mean predicted probability')
ax.set_ylabel('Fraction of positives')
ax.set_title('Calibration Curve (Reliability Diagram)')
ax.legend()
ax.grid(True, alpha=0.3)
plt.savefig('calibration_curve.png', dpi=150, bbox_inches='tight')
```

### SHAP Feature Importance for Linear Models

```python
# Source: https://shap.readthedocs.io/ (WebFetch verified)
import shap

# For linear models, use LinearExplainer (fast and exact)
explainer = shap.LinearExplainer(model, X_train)

# Compute SHAP values
shap_values = explainer.shap_values(X_test)

# Summary plot (bar chart of mean absolute SHAP values)
shap.summary_plot(shap_values, X_test, plot_type="bar")

# Check top features: should be game mechanics
# (economy_differential, momentum, side_performance)
# NOT team identity (which doesn't exist per Phase 8 decisions)
```

### Pydantic Model Configuration

```python
# Source: https://docs.pydantic.dev/ (WebSearch verified)
from pydantic import BaseModel, Field
from pathlib import Path

class ModelConfig(BaseModel):
    """Configuration for baseline logistic regression."""
    model_type: str = "logistic_regression"
    feature_set: str = Field(..., description="Feature set from registry")
    C: float = Field(1.0, gt=0, description="Inverse regularization strength")
    solver: str = Field("lbfgs", pattern="^(lbfgs|newton-cg|sag|saga)$")
    max_iter: int = Field(1000, ge=100, description="Max solver iterations")
    random_state: int = 42

class ExperimentConfig(BaseModel):
    """Full experiment configuration."""
    experiment_id: str = Field(..., min_length=1)
    model: ModelConfig
    calibration_method: str = Field("sigmoid", pattern="^(sigmoid|isotonic)$")
    cv_strategy: str = "leave_one_series_out"
    output_dir: Path = Path("experiments")

    class Config:
        # Pydantic v2 uses model_config instead of Config class
        # For v2: use ConfigDict
        frozen = True  # Immutable config
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pickle for model serialization | XGBoost native JSON, joblib for sklearn | XGBoost 1.6.0 (2022), joblib always preferred | Better cross-version compatibility, human-readable formats |
| Accuracy as primary metric for probabilistic prediction | Log loss + calibration metrics | Always best practice, emphasized in sports betting research (2024-2026) | Betting edge depends on calibrated probabilities, not binary accuracy |
| K-fold CV on time series | Walk-forward / leave-one-group-out | Always best practice, recent emphasis in 2025 research | Prevents look-ahead bias, respects temporal causality |
| Manual calibration (Platt scaling by hand) | `CalibratedClassifierCV` | sklearn 0.18+ (2016), stable since | Less error-prone, handles ensemble averaging, internal CV |
| SHAP v1 (slow Python) | SHAP v2 with optimized C++ backend | SHAP 0.40+ (2022) | 10-100x faster, scales to larger datasets |

**Deprecated/outdated:**
- **Pickle for scikit-learn models:** Fragile across versions. Use joblib instead (more stable, cross-platform).
- **TimeSeriesSplit for sports data:** Assumes evenly-spaced observations. Sports matches are irregular, use LeaveOneGroupOut with series grouping.
- **Ignoring calibration for betting models:** Recent research (2024-2026) shows calibration > accuracy for sports betting ROI.

## Open Questions

Things that couldn't be fully resolved:

1. **Exact hyperparameter tuning strategy for n=71**
   - What we know: Nested CV is standard (outer: performance, inner: tuning), but with 71 maps and leave-one-series-out CV, inner loop may have very few samples
   - What's unclear: Whether to use GroupKFold (k=5) for inner loop or simpler grid search on full training set (less rigorous but more stable)
   - Recommendation: Start with simple grid search on full training set (document as limitation), upgrade to nested CV when Phase 7 expands dataset to 117+ maps

2. **Baseline comparison: "always pick higher-ranked team"**
   - What we know: Requirement EVAL-05 requires beating this baseline, but Phase 8 dropped Elo ratings
   - What's unclear: How to implement "higher-ranked team" without external ranking data
   - Recommendation: Use match outcome as proxy (team that won the match is "higher-ranked" for that series), or defer this baseline to Phase 10 when Elo ratings are reconsidered

3. **Series-level vs map-level evaluation in Phase 9**
   - What we know: Phase 9 requirements focus on map-level prediction, Phase 10 adds series-level
   - What's unclear: Whether Phase 9 should evaluate both or just map-level
   - Recommendation: Focus Phase 9 on map-level prediction (simpler, faster iteration), defer series-level evaluation to Phase 10 per roadmap

4. **SHAP interpretation threshold for "learns game mechanics"**
   - What we know: Requirement MODL-07 says model must learn game mechanics, not team identity
   - What's unclear: What quantitative threshold validates this (e.g., "top 5 features must be game mechanics")
   - Recommendation: Qualitative inspection for Phase 9 (top 10 features should be recognizable game mechanics), establish quantitative threshold in Phase 10 if needed

## Sources

### Primary (HIGH confidence)
- [scikit-learn/scikit-learn](https://github.com/scikit-learn/scikit-learn) (Context7: /scikit-learn/scikit-learn) - LogisticRegression, CalibratedClassifierCV, LeaveOneGroupOut, metrics
- [XGBoost Model IO Documentation](https://xgboost.readthedocs.io/en/latest/tutorials/saving_model.html) - JSON serialization best practices
- [SHAP Documentation](https://shap.readthedocs.io/en/latest/example_notebooks/tabular_examples/linear_models/Sentiment%20Analysis%20with%20Logistic%20Regression.html) - LinearExplainer for logistic regression
- [Pydantic Documentation](https://docs.pydantic.dev/) - Model configuration validation

### Secondary (MEDIUM confidence)
- [Machine learning for sports betting: Should model selection be based on accuracy or calibration?](https://www.sciencedirect.com/science/article/pii/S266682702400015X) - Calibration > accuracy for betting (+34.69% ROI vs -35.17%)
- [Understanding Walk Forward Validation in Time Series Analysis](https://medium.com/@ahmedfahad04/understanding-walk-forward-validation-in-time-series-analysis-a-practical-guide-ea3814015abf) - Walk-forward best practices
- [Sports prediction and betting models in the machine learning age](https://journals.sagepub.com/doi/10.3233/JSA-200463) - Log loss under 0.5 is strong for sports

### Tertiary (LOW confidence)
- WebSearch results on small dataset regularization - General ML best practices (not sports-specific)
- WebSearch results on Pydantic vs dataclasses - General Python best practices (not ML-specific)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - scikit-learn, pandas, numpy, matplotlib are industry-standard, well-documented
- Architecture: HIGH - Patterns verified from official docs and Context7
- Pitfalls: MEDIUM - Based on WebSearch research and general ML best practices, not project-specific testing
- Code examples: HIGH - All examples sourced from official docs (Context7 or WebFetch)

**Research date:** 2026-02-14
**Valid until:** 2026-03-14 (30 days - scikit-learn is stable, betting ML research is recent but evolving)

**Notes:**
- Phase 9 builds on Phase 8's feature engineering (FeaturePipeline, FeatureRegistry)
- Phase 10 will extend this evaluation framework to XGBoost and series-level prediction
- Small dataset (n=71 maps) makes regularization and calibration critical - this is a core constraint
- Temporal validation is non-negotiable per STATE.md decisions (walk-forward only, no random splits)
