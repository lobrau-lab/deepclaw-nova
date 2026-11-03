import tempfile
import unittest
from pathlib import Path

from memory.db import MemoryStore
from memory.manager import MemoryManager


class MemoryManagerTests(unittest.TestCase):
    def test_rollover_moves_oldest_fraction_to_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = MemoryManager(MemoryStore(Path(tmp) / "memory.db"), Path(tmp) / "memory.md")
            history = [{"role": "user", "content": str(i)} for i in range(10)]
            remaining = manager.rollover_if_needed(history, prompt_tokens=16000)
            self.assertEqual(len(remaining), 6)
            self.assertIn("0", Path(tmp, "memory.md").read_text())
            self.assertNotIn("0", " ".join(item["content"] for item in remaining))

    def test_compaction_replaces_large_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memory.md"
            path.write_text("old context\n" * 100, encoding="utf-8")
            manager = MemoryManager(MemoryStore(Path(tmp) / "memory.db"), path)
            original_limit = __import__("config").MEMORY_COMPACTION_MAX_CHARS
            __import__("config").MEMORY_COMPACTION_MAX_CHARS = 20
            try:
                self.assertTrue(manager.maybe_compact(lambda _: "compact summary"))
                self.assertIn("compact summary", path.read_text())
            finally:
                __import__("config").MEMORY_COMPACTION_MAX_CHARS = original_limit


if __name__ == "__main__":
    unittest.main()
