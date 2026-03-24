"""
SQLite database for persisting weekly training plans.
"""

import sqlite3
import json
import os
from datetime import date, datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "plans.db")


def get_connection():
    """Get a connection to the SQLite database, creating tables if needed."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS weekly_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_start DATE NOT NULL UNIQUE,
            plan JSON NOT NULL,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


def get_week_start(d=None):
    """Get Monday of the week for a given date (default: today)."""
    if d is None:
        d = date.today()
    return d - timedelta(days=d.weekday())


def save_plan(week_start, plan, notes=""):
    """Save or update a weekly plan."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO weekly_plans (week_start, plan, notes)
        VALUES (?, ?, ?)
        ON CONFLICT(week_start) DO UPDATE SET
            plan = excluded.plan,
            notes = excluded.notes,
            created_at = CURRENT_TIMESTAMP
    """, (week_start.isoformat(), json.dumps(plan, ensure_ascii=False), notes))
    conn.commit()
    conn.close()


def get_plan(week_start):
    """Get plan for a specific week. Returns dict or None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM weekly_plans WHERE week_start = ?",
        (week_start.isoformat(),)
    ).fetchone()
    conn.close()
    if row:
        return {
            "id": row["id"],
            "week_start": date.fromisoformat(row["week_start"]),
            "plan": json.loads(row["plan"]),
            "notes": row["notes"],
            "created_at": row["created_at"],
        }
    return None


def get_all_plans():
    """Get all saved plans, most recent first."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM weekly_plans ORDER BY week_start DESC"
    ).fetchall()
    conn.close()
    return [
        {
            "id": row["id"],
            "week_start": date.fromisoformat(row["week_start"]),
            "plan": json.loads(row["plan"]),
            "notes": row["notes"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def delete_plan(week_start):
    """Delete a plan for a specific week."""
    conn = get_connection()
    conn.execute(
        "DELETE FROM weekly_plans WHERE week_start = ?",
        (week_start.isoformat(),)
    )
    conn.commit()
    conn.close()


def update_notes(week_start, notes):
    """Update notes for a specific week."""
    conn = get_connection()
    conn.execute(
        "UPDATE weekly_plans SET notes = ? WHERE week_start = ?",
        (notes, week_start.isoformat())
    )
    conn.commit()
    conn.close()
