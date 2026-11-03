"""Bounded short-term context rollover and long-term Markdown memory."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Dict, List, Any, Optional

import config
from memory.db import MemoryStore


class MemoryManager:
    def __init__(self, store: Optional[MemoryStore] = None, path: Optional[Path] = None):
        self.store = store or MemoryStore()
        self.path = path or config.MEMORY_MARKDOWN_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def rollover_if_needed(
        self,
        history: List[Dict[str, Any]],
        prompt_tokens: int = 0,
    ) -> List[Dict[str, Any]]:
        if prompt_tokens < config.MAX_CONTEXT_TOKENS * config.CONTEXT_ROLLOVER_RATIO:
            return history
        if len(history) < 2:
            return history

        cut = max(1, int(len(history) * config.CONTEXT_ROLLOVER_FRACTION))
        moved = history[:cut]
        remaining = history[cut:]
        self._append_markdown("Context rollover", moved)
        self.store.add_memory(
            f"Context rollover moved {cut} messages to {self.path} at {time.strftime('%Y-%m-%d %H:%M:%S')}",
            category="context_rollover",
            importance=7.0,
        )
        return remaining

    def recall_tail(self, max_chars: int = 4000) -> str:
        if not self.path.exists():
            return ""
        return self.path.read_text(encoding="utf-8", errors="replace")[-max_chars:]

    def maybe_compact(self, summarize: Callable[[str], str]) -> bool:
        if not self.path.exists():
            return False
        stat = self.path.stat()
        due_to_size = stat.st_size > config.MEMORY_COMPACTION_MAX_CHARS
        due_to_time = time.time() - stat.st_mtime >= config.MEMORY_COMPACTION_INTERVAL_SECONDS
        if not (due_to_size or due_to_time):
            return False

        source = self.path.read_text(encoding="utf-8", errors="replace")
        summary = summarize(source[: config.MEMORY_COMPACTION_MAX_CHARS * 2]).strip()
        if not summary:
            return False
        self.path.write_text(
            "# DeepClaw Long-Term Memory\n\n"
            f"_Compacted {time.strftime('%Y-%m-%d %H:%M:%S')}; source retained in SQLite traces._\n\n"
            f"{summary}\n",
            encoding="utf-8",
        )
        return True

    def _append_markdown(self, title: str, messages: List[Dict[str, Any]]) -> None:
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(f"\n## {title} — {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            for message in messages:
                role = message.get("role", "unknown").title()
                content = str(message.get("content", "")).strip()
                if content:
                    stream.write(f"**{role}:**\n\n{content}\n\n")
