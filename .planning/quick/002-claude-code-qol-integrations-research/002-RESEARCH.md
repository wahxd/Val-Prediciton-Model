# Claude Code QoL Integrations Research

## Executive Summary

Research into the MCP server ecosystem, community resources, and Claude Code configuration opportunities for this Valorant Match Prediction Model project. Key findings:

- **DuckDB MCP Server** is the highest-value integration: load Valoscribe JSONL/CSV into DuckDB for SQL-based data analysis directly from Claude Code, eliminating manual pandas wrangling during data pipeline development (Phases 5-8)
- **Jupyter MCP Server** enables interactive notebook-based ML experimentation with real-time cell execution, critical for Phases 8-10 (feature engineering, model training, evaluation)
- **Context7 MCP Server** provides up-to-date library documentation for scikit-learn, pandas, XGBoost, and Optuna -- preventing hallucinated API calls during model development
- **A CLAUDE.md file** is the single biggest zero-cost improvement: encoding Valoscribe data formats, Valorant game mechanics, and project conventions eliminates repeated context-setting across sessions
- **OP.GG MCP Server** provides real-time Valorant agent statistics and map compositions that could supplement training features

---

## 1. MCP Server Integrations

### 1.1 Recommended (High Value)

#### 1. DuckDB MCP Server

- **What**: SQL interface to local DuckDB databases; can natively read JSONL, CSV, and Parquet files
- **Why for this project**: Valoscribe outputs JSONL events and CSV frames for 71+ maps. DuckDB can query these files directly with SQL (`SELECT * FROM read_json_auto('events.jsonl')`) without any ETL. During Phase 5 (Data Pipeline & Validation), this lets Claude Code run analytical queries over the entire dataset -- count events per map, check kill distributions, validate round progressions, compute quality scores -- all via SQL rather than writing throwaway Python scripts. DuckDB's columnar engine handles analytical queries on 71 maps (roughly 40K-60K events) in milliseconds.
- **Install**:
  ```json
  // Add to .claude/settings.local.json under "mcpServers"
  {
    "mcpServers": {
      "duckdb": {
        "command": "uvx",
        "args": [
          "mcp-server-duckdb",
          "--db-path",
          "D:/Git/Val-Prediciton-Model/data/analysis.db"
        ]
      }
    }
  }
  ```
  Prerequisite: `uv` must be installed (`pip install uv` or via installer).
- **Effort**: 5 min setup
- **Value**: **High** -- Directly accelerates Phase 5 data audit and Phase 8 feature engineering. DuckDB can also read Parquet (useful if we convert Valoscribe output for faster loading). The read-only mode (`--readonly`) prevents accidental data modification.
- **Repo**: https://github.com/ktanaka101/mcp-server-duckdb (Python, PyPI: `mcp-server-duckdb`)

---

#### 2. Jupyter MCP Server

- **What**: Real-time control of Jupyter Notebooks from Claude Code -- create, read, execute cells, view outputs including plots and images
- **Why for this project**: Phases 8-10 are heavily ML-experimental: feature engineering, model training (logistic regression, XGBoost), hyperparameter tuning (Optuna), calibration curves, SHAP analysis. Jupyter notebooks are the natural environment for this. With the Jupyter MCP, Claude Code can create notebooks, write and execute cells, see matplotlib/SHAP plots inline, and iterate on experiments -- all while maintaining a persistent kernel with loaded data. This is dramatically faster than writing standalone Python scripts for each experiment.
- **Install**:
  ```json
  {
    "mcpServers": {
      "jupyter": {
        "command": "uvx",
        "args": ["jupyter-mcp-server"],
        "env": {
          "JUPYTER_URL": "http://localhost:8888",
          "JUPYTER_TOKEN": "YOUR_TOKEN"
        }
      }
    }
  }
  ```
  Prerequisite: Run `jupyter lab --port 8888 --IdentityProvider.token=YOUR_TOKEN` in a separate terminal. Install via `pip install jupyter-mcp-server`.
- **Effort**: 15 min (install + configure + verify)
- **Value**: **High** -- Essential for ML experimentation phases. Supports multimodal output (plots, tables), multi-notebook management, and smart execution with error feedback. The persistent kernel means loaded DataFrames persist between Claude Code interactions.
- **Repo**: https://github.com/datalayer/jupyter-mcp-server (Python, PyPI: `jupyter-mcp-server`, 3.8K+ stars)

---

#### 3. Context7 MCP Server

- **What**: Provides up-to-date documentation for popular libraries directly to Claude Code, preventing outdated/hallucinated API usage
- **Why for this project**: This project uses scikit-learn, pandas, numpy, XGBoost, Optuna, matplotlib, and SHAP. These libraries update frequently (sklearn 1.5+ has breaking changes). Context7 pulls current documentation so Claude Code generates correct API calls -- critical when writing sklearn Pipeline configs, Optuna objective functions, or SHAP TreeExplainer calls.
- **Install**:
  ```json
  {
    "mcpServers": {
      "context7": {
        "command": "npx",
        "args": ["-y", "@upstash/context7-mcp@latest"]
      }
    }
  }
  ```
  Prerequisite: Node.js/npm installed.
- **Effort**: 5 min
- **Value**: **High** -- Prevents subtle bugs from outdated API usage. Particularly valuable for less-common library features (Optuna's TPESampler, SHAP's force_plot, sklearn's calibration_curve). Zero ongoing maintenance.
- **Repo**: https://github.com/upstash/context7 (TypeScript, npm: `@upstash/context7-mcp`, 11K+ stars)

---

#### 4. Sequential Thinking MCP Server

- **What**: Structured step-by-step problem-solving tool that enables Claude to break down complex problems, revise thinking, and branch into alternative approaches
- **Why for this project**: Several phases involve complex analytical decisions: quality scoring heuristics (Phase 5), economy reconstruction algorithms (Phase 8), walk-forward validation design (Phase 9), and hyperparameter search space definition (Phase 10). Sequential Thinking helps Claude reason through these multi-step problems systematically rather than generating a single-shot answer.
- **Install**:
  ```json
  {
    "mcpServers": {
      "sequential-thinking": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
      }
    }
  }
  ```
- **Effort**: 5 min
- **Value**: **High** -- Zero cost, improves reasoning quality on complex analytical tasks. Official MCP reference server, well-maintained.
- **Repo**: https://github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking

---

### 1.2 Worth Considering (Medium Value)

#### 5. Memory (Knowledge Graph) MCP Server

- **What**: Persistent knowledge graph that stores entities, relations, and observations across sessions
- **Why for this project**: Could store learned facts about Valoscribe data format, Valorant game mechanics (economy rules, agent abilities), map characteristics, and team performance patterns. Persists across Claude Code sessions without needing to re-read project files.
- **Install**:
  ```json
  {
    "mcpServers": {
      "memory": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-memory"]
      }
    }
  }
  ```
- **Effort**: 5 min setup, but requires deliberate seeding with project knowledge
- **Value**: **Medium** -- Useful for cross-session memory, but CLAUDE.md + STATE.md from GSD already provide good session continuity. Best value comes later when the project has many learned facts about data patterns.
- **Repo**: https://github.com/modelcontextprotocol/servers/tree/main/src/memory

---

#### 6. Fetch MCP Server

- **What**: Fetches web content and converts to markdown for LLM consumption
- **Why for this project**: Useful for looking up Valorant patch notes (game mechanic changes), VCT tournament schedules, Polymarket contract specifications, and ML technique papers. Already partially covered by Claude Code's built-in web tools, but the MCP version provides more control (pagination, raw mode).
- **Install**:
  ```json
  {
    "mcpServers": {
      "fetch": {
        "command": "uvx",
        "args": ["mcp-server-fetch"]
      }
    }
  }
  ```
- **Effort**: 5 min
- **Value**: **Medium** -- Incremental improvement over built-in capabilities. Most useful during research tasks.
- **Repo**: https://github.com/modelcontextprotocol/servers/tree/main/src/fetch

---

#### 7. OP.GG MCP Server (Valorant Data)

- **What**: Access to OP.GG's gaming data APIs including Valorant agent statistics, agent compositions per map, and meta analysis
- **Why for this project**: Could supplement features with meta-level data: which agent compositions are currently strong on each map, agent pick/win rates by map. This is external signal that goes beyond what Valoscribe extracts from VODs. Could be valuable for Phase 8 feature engineering.
- **Install**: Remote MCP server (Streamable HTTP):
  ```json
  {
    "mcpServers": {
      "opgg": {
        "type": "http",
        "url": "https://mcp-api.op.gg/mcp"
      }
    }
  }
  ```
  Note: Claude Code may not support remote HTTP MCP servers yet. Check Claude Code version. Alternative: use their API directly in Python code.
- **Effort**: 5 min (if remote MCP supported) / 30 min (if wrapping API manually)
- **Value**: **Medium** -- Provides external Valorant meta data. Key tools: `valorant_list_agent_statistics`, `valorant_list_agent_compositions_for_map`. Requires `desired_output_fields` parameter for efficient responses.
- **Repo**: https://github.com/opgginc/opgg-mcp

---

#### 8. Zaturn (Data Analytics MCP)

- **What**: Multi-source data analytics MCP that connects to SQL databases, CSV, Parquet files; runs SQL queries and generates visualizations
- **Why for this project**: Combines DuckDB-like SQL capabilities with built-in visualization (scatter plots, histograms, bar plots). Could be a one-stop solution for data exploration during Phases 5 and 8.
- **Install**:
  ```json
  {
    "mcpServers": {
      "zaturn": {
        "command": "uvx",
        "args": ["zaturn"]
      }
    }
  }
  ```
- **Effort**: 10 min
- **Value**: **Medium** -- Overlaps significantly with DuckDB MCP + Jupyter MCP combination. Choose this if you want a single simpler tool instead of two separate ones. Roadmap includes ML features.
- **Repo**: https://github.com/kdqed/zaturn (Python, PyPI: `zaturn`)

---

#### 9. Vizro MCP (Data Visualization)

- **What**: McKinsey's data charting MCP server for creating validated, maintainable data charts and dashboards
- **Why for this project**: Could generate calibration curves, feature importance charts, and model comparison dashboards during Phases 9-10. More polished output than raw matplotlib.
- **Install**:
  ```json
  {
    "mcpServers": {
      "vizro-mcp": {
        "command": "uvx",
        "args": ["vizro-mcp"]
      }
    }
  }
  ```
- **Effort**: 10 min
- **Value**: **Medium** -- Nice for presentation-quality charts, but Jupyter + matplotlib covers the core need. Best value if you want shareable dashboards.
- **Repo**: https://github.com/mckinsey/vizro/tree/main/vizro-mcp (Python, PyPI: `vizro-mcp`)

---

### 1.3 Not Recommended for This Project

#### Filesystem MCP Server
- **What**: File read/write/search/move operations
- **Why not**: Claude Code already has built-in filesystem access that is more capable and better integrated. Adding this MCP server would create redundant tools and tool-selection confusion.
- **Repo**: https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem

#### Git MCP Server (reference)
- **What**: Git repository operations (log, diff, blame, search)
- **Why not**: Claude Code already has excellent built-in Git support via Bash tool. The GSD skill system also manages commits. Adding a Git MCP would duplicate functionality.
- **Repo**: https://github.com/modelcontextprotocol/servers/tree/main/src/git

#### GitHub MCP Server
- **What**: Full GitHub API integration (issues, PRs, Actions, code search)
- **Why not**: This project is local-first. We use `gh` CLI for GitHub operations when needed. The GitHub MCP Server adds complexity for functionality we rarely use. Could reconsider if the project moves to collaborative development.
- **Repo**: https://github.com/github/github-mcp-server

#### SQLite MCP Server (reference/archived)
- **What**: SQLite database operations
- **Why not**: DuckDB MCP is strictly better for analytical workloads on JSONL/CSV data. SQLite MCP is oriented toward transactional databases, not data analysis.
- **Repo**: https://github.com/modelcontextprotocol/servers-archived/tree/main/src/sqlite

#### Brave Search MCP Server
- **What**: Web search, local search, news, image, and video search via Brave API
- **Why not**: Requires Brave API key (paid for full features). Claude Code's built-in WebSearch and the simpler Fetch MCP cover our needs. We are not search-heavy enough to justify the API cost.
- **Repo**: https://github.com/brave/brave-search-mcp-server

#### Python REPL / Code Execution Sandboxes
- **What**: Various MCP servers for running Python in sandboxed environments
- **Why not**: Claude Code already executes Python via Bash. Jupyter MCP is the better choice for interactive execution because it maintains kernel state. Standalone sandbox MCPs add complexity without clear benefit.
- **Examples**: pydantic-ai/mcp-run-python, yepcode/mcp-server-js

---

## 2. Community Resources

### 2.1 Key Repos

#### awesome-mcp-servers
- **URL**: https://github.com/punkpeye/awesome-mcp-servers (50K+ stars)
- **What**: The definitive community-curated list of MCP servers, organized by category. Includes Data Science Tools, Databases, Gaming, Sports, and other categories relevant to this project.
- **Why useful**: First place to check when looking for new MCP integrations. Categories like "Data Science Tools" and "Databases" are directly relevant. Updated frequently.

#### Official MCP Servers (Reference Implementations)
- **URL**: https://github.com/modelcontextprotocol/servers
- **What**: Official reference implementations maintained by the MCP steering group. Includes Filesystem, Fetch, Git, Memory, Sequential Thinking, and Time servers.
- **Why useful**: These are the most stable, best-documented MCP servers. The README now points to the MCP Registry (https://registry.modelcontextprotocol.io/) as the canonical place to browse published servers.

#### MCP Registry
- **URL**: https://registry.modelcontextprotocol.io/
- **What**: The official registry of published MCP servers, searchable and browsable
- **Why useful**: Canonical source for discovering new MCP servers. Better than browsing GitHub repos individually.

### 2.2 Plugin/Extension Ecosystem

#### Skill-Cortex Server
- **URL**: https://github.com/Sim-xia/skill-cortex-server
- **What**: MCP server that indexes SKILL.md files and provides skill discovery, search, and retrieval for Claude Code. Supports `~/.claude/skills/` directory.
- **Why useful**: If we create custom Claude Code skills (quality audit, Valoscribe status check), Skill-Cortex can make them discoverable across sessions. Works with hierarchical skill organization.
- **Relevance**: Medium -- only useful after we have several custom skills.

#### ViperJuice MCP Gateway
- **URL**: https://github.com/ViperJuice/mcp-gateway
- **What**: Meta-server that reduces Claude Code tool bloat by exposing 9 meta-tools and dynamically provisioning 25+ MCP servers on demand
- **Why useful**: If we end up with many MCP servers configured, this prevents tool-list overwhelm. Progressive disclosure: only loads servers when needed.
- **Relevance**: Low now, but worth knowing about if the MCP setup grows.

#### GSD Skill System (Already Installed)
- **URL**: Already active in this project at `~/.claude/get-shit-done/`
- **What**: Planning, execution, and summary workflow for structured project delivery
- **Why useful**: Already providing value. The research question is how to complement it with MCP servers and CLAUDE.md content.

### 2.3 Data Science Specific

#### Fermat MCP (Math Engine)
- **URL**: https://github.com/abhiphile/fermat-mcp
- **What**: Unified math engine combining SymPy, NumPy, and Matplotlib in one MCP server
- **Why useful**: Could help with mathematical verification of economy reconstruction formulas, combinatorial series probability calculations (BO3/BO5), and quick statistical computations.

#### Label Studio MCP (Data Labeling)
- **URL**: https://github.com/HumanSignal/label-studio-mcp-server
- **What**: Official MCP for Label Studio data labeling platform
- **Why useful**: Not directly applicable now, but could be relevant if we need to manually label edge cases in Valoscribe's output (disputed kills, ambiguous round outcomes).

---

## 3. Custom Skills & Configuration

### 3.1 CLAUDE.md Recommendations

A CLAUDE.md file at the project root is the single most impactful zero-cost improvement. It persists across sessions and tells Claude exactly how to work with this project.

**Recommended CLAUDE.md content:**

```markdown
# Valorant Match Prediction Model

## Project Overview
Prediction model for VCT match outcomes (map winner + match winner) trained on
Valoscribe event data. Goal: identify edge against Polymarket prices.

## Tech Stack
- Python 3.x (scikit-learn, pandas, numpy, XGBoost, Optuna)
- Valoscribe (external dep at D:\Git\valoscribe) -- DO NOT modify
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
- Valoscribe is READ-ONLY: consume its output, never modify its code or data

## Current Phase
Check .planning/STATE.md for current position in the v2 roadmap.
```

- **Effort**: 15 min to write and refine
- **Value**: **Very High** -- Prevents Claude from making incorrect assumptions about data formats, game mechanics, and project conventions. Saves 2-3 minutes per session in context setting.

### 3.2 Custom Workflow Opportunities

#### Quality Audit Skill
A custom slash command or GSD skill that runs a standardized quality audit on a specific map's data:
```
/audit-map <map_id>
  1. Load events.jsonl for the map
  2. Check: kill count vs expected (20-50 per map), round progression (monotonic scores)
  3. Check: round_start/round_end balance, spike events only during rounds
  4. Check: alive counts never exceed 5, timer values in valid range
  5. Output: quality score + specific issues found
```
- **Effort**: 30 min to implement as a GSD skill
- **Value**: **High** -- Standardizes the Phase 5 audit process. Reusable across all 71+ maps.

#### Valoscribe Status Check Skill
A skill to check the status of ongoing VOD processing:
```
/vod-status
  1. List processed maps in D:\Git\valoscribe\data\processed\
  2. List in-progress maps in D:\Git\valoscribe\data\raw\ (not yet processed)
  3. Show: total maps, recently completed, estimated remaining time
```
- **Effort**: 15 min
- **Value**: **Medium** -- Useful during Phase 7 (Dataset Expansion) to track background VOD processing.

#### Experiment Tracker Skill
A skill to log ML experiments consistently:
```
/log-experiment
  1. Record: feature_set, model_type, hyperparameters
  2. Record: log_loss, brier_score, accuracy, calibration_error
  3. Record: training_maps_count, test_maps, date
  4. Append to experiments.jsonl
  5. Compare with previous experiments
```
- **Effort**: 30 min
- **Value**: **High** -- Essential for Phase 9-10 to track experiment results systematically. Could also be a simple Python script that the Jupyter MCP runs.

### 3.3 Settings Improvements

The current `.claude/settings.local.json` only has basic bash permissions. Recommended improvements:

```json
{
  "permissions": {
    "allow": [
      "Bash(grep:*)",
      "Bash(wc:*)",
      "Bash(git add:*)",
      "Bash(git commit:*)",
      "Bash(git status:*)",
      "Bash(git log:*)",
      "Bash(git diff:*)",
      "Bash(python:*)",
      "Bash(pip:*)",
      "Bash(uv:*)",
      "Bash(uvx:*)",
      "Bash(pytest:*)",
      "Bash(jupyter:*)",
      "Bash(ls:*)",
      "Bash(mkdir:*)",
      "Bash(cp:*)",
      "Bash(mv:*)",
      "Bash(cat:*)",
      "Bash(head:*)",
      "Bash(tail:*)",
      "Bash(find:*)",
      "Bash(du:*)",
      "Bash(gh:*)"
    ]
  },
  "mcpServers": {
    "duckdb": {
      "command": "uvx",
      "args": ["mcp-server-duckdb", "--db-path", "D:/Git/Val-Prediciton-Model/data/analysis.db"]
    },
    "sequential-thinking": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
    },
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp@latest"]
    }
  }
}
```

Key additions:
- **python/pytest**: Allows running Python scripts and tests without permission prompts
- **uv/uvx**: Package management for MCP servers and Python dependencies
- **jupyter**: Launching Jupyter servers
- **gh**: GitHub CLI for PR management
- **File operations**: ls, mkdir, cp, mv for project file management
- **MCP servers**: Top 3 recommended servers pre-configured

- **Effort**: 5 min
- **Value**: **High** -- Eliminates constant permission prompts that interrupt flow. The permission list is still restrictive (no `rm -rf`, no `curl` to arbitrary URLs).

### 3.4 Memory/Context Patterns

For maintaining project knowledge across sessions, there are three complementary approaches:

1. **CLAUDE.md** (Static Knowledge)
   - Data formats, game mechanics, conventions
   - Loaded automatically every session
   - Update manually when conventions change

2. **STATE.md from GSD** (Dynamic Position)
   - Current phase, decisions, blockers
   - Updated after each plan execution
   - Loaded when using GSD commands

3. **Memory MCP Server** (Learned Facts)
   - Patterns discovered during data analysis
   - Team-specific insights (e.g., "Team X has 70% pistol round win rate")
   - Data quality patterns (e.g., "Maps from Day 3 of Champions have lower validation rates")
   - Grows organically during development

Best pattern: Start with CLAUDE.md + STATE.md (already have STATE.md). Add Memory MCP later when there are enough learned facts to justify it.

---

## 4. Implementation Roadmap

Prioritized by value and effort. Set up in this order:

### Wave 1: Immediate (Today, 15 minutes total)

| Step | What | Command | Time |
|------|------|---------|------|
| 1 | Create CLAUDE.md | Write file at project root with content from Section 3.1 | 5 min |
| 2 | Update settings.local.json | Add permissions + MCP servers from Section 3.3 | 5 min |
| 3 | Install uv (if not present) | `pip install uv` or `powershell -c "irm https://astral.sh/uv/install.ps1 \| iex"` | 2 min |
| 4 | Verify Sequential Thinking | Restart Claude Code, confirm server loads | 3 min |

### Wave 2: Before Phase 5 (30 minutes)

| Step | What | Command | Time |
|------|------|---------|------|
| 5 | Verify DuckDB MCP | Open Claude Code, ask it to query a Valoscribe JSONL file via DuckDB | 5 min |
| 6 | Verify Context7 | Ask Claude Code to look up a scikit-learn API using Context7 | 5 min |
| 7 | Create quality audit skill | Implement /audit-map as described in Section 3.2 | 20 min |

### Wave 3: Before Phase 8 (30 minutes)

| Step | What | Command | Time |
|------|------|---------|------|
| 8 | Install Jupyter MCP | `pip install jupyter-mcp-server` + configure | 10 min |
| 9 | Create experiment tracker | Implement /log-experiment skill or Python script | 20 min |

### Wave 4: Ongoing (As Needed)

| Step | What | When | Time |
|------|------|------|------|
| 10 | Add Memory MCP | After Phase 5 data audit reveals patterns worth persisting | 10 min |
| 11 | Try OP.GG MCP | During Phase 8 feature engineering for agent meta data | 10 min |
| 12 | Add Zaturn or Vizro MCP | If need better visualization during Phase 9-10 evaluation | 10 min |

**Total investment**: ~1.5 hours across all waves, spread over the project timeline.

**Expected ROI**: 3-5 minutes saved per Claude Code session from CLAUDE.md alone. DuckDB and Jupyter MCP eliminate multiple manual workflows per phase. Conservative estimate: 2-4 hours saved across v2 development.

---

## 5. Reference Links

### Official MCP Resources
- MCP Specification: https://modelcontextprotocol.io/
- MCP Registry: https://registry.modelcontextprotocol.io/
- Official Reference Servers: https://github.com/modelcontextprotocol/servers
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- MCP TypeScript SDK: https://github.com/modelcontextprotocol/typescript-sdk

### Recommended MCP Servers (Repos)
- DuckDB MCP: https://github.com/ktanaka101/mcp-server-duckdb
- Jupyter MCP: https://github.com/datalayer/jupyter-mcp-server
- Context7 MCP: https://github.com/upstash/context7
- Sequential Thinking MCP: https://github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking
- Memory MCP: https://github.com/modelcontextprotocol/servers/tree/main/src/memory
- Fetch MCP: https://github.com/modelcontextprotocol/servers/tree/main/src/fetch
- OP.GG MCP: https://github.com/opgginc/opgg-mcp
- Zaturn: https://github.com/kdqed/zaturn
- Vizro MCP: https://github.com/mckinsey/vizro/tree/main/vizro-mcp

### Community Directories
- Awesome MCP Servers: https://github.com/punkpeye/awesome-mcp-servers
- Glama MCP Directory: https://glama.ai/mcp/servers
- Smithery (MCP installer): https://smithery.ai/

### Claude Code Configuration
- Claude Code MCP docs: https://docs.anthropic.com/en/docs/claude-code/mcp
- Skill-Cortex (skills indexer): https://github.com/Sim-xia/skill-cortex-server
- MCP Gateway (tool bloat reducer): https://github.com/ViperJuice/mcp-gateway

### Valorant/Esports Data
- OP.GG Valorant: https://www.op.gg/valorant
- Henrik's Valorant API (unofficial): https://docs.henrikdev.xyz/valorant
- VLR.gg (esports data): https://vlr.gg
- Riot Games Valorant API (official): https://developer.riotgames.com/apis#val-match-v1

### Tools Referenced
- uv (Python package manager): https://docs.astral.sh/uv/
- DuckDB: https://duckdb.org/
- Jupyter: https://jupyter.org/
