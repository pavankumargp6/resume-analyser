"""Opt-in local persistence for generated analysis reports."""

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from typing import Any


@dataclass(frozen=True)
class SavedAnalysis:
    """A locally saved report without the original resume text."""

    id: int
    created_at: str
    analysis: dict[str, Any]


class ReportRepository:
    """Store report JSON in SQLite; callers must obtain user consent."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def initialize(self) -> None:
        """Create the database and reports table if needed."""
        if str(self.database_path) != ":memory:":
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS saved_analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    analysis_json TEXT NOT NULL
                )
                """
            )

    def save(self, analysis: dict[str, Any]) -> int:
        """Persist a generated report and return its row ID."""
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO saved_analyses (analysis_json) VALUES (?)",
                (json.dumps(analysis, ensure_ascii=True),),
            )
            return int(cursor.lastrowid)

    def list_recent(self, limit: int = 10) -> list[SavedAnalysis]:
        """Return the newest saved reports."""
        if limit <= 0:
            raise ValueError("limit must be greater than zero.")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, created_at, analysis_json
                FROM saved_analyses
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            SavedAnalysis(
                id=row["id"],
                created_at=row["created_at"],
                analysis=json.loads(row["analysis_json"]),
            )
            for row in rows
        ]

    def delete(self, report_id: int) -> None:
        """Delete one locally saved report."""
        with self._connect() as connection:
            connection.execute("DELETE FROM saved_analyses WHERE id = ?", (report_id,))

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.database_path))
        connection.row_factory = sqlite3.Row
        return connection
