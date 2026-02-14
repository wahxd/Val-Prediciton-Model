---
phase: 08
plan: 02
subsystem: features
tags: [feature-extraction, combat, round-features, side-performance]
requires: [08-01]
provides: [round-level-features, combat-metrics, side-performance]
affects: [08-03]
tech-stack:
  added: []
  patterns: [dataclass-features, timestamp-based-detection, backward-compatibility]
key-files:
  created:
    - src/features/extractors/round_features.py
    - src/features/extractors/combat.py
    - tests/features/test_round_features.py
    - tests/features/test_combat.py
  modified:
    - src/features/extractors/__init__.py
decisions:
  - slug: round-features-backward-compatible
    what: Round features handle missing sides field gracefully
    why: Pre-Phase 6 Valoscribe data lacks sides tracking
    impact: Works with both old and new data formats
    alternatives: [require-sides-field, skip-old-data]
  - slug: clutch-detection-simplified
    what: Clutch detection uses single-player kill pattern
    why: Full state tracking (alive counts) not available from events alone
    impact: High-precision detection for true 1vX scenarios
    alternatives: [frame-based-alive-tracking, skip-clutch-feature]
  - slug: multi-kill-10s-window
    what: Multi-kills detected within 10-second time window
    why: Standard Valorant multi-kill timing convention
    impact: Captures double/triple/quad kills accurately
    alternatives: [5s-window, 15s-window, round-based-only]
  - slug: anti-eco-graceful-degradation
    what: Anti-eco stats return zeros when economy data unavailable
    why: Plan 02 executes before Plan 01 data available in some maps
    impact: Feature works with partial data, full functionality when economy available
    alternatives: [require-economy-data, skip-anti-eco-entirely]
  - slug: side-inference-fallback
    what: Infer sides from round number when explicit field missing
    why: Backward compatibility with pre-Phase 6 data
    impact: Reasonable approximation (R1-12 attack, R13-24 defense swap, OT logic)
    alternatives: [require-sides-field, skip-side-performance]
metrics:
  duration: 5 min
  completed: 2026-02-14
---

# Phase 08 Plan 02: Round Features & Combat Extractors Summary

Round-level and combat feature extractors implemented with timestamp-based detection and backward compatibility.

## What Was Built

### Round-Level Features (`round_features.py`)
- **RoundFeatures dataclass**: Per-round game state with score differential, spike events, kill counts, side tracking
- **extract_round_features()**: Processes all events for a map, returns list of per-round features
- **Backward compatibility**: Gracefully handles missing sides field (pre-Phase 6 data)
- **Edge case handling**: Skips rounds without round_end events, handles rounds with no kills

**Key capabilities:**
- Score progression tracking (cumulative scores + differentials)
- Spike plant/defuse detection
- Kill counts per team with differentials
- Side tracking (attack/defense) with fallback inference

### Combat Features (`combat.py`)
- **First Blood**: Identifies first kill per round (lowest timestamp)
- **Clutch Detection**: 1vX scenarios where single player gets all winning kills
- **Multi-Kill Detection**: 2+ kills by same player within 10-second window
- **Side Performance**: Attack/defense win rates per team with inference fallback
- **Anti-Eco Stats**: Conversion rates against eco opponents (graceful degradation)

**Dataclasses:**
- `FirstBlood`: round, killer, killer_team, victim, timestamp
- `ClutchRound`: round, clutch_player, clutch_team, opponents_remaining
- `MultiKill`: round, player, player_team, kill_count, time_window
- `SidePerformance`: attack/defense wins/rounds per team + computed win rates
- `AntiEcoStats`: anti-eco wins/rounds per team + conversion rates

### Test Coverage
- **test_round_features.py**: 6 tests covering standard rounds, no kills, multiple rounds, no sides, missing round_end, edge cases
- **test_combat.py**: 12 tests covering first bloods, clutches (1v2, 1v3), multi-kills, side performance, anti-eco graceful degradation

All 18 new tests pass (34 total in test_features/).

## Decisions Made

### 1. Round Features Backward Compatible
**Decision**: Handle missing sides field gracefully, infer team mapping from kill events
**Rationale**: Pre-Phase 6 Valoscribe data lacks sides tracking
**Impact**: Works with both old and new data formats seamlessly

### 2. Clutch Detection Simplified
**Decision**: Detect clutches by checking if single player got all winning team kills (2+)
**Rationale**: Full state tracking (alive counts per frame) not available from events alone
**Impact**: High-precision detection for true 1vX scenarios, may miss some edge cases
**Alternative considered**: Frame-based alive tracking (requires frames.csv integration)

### 3. Multi-Kill 10-Second Window
**Decision**: Multi-kills detected when 2+ kills by same player within 10 seconds
**Rationale**: Standard Valorant multi-kill timing convention
**Impact**: Captures double/triple/quad kills accurately
**Alternatives considered**: 5s (too strict), 15s (too loose)

### 4. Anti-Eco Graceful Degradation
**Decision**: `compute_anti_eco_stats()` returns zeros when economy data unavailable
**Rationale**: Plan 02 may run before Plan 01 data available on some maps
**Impact**: Feature works with partial data, full functionality unlocked when economy tiers present
**Alternative considered**: Require economy data (breaks Plan 02 independence)

### 5. Side Inference Fallback
**Decision**: Infer sides from round number (R1-12 initial, R13-24 swapped, OT alternates)
**Rationale**: Backward compatibility with pre-Phase 6 data
**Impact**: Reasonable approximation for old data, exact for new data with sides field
**Alternatives considered**: Require sides field (breaks old data), skip side performance entirely

## Technical Implementation Notes

### Timestamp-Based Detection
All combat features use event timestamps for sequencing:
- First blood: `min(kills, key=lambda k: k.timestamp)`
- Multi-kill: Sliding window checks `kills[i+1].timestamp - kills[i].timestamp <= 10.0`

### Team Name Mapping
Round features and combat extractors infer team1/team2 from:
1. Sides dict keys (when available): `list(round_end.sides.keys())`
2. Sorted unique team names from events (fallback)

Ensures consistent team ordering across all features.

### Backward Compatibility Pattern
All extractors check for Phase 6 fields (`sides`, `buy_phase`) and degrade gracefully:
```python
if round_end.sides is not None:
    # Use explicit sides
else:
    # Infer from round number
```

## Integration Points

### Imports from Data Layer
- `src.data.schemas`: ValoscribeEvent, KillEvent, RoundEndEvent, SpikePlantEvent, SpikeDefuseEvent

### Exports to Downstream
- `src.features.extractors.__init__.py`: All dataclasses and extraction functions

### Dependency on Plan 01
- `compute_anti_eco_stats()` accepts optional `economy_tiers` parameter
- When Plan 01 data available, anti-eco conversion rates computed
- When unavailable, returns zeros (no crash)

## Next Phase Readiness

**Ready for 08-03 (Aggregation)**:
- ✅ Round-level features provide per-round building blocks
- ✅ Combat metrics provide advanced tactical signals
- ✅ All features return dataclasses ready for aggregation
- ✅ Backward compatibility ensures works with Phase 5-7 data

**Potential enhancements** (out of scope for v2):
- Frame-based clutch detection (requires frames.csv integration)
- Trade kill detection (requires kill sequencing analysis)
- Utility usage correlation (requires ability event tracking)

## Commits

| Commit | Type | Description |
|--------|------|-------------|
| 8fab802 | feat | Implement round-level feature extraction |
| 83613b7 | feat | Implement combat and side performance extractors |

**Files modified**: 7 created, 1 modified
**Lines of code**: ~600 (features) + ~500 (tests)
**Tests added**: 18 (all passing)

---

*Execution time: 5 minutes*
*Completed: 2026-02-14*
