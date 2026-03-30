# ST Records (Snow-Town)

Closed-loop learning ecosystem for the ST Metro pipeline. Connects three autonomous systems into a feedback triangle: outcomes drive analysis, analysis produces recommendations, recommendations upgrade personas, upgraded personas improve future outcomes.

## Architecture

```
Ultra Magnus (idea pipeline)
    |
    +-- OutcomeRecord --> ST Records ContractStore (JSONL + SQLite)
                               |
                               v
                         Sky-Lynx (weekly analysis)
                               |
                               +-- ImprovementRecommendation --> ContractStore
                                                                      |
                                                                      v
                                                               persona_upgrader.py
                                                                      |
                                                                      +-- PersonaUpgradePatch --> ContractStore
                                                                                                      |
                                                                                                      v
                                                                                           Agent Persona Academy
                                                                                           (YAML persona files)
                                                                                                      |
                                                                                                      +--> Ultra Magnus (upgraded personas)
```

**External readers**: Metroplex reads `persona_metrics.db` via `?mode=ro` to source patches for Gate 3 (patcher). Sky-Lynx reads JSONL + SQLite for weekly analysis.

## Data Model

### Contracts (Pydantic v2)

| Contract | From | To | File |
|----------|------|----|------|
| `OutcomeRecord` | Ultra Magnus | Sky-Lynx | `contracts/outcome_record.py` |
| `ImprovementRecommendation` | Sky-Lynx | persona_upgrader | `contracts/improvement_recommendation.py` |
| `PersonaUpgradePatch` | persona_upgrader | Academy | `contracts/persona_upgrade_patch.py` |
| `ResearchSignal` | Research Agents | IdeaForge | `contracts/research_signal.py` |

### Storage: Dual-Write (JSONL + SQLite)

- **JSONL** (`data/*.jsonl`) — append-only, git-tracked, source of truth
- **SQLite** (`data/persona_metrics.db`) — query layer with status tracking, rebuildable from JSONL via `ContractStore.rebuild_sqlite()`

The `ContractStore` (`contracts/store.py`) handles both writes atomically. Status updates (e.g. patch proposed -> applied) are written to SQLite only; JSONL preserves the original record.

### SQLite Tables

| Table | Key Columns | Status Values |
|-------|------------|---------------|
| `outcome_records` | idea_id, outcome, overall_score, emitted_at | - |
| `improvement_recommendations` | recommendation_id, recommendation_type, target_system, priority | pending, applied, rejected |
| `persona_patches` | patch_id, persona_id, from_version, to_version, schema_valid | proposed, applied, rejected |
| `research_signals` | signal_id, source, relevance, domain, consumed_by | - |

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"        # Contracts + scripts + tests
pip install -e ".[api]"        # Also installs FastAPI/uvicorn for the API
```

## Usage

### Scripts

```bash
source .venv/bin/activate

# Full feedback loop (Sky-Lynx analysis -> persona upgrader -> status report)
./scripts/run_loop.sh                     # Live run
./scripts/run_loop.sh --dry-run           # No API calls or patches

# Individual tools
python scripts/loop_status.py             # Report loop health and counts
python scripts/persona_upgrader.py        # Generate patches from pending recommendations
python scripts/persona_upgrader.py --dry-run --persona sky-lynx  # Dry-run single persona

# Human-in-the-loop patch review
python scripts/review_patch.py list       # List pending patches
python scripts/review_patch.py show PATCH_ID   # Show patch details
python scripts/review_patch.py apply PATCH_ID  # Apply patch to Academy repo
python scripts/review_patch.py reject PATCH_ID # Reject patch
```

### Visualization API (FastAPI)

```bash
source .venv/bin/activate
uvicorn api.main:app --reload --port 8000
```

**Endpoints** (all under `/api/v1/`):

| Route | Description |
|-------|-------------|
| `GET /api/v1/health` | Health check (ContractStore, Academy, UM status) |
| `GET /api/v1/ecosystem` | Full ecosystem snapshot (nodes, edges, metrics) |
| `GET /api/v1/nodes/{node_id}` | Node detail with metrics and recent records |
| `GET /api/v1/agents` | List all persona agents from Academy |
| `GET /api/v1/agents/{agent_id}` | Persona detail (identity, voice, frameworks) |
| `GET /api/v1/pipeline` | Idea pipeline status from Ultra Magnus |
| `GET /api/v1/pipeline/{idea_id}` | Idea detail with stage history |
| `GET /api/v1/activity` | Activity feed (recent records across all contract types) |
| `GET /api/v1/research/signals` | Research signal list with filtering |

**Environment variables**:

| Variable | Default | Description |
|----------|---------|-------------|
| `ST_RECORDS_DATA_DIR` | `~/projects/st-records/data` | ContractStore data directory |
| `ACADEMY_PERSONAS_DIR` | `~/projects/st-agent-registry/personas` | Academy persona YAML directory |
| `UM_DB_PATH` | `~/incoming/caught_ideas.db` | Ultra Magnus database path |

### Dashboard (Next.js 14)

```bash
cd dashboard
npm install
npm run dev    # http://localhost:3000
```

**Pages**:
- `/` — Home: health banner, node status cards, activity feed
- `/ecosystem` — 3D ecosystem view (React Three Fiber): nodes as platonic solids, bezier edges, growth tiers
- `/agents` — Agent card grid with category badges
- `/agents/[agentId]` — Persona detail (identity, voice, frameworks, case studies)
- `/pipeline` — Pipeline funnel with stage/status badges, scores, filters
- `/pipeline/[ideaId]` — Idea detail view
- `/nodes/[nodeId]` — Node detail with metrics breakdown

## Cron / Automation

Weekly feedback loop (Sundays 2 AM) via `/etc/cron.d/st-records`:

```
0 2 * * 0 apexaipc /home/apexaipc/projects/st-records/scripts/run_loop.sh >> /var/log/st-records/loop.log 2>&1
```

Logrotate configured at `cron/logrotate-st-records`.

**Note**: With Metroplex operational, autonomous patch application is handled by Metroplex Gate 3 (systemd service). The cron job above runs the Sky-Lynx analysis and patch generation loop independently.

## Project Structure

```
st-records/
├── contracts/                      # Pydantic v2 data contracts
│   ├── outcome_record.py           # UM -> SL
│   ├── improvement_recommendation.py  # SL -> Academy
│   ├── persona_upgrade_patch.py    # Academy -> UM
│   ├── research_signal.py          # Research Agents -> IdeaForge
│   └── store.py                    # Dual-write JSONL + SQLite store
├── schemas/                        # JSON Schema exports (v1)
├── api/                            # FastAPI visualization backend
│   ├── main.py                     # App entry point (CORS, lifespan, health)
│   ├── deps.py                     # Singleton data sources (store, academy, UM)
│   ├── models/responses.py         # Pydantic response models
│   ├── readers/                    # Academy YAML reader, UM SQLite reader
│   └── routers/                    # 6 routers (ecosystem, nodes, agents, pipeline, activity, research)
├── dashboard/                      # Next.js 14 + React Three Fiber
│   └── src/
│       ├── app/                    # App Router pages
│       ├── components/             # UI components (ecosystem 3D, agents, pipeline, layout)
│       ├── hooks/                  # SWR data hooks
│       └── lib/                    # API client, types, growth tier system
├── scripts/
│   ├── run_loop.sh                 # Full feedback loop orchestrator
│   ├── loop_status.py              # Loop health reporter
│   ├── persona_upgrader.py         # Claude-powered patch generation
│   └── review_patch.py             # HIL patch review tool
├── cron/                           # Cron + logrotate configs
├── data/                           # JSONL (git-tracked) + SQLite (git-ignored)
│   ├── outcome_records.jsonl
│   ├── improvement_recommendations.jsonl
│   ├── persona_patches.jsonl
│   ├── research_signals.jsonl
│   └── persona_metrics.db          # SQLite query layer
├── tests/
│   ├── test_contracts/             # 5 test modules (contracts + store)
│   └── test_api/                   # 4 test modules (routers)
├── pyproject.toml                  # Package config (snow-town 0.1.0)
├── BLUEPRINT.md                    # Phase tracker (Phases 0-9)
├── CLAUDE.md                       # Claude Code instructions
└── decisions.log                   # Historical decisions log
```

## Testing

```bash
source .venv/bin/activate
pytest tests/                              # All tests
pytest tests/test_contracts/ -v            # Contract + store tests
pytest tests/test_api/ -v                  # API router tests (requires API deps)
```

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| JSONL as source of truth | Append-only, git-tracked, human-readable, survives SQLite corruption |
| SQLite as query layer | Rebuildable from JSONL; status updates written here only |
| Contracts defined here, imported by layers | Single source of truth for inter-system schemas |
| Weekly cadence | Matches Sky-Lynx's existing cron schedule |
| HIL patch review | `review_patch.py` — human approves/rejects before Academy changes |

## Related Projects

| Project | Relationship |
|---------|-------------|
| **Metroplex** | Reads `persona_metrics.db` (patches table) via `?mode=ro` for Gate 3 auto-apply |
| **Sky-Lynx** | Writes `ImprovementRecommendation` records; reads outcomes + signals |
| **Ultra Magnus** | Writes `OutcomeRecord` on terminal pipeline states |
| **Research Agents** | Write `ResearchSignal` records (Perplexity/Gemini/ChatGPT daily) |
| **Agent Persona Academy** | Target of persona patches (YAML files) |

## License

Proprietary - ST Metro Ecosystem
