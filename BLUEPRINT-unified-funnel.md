# BLUEPRINT: Unified Idea Funnel (Option D)

**Created**: 2026-02-23
**Owner**: Matthew Snow
**Purpose**: Close the pipeline gap where research-agents bypass IdeaForge, leaving Metroplex with no data to triage.

---

## Problem Statement

The ST Metro pipeline has a disconnected seam:

```
ACTUAL (broken):
  Research Agents → ST Records ContractStore (signals)
  Idea Surfacer   → Ultra-Magnus caught_ideas.db (ideas)
  IdeaForge       → harvests HN only → empty DB
  Metroplex       → reads IdeaForge → finds nothing

INTENDED (from roadmap):
  All signal sources → IdeaForge (unified intake)
  IdeaForge          → score → classify
  Metroplex          → reads IdeaForge scored ideas → triage → build
```

## Design Decision

**IdeaForge becomes the single idea intake.** All sources produce ideas that land in `ideaforge.db` with `status='unscored'`. IdeaForge's existing scorer and classifier process everything uniformly. Metroplex reads the output.

```
HN Harvester ─────────┐
                       ├──> ideaforge.db (ideas table, status='unscored')
Idea Surfacer ─────────┘         |
(from research-agent signals)    v
                          IdeaForge score + classify
                                 |
                                 v
                          Metroplex triage (reads status='scored')
                                 |
                                 v
                          Linear issue (via Arcade) → YCE Harness build
```

Research agents continue writing raw signals to ST Records ContractStore (Sky-Lynx reads those). Only the idea-surfacer's output destination changes.

---

## Phases

### Phase 1: Redirect Idea Surfacer → IdeaForge ✅ READY TO BUILD
**Effort**: ~30 min code change + tests
**Files touched**: 2-3 files in research-agents

Modify `idea_surfacer.py` to write synthesized ideas to IdeaForge's `ideas` table instead of Ultra-Magnus `caught_ideas.db`.

| Step | Description | Status |
|------|-------------|--------|
| 1a | Add IdeaForge DB path to research-agents config (`IDEAFORGE_DB`) | [ ] |
| 1b | Create `ideaforge_writer.py` in research-agents — inserts ideas into IdeaForge `ideas` table with `status='unscored'`, matching IdeaForge's schema (title, description, problem_statement, target_audience, source_signals, signal_count, synthesized_at) | [ ] |
| 1c | Update `idea_surfacer.py` — replace `_write_idea_to_um()` call with IdeaForge writer. Keep the existing Claude synthesis logic unchanged. | [ ] |
| 1d | Update tests — verify idea lands in IdeaForge schema, status='unscored' | [ ] |
| 1e | Manual validation — run `research-agents run idea-surfacer` and confirm row appears in `ideaforge.db` | [ ] |

**Schema mapping** (idea_surfacer output → IdeaForge ideas table):
```
title           → title
description     → description
(generate)      → problem_statement (extract from description or leave empty)
(generate)      → target_audience (extract from description or leave empty)
source_signal_ids → source_signals (JSON array)
tags            → (not in IdeaForge schema — store in source_subreddits as workaround, or drop)
"research-agents:idea-surfacer" → (store in source_subreddits[0] for provenance)
len(source_signal_ids) → signal_count
now()           → synthesized_at
'unscored'      → status
```

**Key constraint**: IdeaForge's `insert_idea()` in `db.py` expects an `Idea` Pydantic model. The writer can either:
- Import and use IdeaForge's models directly (adds cross-project dependency via sys.path, same pattern as ST Records)
- Do raw SQL INSERT (simpler, no import dependency)

**Recommendation**: Raw SQL INSERT. Keeps research-agents decoupled. Same pattern already used for Ultra-Magnus writes.

**Exit criteria**: `SELECT count(*) FROM ideas WHERE status='unscored'` returns > 0 in ideaforge.db after idea-surfacer runs.

---

### Phase 2: Activate IdeaForge Pipeline
**Effort**: ~20 min (cron install + validation)
**Files touched**: IdeaForge cron files (may need creation), verify existing venv

| Step | Description | Status |
|------|-------------|--------|
| 2a | Verify IdeaForge venv exists and `ideaforge run` works locally | [ ] |
| 2b | Run `ideaforge score` manually to score the ideas from Phase 1 | [ ] |
| 2c | Run `ideaforge classify` to classify scored ideas | [ ] |
| 2d | Verify `ideaforge status` shows scored + classified ideas | [ ] |
| 2e | Create IdeaForge cron file if not exists (daily 6 AM UTC — after research agents 5 AM) | [ ] |
| 2f | Install IdeaForge cron (`sudo cp`) | [ ] |

**Timing coordination**:
```
5:00 AM UTC  — research agents: arxiv + tool-monitor (daily)
5:00 AM UTC  — research agents: domain-watch (every 3 days)
6:00 AM UTC  — IdeaForge: harvest HN + score + classify (daily, 1hr after agents)
11:00 PM SAT — research agents: idea-surfacer (weekly, before Sunday loop)
```

Note: idea-surfacer runs Saturday 11 PM. Its ideas won't be scored until the next daily IdeaForge run (Sunday 6 AM). This is fine — Metroplex can run anytime after.

**Exit criteria**: IdeaForge cron installed, `ideaforge status` shows scored ideas from both HN harvester and research-agents idea-surfacer.

---

### Phase 3: End-to-End Validation (Metroplex Triage)
**Effort**: ~15 min
**Files touched**: None (read-only validation)

| Step | Description | Status |
|------|-------------|--------|
| 3a | Run `python metroplex.py triage --dry-run` — verify it finds scored ideas from IdeaForge | [ ] |
| 3b | Run `python metroplex.py triage` — verify approve/reject/defer decisions are recorded | [ ] |
| 3c | Run `python metroplex.py status` — verify triage decisions in state DB | [ ] |
| 3d | Update ST_METRO_ROADMAP.md — mark Phase 7f and 7g as Done | [ ] |

**Exit criteria**: Metroplex triages real ideas from IdeaForge. The signal→score→triage loop is proven end-to-end.

---

### Phase 4: Cleanup & Documentation (Optional, low priority)
**Effort**: ~15 min

| Step | Description | Status |
|------|-------------|--------|
| 4a | Decide fate of Ultra-Magnus caught_ideas.db path — still needed for MCP idea-catcher tool? Keep as separate input or redirect too? | [ ] |
| 4b | Update research-agents CLAUDE.md — document IdeaForge as output destination | [ ] |
| 4c | Update IdeaForge CLAUDE.md — document research-agents as signal source | [ ] |
| 4d | Update ST_METRO_ROADMAP.md "Current State" diagram to reflect unified funnel | [ ] |

---

## What NOT to Change

- **ST Records ContractStore**: Research agents still write raw signals here. Sky-Lynx reads them. Don't touch this.
- **Metroplex readers**: Already reads IdeaForge. No change needed.
- **IdeaForge scorer/classifier**: Already processes unscored ideas. No change needed.
- **IdeaForge HN harvester**: Stays as-is. It's one signal source among potentially many.
- **Research agents (arxiv, tool-monitor, domain-watch)**: These write signals to ST Records. No change — only idea-surfacer output changes.

## Risks

| Risk | Mitigation |
|------|------------|
| IdeaForge venv may be stale post-DR | Phase 2a verifies this early |
| IdeaForge scorer uses Anthropic API (cost) | Already budgeted — same API key as research agents |
| Schema mismatch between idea-surfacer output and IdeaForge ideas table | Phase 1 schema mapping is explicit above |
| caught_ideas.db becomes orphaned | Phase 4a addresses this — MCP idea-catcher may still use it for manual captures |
