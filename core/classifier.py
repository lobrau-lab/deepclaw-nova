#!/usr/bin/env python3
"""
DeepClaw Nova - Deterministic Failure Classifier
Regex-driven classification of runtime errors without LLM hallucinations.
"""

import re
from typing import Tuple

CLASS_MEMORY_PRESSURE = "UNIFIED_MEMORY_PRESSURE"
CLASS_SWAP_THRASHING = "SWAP_THRASHING"
CLASS_MODEL_SERVER_DOWN = "MODEL_SERVER_DOWN"
CLASS_SYNTAX_ERROR = "SYNTAX_ERROR"
CLASS_COMMAND_NOT_FOUND = "COMMAND_NOT_FOUND"
CLASS_PERMISSION_DENIED = "PERMISSION_DENIED"
CLASS_WORKSPACE_VIOLATION = "WORKSPACE_VIOLATION"
CLASS_TIMEOUT_EXPIRED = "TIMEOUT_EXPIRED"
CLASS_NETWORK_ERROR = "NETWORK_ERROR"
CLASS_UNKNOWN = "UNKNOWN_FAILURE"

PATTERNS = [
    (CLASS_WORKSPACE_VIOLATION, re.compile(r"WorkspaceViolationError|security boundary|outside approved workspace|restricted path", re.I)),
    (CLASS_MEMORY_PRESSURE, re.compile(r"MemoryPressureError|out of memory|MPS backend out of memory|Metal memory|cannot allocate memory|std::bad_alloc", re.I)),
    (CLASS_SWAP_THRASHING, re.compile(r"swap usage exceeded|paging pressure|vm.swapusage", re.I)),
    (CLASS_MODEL_SERVER_DOWN, re.compile(r"Connection refused|Failed to connect to Ollama|ollama request failed|503 Service Unavailable|model not found", re.I)),
    (CLASS_COMMAND_NOT_FOUND, re.compile(r"command not found|No such file or directory|executable file not found", re.I)),
    (CLASS_PERMISSION_DENIED, re.compile(r"Permission denied|Operation not permitted|EACCES", re.I)),
    (CLASS_TIMEOUT_EXPIRED, re.compile(r"timed out|TimeoutExpired|deadline exceeded", re.I)),
    (CLASS_SYNTAX_ERROR, re.compile(r"SyntaxError|JSONDecodeError|invalid syntax|unparseable tool arguments", re.I)),
    (CLASS_NETWORK_ERROR, re.compile(r"Network is unreachable|Connection reset|getaddrinfo failed|TLS handshake timeout", re.I)),
]

def classify_failure(exit_code: int = 0, stderr: str = "", stdout: str = "") -> str:
    combined = f"{stderr}\n{stdout}"
    for cls_name, pattern in PATTERNS:
        if pattern.search(combined):
            return cls_name

    if exit_code == 127:
        return CLASS_COMMAND_NOT_FOUND
    if exit_code == 124:
        return CLASS_TIMEOUT_EXPIRED
    if exit_code == 126:
        return CLASS_PERMISSION_DENIED

    return CLASS_UNKNOWN
