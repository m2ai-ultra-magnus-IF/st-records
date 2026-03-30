# CLAUDE.md - ST Records

## Quick Commands

```bash
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/
```

## Project Purpose

ST Records is the orchestration layer that closes the feedback loop between:
1. **Metroplex** - Idea pipeline (produces OutcomeRecords)
2. **Sky-Lynx** - Observer (analyzes outcomes, produces ImprovementRecommendations)
3. **ST Agent Registry** - Factory (consumes recommendations, produces PersonaUpgradePatches)

## Architecture

```
contracts/              # Pydantic models defining inter-layer data contracts
  outcome_record.py     # Metroplex -> SL
  improvement_recommendation.py  # SL -> Academy
  persona_upgrade_patch.py       # Academy -> Metroplex
  store.py              # Dual-write JSONL + SQLite store
schemas/                # JSON Schema exports for TypeScript consumers
data/                   # JSONL data files (append-only, git-tracked)
scripts/                # Orchestration and automation
tests/                  # Contract tests
```

## Key Decisions

- **JSONL as source of truth** - append-only, git-tracked, human-readable
- **SQLite as query layer** - rebuildable from JSONL at any time
- **Contracts defined here, imported by layers** - single source of truth for schemas
- **Weekly cadence** - matches Sky-Lynx's existing cron schedule

## Data Flow

```
Metroplex terminal state -> OutcomeRecord -> JSONL
Sky-Lynx reads JSONL -> analyzes -> ImprovementRecommendation -> JSONL
persona_upgrader reads JSONL -> generates patch -> PersonaUpgradePatch -> JSONL
```
