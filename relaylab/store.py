"""Persistence shared by the API and the single delivery worker."""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path(os.getenv("RELAYLAB_DB", "data/relaylab.sqlite3"))


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connection(db):
    con = sqlite3.connect(str(db), timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        with con:
            yield con
    finally:
        con.close()


def initialize(db=DEFAULT_DB):
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    with connection(db) as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS jobs (
                event_id TEXT PRIMARY KEY REFERENCES events(id),
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending', 'delivered', 'failed')),
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL REFERENCES events(id),
                attempted_at TEXT NOT NULL,
                http_status INTEGER,
                error TEXT
            );
        """)


def accept_event(db, event_id, event_type, payload):
    """Return True for a new event, False for an identical duplicate.

    Reusing an ID with a different event is a conflict. The event and delivery
    job commit together, so an accepted event always has a pending job.
    """
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    with connection(db) as con:
        con.execute("BEGIN IMMEDIATE")
        existing = con.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if existing:
            if existing["event_type"] != event_type or existing["payload"] != encoded:
                raise ValueError("Event ID already belongs to a different event")
            return False
        timestamp = now()
        con.execute("INSERT INTO events VALUES (?, ?, ?, ?)",
                    (event_id, event_type, encoded, timestamp))
        con.execute("INSERT INTO jobs VALUES (?, 'pending', ?)", (event_id, timestamp))
        return True


def decode(row):
    event = dict(row)
    event["payload"] = json.loads(event["payload"])
    return event


def list_events(db, limit=50):
    with connection(db) as con:
        rows = con.execute("""
            SELECT e.*, j.status, j.updated_at FROM events e
            JOIN jobs j ON j.event_id = e.id
            ORDER BY e.rowid DESC LIMIT ?
        """, (limit,)).fetchall()
    return [decode(row) for row in rows]


def get_event(db, event_id):
    with connection(db) as con:
        row = con.execute("""
            SELECT e.*, j.status, j.updated_at FROM events e
            JOIN jobs j ON j.event_id = e.id WHERE e.id = ?
        """, (event_id,)).fetchone()
        if row is None:
            return None
        result = decode(row)
        result["attempts"] = [dict(r) for r in con.execute(
            "SELECT * FROM attempts WHERE event_id = ? ORDER BY id", (event_id,))]
        return result


def next_pending(db):
    # Only ONE worker is supported. This is not a concurrent job-claim protocol.
    with connection(db) as con:
        row = con.execute("""
            SELECT e.* FROM events e JOIN jobs j ON j.event_id = e.id
            WHERE j.status = 'pending' ORDER BY e.rowid LIMIT 1
        """).fetchone()
    return decode(row) if row else None


def record_attempt(db, event_id, http_status, error):
    succeeded = error is None and http_status is not None and 200 <= http_status < 300
    with connection(db) as con:
        timestamp = now()
        con.execute("""
            INSERT INTO attempts (event_id, attempted_at, http_status, error)
            VALUES (?, ?, ?, ?)
        """, (event_id, timestamp, http_status, error))
        con.execute("UPDATE jobs SET status = ?, updated_at = ? WHERE event_id = ?",
                    ("delivered" if succeeded else "failed", timestamp, event_id))
