"""Reviewer decisions persisted in SQLite. Stores case ids and free-text notes
only; the UI tells reviewers not to type patient identifiers into notes."""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('accept', 'reject', 'note')),
    note TEXT NOT NULL DEFAULT '',
    reviewer TEXT NOT NULL DEFAULT 'reviewer',
    score REAL,
    review_limit REAL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS reviews_case ON reviews(case_id);
"""


class ReviewLog:
    def __init__(self, path: Path | str):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def add(self, case_id: str, decision: str, note: str = "", reviewer: str = "reviewer",
            score: float | None = None, review_limit: float | None = None) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO reviews (case_id, decision, note, reviewer, score, review_limit, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (case_id, decision, note, reviewer, score, review_limit, now),
            )
            self._conn.commit()
            rid = cur.lastrowid
        return self.get(int(rid))  # type: ignore[arg-type]

    def get(self, rid: int) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute("SELECT * FROM reviews WHERE id = ?", (rid,)).fetchone()
        return dict(row)

    def list(self, case_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            if case_id:
                rows = self._conn.execute("SELECT * FROM reviews WHERE case_id = ? ORDER BY id", (case_id,)).fetchall()
            else:
                rows = self._conn.execute("SELECT * FROM reviews ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    def latest_by_case(self) -> dict[str, str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT case_id, decision FROM reviews WHERE id IN (SELECT MAX(id) FROM reviews "
                "WHERE decision IN ('accept', 'reject') GROUP BY case_id)"
            ).fetchall()
        return {r["case_id"]: r["decision"] for r in rows}

    def close(self) -> None:
        self._conn.close()
