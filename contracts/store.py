"""ContractStore: Dual-write to JSONL (source of truth) + SQLite (query layer).

JSONL files are append-only and git-tracked.
SQLite is rebuildable from JSONL at any time.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from .agent_upgrade_patch import AgentUpgradePatch
from .improvement_recommendation import ImprovementRecommendation
from .outcome_record import OutcomeRecord
from .persona_upgrade_patch import PersonaUpgradePatch
from .research_signal import ResearchSignal

T = TypeVar("T", bound=BaseModel)

# Default paths
DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "persona_metrics.db"


class ContractStore:
    """Dual-write store for Snow-Town contracts.

    Source of truth: JSONL files (append-only, git-tracked).
    Query layer: SQLite (rebuildable from JSONL).
    """

    def __init__(self, data_dir: Path | None = None, db_path: Path | None = None):
        self.data_dir = data_dir or DATA_DIR
        self.db_path = db_path or (self.data_dir / "persona_metrics.db")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._ensure_tables()
        return self._conn

    def _ensure_tables(self) -> None:
        conn = self._conn
        assert conn is not None
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS outcome_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                idea_id INTEGER NOT NULL,
                idea_title TEXT NOT NULL,
                outcome TEXT NOT NULL,
                overall_score REAL,
                recommendation TEXT,
                capabilities_fit TEXT,
                build_outcome TEXT,
                artifact_count INTEGER DEFAULT 0,
                tech_stack TEXT DEFAULT '[]',
                total_duration_seconds REAL DEFAULT 0,
                tags TEXT DEFAULT '[]',
                github_url TEXT,
                emitted_at TEXT NOT NULL,
                raw_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS improvement_recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recommendation_id TEXT NOT NULL UNIQUE,
                session_id TEXT,
                recommendation_type TEXT NOT NULL,
                target_system TEXT DEFAULT 'persona',
                title TEXT NOT NULL,
                priority TEXT DEFAULT 'medium',
                scope TEXT,
                target_department TEXT,
                status TEXT DEFAULT 'pending',
                emitted_at TEXT NOT NULL,
                raw_json TEXT NOT NULL,
                effectiveness TEXT,
                effectiveness_score REAL,
                effectiveness_evaluated_at TEXT
            );

            -- Migration: add effectiveness columns if missing
        """)
        # Safe column additions (SQLite ignores if column already exists via try/except)
        for col, col_type in [
            ("effectiveness", "TEXT"),
            ("effectiveness_score", "REAL"),
            ("effectiveness_evaluated_at", "TEXT"),
        ]:
            try:
                conn.execute(
                    f"ALTER TABLE improvement_recommendations ADD COLUMN {col} {col_type}"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists

        conn.executescript("""
            CREATE TABLE IF NOT EXISTS persona_patches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patch_id TEXT NOT NULL UNIQUE,
                persona_id TEXT NOT NULL,
                rationale TEXT,
                from_version TEXT,
                to_version TEXT,
                schema_valid INTEGER DEFAULT 1,
                status TEXT DEFAULT 'proposed',
                emitted_at TEXT NOT NULL,
                raw_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS research_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id TEXT NOT NULL UNIQUE,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                url TEXT,
                relevance TEXT NOT NULL,
                relevance_rationale TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                domain TEXT,
                consumed_by TEXT,
                emitted_at TEXT NOT NULL,
                raw_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS agent_patches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patch_id TEXT NOT NULL UNIQUE,
                agent_id TEXT NOT NULL,
                target TEXT NOT NULL,
                section TEXT NOT NULL,
                operation TEXT NOT NULL,
                rationale TEXT,
                status TEXT DEFAULT 'proposed',
                emitted_at TEXT NOT NULL,
                raw_json TEXT NOT NULL,
                effectiveness TEXT,
                effectiveness_score REAL,
                effectiveness_evaluated_at TEXT
            );
        """)
        # Migration: add effectiveness columns to agent_patches if missing
        for col, col_type in [
            ("effectiveness", "TEXT"),
            ("effectiveness_score", "REAL"),
            ("effectiveness_evaluated_at", "TEXT"),
        ]:
            try:
                conn.execute(
                    f"ALTER TABLE agent_patches ADD COLUMN {col} {col_type}"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists
        conn.commit()

    def _jsonl_path(self, contract_type: str) -> Path:
        paths = {
            "outcome_record": self.data_dir / "outcome_records.jsonl",
            "improvement_recommendation": self.data_dir / "improvement_recommendations.jsonl",
            "persona_patch": self.data_dir / "persona_patches.jsonl",
            "research_signal": self.data_dir / "research_signals.jsonl",
            "agent_patch": self.data_dir / "agent_patches.jsonl",
        }
        return paths[contract_type]

    def _append_jsonl(self, contract_type: str, record: BaseModel) -> None:
        path = self._jsonl_path(contract_type)
        with open(path, "a") as f:
            f.write(record.model_dump_json() + "\n")

    # --- OutcomeRecord ---

    def _insert_outcome_sqlite(self, record: OutcomeRecord) -> None:
        """Insert an OutcomeRecord into SQLite only."""
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO outcome_records
            (idea_id, idea_title, outcome, overall_score, recommendation,
             capabilities_fit, build_outcome, artifact_count, tech_stack,
             total_duration_seconds, tags, github_url, emitted_at, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.idea_id,
                record.idea_title,
                record.outcome.value,
                record.overall_score,
                record.recommendation,
                record.capabilities_fit,
                record.build_outcome,
                record.artifact_count,
                json.dumps(record.tech_stack),
                record.total_duration_seconds,
                json.dumps(record.tags),
                record.github_url,
                record.emitted_at.isoformat(),
                record.model_dump_json(),
            ),
        )
        conn.commit()

    def write_outcome(self, record: OutcomeRecord) -> None:
        """Write an OutcomeRecord to JSONL and SQLite."""
        self._append_jsonl("outcome_record", record)
        self._insert_outcome_sqlite(record)

    def read_outcomes(self, limit: int = 100) -> list[OutcomeRecord]:
        """Read OutcomeRecords from JSONL (source of truth)."""
        path = self._jsonl_path("outcome_record")
        if not path.exists():
            return []
        records = []
        for line in path.read_text().strip().splitlines():
            if line:
                records.append(OutcomeRecord.model_validate_json(line))
        return records[-limit:]

    def query_outcomes(
        self,
        outcome: str | None = None,
        idea_id: int | None = None,
        limit: int = 100,
    ) -> list[OutcomeRecord]:
        """Query OutcomeRecords from SQLite."""
        conn = self._get_conn()
        query = "SELECT raw_json FROM outcome_records"
        conditions: list[str] = []
        params: list = []
        if outcome:
            conditions.append("outcome = ?")
            params.append(outcome)
        if idea_id is not None:
            conditions.append("idea_id = ?")
            params.append(idea_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY emitted_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [OutcomeRecord.model_validate_json(row["raw_json"]) for row in rows]

    # --- ImprovementRecommendation ---

    def _insert_recommendation_sqlite(self, rec: ImprovementRecommendation) -> None:
        """Insert an ImprovementRecommendation into SQLite only."""
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO improvement_recommendations
            (recommendation_id, session_id, recommendation_type, target_system,
             title, priority, scope, target_department, status, emitted_at, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rec.recommendation_id,
                rec.session_id,
                rec.recommendation_type.value,
                rec.target_system,
                rec.title,
                rec.priority,
                rec.scope.value,
                rec.target_department,
                rec.status,
                rec.emitted_at.isoformat(),
                rec.model_dump_json(),
            ),
        )
        conn.commit()

    def write_recommendation(self, rec: ImprovementRecommendation) -> None:
        """Write an ImprovementRecommendation to JSONL and SQLite."""
        self._append_jsonl("improvement_recommendation", rec)
        self._insert_recommendation_sqlite(rec)

    def read_recommendations(self, limit: int = 100) -> list[ImprovementRecommendation]:
        """Read ImprovementRecommendations from JSONL."""
        path = self._jsonl_path("improvement_recommendation")
        if not path.exists():
            return []
        records = []
        for line in path.read_text().strip().splitlines():
            if line:
                records.append(ImprovementRecommendation.model_validate_json(line))
        return records[-limit:]

    def query_recommendations(
        self,
        target_system: str | None = None,
        status: str | None = None,
        target_department: str | None = None,
        limit: int = 100,
    ) -> list[ImprovementRecommendation]:
        """Query ImprovementRecommendations from SQLite.

        Overlays current SQLite status onto deserialized objects,
        since raw_json retains the original write-time status.
        """
        conn = self._get_conn()
        query = "SELECT raw_json, status AS current_status FROM improvement_recommendations"
        conditions: list[str] = []
        params: list = []
        if target_system:
            conditions.append("target_system = ?")
            params.append(target_system)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if target_department:
            conditions.append("target_department = ?")
            params.append(target_department)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY emitted_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        results = []
        for row in rows:
            rec = ImprovementRecommendation.model_validate_json(row["raw_json"])
            rec.status = row["current_status"]
            results.append(rec)
        return results

    def update_recommendation_status(self, recommendation_id: str, status: str) -> None:
        """Update the status of a recommendation in SQLite."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE improvement_recommendations SET status = ? WHERE recommendation_id = ?",
            (status, recommendation_id),
        )
        conn.commit()

    def update_recommendation_effectiveness(
        self,
        recommendation_id: str,
        effectiveness: str,
        effectiveness_score: float,
        evaluated_at: str,
    ) -> None:
        """Record effectiveness evaluation for a recommendation.

        Args:
            recommendation_id: The recommendation to update
            effectiveness: 'effective', 'neutral', or 'harmful'
            effectiveness_score: -1.0 to 1.0 (negative = harmful, positive = effective)
            evaluated_at: ISO timestamp of evaluation
        """
        conn = self._get_conn()
        conn.execute(
            """UPDATE improvement_recommendations
            SET effectiveness = ?, effectiveness_score = ?, effectiveness_evaluated_at = ?
            WHERE recommendation_id = ?""",
            (effectiveness, effectiveness_score, evaluated_at, recommendation_id),
        )
        conn.commit()

    def get_applied_recommendations_for_evaluation(self) -> list[dict]:
        """Get applied recommendations that haven't been evaluated for effectiveness yet.

        Returns recommendations where status is 'applied' (auto-applied to CLAUDE.md)
        and effectiveness is NULL.
        """
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT recommendation_id, session_id, title, recommendation_type,
                      target_system, priority, emitted_at, raw_json
            FROM improvement_recommendations
            WHERE status = 'applied' AND effectiveness IS NULL
            ORDER BY emitted_at ASC""",
        ).fetchall()
        return [dict(row) for row in rows]

    def get_effectiveness_summary(self) -> dict:
        """Get summary of effectiveness evaluations for reporting.

        Returns counts and averages by effectiveness category.
        """
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT effectiveness, COUNT(*) as count,
                      AVG(effectiveness_score) as avg_score
            FROM improvement_recommendations
            WHERE effectiveness IS NOT NULL
            GROUP BY effectiveness"""
        ).fetchall()
        return {row["effectiveness"]: {"count": row["count"], "avg_score": row["avg_score"]} for row in rows}

    # --- PersonaUpgradePatch ---

    def _insert_patch_sqlite(self, patch: PersonaUpgradePatch) -> None:
        """Insert a PersonaUpgradePatch into SQLite only."""
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO persona_patches
            (patch_id, persona_id, rationale, from_version, to_version,
             schema_valid, status, emitted_at, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                patch.patch_id,
                patch.persona_id,
                patch.rationale,
                patch.from_version,
                patch.to_version,
                1 if patch.schema_valid else 0,
                patch.status,
                patch.emitted_at.isoformat(),
                patch.model_dump_json(),
            ),
        )
        conn.commit()

    def write_patch(self, patch: PersonaUpgradePatch) -> None:
        """Write a PersonaUpgradePatch to JSONL and SQLite."""
        self._append_jsonl("persona_patch", patch)
        self._insert_patch_sqlite(patch)

    def read_patches(self, limit: int = 100) -> list[PersonaUpgradePatch]:
        """Read PersonaUpgradePatches from JSONL."""
        path = self._jsonl_path("persona_patch")
        if not path.exists():
            return []
        records = []
        for line in path.read_text().strip().splitlines():
            if line:
                records.append(PersonaUpgradePatch.model_validate_json(line))
        return records[-limit:]

    def query_patches(
        self,
        persona_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[PersonaUpgradePatch]:
        """Query PersonaUpgradePatches from SQLite.

        Overlays current SQLite status onto deserialized objects,
        since raw_json retains the original write-time status.
        """
        conn = self._get_conn()
        query = "SELECT raw_json, status AS current_status FROM persona_patches"
        conditions: list[str] = []
        params: list = []
        if persona_id:
            conditions.append("persona_id = ?")
            params.append(persona_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY emitted_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        results = []
        for row in rows:
            patch = PersonaUpgradePatch.model_validate_json(row["raw_json"])
            patch.status = row["current_status"]
            results.append(patch)
        return results

    def update_patch_status(self, patch_id: str, status: str) -> None:
        """Update the status of a patch in SQLite."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE persona_patches SET status = ? WHERE patch_id = ?",
            (status, patch_id),
        )
        conn.commit()

    # --- AgentUpgradePatch ---

    def _insert_agent_patch_sqlite(self, patch: AgentUpgradePatch) -> None:
        """Insert an AgentUpgradePatch into SQLite only."""
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO agent_patches
            (patch_id, agent_id, target, section, operation,
             rationale, status, emitted_at, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                patch.patch_id,
                patch.agent_id,
                patch.target,
                patch.section,
                patch.operation,
                patch.rationale,
                patch.status,
                patch.emitted_at.isoformat(),
                patch.model_dump_json(),
            ),
        )
        conn.commit()

    def write_agent_patch(self, patch: AgentUpgradePatch) -> None:
        """Write an AgentUpgradePatch to JSONL and SQLite."""
        self._append_jsonl("agent_patch", patch)
        self._insert_agent_patch_sqlite(patch)

    def read_agent_patches(self, limit: int = 100) -> list[AgentUpgradePatch]:
        """Read AgentUpgradePatches from JSONL."""
        path = self._jsonl_path("agent_patch")
        if not path.exists():
            return []
        records = []
        for line in path.read_text().strip().splitlines():
            if line:
                records.append(AgentUpgradePatch.model_validate_json(line))
        return records[-limit:]

    def query_agent_patches(
        self,
        agent_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[AgentUpgradePatch]:
        """Query AgentUpgradePatches from SQLite.

        Overlays current SQLite status onto deserialized objects,
        since raw_json retains the original write-time status.
        """
        conn = self._get_conn()
        query = "SELECT raw_json, status AS current_status FROM agent_patches"
        conditions: list[str] = []
        params: list = []
        if agent_id:
            conditions.append("agent_id = ?")
            params.append(agent_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY emitted_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        results = []
        for row in rows:
            patch = AgentUpgradePatch.model_validate_json(row["raw_json"])
            patch.status = row["current_status"]
            results.append(patch)
        return results

    def update_agent_patch_status(self, patch_id: str, status: str) -> None:
        """Update the status of an agent patch in SQLite."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE agent_patches SET status = ? WHERE patch_id = ?",
            (status, patch_id),
        )
        conn.commit()

    def update_agent_patch_effectiveness(
        self,
        patch_id: str,
        effectiveness: str,
        effectiveness_score: float,
        evaluated_at: str,
    ) -> None:
        """Record effectiveness evaluation for an agent patch."""
        conn = self._get_conn()
        conn.execute(
            """UPDATE agent_patches
            SET effectiveness = ?, effectiveness_score = ?, effectiveness_evaluated_at = ?
            WHERE patch_id = ?""",
            (effectiveness, effectiveness_score, evaluated_at, patch_id),
        )
        conn.commit()

    def get_applied_agent_patches_for_evaluation(self) -> list[dict]:
        """Get applied agent patches that haven't been evaluated yet."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT patch_id, agent_id, target, section, operation,
                      rationale, status, emitted_at, raw_json
            FROM agent_patches
            WHERE status = 'applied' AND effectiveness IS NULL
            ORDER BY emitted_at ASC"""
        ).fetchall()
        return [dict(row) for row in rows]

    def get_agent_effectiveness_summary(self) -> dict:
        """Get summary of agent patch effectiveness evaluations."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT effectiveness, COUNT(*) as count,
                      AVG(effectiveness_score) as avg_score
            FROM agent_patches
            WHERE effectiveness IS NOT NULL
            GROUP BY effectiveness"""
        ).fetchall()
        return {
            row["effectiveness"]: {"count": row["count"], "avg_score": row["avg_score"]}
            for row in rows
        }

    def get_recent_agent_patches_with_scores(self, limit: int = 20) -> list[dict]:
        """Get recent agent patches with effectiveness scores for digest."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT patch_id, agent_id, target, section, operation,
                      rationale, status, effectiveness, effectiveness_score,
                      effectiveness_evaluated_at, emitted_at
            FROM agent_patches
            ORDER BY emitted_at DESC
            LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    # --- ResearchSignal ---

    def _insert_signal_sqlite(self, signal: ResearchSignal) -> None:
        """Insert a ResearchSignal into SQLite only."""
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO research_signals
            (signal_id, source, title, summary, url, relevance,
             relevance_rationale, tags, domain, consumed_by, emitted_at, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                signal.signal_id,
                signal.source.value,
                signal.title,
                signal.summary,
                signal.url,
                signal.relevance.value,
                signal.relevance_rationale,
                json.dumps(signal.tags),
                signal.domain,
                signal.consumed_by,
                signal.emitted_at.isoformat(),
                signal.model_dump_json(),
            ),
        )
        conn.commit()

    def write_signal(self, signal: ResearchSignal) -> None:
        """Write a ResearchSignal to JSONL and SQLite."""
        self._append_jsonl("research_signal", signal)
        self._insert_signal_sqlite(signal)

    def read_signals(self, limit: int = 100) -> list[ResearchSignal]:
        """Read ResearchSignals from JSONL (source of truth)."""
        path = self._jsonl_path("research_signal")
        if not path.exists():
            return []
        records = []
        for line in path.read_text().strip().splitlines():
            if line:
                records.append(ResearchSignal.model_validate_json(line))
        return records[-limit:]

    def query_signals(
        self,
        source: str | None = None,
        relevance: str | None = None,
        domain: str | None = None,
        consumed: bool | None = None,
        limit: int = 100,
    ) -> list[ResearchSignal]:
        """Query ResearchSignals from SQLite.

        Overlays current SQLite consumed_by onto deserialized objects,
        since raw_json retains the original write-time state.
        """
        conn = self._get_conn()
        query = "SELECT raw_json, consumed_by AS current_consumed_by FROM research_signals"
        conditions: list[str] = []
        params: list = []
        if source:
            conditions.append("source = ?")
            params.append(source)
        if relevance:
            conditions.append("relevance = ?")
            params.append(relevance)
        if domain:
            conditions.append("domain = ?")
            params.append(domain)
        if consumed is True:
            conditions.append("consumed_by IS NOT NULL")
        elif consumed is False:
            conditions.append("consumed_by IS NULL")
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY emitted_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        results = []
        for row in rows:
            signal = ResearchSignal.model_validate_json(row["raw_json"])
            signal.consumed_by = row["current_consumed_by"]
            results.append(signal)
        return results

    def update_signal_consumed_by(self, signal_id: str, consumed_by: str) -> None:
        """Mark a signal as consumed by a downstream process."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE research_signals SET consumed_by = ? WHERE signal_id = ?",
            (consumed_by, signal_id),
        )
        conn.commit()

    # --- Rebuild ---

    def rebuild_sqlite(self) -> None:
        """Rebuild SQLite from JSONL files. Useful for recovery.

        Drops and recreates tables to handle schema changes,
        then re-inserts all records from JSONL without re-appending to JSONL.
        """
        conn = self._get_conn()
        conn.executescript("""
            DROP TABLE IF EXISTS outcome_records;
            DROP TABLE IF EXISTS improvement_recommendations;
            DROP TABLE IF EXISTS persona_patches;
            DROP TABLE IF EXISTS agent_patches;
            DROP TABLE IF EXISTS research_signals;
        """)
        self._ensure_tables()

        for record in self.read_outcomes(limit=10000):
            self._insert_outcome_sqlite(record)
        for rec in self.read_recommendations(limit=10000):
            self._insert_recommendation_sqlite(rec)
        for patch in self.read_patches(limit=10000):
            self._insert_patch_sqlite(patch)
        for signal in self.read_signals(limit=10000):
            self._insert_signal_sqlite(signal)
        for agent_patch in self.read_agent_patches(limit=10000):
            self._insert_agent_patch_sqlite(agent_patch)

    def close(self) -> None:
        """Close the SQLite connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
