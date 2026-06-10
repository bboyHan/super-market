"""SQLite database initialization and access."""

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Optional

from config import settings


DB_SCHEMA_VERSION = 1

_local = threading.local()


def get_connection() -> sqlite3.Connection:
    """Get a thread-local database connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(settings.DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


@contextmanager
def get_db():
    """Context manager yielding a database connection."""
    conn = get_connection()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()


@contextmanager
def get_cursor():
    """Context manager yielding a database cursor with auto-commit."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        yield cursor
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def init_db():
    """Initialize database tables and run migrations."""
    os.makedirs(os.path.dirname(settings.DB_PATH), exist_ok=True)
    conn = get_connection()
    cursor = conn.cursor()

    # Create schema version table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
    """)

    current_version = cursor.execute(
        "SELECT MAX(version) FROM schema_version"
    ).fetchone()[0] or 0

    if current_version < 1:
        _apply_v1(cursor)
        cursor.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (1, _now()),
        )
        conn.commit()

    conn.commit()


def _apply_v1(cursor: sqlite3.Cursor):
    """Apply schema version 1."""
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT UNIQUE NOT NULL,
            platform TEXT NOT NULL,
            product_id TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            method TEXT NOT NULL DEFAULT 'browser',
            auto_mode TEXT NOT NULL DEFAULT 'semi',
            account_id TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            progress INTEGER NOT NULL DEFAULT 0,
            current_step TEXT NOT NULL DEFAULT '',
            error_message TEXT,
            result TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_id TEXT UNIQUE NOT NULL,
            task_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            product_id TEXT NOT NULL,
            resource_type TEXT NOT NULL DEFAULT 'credential',
            value TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'collected',
            expires_at TEXT,
            metadata TEXT,
            created_at TEXT NOT NULL,
            uploaded_at TEXT,
            FOREIGN KEY (task_id) REFERENCES tasks(task_id)
        );

        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT UNIQUE NOT NULL,
            platform TEXT NOT NULL,
            name TEXT NOT NULL,
            cookie_encrypted TEXT NOT NULL DEFAULT '',
            cookie_valid INTEGER NOT NULL DEFAULT 0,
            last_checked_at TEXT,
            note TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT NOT NULL DEFAULT 'info',
            source TEXT NOT NULL DEFAULT 'system',
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
        CREATE INDEX IF NOT EXISTS idx_tasks_platform ON tasks(platform);
        CREATE INDEX IF NOT EXISTS idx_resources_status ON resources(status);
        CREATE INDEX IF NOT EXISTS idx_resources_task_id ON resources(task_id);
        CREATE INDEX IF NOT EXISTS idx_accounts_platform ON accounts(platform);
        CREATE INDEX IF NOT EXISTS idx_logs_source ON logs(source);
        CREATE INDEX IF NOT EXISTS idx_logs_created_at ON logs(created_at);
    """)


def get_setting(key: str, default: Any = None) -> Optional[str]:
    """Get a setting value from the database."""
    with get_cursor() as cursor:
        row = cursor.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    """Set a setting value in the database."""
    with get_cursor() as cursor:
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )


def add_log(level: str, source: str, message: str):
    """Insert a log entry."""
    now = _now()
    with get_cursor() as cursor:
        cursor.execute(
            "INSERT INTO logs (level, source, message, created_at) VALUES (?, ?, ?, ?)",
            (level, source, message, now),
        )


def get_recent_logs(limit: int = 100, offset: int = 0, source: Optional[str] = None):
    """Get recent log entries."""
    with get_cursor() as cursor:
        if source:
            rows = cursor.execute(
                "SELECT * FROM logs WHERE source = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                (source, limit, offset),
            ).fetchall()
        else:
            rows = cursor.execute(
                "SELECT * FROM logs ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(r) for r in rows]
