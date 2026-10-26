#!/usr/bin/env python3
"""
DeepClaw Nova - Surgical Bounded Auto-Repair Engine
Translates deterministic failure classes into automated restorative operations.
"""

import time
import gc
from typing import Dict, Any, Optional
import config
from core.classifier import (
    CLASS_MEMORY_PRESSURE,
    CLASS_SWAP_THRASHING,
    CLASS_MODEL_SERVER_DOWN,
    CLASS_SYNTAX_ERROR,
    CLASS_COMMAND_NOT_FOUND,
    CLASS_PERMISSION_DENIED,
    CLASS_WORKSPACE_VIOLATION,
    CLASS_TIMEOUT_EXPIRED,
    CLASS_NETWORK_ERROR,
    CLASS_UNKNOWN,
)

MAX_RETRIES = 3

class RepairAction:
    def __init__(self, name: str, description: str, can_retry: bool = True):
        self.name = name
        self.description = description
        self.can_retry = can_retry

    def execute(self, context: Dict[str, Any]) -> bool:
        raise NotImplementedError

class MemoryPurgeRepair(RepairAction):
    def __init__(self):
        super().__init__(
            "MEMORY_PURGE_AND_COOLDOWN",
            "Triggers Python GC, clears cached buffers, and pauses to allow macOS VM compressor to settle.",
            can_retry=True
        )

    def execute(self, context: Dict[str, Any]) -> bool:
        gc.collect()
        time.sleep(2.0)
        return True

class ModelWarmupRepair(RepairAction):
    def __init__(self):
        super().__init__(
            "MODEL_REPIN_WARMUP",
            "Pings Ollama endpoint and sends keep_alive: -1 to re-lock model into unified RAM.",
            can_retry=True
        )

    def execute(self, context: Dict[str, Any]) -> bool:
        try:
            from core.residency import ModelResidencyManager
            mgr = ModelResidencyManager()
            return mgr.pin_model_in_ram()
        except Exception:
            return False

class ToolSyntaxCorrectionRepair(RepairAction):
    def __init__(self):
        super().__init__(
            "TOOL_SYNTAX_FEEDBACK",
            "Injects structured error feedback into conversation history prompting model self-correction.",
            can_retry=True
        )

    def execute(self, context: Dict[str, Any]) -> bool:
        feedback = context.get("error_feedback_receiver")
        if callable(feedback):
            feedback("Syntax Error: Your previous tool call parameters were malformed. Re-generate strictly adhering to JSON schema.")
        return True

class SecurityBlockedRepair(RepairAction):
    def __init__(self, reason: str):
        super().__init__("SECURITY_BLOCKED", reason, can_retry=False)

    def execute(self, context: Dict[str, Any]) -> bool:
        return False

class DefaultCooldownRepair(RepairAction):
    def __init__(self):
        super().__init__("TRANSIENT_COOLDOWN", "Pauses briefly before retrying operation.", can_retry=True)

    def execute(self, context: Dict[str, Any]) -> bool:
        time.sleep(1.5)
        return True

def select_repair_strategy(failure_class: str, retry_count: int) -> RepairAction:
    if retry_count >= MAX_RETRIES:
        return SecurityBlockedRepair(f"Retry budget exhausted ({retry_count}/{MAX_RETRIES}). Job marked BLOCKED.")

    if failure_class in (CLASS_MEMORY_PRESSURE, CLASS_SWAP_THRASHING):
        return MemoryPurgeRepair()
    elif failure_class == CLASS_MODEL_SERVER_DOWN:
        return ModelWarmupRepair()
    elif failure_class == CLASS_SYNTAX_ERROR:
        return ToolSyntaxCorrectionRepair()
    elif failure_class in (CLASS_WORKSPACE_VIOLATION, CLASS_PERMISSION_DENIED):
        return SecurityBlockedRepair("Access outside designated workspace or permission denied.")
    elif failure_class == CLASS_COMMAND_NOT_FOUND:
        return SecurityBlockedRepair("Required binary or CLI tool not found on system PATH.")
    else:
        return DefaultCooldownRepair()
