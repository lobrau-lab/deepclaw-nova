#!/usr/bin/env python3
"""
DeepClaw Nova Configuration
Tailored for Apple Silicon (Mac M5, 32GB Unified Memory Architecture).
"""

import os
import json
import sqlite3
from pathlib import Path

# System Directories
APP_DIR = Path.home() / ".deepclaw"
try:
    APP_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    APP_DIR = Path("/tmp") / ".deepclaw"
    APP_DIR.mkdir(parents=True, exist_ok=True)

WORKSPACE_ROOTS = [
    Path.home() / "workspace",
    Path.home() / "projects",
    Path.home() / "Desktop",
    Path.home() / "Documents" / "DeepClaw",
    APP_DIR,
    Path("/tmp"),
]

# Create standard workspaces
for p in WORKSPACE_ROOTS:
    if p != Path("/tmp"):
        try:
            p.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

def _resolve_safe_db_path(default_path: Path) -> Path:
    env_override = os.getenv("NOVA_DB_PATH")
    if env_override:
        return Path(env_override)
    try:
        default_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(default_path), timeout=1.0)
        conn.execute("CREATE TABLE IF NOT EXISTS _probe (id int);")
        conn.execute("DROP TABLE IF EXISTS _probe;")
        conn.close()
        return default_path
    except Exception:
        fallback_dir = Path("/tmp") / ".deepclaw"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        return fallback_dir / default_path.name

# Database & Storage
DB_PATH = _resolve_safe_db_path(APP_DIR / "nova_memory.db")
TRAINING_DIR = APP_DIR / "training"
SKILLS_DIR = APP_DIR / "skills"
PLUGINS_DIR = APP_DIR / "plugins"
LOGS_DIR = APP_DIR / "logs"
MEMORY_MARKDOWN_PATH = APP_DIR / "memory.md"

for d in [TRAINING_DIR, SKILLS_DIR, PLUGINS_DIR, LOGS_DIR]:
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

# 32GB Unified Memory Safety Thresholds (in MB)
TOTAL_RAM_MB = 32768.0
MAX_SAFE_RAM_MB = 28160.0        # Leave ~4.6GB headroom for macOS window server and kernel
RESERVE_RAM_MB = 3072.0          # 3GB minimum reserve before hard throttle
MAX_SWAP_MB = 2048.0             # Swap trigger point for dynamic backpressure pacing
BASE_DYNAMIC_DELAY = 0.05       # Base interval in seconds

# Context/memory lifecycle. Keep headroom for model KV cache and macOS.
MAX_CONTEXT_TOKENS = int(os.getenv("NOVA_MAX_CONTEXT_TOKENS", "16384"))
CONTEXT_ROLLOVER_RATIO = float(os.getenv("NOVA_CONTEXT_ROLLOVER_RATIO", "0.90"))
CONTEXT_ROLLOVER_FRACTION = float(os.getenv("NOVA_CONTEXT_ROLLOVER_FRACTION", "0.40"))
MEMORY_COMPACTION_INTERVAL_SECONDS = int(os.getenv("NOVA_MEMORY_COMPACTION_INTERVAL", "3600"))
MEMORY_COMPACTION_MAX_CHARS = int(os.getenv("NOVA_MEMORY_MAX_CHARS", "24000"))

# KV prefix cache budget: a 31B model's cached prompt states are large, so cap
# them by bytes (share of safe RAM) rather than trusting the slot count alone.
KV_CACHE_SLOTS = int(os.getenv("NOVA_KV_SLOTS", "8"))
KV_CACHE_MAX_BYTES = int(MAX_SAFE_RAM_MB * 0.25 * 1024 * 1024)

def _local_omlx_api_key() -> str:
    """Reuse the local oMLX key without placing credentials in source or logs."""
    settings_path = Path.home() / ".omlx" / "settings.json"
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        return str(settings.get("auth", {}).get("api_key", ""))
    except (OSError, ValueError, TypeError):
        return ""


# Model & Neural Runtime
MODEL_BACKEND = os.getenv("NOVA_MODEL_BACKEND", "embedded").lower()
OMLX_URL = os.getenv("OMLX_URL", "http://127.0.0.1:8000").rstrip("/")
OMLX_API_KEY = os.getenv("OMLX_API_KEY") or _local_omlx_api_key()
ENABLE_OFFLINE_FALLBACK = os.getenv("NOVA_ENABLE_OFFLINE_FALLBACK", "0") == "1"
ENABLE_EXTERNAL_SKILLS = os.getenv("NOVA_ENABLE_EXTERNAL_SKILLS", "0") == "1"
ENABLE_DYNAMIC_SKILLS = os.getenv("NOVA_ENABLE_DYNAMIC_SKILLS", "0") == "1"
EMBEDDED_MODEL = os.getenv("NOVA_MODEL", "mlx-community/Qwen3.5-35B-A3B-4bit")
OMLX_MODEL = os.getenv("NOVA_OMLX_MODEL", "gemma-4-E4B-it-ultra-uncensored-heretic-MLX-4bit-mixed_4_6")
DEFAULT_MODEL = EMBEDDED_MODEL if MODEL_BACKEND == "embedded" else OMLX_MODEL
MLX_MODEL_PATH = os.getenv(
    "NOVA_MLX_MODEL",
    EMBEDDED_MODEL,
)
# Retained for callers that still use the legacy Ollama configuration name.
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
# Embedded native models may need a one-time Hugging Face download.
if os.getenv("NOVA_OFFLINE", "0") == "1":
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
MODEL_KEEP_ALIVE = 99           # -1 tells Ollama / engine NEVER to unload from RAM

# Voice & Speech
WAKE_WORDS = ["nova", "hey nova", "claw", "deepclaw"]
VOICE_NAME = "Samantha"         # Native macOS high-clarity voice (or Siri / custom)
SPEECH_INPUT_DEVICE = None      # Default microphone
WHISPER_MODEL = "base.en"       # Local Whisper model running on Apple Neural Engine / Metal
VOICE_MODE = os.getenv("NOVA_VOICE_MODE", "hands-free")
VOICE_RECORD_SECONDS = int(os.getenv("NOVA_VOICE_RECORD_SECONDS", "4"))

# Computer Control Safety
RESTRICTED_SYSTEM_PATHS = [
    "/System", "/usr/bin", "/usr/sbin", "/bin", "/sbin",
    "/Applications/Utilities", "/private/var"
]
