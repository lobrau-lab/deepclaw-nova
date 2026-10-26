#!/usr/bin/env python3
"""
DeepClaw Nova - Job Store & Lifecycle State Machine
Persistent SQLite-backed registry tracking jobs and recovery states.
"""

import os
import time
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

APP_DIR = config.APP_DIR
DEFAULT_JOB_DB_PATH = Path(os.environ.get("NOVA_JOBS_DB", APP_DIR / "governor_jobs.db"))

VALID_STATES = {
    "QUEUED", "VALIDATING", "WAITING_RESOURCE", "RUNNING",
    "VALIDATING_OUTPUT", "RECOVERING", "COMPLETE", "FAILED", "BLOCKED",
}


class InvalidStateError(ValueError):
    pass


class JobStore:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path or DEFAULT_JOB_DB_PATH).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    parent_job TEXT,
                    owner TEXT,
                    project TEXT,
                    command TEXT,
                    working_directory TEXT,
                    resource_class TEXT,
                    priority INTEGER,
                    created_at REAL,
                    started_at REAL,
                    ended_at REAL,
                    status TEXT,
                    retry_count INTEGER DEFAULT 0,
                    checkpoint_path TEXT,
                    last_failure_class TEXT,
                    last_repair_action TEXT,
                    log_file TEXT,
                    metadata_json TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at);")

    def create_job(
        self,
        command: str,
        resource_class: str = "compute",
        owner: str = "nova",
        project: str = "default",
        working_directory: Optional[str] = None,
        parent_job: Optional[str] = None,
        priority: int = 50,
        checkpoint_path: Optional[str] = None,
        job_id: Optional[str] = None,
        log_file: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        jid = job_id or f"job-{uuid.uuid4().hex[:12]}"
        now = time.time()
        wd = working_directory or str(Path.home() / "workspace")
        meta_str = json.dumps(metadata or {})
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO jobs (
                    job_id, parent_job, owner, project, command,
                    working_directory, resource_class, priority,
                    created_at, started_at, ended_at, status,
                    retry_count, checkpoint_path, last_failure_class,
                    last_repair_action, log_file, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                jid, parent_job, owner, project, command, wd, resource_class, priority,
                now, 0.0, 0.0, "QUEUED", 0, checkpoint_path, "", "",
                log_file or f"/tmp/runctl_{jid}.log", meta_str,
            ))
        return self.get_job(jid)  # type: ignore

    def update_status(
        self,
        job_id: str,
        status: str,
        failure_class: Optional[str] = None,
        repair_action: Optional[str] = None,
        increment_retry: bool = False,
        checkpoint_path: Optional[str] = None,
    ) -> None:
        st = status.upper()
        if st not in VALID_STATES:
            raise InvalidStateError(f"Invalid state '{st}'.")
        now = time.time()
        updates = ["status = ?"]
        params: List[Any] = [st]
        if st in {"RUNNING", "WAITING_RESOURCE", "VALIDATING"}:
            updates.append("started_at = CASE WHEN started_at = 0 THEN ? ELSE started_at END")
            params.append(now)
        if st in {"COMPLETE", "FAILED", "BLOCKED"}:
            updates.append("ended_at = ?")
            params.append(now)
        if failure_class is not None:
            updates.append("last_failure_class = ?")
            params.append(failure_class)
        if repair_action is not None:
            updates.append("last_repair_action = ?")
            params.append(repair_action)
        if increment_retry:
            updates.append("retry_count = retry_count + 1")
        if checkpoint_path is not None:
            updates.append("checkpoint_path = ?")
            params.append(checkpoint_path)
        params.append(job_id)
        with self._get_conn() as conn:
            conn.execute(f"UPDATE jobs SET {', '.join(updates)} WHERE job_id = ?", params)

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            row = cur.fetchone()
            if not row:
                return None
            d = dict(row)
            try:
                d["metadata"] = json.loads(d.get("metadata_json") or "{}")
            except Exception:
                d["metadata"] = {}
            return d

    def list_jobs(self, limit: int = 50, status: Optional[str] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM jobs"
        params: List[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status.upper())
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._get_conn() as conn:
            cur = conn.execute(query, params)
            out = []
            for r in cur.fetchall():
                d = dict(r)
                try:
                    d["metadata"] = json.loads(d.get("metadata_json") or "{}")
                except Exception:
                    d["metadata"] = {}
                out.append(d)
            return out

    def get_active_jobs(self) -> List[Dict[str, Any]]:
        active = ("QUEUED", "VALIDATING", "WAITING_RESOURCE", "RUNNING", "VALIDATING_OUTPUT", "RECOVERING")
        placeholders = ",".join("?" for _ in active)
        with self._get_conn() as conn:
            cur = conn.execute(f"SELECT * FROM jobs WHERE status IN ({placeholders}) ORDER BY priority DESC, created_at ASC", active)
            return [dict(r) for r in cur.fetchall()]

    def get_last_failure(self) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            cur = conn.execute("""
                SELECT * FROM jobs
                WHERE status IN ('FAILED', 'BLOCKED') OR last_failure_class != ''
                ORDER BY created_at DESC LIMIT 1
            """)
            row = cur.fetchone()
            return dict(row) if row else None


if __name__ == "__main__":
    # self-check
    js = JobStore(db_path=Path("/tmp") / "nova_job_selfcheck.db")
    j = js.create_job("echo hi", owner="selfcheck")
    assert j["status"] == "QUEUED"
    js.update_status(j["job_id"], "RUNNING")
    assert js.get_job(j["job_id"])["status"] == "RUNNING"
    js.update_status(j["job_id"], "COMPLETE")
    print("job_store self-check ok")
