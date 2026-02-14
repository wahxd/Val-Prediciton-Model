"""Thesis validation framework for feature hierarchy checking.

Validates that SHAP feature importance aligns with the game-mechanics hierarchy
established in Phase 10 CONTEXT decisions:

    Side × Map > Pistol > Economy > Momentum > Combat

This framework categorizes features into thesis levels, validates the hierarchy,
measures cross-tournament stability, and generates structured reports for
identifying genuine edge vs. noise.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional


def categorize_features(feature_names: List[str]) -> Dict[str, List[str]]:
    """Categorize features into thesis hierarchy levels.

    Maps each feature to its thesis level using keyword matching:
    - side_map: Features with attack/defense/half/side (structural advantage)
    - pistol: Features with "pistol" (cascades into economy)
    - economy: Features with economy/eco/buy/credit/tier (post-pistol)
    - momentum: Features with streak/momentum/comeback/overtime
    - combat: Features with clutch/multi_kill/first_blood/kill (rare/noisy)
    - other: Features that don't match any category

    Args:
        feature_names: List of feature names to categorize

    Returns:
        Dict mapping category name -> list of feature names in that category
    """
    categories = {
        "side_map": [],
        "pistol": [],
        "economy": [],
        "momentum": [],
        "combat": [],
        "other": []
    }

    # Define keywords for each category (order matters - check pistol before economy)
    category_keywords = {
        "side_map": ["attack", "defense", "half", "side", "first_half", "second_half"],
        "pistol": ["pistol"],
        "economy": ["economy", "eco", "buy", "credit", "tier"],
        "momentum": ["streak", "momentum", "comeback", "overtime"],
        "combat": ["clutch", "multi_kill", "first_blood", "kill"],
    }

    for feature_name in feature_names:
        feature_lower = feature_name.lower()
        categorized = False

        # Check each category in order
        # Pistol checked before economy to avoid "eco" in "pistol" confusion
        for category in ["side_map", "pistol", "economy", "momentum", "combat"]:
            keywords = category_keywords[category]
            if any(keyword in feature_lower for keyword in keywords):
                categories[category].append(feature_name)
                categorized = True
                break

        # If no match, goes to "other"
        if not categorized:
            categories["other"].append(feature_name)

    return categories


def validate_thesis_hierarchy(
    feature_importance: Dict[str, float],
    feature_names: List[str]
) -> Dict:
    """Validate that feature importance aligns with thesis hierarchy.

    Checks whether SHAP feature importance respects the hierarchy:
        Side × Map >= Pistol >= Economy (top 3 levels)

    Args:
        feature_importance: Dict mapping feature name -> SHAP importance (mean |SHAP|)
        feature_names: List of all feature names

    Returns:
        Dict containing:
            - level_counts: count of each category in top 10 features
            - level_avg_importance: average SHAP importance per thesis level
            - hierarchy_respected: bool (side_map avg >= pistol avg >= economy avg)
            - top_10_features: list of (name, category, importance) tuples
            - game_mechanics_pct: % of top 10 that are game mechanics (not team identity)
            - interpretation: human-readable summary
            - concerns: list of specific violations
    """
    # Categorize all features
    categories = categorize_features(feature_names)

    # Get top 10 features by importance
    sorted_features = sorted(
        feature_importance.items(),
        key=lambda x: x[1],
        reverse=True
    )
    top_10 = sorted_features[:10]
    top_10_names = [name for name, _ in top_10]

    # Count how many top-10 features belong to each category
    level_counts = {}
    for category, feature_list in categories.items():
        level_counts[category] = sum(
            1 for name in top_10_names if name in feature_list
        )

    # Compute average importance per level (across all features in that level)
    level_avg_importance = {}
    for category, feature_list in categories.items():
        if len(feature_list) > 0:
            avg_importance = np.mean([
                feature_importance.get(name, 0.0)
                for name in feature_list
            ])
            level_avg_importance[category] = float(avg_importance)
        else:
            level_avg_importance[category] = 0.0

    # Build top 10 with category labels
    top_10_features = []
    for name, importance in top_10:
        # Find which category this feature belongs to
        category = "other"
        for cat, feature_list in categories.items():
            if name in feature_list:
                category = cat
                break
        top_10_features.append((name, category, importance))

    # Check hierarchy: side_map >= pistol >= economy (with tolerance)
    tolerance = 0.001  # Allow small numerical differences
    concerns = []

    side_map_avg = level_avg_importance.get("side_map", 0.0)
    pistol_avg = level_avg_importance.get("pistol", 0.0)
    economy_avg = level_avg_importance.get("economy", 0.0)
    momentum_avg = level_avg_importance.get("momentum", 0.0)

    # Check side_map >= pistol
    if pistol_avg > side_map_avg + tolerance:
        concerns.append(
            f"Pistol features (avg {pistol_avg:.4f}) ranked higher than "
            f"Side×Map features (avg {side_map_avg:.4f})"
        )

    # Check pistol >= economy
    if economy_avg > pistol_avg + tolerance:
        concerns.append(
            f"Economy features (avg {economy_avg:.4f}) ranked higher than "
            f"Pistol features (avg {pistol_avg:.4f})"
        )

    # Check momentum not dominating
    if momentum_avg > economy_avg + tolerance:
        concerns.append(
            f"Momentum features (avg {momentum_avg:.4f}) ranked higher than "
            f"Economy features (avg {economy_avg:.4f}) - momentum overrated"
        )

    # Hierarchy respected if no concerns
    hierarchy_respected = len(concerns) == 0

    # Compute game mechanics percentage (all categories except "other" are game mechanics)
    game_mechanics_count = sum(
        level_counts.get(cat, 0)
        for cat in ["side_map", "pistol", "economy", "momentum", "combat"]
    )
    game_mechanics_pct = (game_mechanics_count / len(top_10_names)) * 100.0

    # Generate interpretation
    if hierarchy_respected:
        interpretation = (
            f"Thesis hierarchy respected: Side×Map (avg {side_map_avg:.4f}) >= "
            f"Pistol (avg {pistol_avg:.4f}) >= Economy (avg {economy_avg:.4f}). "
            f"{game_mechanics_pct:.0f}% of top 10 are game mechanics."
        )
    else:
        interpretation = (
            f"Thesis hierarchy violated. {len(concerns)} concern(s) detected. "
            f"{game_mechanics_pct:.0f}% of top 10 are game mechanics."
        )

    return {
        "level_counts": level_counts,
        "level_avg_importance": level_avg_importance,
        "hierarchy_respected": hierarchy_respected,
        "top_10_features": top_10_features,
        "game_mechanics_pct": game_mechanics_pct,
        "interpretation": interpretation,
        "concerns": concerns,
    }


def compare_feature_importance_across_groups(
    importances: Dict[str, Dict[str, float]],
    top_n: int = 10
) -> Dict:
    """Compare feature importance across groups (e.g., tournaments).

    Measures cross-tournament stability by computing top-N feature overlap
    between all pairs of groups.

    Args:
        importances: Dict mapping group_name -> {feature_name -> importance}
        top_n: Number of top features to compare (default: 10)

    Returns:
        Dict containing:
            - pairwise_overlap: dict of (group_a, group_b) -> overlap percentage
            - avg_overlap: mean overlap across all pairs
            - stable_features: features appearing in top-N across ALL groups
            - unstable_features: features in top-N of some groups but not others
            - meta_shift_detected: bool (avg_overlap < 70% suggests meta shift)
            - trading_implications: interpretation for betting edge
    """
    if len(importances) < 2:
        # Need at least 2 groups to compare
        return {
            "pairwise_overlap": {},
            "avg_overlap": 100.0,  # Single group = perfect stability
            "stable_features": list(list(importances.values())[0].keys())[:top_n],
            "unstable_features": [],
            "meta_shift_detected": False,
            "trading_implications": {
                "stable": "Single group - no cross-group validation available",
                "unstable": "Recommend adding more tournaments for stability check"
            }
        }

    # Get top-N features for each group
    top_features_by_group = {}
    for group_name, feature_importance in importances.items():
        sorted_features = sorted(
            feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )
        top_features_by_group[group_name] = set(
            [name for name, _ in sorted_features[:top_n]]
        )

    # Compute pairwise overlap (Jaccard similarity)
    pairwise_overlap = {}
    group_names = list(importances.keys())

    for i, group_a in enumerate(group_names):
        for j, group_b in enumerate(group_names):
            if i < j:  # Only compute upper triangle (avoid duplicates)
                set_a = top_features_by_group[group_a]
                set_b = top_features_by_group[group_b]

                # Overlap = intersection / union * 100
                intersection = len(set_a & set_b)
                union = len(set_a | set_b)

                if union > 0:
                    overlap_pct = (intersection / union) * 100.0
                else:
                    overlap_pct = 0.0

                pairwise_overlap[(group_a, group_b)] = overlap_pct

    # Compute average overlap
    if len(pairwise_overlap) > 0:
        avg_overlap = np.mean(list(pairwise_overlap.values()))
    else:
        avg_overlap = 100.0

    # Find stable features (appear in ALL groups' top-N)
    all_groups_top_features = [
        top_features_by_group[group_name]
        for group_name in group_names
    ]
    stable_features_set = set.intersection(*all_groups_top_features)
    stable_features = sorted(list(stable_features_set))

    # Find unstable features (appear in SOME but not ALL groups' top-N)
    all_top_features = set.union(*all_groups_top_features)
    unstable_features = sorted(list(all_top_features - stable_features_set))

    # Meta shift detection (avg overlap < 70% per CONTEXT)
    meta_shift_detected = bool(avg_overlap < 70.0)

    # Trading implications
    if meta_shift_detected:
        trading_implications = {
            "stable": (
                f"{len(stable_features)} features stable across tournaments - "
                "trustworthy for betting edge"
            ),
            "unstable": (
                f"{len(unstable_features)} features unstable - signal may expire, "
                f"recommend retrain when meta shifts (avg overlap {avg_overlap:.1f}%)"
            )
        }
    else:
        trading_implications = {
            "stable": (
                f"{len(stable_features)} features stable across tournaments - "
                "model generalizes well, trustworthy for betting"
            ),
            "unstable": (
                f"{len(unstable_features)} features vary by tournament but "
                f"overall stability high (avg overlap {avg_overlap:.1f}%)"
            )
        }

    return {
        "pairwise_overlap": pairwise_overlap,
        "avg_overlap": float(avg_overlap),
        "stable_features": stable_features,
        "unstable_features": unstable_features,
        "meta_shift_detected": meta_shift_detected,
        "trading_implications": trading_implications,
    }


def generate_thesis_report(
    hierarchy_result: Dict,
    stability_result: Optional[Dict] = None
) -> Dict:
    """Generate structured thesis validation report.

    Follows the pattern: evidence → diagnosis → thesis check → trading implication

    Args:
        hierarchy_result: Output from validate_thesis_hierarchy()
        stability_result: Optional output from compare_feature_importance_across_groups()

    Returns:
        Structured dict with 4 sections suitable for JSON serialization
    """
    # Section 1: Evidence - SHAP feature importance ranked by thesis level
    evidence = {
        "top_10_features": [
            {
                "rank": i + 1,
                "feature": name,
                "category": category,
                "importance": importance
            }
            for i, (name, category, importance) in enumerate(
                hierarchy_result["top_10_features"]
            )
        ],
        "level_counts": hierarchy_result["level_counts"],
        "level_avg_importance": hierarchy_result["level_avg_importance"],
    }

    # Section 2: Diagnosis - Which levels dominate? Does it match hierarchy?
    diagnosis = {
        "hierarchy_respected": hierarchy_result["hierarchy_respected"],
        "game_mechanics_pct": hierarchy_result["game_mechanics_pct"],
        "interpretation": hierarchy_result["interpretation"],
        "concerns": hierarchy_result["concerns"],
    }

    # Section 3: Thesis check - Pass/fail with specific violations
    thesis_check = {
        "passes": hierarchy_result["hierarchy_respected"],
        "violations": hierarchy_result["concerns"],
        "summary": (
            "PASS - Model aligns with game mechanics thesis"
            if hierarchy_result["hierarchy_respected"]
            else f"FAIL - {len(hierarchy_result['concerns'])} violation(s) detected"
        )
    }

    # Section 4: Trading implication - Stability and edge trustworthiness
    if stability_result is not None:
        trading_implication = {
            "cross_tournament_stability": {
                "avg_overlap": stability_result["avg_overlap"],
                "meta_shift_detected": stability_result["meta_shift_detected"],
                "stable_features": stability_result["stable_features"],
                "unstable_features": stability_result["unstable_features"],
            },
            "recommendations": stability_result["trading_implications"],
        }
    else:
        # No stability data available
        trading_implication = {
            "cross_tournament_stability": None,
            "recommendations": {
                "stable": "No cross-tournament data available",
                "unstable": "Run experiments on multiple tournaments to validate stability"
            }
        }

    return {
        "evidence": evidence,
        "diagnosis": diagnosis,
        "thesis_check": thesis_check,
        "trading_implication": trading_implication,
    }
