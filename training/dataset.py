#!/usr/bin/env python3
"""
DeepClaw Nova - Dataset Harvester & Preprocessor
Extracts successful execution traces, memories, and skills into fine-tuning datasets.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import config
from memory.db import MemoryStore

class DatasetBuilder:
    def __init__(self, store: Optional[MemoryStore] = None):
        self.store = store or MemoryStore()

    def export_chatml_jsonl(self, output_path: Path) -> int:
        traces = self.store.get_successful_traces(limit=2000)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        count = 0
        with open(output_path, "w", encoding="utf-8") as f:
            for t in traces:
                messages = [
                    {"role": "system", "content": "You are Nova, an autonomous on-device intelligence running on Apple Silicon."},
                    {"role": "user", "content": t["prompt"]},
                ]
                if t["tool_name"]:
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "type": "function",
                            "function": {
                                "name": t["tool_name"],
                                "arguments": json.loads(t["tool_args"]) if t["tool_args"] else {}
                            }
                        }]
                    })
                    messages.append({
                        "role": "tool",
                        "name": t["tool_name"],
                        "content": t["tool_result"] or "success"
                    })
                messages.append({
                    "role": "assistant",
                    "content": t["completion"]
                })

                f.write(json.dumps({"messages": messages}) + "\n")
                count += 1
        return count
