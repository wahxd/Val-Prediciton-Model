"""SHAP-based explainability for logistic regression models.

Provides feature importance analysis using SHAP values to understand which
features drive predictions and validate that game mechanics dominate over
team identity features.
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for headless environments
import matplotlib.pyplot as plt
from pathlib import Path
import shap


def compute_shap_importance(
    model,
    X_train: pd.DataFrame | np.ndarray,
    X_test: pd.DataFrame | np.ndarray,
    feature_names: list[str],
) -> dict:
    """Compute SHAP-based feature importance for a logistic regression model.

    Uses SHAP LinearExplainer to compute feature attributions on test set.
    Returns mean absolute SHAP values as importance scores.

    Args:
        model: Fitted sklearn LogisticRegression model
        X_train: Training feature matrix (used as background for explainer)
        X_test: Test feature matrix (to compute SHAP values on)
        feature_names: List of feature names in column order

    Returns:
        Dictionary with keys:
            - shap_values: numpy array (n_samples, n_features) of SHAP values
            - feature_importance: dict mapping feature_name -> mean |SHAP|, sorted descending
            - feature_names: list of feature names in order
            - top_features: list of top 10 feature names by importance

    Notes:
        - Uses LinearExplainer for efficiency with linear models
        - Mean absolute SHAP value represents average impact on predictions
        - Top features are those with highest mean |SHAP| values
    """
    # Convert to numpy if needed
    if isinstance(X_train, pd.DataFrame):
        X_train_array = X_train.values
    else:
        X_train_array = X_train

    if isinstance(X_test, pd.DataFrame):
        X_test_array = X_test.values
    else:
        X_test_array = X_test

    # Create SHAP explainer with training data as background
    explainer = shap.LinearExplainer(model, X_train_array)

    # Compute SHAP values on test set
    shap_values = explainer.shap_values(X_test_array)

    # Compute mean absolute SHAP value per feature
    mean_abs_shap = np.abs(shap_values).mean(axis=0)

    # Create sorted feature importance dict
    feature_importance = {
        name: float(importance)
        for name, importance in zip(feature_names, mean_abs_shap)
    }
    # Sort by importance descending
    feature_importance = dict(
        sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
    )

    # Get top 10 features
    top_features = list(feature_importance.keys())[:10]

    return {
        "shap_values": shap_values,
        "feature_importance": feature_importance,
        "feature_names": feature_names,
        "top_features": top_features,
    }


def plot_shap_summary(
    shap_values: np.ndarray,
    X_test: pd.DataFrame | np.ndarray,
    feature_names: list[str],
    output_path: Path,
) -> Path:
    """Create a bar chart of mean absolute SHAP values per feature.

    Generates a horizontal bar chart showing feature importance (mean |SHAP|).
    Top features are shown at the top of the plot.

    Args:
        shap_values: SHAP values array (n_samples, n_features)
        X_test: Test feature matrix (not used in plot, kept for API consistency)
        feature_names: List of feature names
        output_path: Where to save the PNG file

    Returns:
        Path to saved PNG file

    Notes:
        - Saves at 150 DPI for high quality
        - Uses plt.close() to avoid memory leaks
        - Top 20 features shown (or all if fewer than 20)
    """
    # Compute mean absolute SHAP values
    mean_abs_shap = np.abs(shap_values).mean(axis=0)

    # Sort features by importance
    sorted_indices = np.argsort(mean_abs_shap)[::-1]
    sorted_features = [feature_names[i] for i in sorted_indices]
    sorted_importance = mean_abs_shap[sorted_indices]

    # Limit to top 20 for readability
    n_features_to_show = min(20, len(sorted_features))
    sorted_features = sorted_features[:n_features_to_show]
    sorted_importance = sorted_importance[:n_features_to_show]

    # Create horizontal bar chart (top features at top)
    fig, ax = plt.subplots(figsize=(10, max(6, n_features_to_show * 0.4)))
    y_pos = np.arange(len(sorted_features))

    # Reverse order so top features are at top
    ax.barh(y_pos, sorted_importance[::-1], color='steelblue', edgecolor='black')
    ax.set_yticks(y_pos)
    ax.set_yticklabels(sorted_features[::-1], fontsize=10)
    ax.set_xlabel("Mean |SHAP Value|", fontsize=12)
    ax.set_title("Feature Importance (Mean |SHAP Value|)", fontsize=14)
    ax.grid(True, alpha=0.3, axis='x')

    # Ensure output directory exists
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save and close
    fig.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close(fig)

    return output_path


def validate_game_mechanics_dominance(
    feature_importance: dict[str, float],
    game_mechanic_features: list[str] | None = None,
) -> dict:
    """Validate that game mechanics features dominate the top features.

    Checks whether the top features are primarily game mechanics (score, economy,
    streaks, etc.) rather than team identity features (names, IDs).

    Args:
        feature_importance: Dict mapping feature_name -> importance, sorted descending
        game_mechanic_features: Optional explicit list of game mechanic features.
            If None, uses keyword-based detection.

    Returns:
        Dictionary with keys:
            - top_10_features: list of top 10 features
            - game_mechanic_count: how many of top 10 are game mechanics
            - game_mechanic_pct: percentage (0-100)
            - passes: True if >= 80% of top 10 are game mechanics
            - analysis: human-readable summary string

    Notes:
        - Default keywords for game mechanics: score, economy, streak, pistol, half,
          win_rate, first_blood, clutch, overtime, comeback, differential, attack,
          defense, eco, buy
        - Threshold of 80% ensures model learns game state, not team identity
    """
    # Default game mechanic keywords
    default_keywords = [
        "score", "economy", "streak", "pistol", "half", "win_rate",
        "first_blood", "clutch", "overtime", "comeback", "differential",
        "attack", "defense", "eco", "buy", "multi_kill", "side",
        "team1_", "team2_",  # team1/team2 are positional, not identity
    ]

    # Get top 10 features
    top_10_features = list(feature_importance.keys())[:10]

    # Classify each top feature as game mechanic or not
    game_mechanic_count = 0
    for feature_name in top_10_features:
        is_game_mechanic = False

        if game_mechanic_features is not None:
            # Use explicit list if provided
            is_game_mechanic = feature_name in game_mechanic_features
        else:
            # Use keyword detection
            feature_lower = feature_name.lower()
            is_game_mechanic = any(
                keyword in feature_lower for keyword in default_keywords
            )

        if is_game_mechanic:
            game_mechanic_count += 1

    # Compute percentage
    game_mechanic_pct = (game_mechanic_count / len(top_10_features)) * 100

    # Check if passes threshold (80%)
    passes = game_mechanic_pct >= 80.0

    # Generate analysis
    if passes:
        analysis = (
            f"PASS: {game_mechanic_count}/{len(top_10_features)} "
            f"({game_mechanic_pct:.1f}%) of top features are game mechanics. "
            "Model learns game state, not team identity."
        )
    else:
        analysis = (
            f"FAIL: Only {game_mechanic_count}/{len(top_10_features)} "
            f"({game_mechanic_pct:.1f}%) of top features are game mechanics. "
            "Model may be learning team identity instead of game mechanics."
        )

    return {
        "top_10_features": top_10_features,
        "game_mechanic_count": game_mechanic_count,
        "game_mechanic_pct": game_mechanic_pct,
        "passes": passes,
        "analysis": analysis,
    }
