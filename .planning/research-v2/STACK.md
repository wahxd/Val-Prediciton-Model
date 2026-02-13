# Technology Stack: Prediction Model

**Project:** VCT Match Prediction Model (v2 milestone)
**Researched:** 2026-02-13
**Research Mode:** Stack dimension (subsequent milestone)
**Overall Confidence:** HIGH

---

## Executive Summary

The prediction model milestone extends the existing Python ML stack (scikit-learn, pandas, numpy) with gradient boosting for modeling, calibration tooling for betting-grade probabilities, and model interpretability for feature validation. The data source is Valoscribe's JSONL event logs (71 Champions 2025 maps), so the new stack is pure data science -- no new CV, no new storage, no new infrastructure.

**Key principle:** This is a small-data tabular classification problem (71-200 maps, 50-100 features). The stack should reflect that reality. Deep learning is overkill. Automated feature engineering tools (featuretools, tsfresh) add complexity without value at this scale. Hand-crafted domain features from Valorant match events will outperform automated approaches on a dataset this small. Keep the stack minimal and let domain knowledge drive feature engineering.

---

## Existing Stack (Already Installed -- DO NOT re-add)

| Technology | Current Use | Prediction Model Use |
|------------|-------------|---------------------|
| scikit-learn | Logistic regression on synthetic data | Baseline model, calibration (CalibratedClassifierCV), metrics (brier_score_loss, log_loss), train/test splitting, cross-validation |
| pandas | DataFrame manipulation in dashboard | Primary data wrangling: JSONL ingestion, feature engineering, aggregation |
| numpy | Pixel array operations | Numerical operations, array manipulation |
| Python stdlib | General | json (JSONL parsing), pathlib (file paths), dataclasses (feature schemas) |

**scikit-learn 1.8.0** (current stable, released Dec 2025) already provides everything needed for calibration, including the new `method="temperature"` option in `CalibratedClassifierCV` added in 1.8. No upgrade blockers. Supports Python 3.11-3.14.

---

## Recommended New Additions

### Tier 1: Required (install immediately)

#### XGBoost -- Primary Prediction Model

| | |
|---|---|
| **Library** | xgboost |
| **Version** | 3.2.0 (released 2026-02-10) |
| **Purpose** | Gradient boosted trees for map winner and match winner prediction |
| **Install** | `pip install xgboost` |
| **Confidence** | HIGH (verified via PyPI, Feb 2026) |

**Why XGBoost over LightGBM:**
- XGBoost outperforms LightGBM on small tabular datasets (n < 10,000 samples). With 71-200 maps, this is firmly in small-data territory. LightGBM's speed advantages (histogram-based splitting, leaf-wise growth) matter at 100K+ rows, not at 71 rows.
- XGBoost has stronger regularization defaults (L1/L2 on leaf weights), critical for preventing overfitting on small datasets.
- Better native handling of missing values (common in CV-extracted data where OCR can fail).
- XGBoost demonstrated best performance in esports prediction research: studies on NBA prediction (Wang et al. 2024) and Counter-Strike analysis (Jing et al. 2025) found XGBoost outperforming LightGBM and other boosting methods on match outcome prediction tasks.
- Research specific to Valorant (TechRxiv, 2024) found that team loadout value was the most impactful feature, followed by ultimate points -- both features extractable from Valoscribe data. Logistic regression achieved 60.61% accuracy; gradient boosting should improve on this.
- `save_model()`/`load_model()` provides stable, cross-version serialization (unlike joblib/pickle which break across XGBoost versions).

**Why not CatBoost:**
- CatBoost's primary advantage is native categorical feature handling. Our categorical features (agent names, map names) are low-cardinality (25 agents, 10 maps) and easily one-hot encoded. CatBoost's ordered target encoding shines with high-cardinality categoricals (e.g., user IDs), which we do not have.
- CatBoost 1.2.8 (latest, April 2025) has not had a release in 10 months. XGBoost is more actively maintained.
- CatBoost adds ~1GB of dependencies vs XGBoost's lighter footprint.

**Key XGBoost configuration for this use case:**
```python
import xgboost as xgb

model = xgb.XGBClassifier(
    n_estimators=100,       # Start conservative, tune with Optuna
    max_depth=4,            # Shallow trees for small data
    learning_rate=0.1,      # Standard starting point
    subsample=0.8,          # Row sampling for regularization
    colsample_bytree=0.8,   # Column sampling for regularization
    reg_alpha=0.1,          # L1 regularization
    reg_lambda=1.0,         # L2 regularization
    objective='binary:logistic',
    eval_metric='logloss',  # Primary metric for betting calibration
    enable_categorical=True, # Native categorical support (XGBoost 2.0+)
)
```

**Requires:** Python >=3.10. No additional system dependencies on Windows.

**Source:** [XGBoost PyPI](https://pypi.org/project/xgboost/), [XGBoost Documentation](https://xgboost.readthedocs.io/en/stable/)

---

#### SHAP -- Model Interpretability

| | |
|---|---|
| **Library** | shap |
| **Version** | 0.50.0 (released Nov 2025) |
| **Purpose** | Feature importance analysis, model explainability |
| **Install** | `pip install shap` |
| **Confidence** | HIGH (verified via PyPI) |

**Why SHAP is required, not optional:**
- With only 71 training maps, understanding *which features drive predictions* is more important than raw accuracy. If the model learns "team X always wins" instead of meaningful patterns, SHAP will reveal this.
- SHAP has native `TreeExplainer` for XGBoost that runs in polynomial time (not exponential like KernelExplainer). Fast enough for interactive use.
- Feature importance validation is critical before trusting model output for betting decisions. A model with 70% accuracy that relies on team name features is worthless for predicting future matches against unseen teams.
- SHAP importance plots directly answer: "Is the model learning Valorant game mechanics (economy, round momentum, agent synergy) or just memorizing team strength?"
- Research in esports ML consistently uses SHAP for model validation (Jing et al. 2025 on Counter-Strike used SHAP with XGBoost to identify kill-related features as most predictive).

**Important version note:** SHAP 0.50.0 requires Python >=3.11. If running Python 3.10, use SHAP 0.46.0 instead.

**Source:** [SHAP PyPI](https://pypi.org/project/shap/), [SHAP Documentation](https://shap.readthedocs.io/)

---

#### Matplotlib -- Visualization Foundation

| | |
|---|---|
| **Library** | matplotlib |
| **Version** | 3.10.x (3.10.8 latest, Dec 2025) |
| **Purpose** | Calibration curves, SHAP plots, feature importance charts, model evaluation plots |
| **Install** | `pip install matplotlib` |
| **Confidence** | HIGH |

**Why needed:**
- Required dependency for SHAP visualization (`shap.plots` uses matplotlib backend).
- scikit-learn's `CalibrationDisplay` and `calibration_curve` produce matplotlib figures.
- Custom plots: calibration reliability diagrams, predicted vs actual probability bins, feature importance bar charts, confusion matrices.
- The existing Streamlit dashboard can embed matplotlib figures via `st.pyplot()`.

**Not adding seaborn:** Seaborn adds a dependency for aesthetic sugar on top of matplotlib. For this project's visualization needs (calibration curves, bar charts, SHAP plots), matplotlib alone is sufficient. If richer statistical visualization is needed later, seaborn 0.13.2 can be added incrementally.

**Source:** [Matplotlib PyPI](https://pypi.org/project/matplotlib/)

---

### Tier 2: Recommended (add during hyperparameter tuning phase)

#### Optuna -- Hyperparameter Optimization

| | |
|---|---|
| **Library** | optuna |
| **Version** | 4.7.0 (released Jan 2026) |
| **Purpose** | Bayesian hyperparameter tuning for XGBoost |
| **Install** | `pip install optuna` |
| **Confidence** | HIGH (verified via PyPI) |

**Why Optuna over GridSearchCV/RandomSearchCV:**
- Bayesian optimization converges faster than grid/random search. With 71 maps and leave-one-out cross-validation, each trial is cheap but the hyperparameter space is large (n_estimators, max_depth, learning_rate, subsample, colsample_bytree, reg_alpha, reg_lambda = 7 dimensions). Grid search over 7 dimensions is combinatorially explosive.
- Optuna's pruning stops unpromising trials early, saving compute.
- Built-in visualization (`optuna.visualization`) shows optimization history, parameter importance, parallel coordinates.
- Define-by-run API is more Pythonic than sklearn's param_grid dictionaries.

**When to add:** After baseline model is established and you're ready to tune. Not needed for initial model training.

```python
import optuna

def objective(trial):
    params = {
        'n_estimators': trial.suggest_int('n_estimators', 50, 500),
        'max_depth': trial.suggest_int('max_depth', 2, 8),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
        'subsample': trial.suggest_float('subsample', 0.6, 1.0),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
        'reg_alpha': trial.suggest_float('reg_alpha', 1e-3, 10.0, log=True),
        'reg_lambda': trial.suggest_float('reg_lambda', 1e-3, 10.0, log=True),
    }
    # Cross-validated log loss
    model = xgb.XGBClassifier(**params, objective='binary:logistic')
    scores = cross_val_score(model, X, y, cv=loo, scoring='neg_log_loss')
    return -scores.mean()

study = optuna.create_study(direction='minimize')
study.optimize(objective, n_trials=200)
```

**Source:** [Optuna PyPI](https://pypi.org/project/optuna/), [Optuna Documentation](https://optuna.readthedocs.io/)

---

### Tier 3: Consider Later (not needed for initial model)

#### LightGBM -- Ensemble Diversity

| | |
|---|---|
| **Library** | lightgbm |
| **Version** | 4.6.0 (released Feb 2025) |
| **Purpose** | Second gradient boosting implementation for model ensembling |
| **Install** | `pip install lightgbm` |
| **Confidence** | MEDIUM |

**When to add:** Only if pursuing ensemble approaches after XGBoost baseline is established and you want to blend predictions from multiple model types for improved calibration. Sports betting research shows that combining multiple boosting models can deliver the best performance, but this is an optimization step, not a foundation step.

**Source:** [LightGBM PyPI](https://pypi.org/project/lightgbm/), [LightGBM Documentation](https://lightgbm.readthedocs.io/)

---

## What NOT to Add (and Why)

### Do NOT Add: Deep Learning Frameworks (PyTorch, TensorFlow, Keras)

**Why not:**
- 71 maps is far too little data for neural networks. Gradient boosting dominates tabular prediction tasks at this scale (and often at larger scales too -- see "Tabular Data: Deep Learning is Not All You Need", Shwartz-Ziv & Armon 2021).
- The prediction task is tabular classification from engineered features, not sequence modeling or image recognition.
- Neural networks require orders of magnitude more data for calibrated probability estimates.
- XGBoost + calibration will outperform neural approaches at n=71-200.

### Do NOT Add: Automated Feature Engineering (featuretools, tsfresh)

**Why not:**
- These tools are designed for relational databases (featuretools) or high-frequency time series (tsfresh). Our data is 71 maps with pre-aggregated event logs.
- At 71 samples, automated feature generation creates thousands of features that overwhelm the signal. Feature selection becomes harder than feature engineering.
- Domain knowledge about Valorant (economy cycles, pistol rounds, agent synergies, side advantage) will produce better features than automated approaches. We know that loadout value and ultimate availability are predictive (TechRxiv 2024). We should engineer those features deliberately.
- Adding these libraries pulls in heavy dependency trees for marginal value.

### Do NOT Add: MLflow, Weights & Biases, or Experiment Tracking Platforms

**Why not:**
- Single developer, local-first, 71-200 experiments. A structured directory of model artifacts and a CSV/JSON log of experiment results is sufficient.
- MLflow requires a tracking server. W&B requires cloud. Both violate local-first constraint.
- Track experiments with: `models/{model_name}_{date}_{logloss:.4f}/` directory containing `model.json` (XGBoost native format), `params.json`, `metrics.json`, `shap_importance.png`.

### Do NOT Add: Polars (pandas replacement)

**Why not:**
- pandas is already in the stack and adequate for this data volume. 71 JSONL files with 200-850 events each means ~60K total events. pandas handles this in milliseconds.
- Polars adds a learning curve for the codebase with zero performance benefit at this scale.

### Do NOT Add: DVC (Data Version Control)

**Why not:**
- 71 JSONL files totaling ~5-20MB. Git handles this directly. DVC is for large binary datasets (GB+).
- Track data versions with a simple `data/README.md` noting which Valoscribe commit produced the data.

### Do NOT Add: sktime, prophet, or Time Series Libraries

**Why not:**
- Map winner prediction is not a time series forecasting problem. It is a binary classification problem on tabular features derived from within-match events.
- Round-by-round features within a map are sequential, but the prediction target (map winner) is a single label per map, not a time series to forecast.

### Do NOT Add: category_encoders

**Why not:**
- XGBoost 3.2.0 has `enable_categorical=True` for native categorical feature support. No need for external encoding libraries.
- For scikit-learn pipelines, pandas `get_dummies()` or sklearn `OneHotEncoder` handle the low-cardinality categoricals (agents, maps) adequately.

---

## Complete Installation

```bash
# Tier 1: Required -- install at project start
pip install xgboost==3.2.0
pip install shap==0.50.0
pip install matplotlib==3.10.8

# Tier 2: Recommended -- install during hyperparameter tuning phase
pip install optuna==4.7.0
```

### Updated requirements.txt Additions

```
# === Existing (unchanged) ===
streamlit
opencv-python
numpy
pytesseract
streamlink
scikit-learn
pandas
watchdog

# === New: Prediction Model (v2) ===
xgboost>=3.2.0
shap>=0.50.0
matplotlib>=3.10.0
optuna>=4.7.0
```

---

## Integration Points with Existing Stack

### scikit-learn (already present)

Used heavily for model evaluation and calibration. Key modules:

| Module | Purpose |
|--------|---------|
| `sklearn.model_selection.LeaveOneOut` | Cross-validation strategy for 71-map dataset (too small for standard k-fold) |
| `sklearn.model_selection.cross_val_predict` | Generate out-of-fold predictions for calibration |
| `sklearn.calibration.CalibratedClassifierCV` | Post-hoc probability calibration (isotonic or sigmoid) |
| `sklearn.calibration.calibration_curve` | Reliability diagrams |
| `sklearn.metrics.brier_score_loss` | Primary calibration metric |
| `sklearn.metrics.log_loss` | Primary discrimination metric |
| `sklearn.metrics.roc_auc_score` | Discrimination ability |
| `sklearn.preprocessing.OneHotEncoder` | Agent/map encoding if not using XGBoost native categoricals |
| `sklearn.pipeline.Pipeline` | Feature engineering + model in reproducible pipeline |

### pandas (already present)

Primary data wrangling tool:

```python
import pandas as pd
import json
from pathlib import Path

# Ingest Valoscribe JSONL event logs
def load_match_events(jsonl_path: Path) -> pd.DataFrame:
    events = []
    with open(jsonl_path) as f:
        for line in f:
            events.append(json.loads(line))
    return pd.DataFrame(events)

# Feature engineering: aggregate events per map
def engineer_map_features(events_df: pd.DataFrame) -> dict:
    kills = events_df[events_df['event_type'] == 'kill']
    return {
        'total_kills_team_a': len(kills[kills['team'] == 'team_a']),
        'first_blood_rate_team_a': ...,  # Fraction of rounds with first blood
        'spike_plants_per_round': ...,
        'pistol_rounds_won': ...,
        # ... domain features
    }
```

### Streamlit (already present)

The existing dashboard can display model predictions:

```python
import streamlit as st
import matplotlib.pyplot as plt
from sklearn.calibration import calibration_curve

# Embed calibration curve in Streamlit
fig, ax = plt.subplots()
fraction_pos, mean_predicted = calibration_curve(y_true, y_prob, n_bins=10)
ax.plot(mean_predicted, fraction_pos, 's-', label='XGBoost')
ax.plot([0, 1], [0, 1], '--', label='Perfect calibration')
st.pyplot(fig)
```

---

## Model Serialization Strategy

**Use XGBoost native format, not joblib/pickle.**

| Method | Recommendation | Reason |
|--------|---------------|--------|
| `model.save_model('model.json')` | PRIMARY | Cross-version compatible, human-readable JSON, official recommendation |
| `model.save_model('model.ubj')` | ALTERNATIVE | Binary Universal Binary JSON format, smaller file size |
| `joblib.dump(model, 'model.joblib')` | AVOID | Breaks across XGBoost versions, security risks on untrusted inputs |
| `pickle.dump(model, f)` | AVOID | Same issues as joblib, plus larger file size |

```python
# Save
model.save_model('models/map_winner_v1.json')

# Load
model = xgb.XGBClassifier()
model.load_model('models/map_winner_v1.json')
```

For the calibration wrapper (CalibratedClassifierCV), joblib is acceptable since it only wraps sklearn internals:
```python
import joblib  # Part of scikit-learn, already installed
joblib.dump(calibrated_model, 'models/map_winner_v1_calibrated.joblib')
```

---

## Evaluation Metrics Strategy

For betting-grade probability estimation, **calibration matters more than accuracy.**

| Metric | Library | Purpose | Target |
|--------|---------|---------|--------|
| Log Loss | `sklearn.metrics.log_loss` | Primary: penalizes overconfident wrong predictions heavily | < 0.68 (better than coin flip) |
| Brier Score | `sklearn.metrics.brier_score_loss` | Calibration quality: mean squared error of probability estimates | < 0.25 (better than coin flip) |
| ROC AUC | `sklearn.metrics.roc_auc_score` | Discrimination: can model rank matches by win probability? | > 0.55 |
| Calibration Curve | `sklearn.calibration.calibration_curve` | Visual: are predicted probabilities reliable? | Close to diagonal |
| Accuracy | `sklearn.metrics.accuracy_score` | Secondary: raw classification rate | > 55% |

**Why log loss over accuracy for betting:**
- A model predicting 51% on every match has ~50% accuracy but is useless for betting.
- A model predicting 80% when true probability is 65% will lose money despite good accuracy.
- Log loss penalizes overconfidence: predicting 0.95 when the outcome is wrong costs much more than predicting 0.55 when wrong.
- Walsh and Joshi (2024) showed calibration-optimized models generate 69.86% higher returns than accuracy-optimized models in sports betting.

---

## Cross-Validation Strategy

With n=71 maps, standard k-fold (k=5 or k=10) leaves very small test folds (7-14 maps) with high variance. Recommended approach:

```python
from sklearn.model_selection import LeaveOneOut, cross_val_predict

# Leave-One-Out for probability estimates
loo = LeaveOneOut()
y_prob = cross_val_predict(model, X, y, cv=loo, method='predict_proba')[:, 1]

# Evaluate calibration on LOO predictions
from sklearn.metrics import brier_score_loss, log_loss
print(f"Brier Score: {brier_score_loss(y, y_prob):.4f}")
print(f"Log Loss: {log_loss(y, y_prob):.4f}")
```

**Why LOO:** Each map is precious data. LOO uses 70 maps for training, 1 for testing, repeated 71 times. High variance per fold but unbiased aggregate metrics. Computationally feasible because XGBoost trains on 71 rows in milliseconds.

**Alternative:** Repeated stratified 5-fold (repeat 10 times) for lower variance estimates at the cost of slight pessimistic bias.

---

## Dependency Tree Impact

New dependencies and their transitive pulls:

| Package | Key Transitive Dependencies | Disk Impact |
|---------|---------------------------|-------------|
| xgboost 3.2.0 | scipy (if not present) | ~30MB |
| shap 0.50.0 | numba, llvmlite, cloudpickle, slicer | ~150MB (numba/llvmlite dominate) |
| matplotlib 3.10.8 | pillow, contourpy, cycler, fonttools, kiwisolver, pyparsing | ~50MB |
| optuna 4.7.0 | alembic, sqlalchemy, colorlog, tqdm | ~20MB |

**Total new disk footprint:** ~250MB (SHAP's numba/llvmlite dependency is the largest contributor).

**Note on SHAP size:** The numba/llvmlite dependencies are large but provide JIT compilation for SHAP's TreeExplainer, making it fast enough for interactive use. This is a worthwhile tradeoff for model interpretability.

---

## Python Version Compatibility

| Library | Minimum Python | Maximum Python | Notes |
|---------|---------------|---------------|-------|
| xgboost 3.2.0 | 3.10 | 3.14 | |
| shap 0.50.0 | 3.11 | 3.14 | Use shap 0.46.0 if on Python 3.10 |
| matplotlib 3.10.8 | 3.10 | 3.13 | |
| optuna 4.7.0 | 3.9 | 3.13 | |
| scikit-learn 1.8.0 | 3.11 | 3.14 | Already installed |

**Recommended Python version:** 3.12 or 3.13. All libraries support both. Python 3.11 is the minimum for full compatibility with SHAP 0.50.0 + scikit-learn 1.8.0.

**Action required:** Verify current Python version. The existing `requirements.txt` does not pin Python version. If running Python 3.10, either upgrade to 3.12+ or pin `shap==0.46.0`.

---

## Alternatives Considered (Full Matrix)

| Category | Recommended | Alternative | Why Not Alternative |
|----------|-------------|-------------|-------------------|
| Gradient boosting | XGBoost 3.2.0 | LightGBM 4.6.0 | LightGBM's speed advantage irrelevant at n=71; XGBoost better regularization for small data |
| Gradient boosting | XGBoost 3.2.0 | CatBoost 1.2.8 | Low-cardinality categoricals don't need CatBoost's encoding; stale release cycle |
| Interpretability | SHAP 0.50.0 | eli5, lime | SHAP is theoretically grounded (Shapley values), has native XGBoost TreeExplainer; eli5 is poorly maintained |
| Hyperparameter tuning | Optuna 4.7.0 | sklearn GridSearchCV | Bayesian optimization far more efficient in 7+ dimension space |
| Hyperparameter tuning | Optuna 4.7.0 | Hyperopt | Optuna has better API, better visualization, more active development |
| Visualization | matplotlib 3.10.8 | plotly | matplotlib is sufficient; plotly adds complexity for interactive plots we don't need in a local tool |
| Visualization | matplotlib only | matplotlib + seaborn | Seaborn's statistical plots unnecessary; SHAP has its own plot library |
| Serialization | XGBoost native JSON | joblib/pickle | Native format is cross-version stable; pickle breaks across XGBoost versions |
| Feature engineering | pandas (manual) | featuretools | Automated feature generation counterproductive at n=71; domain features are better |
| Experiment tracking | Directory structure | MLflow | Overkill for single developer; violates local-first if using tracking server |
| Data processing | pandas | polars | No performance benefit at n=71 maps / 60K events |

---

## Domain-Specific Valorant Prediction Research

Research on Valorant match prediction informs our feature engineering strategy (not stack, but relevant context for how the stack will be used):

| Study | Features Used | Best Model | Accuracy | Key Finding |
|-------|--------------|-----------|----------|-------------|
| TechRxiv 2024 (Economy + Ultimate) | Loadout value, ultimate points, ultimate abilities | Logistic Regression | 60.61% | Team loadout value most predictive feature |
| ArXiv 2510.17199 (Tactical Features) | Minimap positions, ability usage timing, auditory cues | TimeSformer | 80.55% | Tactical event features boosted accuracy from 72% to 80% |
| Cal State (Win Probability) | Kills per round, ACS, agent data, round win history | Random Forest | ~65% | Kills Per Round most significant feature, followed by KAST ratio |

**Implication for our stack:** XGBoost can incorporate all feature types these studies found predictive (economy, kills, agents, round progression) while providing better probability calibration than the models used in these studies (none used CalibratedClassifierCV or evaluated calibration metrics).

---

## Sources

**Verified (HIGH confidence):**
- [XGBoost 3.2.0 on PyPI](https://pypi.org/project/xgboost/) -- Version, Python requirements verified Feb 2026
- [XGBoost Documentation](https://xgboost.readthedocs.io/en/stable/) -- API, serialization, categorical support
- [LightGBM 4.6.0 on PyPI](https://pypi.org/project/lightgbm/) -- Version verified Feb 2026
- [SHAP 0.50.0 on PyPI](https://pypi.org/project/shap/) -- Version, Python >=3.11 requirement verified
- [Optuna 4.7.0](https://optuna.readthedocs.io/) -- Version verified Jan 2026
- [scikit-learn 1.8.0 Calibration Module](https://scikit-learn.org/stable/modules/calibration.html) -- CalibratedClassifierCV, temperature scaling, methods verified
- [scikit-learn 1.8 Release Highlights](https://scikit-learn.org/stable/auto_examples/release_highlights/plot_release_highlights_1_8_0.html) -- New temperature method confirmed
- [Matplotlib 3.10.8 on PyPI](https://pypi.org/project/matplotlib/) -- Version verified
- [CatBoost 1.2.8 on PyPI](https://pypi.org/project/catboost/) -- Version, release date verified
- [XGBoost Model IO](https://xgboost.readthedocs.io/en/stable/tutorials/saving_model.html) -- Native save/load recommended over pickle

**Research (MEDIUM confidence -- methodology verified, results from specific datasets):**
- [Valorant Economy + Ultimate Prediction (TechRxiv)](https://www.techrxiv.org/users/916972/articles/1289732-a-predictive-analysis-of-valorant-esports-win-probability-through-economy-and-ultimate-ability) -- Feature importance for Valorant
- [Valorant Tactical Features (ArXiv 2510.17199)](https://arxiv.org/html/2510.17199v1) -- Round outcome prediction with event features
- [XGBoost vs LightGBM Comparison (Neptune.ai)](https://neptune.ai/blog/xgboost-vs-lightgbm) -- Performance comparison
- [SHAP for Counter-Strike (Jing et al. 2025)](https://journals.sagepub.com/doi/10.1177/17479541251388864) -- SHAP + XGBoost in esports
- [Model Calibration in Sports Betting (Walsh & Joshi 2024)](https://www.sports-ai.dev/blog/ai-model-calibration-brier-score) -- Calibration-optimized models outperform accuracy-optimized for betting ROI
- [Gradient Boosting Comparison (Analytics Vidhya 2026)](https://www.analyticsvidhya.com/blog/2026/02/gradient-boosting-vs-adaboost-vs-xgboost-vs-catboost-vs-lightgbm/) -- Comprehensive comparison

**Community patterns (LOW confidence -- cross-referenced where possible):**
- [Joblib vs Pickle Best Practices](https://johal.in/machine-learning-model-serialization-python-pickle-vs-joblib-best-practices/) -- Serialization recommendations
- [Sports Prediction Systematic Review (ArXiv 2410.21484)](https://arxiv.org/html/2410.21484v1) -- ML in sports betting survey

---

## Open Questions (Require Phase-Specific Research)

1. **Optimal cross-validation strategy:** LOO vs repeated stratified k-fold for 71 maps. LOO is unbiased but high variance. Need to test both and compare metric stability.
2. **Feature count budget:** With 71 samples, how many features before overfitting dominates? Rule of thumb: n/10 to n/5 features (7-14). May need aggressive feature selection.
3. **Match-level aggregation from map-level:** How to combine map-level predictions into match/series winner predictions for BO3/BO5. Conditional probability model or direct match-level features?
4. **Valoscribe data quality filtering:** 87% validation rate means 9/71 maps may have bad data. How to handle: exclude, flag, or weight down?
5. **Temporal leakage:** If training on all 71 maps and predicting future matches, are there team roster changes between training data and prediction time that invalidate features?

---
*Stack research complete: 2026-02-13*
