# Phase 11: Repo Cleanup & Organization - Research

**Researched:** 2026-02-14
**Domain:** Python project refactoring, codebase reorganization, safe code deletion
**Confidence:** HIGH

## Summary

This phase reorganizes the codebase from a 71-map research prototype to a production-ready structure capable of scaling to 150+ maps. The research confirms that the planned changes align with Python packaging best practices and machine learning project organization standards. The key challenges are safe code deletion (1,485 LOC of v1 code preserved at git tag v2.0), module boundary clarification (splitting `src/scraping/` into `src/scraping/` and `src/pipeline/`), configuration centralization (4 separate config files → unified `src/config/` package), and experiment organization (grouping v2 baseline experiments for Phase 14 comparison).

The src/ layout (source code in dedicated directory) is the industry-recommended approach for installable Python packages and prevents import issues during development. Configuration centralization via grouped modules (domain-specific config files under a single package) is standard practice for multi-domain projects. Machine learning experiments should separate smoke tests from real results, with processed data staying in a flat structure when data loaders and walk-forward CV depend on it.

**Primary recommendation:** Follow the planned structure (6 packages: config, data, features, modeling, pipeline, scraping), delete v1 code safely via git rm (already preserved at v2.0 tag), update import paths in affected files (2 scripts to delete, VLR scraper to update), centralize config with domain-specific modules, and archive experiments by milestone.

## Standard Stack

No external libraries required for cleanup operations. All work uses built-in Python, git, and filesystem tools.

### Core Tools
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| git | 2.x | Safe deletion, history preservation | Industry standard for version control |
| Python stdlib | 3.x | File operations, module reorganization | Built-in, no dependencies |
| pytest | - | Test discovery after reorganization | Already in project, standard Python testing |

### Not Required
| Tool | Why Not Needed |
|------|---------------|
| git-filter-repo | Only needed for rewriting history (secrets purge); we're doing forward deletions |
| Black/isort | Code formatting tools; no code logic changes in this phase |
| PyCharm/VSCode refactoring | Manual updates are safer for 2 files (scripts that are being deleted anyway) |

## Architecture Patterns

### Recommended Project Structure (Post-Cleanup)

```
Val-Prediciton-Model/
├── src/
│   ├── config/           # NEW: Centralized configuration
│   │   ├── __init__.py
│   │   ├── data.py       # DataPipelineConfig (from src/data/config.py)
│   │   ├── modeling.py   # ModelConfig, ExperimentConfig (from src/modeling/config.py)
│   │   └── processing.py # ProcessingConfig (from src/scraping/config.py)
│   │
│   ├── data/             # Data loading, quality, schemas (config.py REMOVED)
│   ├── features/         # Feature engineering (unchanged)
│   ├── modeling/         # Models, evaluation, experiments (config.py REMOVED)
│   │
│   ├── pipeline/         # NEW: VOD processing orchestration
│   │   ├── __init__.py
│   │   ├── manifest.py   # ProcessingManifest, VODRecord (MOVED from scraping)
│   │   └── orchestrator.py # VODOrchestrator (MOVED from scraping)
│   │
│   └── scraping/         # VLR.gg web scraping only (config.py, manifest.py, orchestrator.py REMOVED)
│       ├── __init__.py
│       └── vlr_events.py # VLREventScraper (KEPT, imports updated)
│
├── tests/
│   ├── config/           # NEW: Tests for centralized config
│   ├── data/             # Tests for data package (test_quality.py KEPT, v1 tests REMOVED)
│   ├── features/         # Tests for features (unchanged)
│   ├── modeling/         # Tests for modeling (unchanged)
│   ├── pipeline/         # NEW: Tests for pipeline package
│   └── scraping/         # Tests for scraping (vlr_events only)
│
├── scripts/
│   ├── run_checkpoint_prediction.py  # KEPT (Phase 14 reference)
│   └── run_real_experiment.py        # KEPT (Phase 14 reference)
│
├── experiments/
│   ├── v2_baseline/                  # NEW: Archive of v2 experiments
│   │   ├── checkpoint_lr/
│   │   ├── checkpoint_xgb/
│   │   ├── checkpoint_r6_lr/
│   │   ├── checkpoint_r12_lr/
│   │   ├── checkpoint_r18_lr/
│   │   ├── real_lr_core/
│   │   ├── real_lr_full/
│   │   ├── real_xgb_core/
│   │   └── real_xgb_full/
│   └── (future v3 experiments)
│
├── data/
│   ├── audit/                        # Data quality audit reports (unchanged)
│   └── processing/
│       └── manifest.json             # RESET to empty (Phase 12 rebuilds)
│
└── (root level stray files DELETED: backend.py, dashboard.py, vision_engine.py, config.py, nul)
```

### Pattern 1: Safe Code Deletion with Git History Preservation

**What:** Delete code using `git rm` rather than manual deletion, ensuring the code remains in git history.

**When to use:** Any time you need to delete code that's been committed and may need to be referenced later.

**Why safe:**
- Code preserved in git history (accessible via git log, git show, git tags)
- v1 code already tagged at `v2.0` milestone for future reference
- Forward deletion (no history rewriting) is safe for shared repositories

**Example:**
```bash
# Delete v1 event detection modules (already preserved at tag v2.0)
git rm -r src/events/ src/state/ src/quality/

# Delete v1 test files
git rm tests/test_event_emitter.py tests/test_state_tracker.py \
       tests/test_ocr_config.py tests/test_integration.py \
       tests/test_replay_detector.py

# Delete root-level stray files
git rm backend.py dashboard.py vision_engine.py config.py nul

# Commit with clear message
git commit -m "refactor: remove v1 event detection code (preserved at v2.0 tag)"
```

**Source:** [Git Undo: 13 Ways to Undo Mistakes in Git](https://gitprotect.io/blog/git-undo-13-ways-to-undo-mistakes-in-git/), [Effective Git Strategies: How to Remove Files from Repository](https://sqlpey.com/git/effective-git-strategies-remove-from-repo-keep-local/)

### Pattern 2: Module Boundary Clarification via Package Split

**What:** Split `src/scraping/` into two focused packages: `src/scraping/` (VLR.gg web scraping) and `src/pipeline/` (VOD processing orchestration).

**When to use:** When a package has grown to include two distinct responsibilities that will evolve independently.

**Why it matters:**
- Phase 12 (VLR scraping) and Phase 13 (VOD processing) are separate phases with different concerns
- Clear boundaries prevent circular dependencies
- Easier to test and modify each concern independently

**Example:**
```python
# BEFORE (in src/scraping/__init__.py):
from src.scraping.config import ProcessingConfig
from src.scraping.manifest import ProcessingManifest, VODRecord
from src.scraping.orchestrator import VODOrchestrator
from src.scraping.vlr_events import VLREventScraper

# AFTER (split into two packages):

# src/scraping/__init__.py (web scraping only)
from src.scraping.vlr_events import VLREventScraper

# src/pipeline/__init__.py (VOD processing orchestration)
from src.pipeline.manifest import ProcessingManifest, VODRecord
from src.pipeline.orchestrator import VODOrchestrator
```

**Source:** [Structuring Your Project — The Hitchhiker's Guide to Python](https://docs.python-guide.org/writing/structure/), [Python Project Structure Best Practices](https://dagster.io/blog/python-project-best-practices)

### Pattern 3: Configuration Centralization with Domain Modules

**What:** Consolidate 4 config files into a single `src/config/` package with domain-specific modules (data.py, modeling.py, processing.py).

**When to use:** Multi-domain projects where each domain has distinct configuration needs but centralized access is desired.

**Why better than a single giant config file:**
- Grouped modules (billing/constants.py, auth/constants.py) scale better than monolithic files
- Each domain can import only its relevant config
- Easier to maintain and test each config schema independently
- Follows Python packaging convention: `from src.config.modeling import ModelConfig`

**Example structure:**
```python
# src/config/__init__.py
"""Centralized configuration for all project domains."""
from src.config.data import DataPipelineConfig
from src.config.modeling import ModelConfig, ExperimentConfig
from src.config.processing import ProcessingConfig

__all__ = [
    "DataPipelineConfig",
    "ModelConfig",
    "ExperimentConfig",
    "ProcessingConfig",
]

# src/config/data.py (moved from src/data/config.py)
class DataPipelineConfig(BaseSettings):
    valoscribe_data_dir: Path
    audit_output_dir: Path = Path("data/audit")
    log_level: str = "INFO"
    # ... (existing implementation)

# src/config/modeling.py (moved from src/modeling/config.py)
class ModelConfig(BaseModel):
    model_type: str = "logistic_regression"
    feature_set: str
    # ... (existing implementation)

# src/config/processing.py (moved from src/scraping/config.py)
class ProcessingConfig(BaseSettings):
    valoscribe_repo: Path = Path("D:/Git/valoscribe")
    output_dir: Path = Path("data/processing/processed")
    # ... (existing implementation)
```

**Source:** [Python Constants in 2026: Practical Patterns](https://thelinuxcode.com/python-constants-in-2026-practical-patterns-immutability-and-realworld-usage/), [Multi-Provider Strategy for App Configuration](https://devblogs.microsoft.com/ise/multi-provider-strategy-configuration-python/)

### Pattern 4: ML Experiment Organization by Milestone

**What:** Group experiment outputs by milestone version (v2_baseline/, future v3_expanded/) rather than keeping them flat.

**When to use:** Projects with multiple experimental iterations where comparison across milestones is expected.

**Why it helps:**
- Phase 14 needs to compare "71-map baseline vs 150-map expanded"
- Clear separation prevents confusion about which experiments are current
- Easier to archive or delete old experiments
- Follows ML project best practices for experiment tracking

**Example:**
```bash
experiments/
├── v2_baseline/          # Baseline experiments (71 maps)
│   ├── checkpoint_lr/
│   ├── checkpoint_xgb/
│   ├── real_lr_core/
│   ├── real_lr_full/
│   ├── real_xgb_core/
│   └── real_xgb_full/
├── v3_expanded/          # Future: Expanded dataset experiments (150+ maps)
│   └── (Phase 14 creates these)
└── archive/              # Future: Deprecated experiments
```

**Delete smoke tests:** `smoke_test/` and `smoke_test_validation/` directories served their purpose in Phase 9/10 and are no longer needed.

**Source:** [Machine Learning Experiment Management](https://neptune.ai/blog/experiment-management), [How to Structure Your Data Science Project in 2026](https://www.analyticsvidhya.com/blog/2026/01/data-science-project-structure/)

### Anti-Patterns to Avoid

- **Modifying root config.py:** This file is v1 OCR config (ROI_TIMER, TESSERACT_CMD) and dead code. Delete it entirely rather than trying to repurpose it.
- **Keeping "just in case" scripts:** Scripts like `compare_baseline.py` (Phase 6 validation), `expand_dataset.py` (superseded by src/pipeline/), and `summarize_progress.py` (superseded by Phase 13 tracking) should be deleted. They're preserved in git history if ever needed.
- **Updating import paths in scripts being deleted:** `scripts/expand_dataset.py` and `scripts/summarize_progress.py` import from `src.scraping`, but they're being deleted anyway. Don't waste time updating their imports.
- **Manually deleting files:** Use `git rm` to preserve history and ensure clean commits.

## Don't Hand-Roll

This phase is about reorganization, not building new functionality. No custom solutions needed.

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Bulk file moves | Custom Python script | `git mv` command | Preserves git history of file moves |
| Import path updates | Manual find/replace | IDE refactoring OR manual (only 2 files affected) | Safe, but manual is fine for small scope |
| __pycache__ cleanup | Custom cleanup script | `git clean -fdX` or manual `rm -rf` | Built-in git command handles gitignored files |
| Config validation | Runtime checks | Pydantic BaseSettings (already in use) | Type-safe, validated configs already implemented |

**Key insight:** Git already provides the tools needed for safe reorganization. The refactoring scope is small enough (2 files with import updates, 1,485 LOC deletion) that custom tooling would be overengineering.

## Common Pitfalls

### Pitfall 1: Breaking Imports with Incomplete Updates

**What goes wrong:** Moving modules (orchestrator.py, manifest.py) from `src/scraping/` to `src/pipeline/` breaks imports in `src/scraping/vlr_events.py` if not updated.

**Why it happens:** `vlr_events.py` currently imports `ProcessingManifest` and `VODRecord` from `src.scraping.manifest`. After the move, this import path is invalid.

**How to avoid:**
1. Update `src/scraping/vlr_events.py` imports:
   ```python
   # OLD:
   from src.scraping.manifest import ProcessingManifest, VODRecord

   # NEW:
   from src.pipeline.manifest import ProcessingManifest, VODRecord
   ```
2. Update `src/scraping/__init__.py` to remove exports of moved classes
3. Create `src/pipeline/__init__.py` with proper exports

**Warning signs:**
- `ImportError: cannot import name 'ProcessingManifest' from 'src.scraping.manifest'`
- Pytest test collection failures
- Module not found errors when running scripts

**Verification:** Run `pytest --collect-only` to verify all tests can be discovered without import errors.

**Source:** [Python Refactoring Pitfalls](https://www.codesee.io/learning-center/python-refactoring), [Fix imports after refactoring - Pylance](https://github.com/microsoft/pylance-release/issues/3929)

### Pitfall 2: Deleting Tests Without Verifying Test Coverage

**What goes wrong:** Deleting v1 test files (`test_event_emitter.py`, `test_state_tracker.py`, etc.) without confirming they're truly obsolete could leave functionality untested.

**Why it happens:** Test files may contain assertions that were ported to other tests, or they may test code that's still in use but moved to Valoscribe.

**How to avoid:**
1. Verify the modules being tested are actually deleted:
   ```bash
   # Confirm src/events/, src/state/, src/quality/ are being deleted
   ls -la src/events/ src/state/ src/quality/
   ```
2. Check if any kept code imports from deleted modules:
   ```bash
   grep -r "from src.events" src/ tests/ scripts/
   grep -r "from src.state" src/ tests/ scripts/
   grep -r "from src.quality" src/ tests/ scripts/
   ```
3. Run full test suite before and after deletion:
   ```bash
   pytest tests/ --tb=short  # Before deletion
   git rm tests/test_event_emitter.py  # (and others)
   pytest tests/ --tb=short  # After deletion - should still pass
   ```

**Warning signs:**
- Test count drops significantly (e.g., from 340 tests to 100)
- ImportError during test collection
- Tests that were passing now fail due to missing test fixtures

**Verification:** Test count should drop by ~7 files but remaining tests should pass. The project shipped v2 with these tests passing; deleting the code they test should not affect remaining tests.

**Source:** [Tips and Tricks - Pytest - clean up resources](https://testdriven.io/tips/6114106d-9e03-4289-a2cb-c7f4d37d5051/), [Changing standard test discovery - pytest](https://docs.pytest.org/en/stable/example/pythoncollection.html)

### Pitfall 3: __pycache__ Pollution After Reorganization

**What goes wrong:** After moving/deleting modules, old `__pycache__` directories remain, causing Python to import stale bytecode instead of updated modules.

**Why it happens:** Python creates `__pycache__/` in every directory with .py files. When modules move, the old `__pycache__/` isn't automatically cleaned up.

**How to avoid:**
1. Clean all `__pycache__` before and after reorganization:
   ```bash
   # Option 1: Git clean (removes all gitignored files)
   git clean -fdX

   # Option 2: Manual (safer, more selective)
   find . -type d -name "__pycache__" -exec rm -rf {} +
   find . -type f -name "*.pyc" -delete
   ```
2. Verify .gitignore includes `__pycache__/` (already present in this project)
3. Consider using PYTHONDONTWRITEBYTECODE=1 environment variable during reorganization to prevent new .pyc creation

**Warning signs:**
- ImportError referencing old module paths
- "Module not found" errors despite correct imports
- Stale test results (old test code running)

**Verification:** After cleanup, `find . -type d -name "__pycache__" | wc -l` should show 0 directories (or only in .venv/).

**Note:** Python 3.8+ supports PYTHONPYCACHEPREFIX to centralize .pyc files outside the source tree, but this project doesn't need it for a one-time cleanup.

**Source:** [How to Ignore Pycache in .gitignore 2026](https://copyprogramming.com/howto/how-to-ignore-pycache-in-gitignore-code-example), [Git Ignore PYCache](https://www.tracedynamics.com/git-ignore-pycache/)

### Pitfall 4: Data Directory Resets Breaking Existing Work

**What goes wrong:** Resetting `data/processing/manifest.json` to empty destroys existing processing records if someone has partially processed maps.

**Why it happens:** The decision states "Reset manifest.json to empty — Phase 12 rebuilds with complete metadata". Existing manifest has 46 entries with empty dates and null patch versions.

**How to avoid:**
1. Back up existing manifest before reset:
   ```bash
   cp data/processing/manifest.json data/processing/manifest.v2_backup.json
   git add data/processing/manifest.v2_backup.json
   ```
2. Document the reset reason in commit message
3. Check if any .mp4 files exist in `data/processing/downloads/` that would need reprocessing:
   ```bash
   ls -lh data/processing/downloads/*.mp4 2>/dev/null | wc -l
   ```
4. If downloads exist, either:
   - Process them before reset, OR
   - Note them in the commit message so they're knowingly discarded

**Warning signs:**
- Lost processing history (can't tell which maps were already attempted)
- Duplicate processing of maps already completed
- Confusion about which VLR matches need scraping

**Verification:** After reset, manifest.json should be `{}` (empty JSON object) or `{"records": []}` depending on schema.

**Why it's okay:** CONTEXT.md explicitly states the existing 46 entries have "empty dates, null patch versions, and will create merge problems" — they're incomplete and Phase 12 will rebuild with proper metadata.

**Source:** User-provided CONTEXT.md decision, [Data Organization Best Practices](https://data.library.arizona.edu/data-management/best-practices/data-project-organization)

### Pitfall 5: Forgetting to Update Package __init__.py Files

**What goes wrong:** Moving files but forgetting to update `__init__.py` exports breaks external imports even if internal imports are correct.

**Why it happens:** `__init__.py` files explicitly list what a package exports. Moving `ProcessingManifest` from `src/scraping/` to `src/pipeline/` requires updating both packages' `__init__.py`.

**How to avoid:**
1. Update `src/scraping/__init__.py` to REMOVE moved exports:
   ```python
   # BEFORE:
   from src.scraping.config import ProcessingConfig
   from src.scraping.manifest import ProcessingManifest, VODRecord
   from src.scraping.orchestrator import VODOrchestrator
   from src.scraping.vlr_events import VLREventScraper

   # AFTER (only VLREventScraper remains):
   from src.scraping.vlr_events import VLREventScraper

   __all__ = ["VLREventScraper"]
   ```

2. Create `src/pipeline/__init__.py` with NEW exports:
   ```python
   """VOD processing pipeline orchestration."""
   from src.pipeline.manifest import ProcessingManifest, VODRecord
   from src.pipeline.orchestrator import VODOrchestrator

   __all__ = [
       "ProcessingManifest",
       "VODRecord",
       "VODOrchestrator",
   ]
   ```

3. Create `src/config/__init__.py` for centralized config:
   ```python
   """Centralized configuration for all project domains."""
   from src.config.data import DataPipelineConfig
   from src.config.modeling import ModelConfig, ExperimentConfig
   from src.config.processing import ProcessingConfig

   __all__ = [
       "DataPipelineConfig",
       "ModelConfig",
       "ExperimentConfig",
       "ProcessingConfig",
   ]
   ```

**Warning signs:**
- `AttributeError: module 'src.scraping' has no attribute 'ProcessingManifest'`
- IDE autocomplete shows old imports as available
- `from src.scraping import ProcessingManifest` succeeds but should fail

**Verification:**
```python
# Should work after reorganization:
from src.pipeline import ProcessingManifest
from src.config import ProcessingConfig

# Should fail after reorganization:
from src.scraping import ProcessingManifest  # AttributeError
```

**Source:** [Python Import System](https://www.pythoncentral.io/understanding-python-import/), [Python Package Structure](https://www.pyopensci.org/python-package-guide/package-structure-code/python-package-structure.html)

## Code Examples

Verified patterns from research and current codebase analysis.

### Moving Modules with Git (Preserves History)

```bash
# Create new directory
mkdir -p src/pipeline

# Move files with git mv (preserves history)
git mv src/scraping/manifest.py src/pipeline/manifest.py
git mv src/scraping/orchestrator.py src/pipeline/orchestrator.py

# Create new config package
mkdir -p src/config
git mv src/data/config.py src/config/data.py
git mv src/modeling/config.py src/config/modeling.py
git mv src/scraping/config.py src/config/processing.py

# Verify moves preserved history
git log --follow src/pipeline/manifest.py  # Shows history from src/scraping/manifest.py
```

**Source:** Git documentation, standard practice for preserving file history

### Safe Code Deletion (Preserves History at Tag)

```bash
# Verify code already preserved at v2.0 tag
git tag | grep v2.0
git show v2.0:src/events/emitter.py  # Verify accessible

# Delete v1 modules
git rm -r src/events/ src/state/ src/quality/

# Delete v1 tests
git rm tests/test_event_emitter.py \
       tests/test_state_tracker.py \
       tests/test_ocr_config.py \
       tests/test_integration.py \
       tests/test_replay_detector.py

# Delete root stray files
git rm backend.py dashboard.py vision_engine.py config.py nul

# Delete superseded scripts
git rm scripts/compare_baseline.py \
       scripts/expand_dataset.py \
       scripts/summarize_progress.py \
       scripts/CHECKPOINT_PREDICTION_PLAN.md

# Commit with clear message
git commit -m "refactor: remove v1 event detection code

- Delete src/events/, src/state/, src/quality/ (1,485 LOC)
- Delete associated v1 test files (7 files)
- Delete root-level stray files (backend.py, dashboard.py, etc.)
- Delete superseded scripts (compare_baseline.py, expand_dataset.py, etc.)
- Code preserved at git tag v2.0 for future reference"
```

**Source:** [Effective Git Strategies: Remove from Repo](https://sqlpey.com/git/effective-git-strategies-remove-from-repo-keep-local/)

### Cleaning __pycache__ After Reorganization

```bash
# Option 1: Git clean (removes ALL gitignored files - use with caution)
git clean -fdX

# Option 2: Selective cleanup (safer)
find . -type d -name "__pycache__" -not -path "./.venv/*" -exec rm -rf {} +
find . -type f -name "*.pyc" -not -path "./.venv/*" -delete

# Option 3: Prevent bytecode during reorganization
export PYTHONDONTWRITEBYTECODE=1
# ... perform reorganization ...
unset PYTHONDONTWRITEBYTECODE

# Verify cleanup
find . -type d -name "__pycache__" -not -path "./.venv/*" | wc -l  # Should be 0
```

**Source:** [Git Ignore Pycache: A Quick Guide](https://gitscripts.com/git-ignore-pycache)

### Reorganizing Experiments by Milestone

```bash
# Create v2_baseline directory
mkdir -p experiments/v2_baseline

# Move v2 experiment directories
mv experiments/checkpoint_lr experiments/v2_baseline/
mv experiments/checkpoint_xgb experiments/v2_baseline/
mv experiments/checkpoint_r6_lr experiments/v2_baseline/
mv experiments/checkpoint_r12_lr experiments/v2_baseline/
mv experiments/checkpoint_r18_lr experiments/v2_baseline/
mv experiments/real_lr_core experiments/v2_baseline/
mv experiments/real_lr_full experiments/v2_baseline/
mv experiments/real_xgb_core experiments/v2_baseline/
mv experiments/real_xgb_full experiments/v2_baseline/

# Delete smoke test directories
rm -rf experiments/smoke_test
rm -rf experiments/smoke_test_validation

# Stage and commit
git add experiments/
git commit -m "refactor: organize experiments by milestone

- Move 9 v2 experiments to experiments/v2_baseline/
- Delete smoke test directories (Phase 9/10 validation complete)
- Prepares for Phase 14 comparison: v2 baseline vs v3 expanded"
```

**Source:** [Machine Learning Experiment Management](https://neptune.ai/blog/experiment-management)

### Resetting Data Processing Manifest

```bash
# Backup existing manifest (46 entries with incomplete metadata)
cp data/processing/manifest.json data/processing/manifest.v2_backup.json

# Reset to empty manifest
echo '{"records": []}' > data/processing/manifest.json

# Stage both files
git add data/processing/manifest.json data/processing/manifest.v2_backup.json

# Commit with explanation
git commit -m "refactor: reset processing manifest for Phase 12 rebuild

- Backup existing 46 entries to manifest.v2_backup.json
- Reset manifest.json to empty
- Existing entries have empty dates and null patch versions
- Phase 12 will rebuild with complete VLR.gg metadata"
```

**Source:** User-provided CONTEXT.md decision

## State of the Art

Python project organization standards have evolved significantly with the maturation of packaging tools and ML/data science workflows.

| Old Approach | Current Approach (2026) | When Changed | Impact |
|--------------|-------------------------|--------------|--------|
| Flat layout (package at root) | src/ layout for installable packages | ~2020 (pytest/packaging adoption) | Prevents import issues, cleaner distributions |
| Monolithic config.py | Domain-specific config modules under src/config/ | Ongoing best practice | Better modularity, easier testing |
| Manual __pycache__ cleanup | PYTHONPYCACHEPREFIX (Python 3.8+) | Python 3.8 (2019) | Centralizes bytecode, cleaner source tree |
| git filter-branch | git filter-repo for history rewriting | ~2019 (git 2.25+) | Faster, safer - but not needed for forward deletions |
| Flat experiments/ directory | Milestone-based experiment organization | ML workflow maturity (~2022+) | Easier comparison, clearer provenance |

**Deprecated/outdated:**
- **git filter-branch:** Deprecated in favor of git filter-repo for history rewriting (but this phase uses forward deletion, not history rewriting)
- **Flat package layout for distribution:** src/ layout is now recommended by pytest and Python packaging guide
- **Single giant config file:** Modern practice favors grouped modules or multi-provider config strategies

**Current best practices (2026):**
- **src/ layout:** Recommended for any package intended for installation/distribution
- **Pydantic BaseSettings:** Standard for validated, environment-aware configuration (already in use)
- **Git tags for code preservation:** More reliable than relying on git log history for major deletions
- **Pytest autodiscovery:** Test files mirror src/ structure (tests/pipeline/, tests/config/, etc.)

## Open Questions

### Question 1: Should import paths in scripts/ be updated proactively?

**What we know:**
- `scripts/run_checkpoint_prediction.py` and `scripts/run_real_experiment.py` are being kept as "reference implementations"
- They don't import from the moved modules (orchestrator, manifest) directly
- They may need updates in Phase 14 regardless of this phase's changes

**What's unclear:**
- Whether keeping them with outdated structure will cause confusion in Phase 14
- Whether updating them now saves time or wastes it (if they get rewritten anyway)

**Recommendation:** Leave imports as-is. CONTEXT.md says "Whether to update import paths in kept scripts or leave as-is (they'll need Phase 14 updates anyway)" is Claude's discretion. Since they don't import moved modules and will likely need updates in Phase 14, updating now provides no value.

### Question 2: Should src/config/ be a single file or multiple files?

**What we know:**
- 4 existing config files: src/data/config.py (50 lines), src/modeling/config.py (212 lines), src/scraping/config.py (50 lines), root config.py (27 lines)
- Total: ~340 lines of config code across 3 domains (data, modeling, processing)
- Pydantic BaseSettings and BaseModel already in use

**What's unclear:**
- Whether the benefit of multiple files (domain separation) outweighs simplicity of a single file
- Whether future phases will add more config needs (e.g., VLR scraper config in Phase 12)

**Recommendation:** Use multiple files (data.py, modeling.py, processing.py) as shown in Pattern 3. Research confirms grouped modules scale better than monolithic files, and 212-line ModelConfig is already large enough to justify separation. Future VLR scraper config (Phase 12) can add src/config/scraping.py cleanly.

### Question 3: Should processed data stay flat or be organized by tournament/date?

**What we know:**
- CONTEXT.md decision: "Processed maps stay merged flat in Valoscribe's data/processed/ — data loader works as-is, provenance lives in metadata/manifest, walk-forward CV stays trivial"
- Current data loader expects flat structure: `data/processed/{map_id}/events.jsonl`
- Walk-forward CV depends on chronological ordering, which is trivial in flat structure

**What's unclear:**
- Whether 150+ maps will make flat structure unwieldy (performance, navigation)
- Whether future phases would benefit from hierarchical organization

**Recommendation:** Keep flat structure as decided in CONTEXT.md. This is a locked decision (not Claude's discretion), and research confirms processed data should live in a canonical location with provenance tracked separately (metadata/manifest). Reorganizing data structure is out of scope for this phase.

## Sources

### Primary (HIGH confidence)

**Python Project Structure:**
- [Python Project Structure Best Practices - Real Python](https://realpython.com/ref/best-practices/project-layout/)
- [Structuring Your Project — The Hitchhiker's Guide to Python](https://docs.python-guide.org/writing/structure/)
- [src layout vs flat layout - Python Packaging User Guide](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
- [Python Package Structure — Python Packaging Guide](https://www.pyopensci.org/python-package-guide/package-structure-code/python-package-structure.html)

**Git Safe Deletion:**
- [Git Undo: 13 Ways to Undo Mistakes in Git](https://gitprotect.io/blog/git-undo-13-ways-to-undo-mistakes-in-git/)
- [Effective Git Strategies: How to Remove Files from Repository](https://sqlpey.com/git/effective-git-strategies-remove-from-repo-keep-local/)
- [How can I restore a deleted file in Git?](https://www.git-tower.com/learn/git/faq/restoring-deleted-files)

**Configuration Centralization:**
- [Python Constants in 2026: Practical Patterns](https://thelinuxcode.com/python-constants-in-2026-practical-patterns-immutability-and-realworld-usage/)
- [Multi-Provider Strategy for App Configuration in Python](https://devblogs.microsoft.com/ise/multi-provider-strategy-configuration-python/)

**Python __pycache__ Cleanup:**
- [Git Ignore PYCache: Managing Temp Python Files](https://www.tracedynamics.com/git-ignore-pycache/)
- [How to Ignore pycache in .gitignore: Complete Code Examples & Best Practices 2026](https://copyprogramming.com/howto/how-to-ignore-pycache-in-gitignore-code-example)
- [Git Ignore Pycache: A Quick Guide to Clean Repos](https://gitscripts.com/git-ignore-pycache)

### Secondary (MEDIUM confidence)

**ML Experiment Organization:**
- [Machine Learning Experiment Management](https://neptune.ai/blog/experiment-management)
- [How to Structure Your Data Science Project in 2026?](https://www.analyticsvidhya.com/blog/2026/01/data-science-project-structure/)
- [Cookiecutter Data Science - Project template](https://cookiecutter-data-science.drivendata.org/)
- [How to Structure a Data Science Project for Readability](https://khuyentran1401.github.io/reproducible-data-science/structure_project/introduction.html)

**Python Refactoring:**
- [Python Refactoring: Techniques, Tools, and Best Practices](https://www.codesee.io/learning-center/python-refactoring)
- [Refactoring Python Applications for Simplicity – Real Python](https://realpython.com/python-refactoring/)
- [Fix imports after refactoring - Pylance Issue](https://github.com/microsoft/pylance-release/issues/3929)

**Pytest Test Organization:**
- [Tips and Tricks - Pytest - clean up resources](https://testdriven.io/tips/6114106d-9e03-4289-a2cb-c7f4d37d5051/)
- [Changing standard test discovery - pytest](https://docs.pytest.org/en/stable/example/pythoncollection.html)

### Tertiary (LOW confidence)

None - all findings verified with official sources or multiple credible sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Git and Python stdlib are standard tools, no external dependencies
- Architecture: HIGH - src/ layout and domain-specific config modules are documented best practices
- Pitfalls: HIGH - Import breakage, __pycache__ pollution, and test deletion risks are well-documented
- ML experiment organization: MEDIUM - Best practices exist but less standardized than core Python packaging

**Research date:** 2026-02-14
**Valid until:** 2026-03-14 (30 days - stable domain, Python packaging evolves slowly)
