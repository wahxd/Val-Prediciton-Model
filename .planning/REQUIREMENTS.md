# Requirements: Valorant Match Prediction Model v3

**Defined:** 2026-02-14
**Core Value:** A prediction model accurate enough to identify edge against Polymarket prices on VCT match outcomes.

## v3 Requirements

Requirements for v3 milestone: Scale Data & Validate at Volume.

### Cleanup & Organization

- [ ] **CLEAN-01**: Remove stray scripts and temporary files from root and scripts/ directory
- [ ] **CLEAN-02**: Remove corrupted/unused files (temp_verify.txt, analysis.db, stray `=1.11`/`=3.0` files)
- [ ] **CLEAN-03**: Organize src/ directory structure with clear module boundaries
- [ ] **CLEAN-04**: Clean up data/ directory structure for scaling to 150+ maps
- [ ] **CLEAN-05**: Archive or remove unused/duplicate experiment files

### Data Sourcing

- [ ] **SCRP-01**: Scrape VCT match results (teams, map scores, match outcomes) from VLR.gg
- [ ] **SCRP-02**: Extract YouTube VOD links from VLR.gg match pages
- [ ] **SCRP-03**: Extract player stats (ACS, K/D/A, KAST%, ADR, HS%, FK/FD) per map
- [ ] **SCRP-04**: Extract agent compositions per map
- [ ] **SCRP-05**: Rate-limited scraping with caching and resume capability
- [ ] **SCRP-06**: Normalize team names across VLR.gg and Valoscribe data sources

### VOD Processing

- [ ] **PROC-01**: Build match manifest mapping VLR.gg data to Valoscribe processing targets
- [ ] **PROC-02**: Batch download YouTube VODs for processing
- [ ] **PROC-03**: Process downloaded VODs through Valoscribe automatically
- [ ] **PROC-04**: Quality validation on each processed map output
- [ ] **PROC-05**: Resumable processing with state tracking (pending/downloaded/processed/failed)
- [ ] **PROC-06**: Progress tracking and reporting for batch operations

### Experiments

- [ ] **EXPR-01**: Run checkpoint prediction experiments on combined dataset (existing + new maps)
- [ ] **EXPR-02**: Run full-map prediction experiments on combined dataset
- [ ] **EXPR-03**: Walk-forward temporal CV on expanded dataset
- [ ] **EXPR-04**: Log loss and calibration evaluation at scale
- [ ] **EXPR-05**: Cross-tournament validation on expanded tournament coverage

### Model Iteration

- [ ] **ITER-01**: Re-tune hyperparameters via Optuna on larger dataset
- [ ] **ITER-02**: Feature importance analysis (SHAP) at scale
- [ ] **ITER-03**: Compare model performance: 71-map baseline vs full dataset

## Future Requirements

Deferred to later milestones. Tracked but not in current roadmap.

### Trading Infrastructure (v4)

- **TRADE-01**: Contract price data integration (Polymarket/Kalshi)
- **TRADE-02**: Kelly criterion position sizing
- **TRADE-03**: Automated trade execution
- **TRADE-04**: Live stream event detection (retrofit Valoscribe)
- **TRADE-05**: Real-time prediction during live matches

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Team Elo/Glicko ratings | Roster changes make team identity unstable in Valorant |
| Player-level prediction features | Scrape stats as metadata; defer as model features until dataset proves sufficient |
| Per-agent win rate features | Meta shifts between patches, unstable signal |
| Ablation studies | Get baseline real-data results first, iterate in v4 |
| Deep learning / neural nets | Gradient boosting outperforms at current dataset size |
| Mobile or web deployment | Local tool for now |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CLEAN-01 | Phase 11 | Pending |
| CLEAN-02 | Phase 11 | Pending |
| CLEAN-03 | Phase 11 | Pending |
| CLEAN-04 | Phase 11 | Pending |
| CLEAN-05 | Phase 11 | Pending |
| SCRP-01 | Phase 12 | Pending |
| SCRP-02 | Phase 12 | Pending |
| SCRP-03 | Phase 12 | Pending |
| SCRP-04 | Phase 12 | Pending |
| SCRP-05 | Phase 12 | Pending |
| SCRP-06 | Phase 12 | Pending |
| PROC-01 | Phase 13 | Pending |
| PROC-02 | Phase 13 | Pending |
| PROC-03 | Phase 13 | Pending |
| PROC-04 | Phase 13 | Pending |
| PROC-05 | Phase 13 | Pending |
| PROC-06 | Phase 13 | Pending |
| EXPR-01 | Phase 14 | Pending |
| EXPR-02 | Phase 14 | Pending |
| EXPR-03 | Phase 14 | Pending |
| EXPR-04 | Phase 14 | Pending |
| EXPR-05 | Phase 14 | Pending |
| ITER-01 | Phase 15 | Pending |
| ITER-02 | Phase 15 | Pending |
| ITER-03 | Phase 15 | Pending |

**Coverage:**
- v3 requirements: 25 total
- Mapped to phases: 25/25 (100%)
- Unmapped: 0

---
*Requirements defined: 2026-02-14*
*Traceability updated: 2026-02-14*
*Last updated: 2026-02-14*
