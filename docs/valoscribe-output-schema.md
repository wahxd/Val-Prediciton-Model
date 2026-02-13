# Valoscribe Output Schema

**Version:** Post-Phase 6 (comprehensive event coverage)
**Last updated:** 2026-02-13

This document is the single source of truth for what the prediction model consumes from Valoscribe.

---

## Overview

Valoscribe processes Valorant VODs and outputs structured game data in three files per map:

```
D:\Git\valoscribe\data\processed\{map_id}\
  ├── events.jsonl       # Event stream (kills, rounds, economy, abilities)
  ├── frames.csv         # Per-frame game state snapshots
  └── metadata.json      # Map-level metadata (teams, agents, date)
```

**Map ID format:** `{team1}_vs_{team2}_{map_name}_{date}` (e.g., `SEN_vs_FNC_Ascent_2025-01-15`)

---

## File Structure

### events.jsonl

**Format:** JSON Lines (one event per line, newline-delimited)

Each event is a JSON object with:
- `type`: Event type identifier (see Event Types section)
- `timestamp`: Float (seconds from video start)
- `round`: Integer (1-indexed round number, 1-25+ for OT)
- Additional fields specific to event type

**Ordering:** Events are emitted in chronological order (sorted by timestamp).

**Phase 6 additions:**
- `buy_phase`: Economy and loadout classification per round
- `ult_usage`: Ultimate ability usage tracking
- `timeout`: Tactical timeout events
- `sides`: Explicit attack/defense tracking on round events

---

### frames.csv

**Format:** CSV with header row

Per-frame snapshots of game state for temporal feature engineering.

**Columns:**
- `timestamp`: Float (seconds from video start)
- `frame_number`: Integer (sequential frame index)
- `phase`: String (`buy` | `live` | `post_round`)
- `round_number`: Integer (current round, 1-indexed)
- `score_team1`: Integer (Team 1 rounds won)
- `score_team2`: Integer (Team 2 rounds won)
- `spike_planted`: Boolean (spike planted this round)
- `spike_site`: String (A | B | C, empty if not planted)
- `round_timer`: Float (seconds remaining in round, null during buy)
- `spike_timer`: Float (seconds until detonation, null if not planted)

**Per-player columns (10 players, repeated for each):**
- `player{N}_name`: String (player name)
- `player{N}_team`: String (team name)
- `player{N}_agent`: String (agent name)
- `player{N}_alive`: Boolean
- `player{N}_health`: Integer (0-100, null if dead)
- `player{N}_armor`: Integer (0-50, null if dead)
- `player{N}_ability1`: Boolean (has charge)
- `player{N}_ability2`: Boolean (has charge)
- `player{N}_ultimate`: Integer (0-10 ult points, varies by agent)

**Sampling rate:** Variable (typically 1-5 FPS during key moments, sparser during downtime)

---

### metadata.json

**Format:** Single JSON object

Map-level metadata and validation results.

**Fields:**
- `teams`: Array of 2 strings (team names in order: [Team 1, Team 2])
- `map_name`: String (Ascent | Bind | Haven | Split | etc.)
- `date`: String (ISO 8601 format: YYYY-MM-DD)
- `starting_sides`: Object mapping team name to initial side (`{"Team A": "attack", "Team B": "defense"}`)
- `players`: Array of 10 objects, each with:
  - `name`: String (player name)
  - `team`: String (team name)
  - `agent`: String (agent picked)
  - `player_index`: Integer (0-9, internal tracking ID)
- `validation_results`: Object with:
  - `status`: String (`pass` | `warning` | `fail`)
  - `checks`: Object mapping check name to boolean result
  - `warnings`: Array of warning strings
  - `errors`: Array of error strings

**Additional fields:** May contain extra metadata from video source (tournament, stage, etc.) preserved via `extra='allow'`.

---

## Event Types

### Core Events (Phase 5)

#### kill

**Description:** Player elimination event.

**Fields:**
- `type`: `"kill"`
- `timestamp`: Float
- `round`: Integer (round number, 1-indexed)
- `killer`: String (player name who got the kill)
- `victim`: String (player name who died)
- `weapon`: String (weapon used: Vandal | Phantom | Operator | Sheriff | etc.)
- `killer_team`: String (team name of killer)
- `victim_team`: String (team name of victim)

**Optional fields (via `extra='allow'`):**
- `headshot`: Boolean (true if headshot kill)
- `first_blood`: Boolean (true if first kill of round)

**Example:**
```json
{"type": "kill", "timestamp": 15.3, "round": 1, "killer": "TenZ", "victim": "Derke", "weapon": "Vandal", "killer_team": "SEN", "victim_team": "FNC", "headshot": true}
```

---

#### round_start

**Description:** Round begins (buy phase → live phase transition).

**Fields:**
- `type`: `"round_start"`
- `timestamp`: Float
- `round`: Integer (round number, 1-indexed)
- `sides`: Object (optional, Phase 6 addition) mapping team name to side (`{"Team A": "attack", "Team B": "defense"}`)

**Notes:**
- Sides swap at halftime (round 13) and every 2 rounds in OT
- `sides` field is `null` or omitted for older Valoscribe data (backward compatibility)

**Example:**
```json
{"type": "round_start", "timestamp": 0.5, "round": 1, "sides": {"SEN": "attack", "FNC": "defense"}}
```

---

#### round_end

**Description:** Round concludes with winner and updated score.

**Fields:**
- `type`: `"round_end"`
- `timestamp`: Float
- `round`: Integer (round number, 1-indexed)
- `winning_team`: String (team name that won the round)
- `score_team1`: Integer (Team 1 total rounds won after this round)
- `score_team2`: Integer (Team 2 total rounds won after this round)
- `sides`: Object (optional, Phase 6 addition) mapping team name to side during this round

**Notes:**
- Scores are cumulative (e.g., after round 1: `{"score_team1": 1, "score_team2": 0}`)
- `sides` field documents which team was attacking/defending when round ended

**Example:**
```json
{"type": "round_end", "timestamp": 52.0, "round": 1, "winning_team": "FNC", "score_team1": 0, "score_team2": 1, "sides": {"SEN": "attack", "FNC": "defense"}}
```

---

#### spike_plant

**Description:** Spike planted by attacking team.

**Fields:**
- `type`: `"spike_plant"`
- `timestamp`: Float
- `round`: Integer (round number, 1-indexed)

**Optional fields:**
- `planter`: String (player who planted)
- `site`: String (A | B | C, spike site)

**Example:**
```json
{"type": "spike_plant", "timestamp": 35.8, "round": 1, "planter": "Zekken", "site": "A"}
```

---

#### spike_defuse

**Description:** Spike defused by defending team.

**Fields:**
- `type`: `"spike_defuse"`
- `timestamp`: Float
- `round`: Integer (round number, 1-indexed)

**Optional fields:**
- `defuser`: String (player who defused)

**Example:**
```json
{"type": "spike_defuse", "timestamp": 95.3, "round": 2, "defuser": "Leo"}
```

---

### Phase 6 Additions

#### buy_phase

**Description:** Economy and loadout classification at round start (Phase 6 addition).

**Purpose:** Captures team economy state and spending patterns for feature engineering.

**Fields:**
- `type`: `"buy_phase"`
- `timestamp`: Float (typically same as or just before `round_start`)
- `round`: Integer (round number, 1-indexed)
- `team1_credits`: Integer (total credits for Team 1, null if OCR failed)
- `team2_credits`: Integer (total credits for Team 2, null if OCR failed)
- `team1_loadout_type`: String (loadout classification: `full_buy` | `half_buy` | `eco` | `force_buy` | `unknown`)
- `team2_loadout_type`: String (loadout classification, same values as team1)

**Loadout classification logic:**
- **full_buy**: 3+ players with rifles (Vandal/Phantom) + full armor
- **half_buy**: Mix of SMGs/Shotguns and rifles, partial armor
- **eco**: Majority on pistols/light armor (saving credits)
- **force_buy**: Full investment despite low economy (post-loss desperation)
- **unknown**: OCR failed to detect enough weapons/armor (requires 3/5 players detected)

**Notes:**
- Credit values are team totals (sum of 5 players)
- Null credits indicate OCR unreliability that round (detector requires 3/5 players visible)
- Emitted once per round during buy phase

**Example:**
```json
{"type": "buy_phase", "timestamp": 15.0, "round": 2, "team1_credits": 24000, "team2_credits": 3900, "team1_loadout_type": "full_buy", "team2_loadout_type": "eco"}
```

---

#### ult_usage

**Description:** Ultimate ability activation (Phase 6 addition).

**Purpose:** Track high-impact ability usage for round outcome prediction.

**Fields:**
- `type`: `"ult_usage"`
- `timestamp`: Float
- `round`: Integer (round number, 1-indexed)
- `player`: String (player name who used ultimate)
- `player_index`: Integer (0-9, player tracking ID)
- `agent`: String (agent name: Jett | Raze | Chamber | etc.)

**Detection method:** OCR on ultimate status indicator (X icon when active).

**Coverage:** Tracks all agents, but detection reliability varies by visual clarity.

**Example:**
```json
{"type": "ult_usage", "timestamp": 85.5, "round": 3, "player": "Demon1", "agent": "Jett", "player_index": 2}
```

---

#### timeout

**Description:** Tactical timeout called by a team (Phase 6 addition).

**Purpose:** Track strategic pauses that may affect subsequent round momentum.

**Fields:**
- `type`: `"timeout"`
- `timestamp`: Float
- `round`: Integer (round number when timeout called, 1-indexed)
- `team`: String (team name that called timeout)

**Detection method:** OCR on round number crop region (most reliable for overlay text).

**Notes:**
- Timeouts last 60 seconds in official VCT matches
- Teams get 1 timeout per half (2 total per map)
- De-duplicated via state tracking to avoid duplicate detections during timeout duration

**Example:**
```json
{"type": "timeout", "timestamp": 120.0, "round": 5, "team": "SEN"}
```

---

### Future Event Types

Valoscribe may emit additional event types in the future. The prediction model's Pydantic schemas use `extra='allow'` to preserve unknown fields for discovery and backward compatibility.

**Parser behavior for unknown types:**
- Unknown event types return base `ValoscribeEvent` class
- All fields preserved in `model_extra` dictionary
- No parse errors raised (graceful degradation)

---

## Game Mechanics Reference

### Economy System

**Starting credits:**
- Pistol round (R1): 800 credits per player
- All other rounds: Earned from previous rounds

**Income sources:**
- **Win bonus**: 3000 credits per player (winning team)
- **Loss bonus**: Escalates per consecutive loss (1900 → 2400 → 2900 → 2900 max)
- **Spike plant bonus**: 300 credits (attacking team, even if round lost)
- **Kill rewards**: Weapon-dependent (200 for rifles, 100 for SMGs, 150 for sidearms, etc.)

**Spending tiers:**
- **Rifles**: Vandal/Phantom = 2900 credits
- **SMG**: Spectre = 1600, Stinger = 950
- **Sidearm**: Sheriff = 800, Ghost = 500, Classic = 0 (free)
- **Armor**: Full = 1000 (50 armor), Light = 400 (25 armor)
- **Abilities**: Agent-specific, purchased in buy phase

---

### Side Mechanics

**Sides:**
- **Attack**: Plant spike on A/B/C site, win by detonation or elimination
- **Defense**: Prevent spike plant or defuse spike, win by elimination or time expiry

**Side swaps:**
- **Halftime**: Round 13 (teams swap sides)
- **Overtime**: Every 2 rounds (R25-26, R27-28, etc.)

**Starting sides:** Documented in `metadata.json` `starting_sides` field.

---

### Round Numbering

**Regulation:** Rounds 1-24 (first to 13 wins)
- Rounds 1-12: First half
- Rounds 13-24: Second half (sides swapped)

**Overtime:** Rounds 25+ (first to 2-round lead wins)
- Each team gets 5000 credits per OT round
- Sides swap every 2 rounds
- No win streak bonuses in OT (flat 5000 credits)

---

### Agent Roles

**4 roles in Valorant:**
- **Duelist**: Entry fraggers (Jett, Raze, Phoenix, Reyna, Yoru, Neon, Iso)
- **Initiator**: Info gatherers (Sova, Breach, Skye, KAY/O, Fade, Gekko)
- **Controller**: Smoke/block vision (Brimstone, Omen, Viper, Astra, Harbor, Clove)
- **Sentinel**: Defensive anchors (Sage, Cypher, Killjoy, Chamber, Deadlock, Vyse)

**Team composition:** Typically 1 of each role + 1 flex pick (meta-dependent).

---

## Data Quality Considerations

### OCR Reliability

**High reliability:**
- Kill events (95%+ accuracy on player names, weapons)
- Round scores (99%+ accuracy)
- Spike plant/defuse (90%+ accuracy when visible)

**Medium reliability:**
- Economy credits (70-80% accuracy, varies by visual clarity)
- Loadout classification (requires 3/5 players detected, ~75% coverage)
- Ultimate usage (80%+ accuracy, varies by agent UI)

**Low reliability:**
- Ability usage (not yet tracked, complex UI variations)
- Exact agent positions (not tracked, requires minimap OCR)

### Validation Checks

Valoscribe runs validation on each map (see `metadata.json` `validation_results`):

**Automatic checks:**
- Round count matches expected (12-13+ per half)
- Score progression is monotonic (never decreases)
- Event timestamps are chronological
- Player names consistent across events
- Team assignments consistent (no mid-map team swaps)

**Quality flags:**
- `status: "pass"`: All checks passed
- `status: "warning"`: Minor issues (missing optional fields, low OCR confidence)
- `status: "fail"`: Critical issues (score desync, missing rounds, corrupt data)

**Recommendation:** Exclude `status: "fail"` maps from training. Review `status: "warning"` maps manually.

---

## Usage in Prediction Model

### Loading Data

**Pydantic schemas:** `src/data/schemas.py` defines typed models for all event types.

**Parser:** `parse_event(raw_json)` dispatches to appropriate subclass based on `type` field.

**Loader:** `src/data/loaders.py` provides `MapDataLoader` for end-to-end parsing.

### Feature Engineering

**Temporal features:**
- Use `frames.csv` for time-series data (alive counts, timers, ult charge)
- Walk-forward windows (last N seconds) for rolling aggregates

**Event-based features:**
- Aggregate `kill` events for K/D ratios, first blood rates
- Use `buy_phase` events for economy differential features
- Track `ult_usage` for ability usage rates per agent/team

**Round-level features:**
- Sequence `round_end` events for win/loss streaks, momentum
- Use `sides` field for attack/defense performance splits
- Combine with `buy_phase` for economy-adjusted win rates

### Validation Protocol

**Walk-forward splits only:**
- NEVER shuffle or randomly split match data
- Train on maps 1 to N, validate on map N+1
- Temporal ordering critical for realistic backtesting

**Cross-validation:**
- Group by tournament/event (avoid data leakage from same teams)
- Use `metadata.json` `date` field for chronological splits

---

## Changelog

**Phase 6 (2026-02-13):**
- Added `buy_phase` event type (economy + loadout classification)
- Added `ult_usage` event type (ultimate ability tracking)
- Added `timeout` event type (tactical timeout tracking)
- Added `sides` field to `round_start` and `round_end` events (explicit attack/defense tracking)
- Standardized filenames: `events.jsonl`, `frames.csv`, `metadata.json`

**Phase 5 (2026-02-12):**
- Initial schema documentation
- Core event types: `kill`, `round_start`, `round_end`, `spike_plant`, `spike_defuse`
- Pydantic models with `extra='allow'` for discovery phase
- Basic metadata and frames format
