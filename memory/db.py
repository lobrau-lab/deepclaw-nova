#!/usr/bin/env python3
"""
DeepClaw Nova - SQLite WAL Memory Retention Engine
Persistent episodic, thematic, file compaction, and training trace registry.
"""

import sqlite3
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL,
    category TEXT,
    content TEXT,
    importance REAL DEFAULT 5.0
);

CREATE TABLE IF NOT EXISTS file_compaction (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT UNIQUE,
    file_hash TEXT,
    file_type TEXT,
    summary TEXT,
    timestamp REAL
);

CREATE TABLE IF NOT EXISTS thematic_synthesis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT,
    synthesis TEXT,
    sources TEXT,
    timestamp REAL
);

CREATE TABLE IF NOT EXISTS training_traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt TEXT,
    completion TEXT,
    tool_name TEXT,
    tool_args TEXT,
    tool_result TEXT,
    success INTEGER,
    score REAL DEFAULT 1.0,
    timestamp REAL
);

CREATE TABLE IF NOT EXISTS skills_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    description TEXT,
    code TEXT,
    enabled INTEGER DEFAULT 1,
    created_at REAL
);

CREATE INDEX IF NOT EXISTS idx_memories_ts ON memories(timestamp);
CREATE INDEX IF NOT EXISTS idx_compaction_path ON file_compaction(file_path);
CREATE INDEX IF NOT EXISTS idx_training_success ON training_traces(success);
"""

class MemoryStore:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or config.DB_PATH
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        try:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
        except Exception:
            pass
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self.get_connection() as conn:
            conn.executescript(SCHEMA)

    def add_memory(self, content: str, category: str = "general", importance: float = 5.0) -> int:
        with self.get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO memories (timestamp, category, content, importance) VALUES (?, ?, ?, ?)",
                (time.time(), category, content, importance)
            )
            return cur.lastrowid

    def search_memories(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        words = query.lower().split()
        if not words:
            return []
        like_clauses = " AND ".join(["LOWER(content) LIKE ?" for _ in words])
        params = [f"%{w}%" for w in words] + [limit]
        with self.get_connection() as conn:
            cur = conn.execute(
                f"SELECT * FROM memories WHERE {like_clauses} ORDER BY importance DESC, timestamp DESC LIMIT ?",
                params
            )
            return [dict(r) for r in cur.fetchall()]

    def record_trace(self, prompt: str, completion: str, tool_name: str = "", tool_args: str = "", tool_result: str = "", success: bool = True) -> int:
        with self.get_connection() as conn:
            cur = conn.execute(
                """INSERT INTO training_traces 
                   (prompt, completion, tool_name, tool_args, tool_result, success, score, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (prompt, completion, tool_name, tool_args, tool_result, 1 if success else 0, 1.0 if success else 0.0, time.time())
            )
            return cur.lastrowid

    def get_successful_traces(self, limit: int = 1000) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM training_traces WHERE success = 1 ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
            return [dict(r) for r in cur.fetchall()]
