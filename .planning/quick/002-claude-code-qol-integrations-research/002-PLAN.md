---
phase: quick
plan: 002
type: execute
wave: 1
depends_on: []
files_modified:
  - .planning/quick/002-claude-code-qol-integrations-research/002-RESEARCH.md
autonomous: true

must_haves:
  truths:
    - "MCP server landscape for data/ML/testing workflows is documented with install commands"
    - "Community repos and plugins relevant to Python ML projects are catalogued"
    - "Custom skill opportunities specific to this project's bottlenecks are identified"
    - "Each recommendation has a clear effort-vs-value assessment"
  artifacts:
    - path: ".planning/quick/002-claude-code-qol-integrations-research/002-RESEARCH.md"
      provides: "Comprehensive analysis of Claude Code QoL integrations"
      min_lines: 150
---

<objective>
Research and document Claude Code quality-of-life integrations that would accelerate development of this Valorant prediction model project.

Purpose: Identify MCP servers, plugins, custom skills, and community resources that can improve the development workflow — particularly around data pipeline testing, VOD verification, ML experiment tracking, and reducing manual overhead in the 6-phase v2 roadmap.

Output: A single comprehensive research document (002-RESEARCH.md) with actionable recommendations organized by category, each with install/setup instructions and effort-vs-value assessment.
</objective>

<execution_context>
@D:\Git\Val-Prediciton-Model\.claude\settings.local.json
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Research MCP servers and community integrations</name>
  <files>.planning/quick/002-claude-code-qol-integrations-research/002-RESEARCH.md</files>
  <action>
Research Claude Code ecosystem integrations across these dimensions, then synthesize into a single comprehensive document:

**A) MCP Server Integrations (primary focus)**

Research available MCP servers that would be useful for this project's workflow. For each, document: what it does, how to install (npm/npx command), and why it matters for this project. Categories to investigate:

1. **Filesystem/Data MCP servers** — servers that help with reading/analyzing JSONL, CSV, JSON files (the Valoscribe output formats). Look for: filesystem server, SQLite server (could we load JSONL into SQLite for querying?), any data-analysis-focused servers.

2. **Git/GitHub MCP servers** — servers for PR workflows, issue tracking, repo management. The project uses git heavily with GSD planning workflow.

3. **Web research MCP servers** — servers like Brave Search, Fetch, or similar that enable better web research from within Claude Code (useful for looking up Valorant game mechanics, esports APIs, ML techniques).

4. **Python/Jupyter MCP servers** — servers that help with Python development, notebook execution, or ML experiment workflows. Look for: Jupyter server, Python REPL server, any ML-focused servers.

5. **Testing/Validation MCP servers** — servers that help with test execution, coverage, or data validation workflows.

6. **Monitoring/Logging MCP servers** — servers for tracking long-running processes (relevant for 20-40 min VOD processing pipeline).

**B) Community Repos and Plugins**

Search for:
1. GitHub repos that implement Claude Code MCP server collections or "awesome-mcp" lists
2. Any Claude Code plugins or extensions beyond MCP (slash commands, custom tools)
3. Repos implementing MCP servers specifically for data science / ML workflows
4. Any Valorant/esports data API wrappers that could be useful

**C) Custom Skills / CLAUDE.md Opportunities**

Based on THIS project's specific needs, identify areas where custom Claude Code configuration would help:
1. CLAUDE.md content — project-specific instructions that would improve Claude's responses (Valoscribe data format knowledge, Valorant game mechanics, v2 roadmap awareness)
2. Custom slash commands or GSD skill extensions — workflows specific to this project (e.g., "run quality audit on map X", "check Valoscribe processing status")
3. Settings.local.json improvements — permissions, environment variables, tool configurations
4. Memory/context patterns — how to structure project knowledge so Claude retains it across sessions

**D) Online Repos Implementing These**

For each category above, find 2-3 real GitHub repos that demonstrate the integration in practice. Prioritize repos that:
- Are for Python/ML projects
- Show actual MCP server configuration (not just docs)
- Have recent activity (2025-2026)
- Include setup instructions

**Research approach:**
- Use WebFetch to check the official MCP server registry/docs
- Use WebFetch to search GitHub for "awesome-mcp", "claude-code mcp", "mcp server python", "mcp server data science"
- Use WebFetch to check Anthropic's official MCP documentation for latest server list
- Use WebFetch to search for community blog posts about Claude Code MCP setups for ML/data projects

**Document structure for 002-RESEARCH.md:**

```
# Claude Code QoL Integrations Research

## Executive Summary
[3-5 bullet points of top recommendations]

## 1. MCP Server Integrations
### 1.1 Recommended (High Value)
[Servers worth setting up immediately]
### 1.2 Worth Considering (Medium Value)
[Servers to add as project grows]
### 1.3 Not Recommended for This Project
[Servers that exist but don't fit our needs, with reason]

## 2. Community Resources
### 2.1 Key Repos
### 2.2 Plugin/Extension Ecosystem

## 3. Custom Skills & Configuration
### 3.1 CLAUDE.md Recommendations
### 3.2 Custom Workflow Opportunities
### 3.3 Settings Improvements

## 4. Implementation Roadmap
[Prioritized list: what to set up first, second, third]
[Each with install command and estimated setup time]

## 5. Reference Links
[All URLs consulted during research]
```

For each recommendation, include:
- **What**: One-line description
- **Why for this project**: Specific benefit tied to our workflow
- **Install**: Exact command or configuration snippet
- **Effort**: Setup time estimate (5 min / 15 min / 30 min / 1 hour)
- **Value**: High / Medium / Low with justification
  </action>
  <verify>
    - File exists at .planning/quick/002-claude-code-qol-integrations-research/002-RESEARCH.md
    - Document has all 5 major sections (MCP Servers, Community Resources, Custom Skills, Implementation Roadmap, Reference Links)
    - At least 5 specific MCP servers evaluated with install commands
    - At least 3 community repos referenced with URLs
    - At least 3 custom skill/CLAUDE.md recommendations specific to this project
    - Implementation roadmap has prioritized steps with effort estimates
    - Document is at least 150 lines
  </verify>
  <done>
    A comprehensive, actionable research document exists that covers the full Claude Code integration landscape relevant to this Valorant prediction model project, with specific install commands and prioritized recommendations the user can act on immediately.
  </done>
</task>

</tasks>

<verification>
- 002-RESEARCH.md exists and is well-structured with all sections
- Recommendations are specific to THIS project (not generic "use MCP" advice)
- Install commands are copy-pasteable
- Effort-vs-value assessments help prioritize what to set up first
</verification>

<success_criteria>
User can read the document and within 30 minutes set up the top 3 recommended integrations. Every recommendation ties back to a specific pain point or workflow in the v2 prediction model roadmap.
</success_criteria>

<output>
After completion, the research document lives at:
`.planning/quick/002-claude-code-qol-integrations-research/002-RESEARCH.md`
</output>
