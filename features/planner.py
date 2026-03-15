"""
Planner – SQLite assignments. Voice-controlled only.
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from core import config

PLANNER_DB_PATH = config.PLANNER_DB_PATH


@contextmanager
def _db():
    conn = sqlite3.connect(PLANNER_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                assignment TEXT NOT NULL,
                due_date TEXT NOT NULL,
                estimated_time TEXT NOT NULL,
                created_at TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0
            )
        """)


def list_assignments(completed: bool | None = None):
    with _db() as conn:
        if completed is None:
            rows = conn.execute(
                "SELECT id, subject, assignment, due_date, estimated_time, created_at, completed FROM assignments ORDER BY due_date ASC, id ASC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, subject, assignment, due_date, estimated_time, created_at, completed FROM assignments WHERE completed = ? ORDER BY due_date ASC, id ASC",
                (1 if completed else 0,),
            ).fetchall()
        return [dict(r) for r in rows]


def add_assignment(subject: str, assignment: str, due_date: str, estimated_time: str) -> int:
    created_at = datetime.utcnow().isoformat() + "Z"
    with _db() as conn:
        cur = conn.execute(
            "INSERT INTO assignments (subject, assignment, due_date, estimated_time, created_at, completed) VALUES (?, ?, ?, ?, ?, 0)",
            (subject.strip(), assignment.strip(), due_date.strip(), estimated_time.strip(), created_at),
        )
        return cur.lastrowid


def set_completed(assignment_id: int, completed: bool):
    with _db() as conn:
        conn.execute("UPDATE assignments SET completed = ? WHERE id = ?", (1 if completed else 0, assignment_id))


def delete_assignment(assignment_id: int):
    with _db() as conn:
        conn.execute("DELETE FROM assignments WHERE id = ?", (assignment_id,))


def get_by_id(assignment_id: int) -> dict | None:
    with _db() as conn:
        row = conn.execute(
            "SELECT id, subject, assignment, due_date, estimated_time, created_at, completed FROM assignments WHERE id = ?",
            (assignment_id,),
        ).fetchone()
        return dict(row) if row else None


def find_by_name_or_id(name_or_id: str):
    try:
        aid = int(name_or_id.strip())
        return get_by_id(aid)
    except ValueError:
        pass
    name = name_or_id.strip().lower()
    for a in list_assignments(completed=None):
        if name in (a["assignment"] or "").lower() or name in (a["subject"] or "").lower():
            return a
    return None
