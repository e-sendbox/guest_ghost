"""Подключение к SQLite (шаг 0; шаг 4: + sqlite-vec; шаг 0.2: pysqlite3 на хостингах)."""

from pathlib import Path

try:
    import pysqlite3 as sqlite3
except ImportError:
    import sqlite3

import sqlite_vec


def connect(db_path: str) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
