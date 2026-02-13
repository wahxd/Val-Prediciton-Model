# Valorant Match Prediction Model

## Project Overview
Prediction model for VCT match outcomes (map winner + match winner) trained on
Valoscribe event data. Goal: identify edge against Polymarket prices.

## Tech Stack
- Python 3.x (scikit-learn, pandas, numpy, XGBoost, Optuna)
- Valoscribe (D:\Git\valoscribe) -- actively developed alongside this repo
- GSD planning workflow in .planning/

## Key Data Formats

### Valoscribe JSONL Events (D:\Git\valoscribe\data\processed\{map_id}\events.jsonl)
Each line is a JSON object with fields:
- `type`: "kill" | "round_start" | "round_end" | "spike_plant" | "spike_defuse" | etc.
- `timestamp`: float (seconds from video start)
- `round`: int (1-indexed round number)
- For kills: `killer`, `victim`, `weapon`, `killer_team`, `victim_team`
- For round events: `winning_team`, `score_team1`, `score_team2`

### Valoscribe CSV Frames (D:\Git\valoscribe\data\processed\{map_id}\frames.csv)
Per-frame state snapshots: timestamp, team1_alive, team2_alive, score, spike_status, timer

### Valoscribe JSON Metadata (D:\Git\valoscribe\data\processed\{map_id}\metadata.json)
Map-level info: teams, map_name, date, agents, validation_results

## Valorant Game Mechanics (Relevant for Feature Engineering)
- Economy: pistol round ($800), loss bonus escalates ($1900/$2400/$2900/$2900),
  win bonus ($3000), spike plant bonus ($300 each), kill rewards vary by weapon
- Sides: Attacker/Defender, swap at half (round 13), OT alternates every 2 rounds
- Win condition: First to 13 rounds (24 rounds regulation), OT is first to 2 ahead
- Agents: 4 roles (Duelist, Initiator, Controller, Sentinel), 1 each + flex

## Conventions
- Temporal ordering: NEVER shuffle or randomly split match data. Always walk-forward.
- Primary metric: log loss (calibration matters for betting)
- Feature sets: Named in a registry (e.g., "baseline_5"), experiments reference names
- Quality threshold: Maps below quality score X are excluded from training
- Valoscribe (D:\Git\valoscribe) is actively developed alongside this repo. ReplayDetector lives in Valoscribe (single source of truth), ported from Phase 1

## Current Phase
Check .planning/STATE.md for current position in the v2 roadmap.
