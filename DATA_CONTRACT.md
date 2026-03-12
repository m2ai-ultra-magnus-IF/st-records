# ST Factory Data Contract

Stable interface for all systems that read from or write to ST Factory's data stores. ST Factory uses a dual-write architecture: **JSONL files are source of truth** (append-only, git-tracked), **SQLite is the query layer** (status updates, indexed queries, rebuildable).

## Database: `data/persona_metrics.db`

SQLite 3 database. External consumers **must** open in read-only mode:

```python
import sqlite3
conn = sqlite3.connect("file:/path/to/persona_metrics.db?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
```

## Tables

### `outcome_records`

Terminal pipeline outcomes from Ultra-Magnus builds.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Internal row ID |
| `idea_id` | INTEGER | NOT NULL | IdeaForge idea ID |
| `idea_title` | TEXT | NOT NULL | Idea title |
| `outcome` | TEXT | NOT NULL | `published`, `rejected`, `deferred`, `build_failed`, `feature_backlog` |
| `overall_score` | REAL | nullable | IdeaForge weighted score |
| `recommendation` | TEXT | nullable | Build recommendation text |
| `capabilities_fit` | TEXT | nullable | Capabilities assessment |
| `build_outcome` | TEXT | nullable | Build result description |
| `artifact_count` | INTEGER | DEFAULT 0 | Number of artifacts produced |
| `tech_stack` | TEXT | JSON array | Technologies used in build |
| `total_duration_seconds` | REAL | DEFAULT 0 | Pipeline wall-clock time |
| `tags` | TEXT | JSON array | Categorization tags |
| `github_url` | TEXT | nullable | Published repo URL |
| `emitted_at` | TEXT | NOT NULL | ISO-8601 emission timestamp |
| `raw_json` | TEXT | NOT NULL | Full contract serialized as JSON |

### `improvement_recommendations`

Sky-Lynx generated recommendations for system improvement.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Internal row ID |
| `recommendation_id` | TEXT | NOT NULL UNIQUE | Unique identifier |
| `session_id` | TEXT | nullable | Analysis session ID (dedup key) |
| `recommendation_type` | TEXT | NOT NULL | See types below |
| `target_system` | TEXT | DEFAULT 'persona' | `persona`, `claude_md`, `pipeline` |
| `title` | TEXT | NOT NULL | Recommendation title |
| `priority` | TEXT | DEFAULT 'medium' | `high`, `medium`, `low` |
| `scope` | TEXT | | `specific_persona`, `all_personas`, `all_in_department` |
| `target_department` | TEXT | nullable | Required when scope = `all_in_department` |
| `status` | TEXT | DEFAULT 'pending' | `pending`, `dispatched`, `applied`, `rejected` |
| `emitted_at` | TEXT | NOT NULL | ISO-8601 timestamp |
| `raw_json` | TEXT | NOT NULL | Full contract as JSON |
| `effectiveness` | TEXT | nullable | `effective`, `neutral`, `harmful` (post-hoc) |
| `effectiveness_score` | REAL | nullable | -1.0 to 1.0 (post-hoc) |
| `effectiveness_evaluated_at` | TEXT | nullable | ISO-8601 timestamp |

**Recommendation types:** `voice_adjustment`, `framework_addition`, `framework_refinement`, `validation_marker_change`, `case_study_addition`, `constraint_addition`, `constraint_removal`, `claude_md_update`, `pipeline_change`, `tier_promotion`, `tier_demotion`, `other`

### `persona_patches`

Persona YAML upgrade patches generated from recommendations.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Internal row ID |
| `patch_id` | TEXT | NOT NULL UNIQUE | Unique identifier |
| `persona_id` | TEXT | NOT NULL | Target persona (e.g. `sky-lynx`) |
| `rationale` | TEXT | nullable | Why this patch was generated |
| `from_version` | TEXT | nullable | Previous persona version |
| `to_version` | TEXT | nullable | New persona version |
| `schema_valid` | INTEGER | DEFAULT 1 | 1=valid, 0=invalid Academy schema |
| `status` | TEXT | DEFAULT 'proposed' | `proposed`, `applied`, `rejected` |
| `emitted_at` | TEXT | NOT NULL | ISO-8601 timestamp |
| `raw_json` | TEXT | NOT NULL | Full contract as JSON |

### `research_signals`

Market research signals from the research agent fleet.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Internal row ID |
| `signal_id` | TEXT | NOT NULL UNIQUE | Unique identifier |
| `source` | TEXT | NOT NULL | See sources below |
| `title` | TEXT | NOT NULL | Signal title |
| `summary` | TEXT | NOT NULL | Signal summary |
| `url` | TEXT | nullable | Source URL |
| `relevance` | TEXT | NOT NULL | `high`, `medium`, `low` |
| `relevance_rationale` | TEXT | DEFAULT '' | Why this relevance level |
| `tags` | TEXT | JSON array | Categorization tags |
| `domain` | TEXT | nullable | Technology domain |
| `consumed_by` | TEXT | nullable | Downstream consumer name |
| `emitted_at` | TEXT | NOT NULL | ISO-8601 timestamp |
| `raw_json` | TEXT | NOT NULL | Full contract as JSON |

**Signal sources:** `arxiv_hf`, `tool_monitor`, `domain_watch`, `idea_machine`, `youtube_scanner`, `rss_scanner`, `manual`, `trend_analyzer`, `perplexity`, `chatgpt`, `gemini_research`

## JSONL Files (Source of Truth)

All in `data/`. Append-only, git-tracked, one JSON record per line.

| File | Contract | Access Methods |
|------|----------|---------------|
| `outcome_records.jsonl` | OutcomeRecord | `store.write_outcome()`, `store.read_outcomes()` |
| `improvement_recommendations.jsonl` | ImprovementRecommendation | `store.write_recommendation()`, `store.read_recommendations()` |
| `persona_patches.jsonl` | PersonaUpgradePatch | `store.write_patch()`, `store.read_patches()` |
| `research_signals.jsonl` | ResearchSignal | `store.write_signal()`, `store.read_signals()` |

## Dual-Write Architecture

- **`write_*()`** — appends to JSONL + inserts to SQLite
- **`read_*()`** — reads from JSONL (immutable historical view)
- **`query_*()`** — reads from SQLite (current state with status overlays)
- **`update_*_status()`** — SQLite only (mutable state)
- **`rebuild_sqlite()`** — drops + recreates all SQLite tables from JSONL

**Rule:** Status-aware queries use `query_*()` (SQLite). Historical/immutable queries use `read_*()` (JSONL).

## Status Lifecycles

### ImprovementRecommendation
```
pending → dispatched → applied
                    → rejected
```

### PersonaUpgradePatch
```
proposed → applied
         → rejected
```
Human review required between states (via `scripts/review_patch.py`).

### OutcomeRecord
No mutable status — `outcome` is terminal: `published`, `rejected`, `deferred`, `build_failed`, `feature_backlog`.

### ResearchSignal
No mutable status — `consumed_by` tracks downstream consumption.

## Reader Contracts

### Metroplex (`readers/stfactory_reader.py`)

**Reads:** `persona_patches` table (opens with `?mode=ro`). Retrieves patches with `status='proposed'` for Gate 3.

**Writes:** Updates `persona_patches.status` to `applied` or `rejected` after processing.

### Sky-Lynx (`src/sky_lynx/`)

**Reads:** `outcome_records.jsonl` via `outcome_reader.py`, `research_signals.jsonl` via `research_reader.py`.

**Purpose:** Weekly analysis loop (Sunday 2 AM) identifies patterns, generates ImprovementRecommendations.

### ClaudeClaw

**Reads:** `persona_metrics.db` for dashboard reporting (research signal age, metrics).

### FastAPI Dashboard (`api/main.py`)

**Reads:** All four tables in `persona_metrics.db`. Never writes. Endpoints: `/api/v1/activity`, `/api/v1/ecosystem`, `/api/v1/nodes`, `/api/v1/agents`, `/api/v1/pipeline`, `/api/v1/research`.

## Writer Contracts

### Ultra-Magnus (`um_bridge_worker.py::emit_outcome_record()`)

**Writes:** `OutcomeRecord` contracts when an idea reaches terminal pipeline state. Uses `store.write_outcome()` (dual-write to JSONL + SQLite). Includes full IdeaForge scores in `raw_json`.

### Sky-Lynx (`src/sky_lynx/report_writer.py`)

**Writes:** `ImprovementRecommendation` contracts after weekly analysis. Uses `store.write_recommendation()`. Deduplication via `session_id`.

### Research Agents (`src/research_agents/signal_writer.py`)

**Writes:** `ResearchSignal` contracts from daily cron agents (one per LLM). Uses `store.write_signal()`.

### persona_upgrader (`scripts/persona_upgrader.py`)

**Writes:** `PersonaUpgradePatch` contracts from pending recommendations where `target_system='persona'`. Uses Claude API to generate patches. Default status: `proposed`.

## Importing Contracts

ST Factory contracts are imported via `sys.path` injection, not pip:

```python
import sys
sys.path.insert(0, os.path.expanduser("~/projects/st-factory"))
from contracts.outcome_record import OutcomeRecord
from contracts.store import ContractStore
```

## Environment Variables

- `SNOW_TOWN_DATA_DIR` (default: `~/projects/st-factory/data`) — JSONL + SQLite directory
- `STFACTORY_DB_PATH` (default: `~/projects/st-factory/data/persona_metrics.db`)

## Stability Guarantees

- Column names and types are stable. New columns may be added; existing columns will not be renamed or removed.
- JSONL files are append-only. Records are never modified or deleted.
- SQLite is rebuildable from JSONL at any time via `store.rebuild_sqlite()`.
- Contract versions follow semver. Breaking changes increment the major version.
- Always use `?mode=ro` for read-only consumers.
- Status values are stable. New values may be added to enums.
