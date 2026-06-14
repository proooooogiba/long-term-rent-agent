from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from src.agent.state import AgentState, RentalRequirements, ScoredListing


MEMORY_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS agent_case_memory (
    case_id TEXT PRIMARY KEY,
    client_id TEXT,
    last_user_message TEXT NOT NULL DEFAULT '',
    last_intent TEXT,
    last_requirements_json TEXT NOT NULL DEFAULT '{}',
    last_ranked_listings_json TEXT NOT NULL DEFAULT '[]',
    last_verification_status TEXT,
    last_final_summary TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES relocation_cases (case_id),
    FOREIGN KEY (client_id) REFERENCES clients (client_id)
);

CREATE TABLE IF NOT EXISTS agent_run_history (
    run_id TEXT PRIMARY KEY,
    case_id TEXT,
    client_id TEXT,
    user_message TEXT NOT NULL DEFAULT '',
    intent TEXT,
    verification_status TEXT,
    ranked_count INTEGER NOT NULL DEFAULT 0,
    final_summary TEXT NOT NULL DEFAULT '',
    requirements_json TEXT NOT NULL DEFAULT '{}',
    shortlist_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES relocation_cases (case_id),
    FOREIGN KEY (client_id) REFERENCES clients (client_id)
);

CREATE INDEX IF NOT EXISTS idx_agent_run_history_case ON agent_run_history(case_id);
CREATE INDEX IF NOT EXISTS idx_agent_run_history_client ON agent_run_history(client_id);
"""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class CaseMemorySnapshot(BaseModel):
    case_id: str
    client_id: str | None = None
    requirements: RentalRequirements | None = None
    ranked_listings: list[ScoredListing] = Field(default_factory=list)
    verification_status: str | None = None
    final_summary: str = ""
    updated_at: str


class AgentMemoryStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.executescript(MEMORY_SCHEMA_SQL)
        return connection

    def load_case_memory(self, case_id: str) -> CaseMemorySnapshot | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    case_id,
                    client_id,
                    last_requirements_json,
                    last_ranked_listings_json,
                    last_verification_status,
                    last_final_summary,
                    updated_at
                FROM agent_case_memory
                WHERE case_id = ?
                """,
                (case_id,),
            ).fetchone()
        if row is None:
            return None

        requirements_payload = json.loads(row["last_requirements_json"] or "null")
        ranked_payload = json.loads(row["last_ranked_listings_json"] or "[]")
        return CaseMemorySnapshot(
            case_id=row["case_id"],
            client_id=row["client_id"],
            requirements=(
                None
                if requirements_payload in (None, {})
                else RentalRequirements.model_validate(requirements_payload)
            ),
            ranked_listings=[ScoredListing.model_validate(item) for item in ranked_payload],
            verification_status=row["last_verification_status"],
            final_summary=row["last_final_summary"] or "",
            updated_at=row["updated_at"],
        )

    def save_state(self, state: AgentState) -> None:
        if not state.case_id:
            return

        requirements_json = json.dumps(
            state.requirements.model_dump(mode="json") if state.requirements else None,
            ensure_ascii=False,
        )
        ranked_json = json.dumps(
            [item.model_dump(mode="json") for item in state.ranked_listings[:5]],
            ensure_ascii=False,
        )
        final_summary = (
            state.final_recommendation.summary
            if state.final_recommendation and state.final_recommendation.summary
            else (state.final_answer or "").splitlines()[0] if state.final_answer else ""
        )
        verification_status = (
            state.verification_result.status
            if state.verification_result is not None
            else None
        )
        updated_at = _utc_now_iso()

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO agent_case_memory (
                    case_id,
                    client_id,
                    last_user_message,
                    last_intent,
                    last_requirements_json,
                    last_ranked_listings_json,
                    last_verification_status,
                    last_final_summary,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(case_id) DO UPDATE SET
                    client_id = excluded.client_id,
                    last_user_message = excluded.last_user_message,
                    last_intent = excluded.last_intent,
                    last_requirements_json = excluded.last_requirements_json,
                    last_ranked_listings_json = excluded.last_ranked_listings_json,
                    last_verification_status = excluded.last_verification_status,
                    last_final_summary = excluded.last_final_summary,
                    updated_at = excluded.updated_at
                """,
                (
                    state.case_id,
                    state.client_id,
                    state.user_message,
                    state.intent,
                    requirements_json,
                    ranked_json,
                    verification_status,
                    final_summary,
                    updated_at,
                ),
            )
            connection.execute(
                """
                INSERT INTO agent_run_history (
                    run_id,
                    case_id,
                    client_id,
                    user_message,
                    intent,
                    verification_status,
                    ranked_count,
                    final_summary,
                    requirements_json,
                    shortlist_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"RUN-{uuid.uuid4().hex[:12]}",
                    state.case_id,
                    state.client_id,
                    state.user_message,
                    state.intent,
                    verification_status,
                    len(state.ranked_listings),
                    final_summary,
                    requirements_json,
                    ranked_json,
                    updated_at,
                ),
            )
            self._write_back_client_preferences(connection, state, final_summary)
            self._write_back_case_notes(connection, state, final_summary, verification_status)
            connection.commit()

    def _write_back_client_preferences(
        self,
        connection: sqlite3.Connection,
        state: AgentState,
        final_summary: str,
    ) -> None:
        if not state.client_id or state.requirements is None:
            return

        current = connection.execute(
            "SELECT * FROM client_preferences WHERE client_id = ?",
            (state.client_id,),
        ).fetchone()

        def existing(field: str, default: object) -> object:
            if current is None:
                return default
            return current[field]

        requirements = state.requirements
        preferred_districts = (
            requirements.preferred_districts
            if requirements.preferred_districts
            else json.loads(existing("preferred_districts", "[]"))
        )
        comments = (
            f"Updated from agent memory on {_utc_now_iso()}: {final_summary}"
            if final_summary
            else f"Updated from agent memory on {_utc_now_iso()}."
        )

        connection.execute(
            """
            INSERT INTO client_preferences (
                client_id,
                preferred_districts,
                furnished,
                elevator,
                floor_max,
                max_commute_minutes,
                school_requirement,
                rooms_min,
                lease_months,
                comments
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(client_id) DO UPDATE SET
                preferred_districts = excluded.preferred_districts,
                furnished = excluded.furnished,
                elevator = excluded.elevator,
                floor_max = excluded.floor_max,
                max_commute_minutes = excluded.max_commute_minutes,
                school_requirement = excluded.school_requirement,
                rooms_min = excluded.rooms_min,
                lease_months = excluded.lease_months,
                comments = excluded.comments
            """,
            (
                state.client_id,
                json.dumps(preferred_districts, ensure_ascii=False),
                self._coerce_bool_for_db(
                    requirements.furnished
                    if requirements.furnished is not None
                    else existing("furnished", None)
                ),
                self._coerce_bool_for_db(
                    requirements.elevator
                    if requirements.elevator is not None
                    else existing("elevator", None)
                ),
                requirements.floor_max
                if requirements.floor_max is not None
                else existing("floor_max", None),
                requirements.max_commute_minutes
                if requirements.max_commute_minutes is not None
                else existing("max_commute_minutes", None),
                self._coerce_bool_for_db(
                    requirements.school_requirement
                    if requirements.school_requirement is not None
                    else existing("school_requirement", None)
                ),
                requirements.rooms_min
                if requirements.rooms_min is not None
                else existing("rooms_min", None),
                requirements.lease_months
                if requirements.lease_months is not None
                else existing("lease_months", None),
                comments,
            ),
        )

    def _write_back_case_notes(
        self,
        connection: sqlite3.Connection,
        state: AgentState,
        final_summary: str,
        verification_status: str | None,
    ) -> None:
        if not state.case_id:
            return

        row = connection.execute(
            "SELECT notes FROM relocation_cases WHERE case_id = ?",
            (state.case_id,),
        ).fetchone()
        if row is None:
            return

        notes = json.loads(row["notes"] or "[]")
        if not isinstance(notes, list):
            notes = []
        notes = [
            note
            for note in notes
            if not (
                isinstance(note, str)
                and (
                    note.startswith("agent_memory_summary:")
                    or note.startswith("agent_memory_status:")
                )
            )
        ]
        if final_summary:
            notes.append(f"agent_memory_summary:{final_summary}")
        if verification_status:
            notes.append(f"agent_memory_status:{verification_status}")

        connection.execute(
            """
            UPDATE relocation_cases
            SET notes = ?
            WHERE case_id = ?
            """,
            (json.dumps(notes, ensure_ascii=False), state.case_id),
        )

    @staticmethod
    def _coerce_bool_for_db(value: object) -> int | None:
        if value is None:
            return None
        return 1 if bool(value) else 0
