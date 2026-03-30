# AGENTS.md - ST Records

## Build & Run

```bash
# Setup
cd ~/projects/st-records
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run loop status
python scripts/loop_status.py

# Run persona upgrader (dry-run)
python scripts/persona_upgrader.py --dry-run

# Run full loop (dry-run)
./scripts/run_loop.sh --dry-run

# Run full loop (live - requires ANTHROPIC_API_KEY)
./scripts/run_loop.sh
```

## Key Paths

| Path | Purpose |
|------|---------|
| `contracts/` | Pydantic models for inter-layer contracts |
| `data/*.jsonl` | Append-only data files (source of truth) |
| `data/persona_metrics.db` | SQLite query layer (rebuildable) |
| `scripts/run_loop.sh` | Full feedback loop orchestrator |
| `scripts/persona_upgrader.py` | Generates persona patches from recommendations |
| `scripts/loop_status.py` | Reports loop health |
| `cron/st-records` | Cron configuration for weekly execution |

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `ANTHROPIC_API_KEY` | For persona_upgrader | Claude API for patch generation |

## Dependencies

- Python 3.11+
- Sky-Lynx (at `~/projects/sky-lynx/`)
- Ultra Magnus (at `~/projects/ultra-magnus/`)
- ST Agent Registry (at `~/projects/st-agent-registry/`)
