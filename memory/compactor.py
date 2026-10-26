#!/usr/bin/env python3
"""
DeepClaw Nova - Continuous Knowledge Compactor & Thematic Synthesizer
Monitors workspaces, digests documents, and synthesizes cross-file knowledge
under strict asymptotic memory backpressure.
"""

import os
import time
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
import config
from memory.db import MemoryStore
from core.throttling import UnifiedMemoryGovernor
from core.residency import ModelResidencyManager

def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

class ContinuousCompactor:
    def __init__(self):
        self.store = MemoryStore()
        self.governor = UnifiedMemoryGovernor()
        self.residency = ModelResidencyManager()
        self.running = False

    def compact_single_file(self, path: Path) -> Optional[str]:
        if not path.is_file() or path.stat().st_size > 5 * 1024 * 1024:
            return None

        # Apply backpressure before heavy work
        self.governor.throttle()

        current_hash = hash_file(path)
        with self.store.get_connection() as conn:
            row = conn.execute(
                "SELECT file_hash FROM file_compaction WHERE file_path = ?",
                (str(path),)
            ).fetchone()
            if row and row["file_hash"] == current_hash:
                return None  # Already up to date

        # Read text content
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(8000)
        except Exception:
            return None

        prompt = f"Analyze file '{path.name}' and provide a dense 3-point technical summary of its purpose, logic, and exports:\n\n{content}"
        summary = ""
        try:
            resp = self.residency.chat([{"role": "user", "content": prompt}])
            summary = resp.get("message", {}).get("content", "").strip()
        except Exception:
            # Fallback extraction if model busy
            summary = f"File {path.name} ({path.stat().st_size} bytes). Suffix: {path.suffix}"

        timestamp = time.time()
        with self.store.get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO file_compaction (file_path, file_hash, file_type, summary, timestamp)
                   VALUES (?, ?, ?, ?, ?)""",
                (str(path), current_hash, path.suffix, summary, timestamp)
            )
            conn.execute(
                "INSERT INTO memories (timestamp, category, content, importance) VALUES (?, ?, ?, ?)",
                (timestamp, "file_knowledge", f"[{path.name}] {summary}", 6.0)
            )
        return summary

    def run_sweep(self) -> int:
        compacted = 0
        for root_path in config.WORKSPACE_ROOTS:
            if not root_path.exists() or root_path == Path("/tmp"):
                continue
            for root, dirs, files in os.walk(root_path):
                # Prune noisy directories
                dirs[:] = [d for d in dirs if d not in (".git", "node_modules", ".venv", "venv", "__pycache__", ".deepclaw")]
                for fname in files:
                    if fname.endswith((".py", ".go", ".js", ".ts", ".md", ".json", ".txt", ".sh", ".toml", ".yaml")):
                        full_path = Path(root) / fname
                        try:
                            if self.compact_single_file(full_path):
                                compacted += 1
                        except Exception:
                            pass
        return compacted

    def synthesize_round(self) -> Optional[str]:
        with self.store.get_connection() as conn:
            rows = conn.execute(
                "SELECT file_path, summary FROM file_compaction ORDER BY RANDOM() LIMIT 6"
            ).fetchall()

        if len(rows) < 2:
            return None

        items = "\n".join([f"- {Path(r['file_path']).name}: {r['summary']}" for r in rows])
        prompt = f"Synthesize these system files into an architectural insight:\n{items}"
        try:
            resp = self.residency.chat([{"role": "user", "content": prompt}])
            synthesis = resp.get("message", {}).get("content", "").strip()
            sources = ", ".join([Path(r["file_path"]).name for r in rows])
            with self.store.get_connection() as conn:
                conn.execute(
                    "INSERT INTO thematic_synthesis (topic, synthesis, sources, timestamp) VALUES (?, ?, ?, ?)",
                    ("System Architecture", synthesis, sources, time.time())
                )
            return synthesis
        except Exception:
            return None
