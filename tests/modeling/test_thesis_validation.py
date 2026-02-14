"""Tests for thesis validation framework."""

import pytest
import numpy as np

from src.modeling.thesis_validation import (
    categorize_features,
    validate_thesis_hierarchy,
    compare_feature_importance_across_groups,
    generate_thesis_report,
)


# --- Feature Categorization Tests ---

def test_categorize_attack_win_rate():
    """Attack features should categorize as side_map."""
    features = ["attack_win_rate", "attack_rounds_won"]
    cats = categorize_features(features)

    assert len(cats["side_map"]) == 2
    assert "attack_win_rate" in cats["side_map"]
    assert "attack_rounds_won" in cats["side_map"]


def test_categorize_pistol_win_rate():
    """Pistol features should categorize as pistol."""
    features = ["pistol_win_rate", "pistol_round1_winner", "pistol_rounds_won_team1"]
    cats = categorize_features(features)

    assert len(cats["pistol"]) == 3
    assert "pistol_win_rate" in cats["pistol"]
    assert "pistol_round1_winner" in cats["pistol"]


def test_categorize_economy_tier():
    """Economy features should categorize as economy."""
    features = ["economy_tier_avg", "eco_round_win_rate_team1", "buy_tier"]
    cats = categorize_features(features)

    assert len(cats["economy"]) == 3
    assert "economy_tier_avg" in cats["economy"]
    assert "eco_round_win_rate_team1" in cats["economy"]


def test_categorize_streak_max():
    """Momentum features should categorize as momentum."""
    features = ["streak_max", "max_win_streak_team1", "comeback_from_behind", "overtime"]
    cats = categorize_features(features)

    assert len(cats["momentum"]) >= 3  # streak, comeback, overtime
    assert "streak_max" in cats["momentum"]
    assert "comeback_from_behind" in cats["momentum"]


def test_categorize_clutch_rate():
    """Combat features should categorize as combat."""
    features = ["clutch_rate", "clutch_rounds_team1", "multi_kill_rounds_team2", "first_blood_rate_team1"]
    cats = categorize_features(features)

    assert len(cats["combat"]) == 4
    assert "clutch_rate" in cats["combat"]
    assert "first_blood_rate_team1" in cats["combat"]


def test_categorize_score_differential():
    """Features without matching keywords should categorize as other."""
    features = ["score_differential", "total_rounds", "map_name"]
    cats = categorize_features(features)

    assert len(cats["other"]) == 3
    assert "score_differential" in cats["other"]
    assert "total_rounds" in cats["other"]


def test_all_features_categorized():
    """Every feature should be categorized into exactly one bucket."""
    features = [
        "attack_win_rate", "pistol_win_rate", "economy_tier_avg",
        "streak_max", "clutch_rate", "score_differential"
    ]
    cats = categorize_features(features)

    # Count total features across all categories
    total_categorized = sum(len(v) for v in cats.values())
    assert total_categorized == len(features)

    # No feature should appear in multiple categories
    all_features = []
    for feature_list in cats.values():
        all_features.extend(feature_list)
    assert len(all_features) == len(set(all_features))  # No duplicates


# --- Hierarchy Validation Tests ---

def test_validate_hierarchy_perfect_alignment():
    """Hierarchy validation passes when side_map features dominate."""
    feature_importance = {
        "attack_win_rate": 0.9,
        "defense_win_rate": 0.85,
        "first_half_score_team1": 0.8,
        "pistol_win_rate": 0.7,
        "pistol_round1_winner": 0.65,
        "economy_tier_avg": 0.6,
        "eco_round_win_rate_team1": 0.55,
        "streak_max": 0.3,
        "clutch_rate": 0.2,
        "score_differential": 0.1,
    }
    feature_names = list(feature_importance.keys())

    result = validate_thesis_hierarchy(feature_importance, feature_names)

    assert result["hierarchy_respected"] is True
    assert len(result["concerns"]) == 0
    assert result["game_mechanics_pct"] >= 80.0  # At least 80% game mechanics
    assert "respected" in result["interpretation"].lower()


def test_validate_hierarchy_momentum_dominates():
    """Hierarchy validation fails when momentum features rank too high."""
    feature_importance = {
        "streak_max": 0.9,  # Momentum dominating
        "max_win_streak_team1": 0.85,
        "comeback_from_behind": 0.8,
        "attack_win_rate": 0.7,
        "pistol_win_rate": 0.6,
        "economy_tier_avg": 0.5,
        "clutch_rate": 0.3,
        "score_differential": 0.2,
        "total_rounds": 0.1,
        "map_name": 0.05,
    }
    feature_names = list(feature_importance.keys())

    result = validate_thesis_hierarchy(feature_importance, feature_names)

    assert result["hierarchy_respected"] is False
    assert len(result["concerns"]) > 0
    # Check for specific concern about momentum
    concern_text = " ".join(result["concerns"])
    assert "momentum" in concern_text.lower()


def test_validate_hierarchy_mixed_but_respected():
    """Hierarchy can pass even with mixed importance if averages respect order."""
    feature_importance = {
        "attack_win_rate": 0.8,  # side_map high
        "pistol_win_rate": 0.75,  # pistol high
        "economy_tier_avg": 0.7,  # economy high
        "score_differential": 0.65,  # other
        "second_half_score_team1": 0.6,  # side_map moderate
        "pistol_round1_winner": 0.55,  # pistol moderate
        "eco_round_win_rate_team1": 0.5,  # economy moderate
        "streak_max": 0.3,  # momentum low
        "clutch_rate": 0.2,  # combat low
        "total_rounds": 0.1,  # other
    }
    feature_names = list(feature_importance.keys())

    result = validate_thesis_hierarchy(feature_importance, feature_names)

    # Should pass if average importance of side_map >= pistol >= economy
    # side_map avg = (0.8 + 0.6) / 2 = 0.7
    # pistol avg = (0.75 + 0.55) / 2 = 0.65
    # economy avg = (0.7 + 0.5) / 2 = 0.6
    # 0.7 >= 0.65 >= 0.6 -> hierarchy respected
    assert result["hierarchy_respected"] is True


def test_validate_hierarchy_game_mechanics_pct():
    """Game mechanics percentage correctly computed."""
    feature_importance = {
        # 8 game mechanics features
        "attack_win_rate": 0.9,
        "pistol_win_rate": 0.85,
        "economy_tier_avg": 0.8,
        "streak_max": 0.75,
        "clutch_rate": 0.7,
        "defense_win_rate": 0.65,
        "eco_round_win_rate_team1": 0.6,
        "first_blood_rate_team1": 0.55,
        # 2 other features
        "score_differential": 0.5,
        "total_rounds": 0.45,
    }
    feature_names = list(feature_importance.keys())

    result = validate_thesis_hierarchy(feature_importance, feature_names)

    # Top 10 = all 10 features, 8 are game mechanics
    assert result["game_mechanics_pct"] == 80.0


def test_validate_hierarchy_interpretation_meaningful():
    """Interpretation string contains meaningful content."""
    feature_importance = {
        "attack_win_rate": 0.9,
        "pistol_win_rate": 0.8,
        "economy_tier_avg": 0.7,
        "streak_max": 0.3,
        "clutch_rate": 0.2,
        "score_differential": 0.1,
    }
    feature_names = list(feature_importance.keys())

    result = validate_thesis_hierarchy(feature_importance, feature_names)

    interpretation = result["interpretation"]
    assert len(interpretation) > 0
    assert "side" in interpretation.lower() or "map" in interpretation.lower()
    assert "pistol" in interpretation.lower()
    assert "economy" in interpretation.lower()


# --- Cross-Tournament Stability Tests ---

def test_compare_identical_importance():
    """Identical importance dicts should have 100% overlap."""
    importance_a = {
        "attack_win_rate": 0.9,
        "pistol_win_rate": 0.8,
        "economy_tier_avg": 0.7,
        "streak_max": 0.3,
        "clutch_rate": 0.2,
    }
    importance_b = importance_a.copy()

    importances = {
        "tournament_a": importance_a,
        "tournament_b": importance_b,
    }

    result = compare_feature_importance_across_groups(importances, top_n=5)

    assert result["avg_overlap"] == 100.0
    assert result["meta_shift_detected"] is False
    assert len(result["stable_features"]) == 5  # All 5 features stable


def test_compare_completely_different_top10():
    """Completely different top-10 should have low overlap and detect meta shift."""
    importance_a = {
        "feature_a1": 1.0,
        "feature_a2": 0.9,
        "feature_a3": 0.8,
        "feature_a4": 0.7,
        "feature_a5": 0.6,
    }
    importance_b = {
        "feature_b1": 1.0,
        "feature_b2": 0.9,
        "feature_b3": 0.8,
        "feature_b4": 0.7,
        "feature_b5": 0.6,
    }

    importances = {
        "tournament_a": importance_a,
        "tournament_b": importance_b,
    }

    result = compare_feature_importance_across_groups(importances, top_n=5)

    # No overlap -> 0/10 union = 0%
    assert result["avg_overlap"] == 0.0
    assert result["meta_shift_detected"] is True
    assert len(result["stable_features"]) == 0  # No features stable


def test_compare_partial_overlap():
    """Partial overlap should compute correct percentage."""
    importance_a = {
        "shared_1": 1.0,
        "shared_2": 0.9,
        "shared_3": 0.8,
        "unique_a1": 0.7,
        "unique_a2": 0.6,
    }
    importance_b = {
        "shared_1": 1.0,
        "shared_2": 0.9,
        "shared_3": 0.8,
        "unique_b1": 0.7,
        "unique_b2": 0.6,
    }

    importances = {
        "tournament_a": importance_a,
        "tournament_b": importance_b,
    }

    result = compare_feature_importance_across_groups(importances, top_n=5)

    # Intersection: 3 shared
    # Union: 7 total unique
    # Overlap = 3/7 * 100 ≈ 42.86%
    assert 42.0 < result["avg_overlap"] < 43.0
    assert result["meta_shift_detected"] is True  # Below 70%
    assert len(result["stable_features"]) == 3
    assert "shared_1" in result["stable_features"]


def test_compare_stable_and_unstable_features():
    """Correctly identifies stable vs unstable features."""
    importance_a = {
        "stable_1": 1.0,
        "stable_2": 0.9,
        "unstable_a": 0.8,
    }
    importance_b = {
        "stable_1": 1.0,
        "stable_2": 0.9,
        "unstable_b": 0.8,
    }

    importances = {
        "tournament_a": importance_a,
        "tournament_b": importance_b,
    }

    result = compare_feature_importance_across_groups(importances, top_n=3)

    # Stable: appear in BOTH top-3
    assert len(result["stable_features"]) == 2
    assert "stable_1" in result["stable_features"]
    assert "stable_2" in result["stable_features"]

    # Unstable: appear in SOME but not ALL
    assert len(result["unstable_features"]) == 2
    assert "unstable_a" in result["unstable_features"]
    assert "unstable_b" in result["unstable_features"]


# --- Thesis Report Tests ---

def test_generate_thesis_report_structure():
    """Report contains all 4 required sections."""
    # Create minimal hierarchy result
    hierarchy_result = {
        "top_10_features": [
            ("attack_win_rate", "side_map", 0.9),
            ("pistol_win_rate", "pistol", 0.8),
        ],
        "level_counts": {"side_map": 1, "pistol": 1},
        "level_avg_importance": {"side_map": 0.9, "pistol": 0.8},
        "hierarchy_respected": True,
        "game_mechanics_pct": 100.0,
        "interpretation": "Test interpretation",
        "concerns": [],
    }

    report = generate_thesis_report(hierarchy_result)

    # Check all 4 sections exist
    assert "evidence" in report
    assert "diagnosis" in report
    assert "thesis_check" in report
    assert "trading_implication" in report


def test_generate_thesis_report_json_serializable():
    """Report should be JSON-serializable (no numpy types)."""
    import json

    hierarchy_result = {
        "top_10_features": [
            ("attack_win_rate", "side_map", 0.9),
            ("pistol_win_rate", "pistol", 0.8),
        ],
        "level_counts": {"side_map": 1, "pistol": 1},
        "level_avg_importance": {"side_map": 0.9, "pistol": 0.8},
        "hierarchy_respected": True,
        "game_mechanics_pct": 100.0,
        "interpretation": "Test interpretation",
        "concerns": [],
    }

    report = generate_thesis_report(hierarchy_result)

    # Should serialize without error
    json_str = json.dumps(report)
    assert len(json_str) > 0


def test_generate_thesis_report_with_stability():
    """Report includes stability data when provided."""
    hierarchy_result = {
        "top_10_features": [
            ("attack_win_rate", "side_map", 0.9),
        ],
        "level_counts": {"side_map": 1},
        "level_avg_importance": {"side_map": 0.9},
        "hierarchy_respected": True,
        "game_mechanics_pct": 100.0,
        "interpretation": "Test",
        "concerns": [],
    }

    stability_result = {
        "avg_overlap": 85.0,
        "meta_shift_detected": False,
        "stable_features": ["attack_win_rate"],
        "unstable_features": [],
        "trading_implications": {
            "stable": "Features trustworthy",
            "unstable": "Low instability"
        }
    }

    report = generate_thesis_report(hierarchy_result, stability_result)

    # Check stability section populated
    assert report["trading_implication"]["cross_tournament_stability"] is not None
    assert report["trading_implication"]["cross_tournament_stability"]["avg_overlap"] == 85.0


def test_generate_thesis_report_without_stability():
    """Report gracefully handles missing stability data."""
    hierarchy_result = {
        "top_10_features": [
            ("attack_win_rate", "side_map", 0.9),
        ],
        "level_counts": {"side_map": 1},
        "level_avg_importance": {"side_map": 0.9},
        "hierarchy_respected": True,
        "game_mechanics_pct": 100.0,
        "interpretation": "Test",
        "concerns": [],
    }

    report = generate_thesis_report(hierarchy_result, stability_result=None)

    # Check stability section is None
    assert report["trading_implication"]["cross_tournament_stability"] is None
    assert "no cross-tournament" in report["trading_implication"]["recommendations"]["stable"].lower()


def test_generate_thesis_report_pass_fail_summary():
    """Thesis check summary correctly reflects pass/fail."""
    # Test PASS case
    hierarchy_result_pass = {
        "top_10_features": [],
        "level_counts": {},
        "level_avg_importance": {},
        "hierarchy_respected": True,
        "game_mechanics_pct": 100.0,
        "interpretation": "Test",
        "concerns": [],
    }

    report_pass = generate_thesis_report(hierarchy_result_pass)
    assert "PASS" in report_pass["thesis_check"]["summary"]

    # Test FAIL case
    hierarchy_result_fail = {
        "top_10_features": [],
        "level_counts": {},
        "level_avg_importance": {},
        "hierarchy_respected": False,
        "game_mechanics_pct": 50.0,
        "interpretation": "Test",
        "concerns": ["Violation 1", "Violation 2"],
    }

    report_fail = generate_thesis_report(hierarchy_result_fail)
    assert "FAIL" in report_fail["thesis_check"]["summary"]
    assert "2 violation(s)" in report_fail["thesis_check"]["summary"]
