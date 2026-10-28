#!/usr/bin/env python3
"""
DeepClaw Nova Configuration
Tailored for Apple Silicon (Mac M5, 32GB Unified Memory Architecture).
"""

import os
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

# KV prefix cache budget: a 31B model's cached prompt states are large, so cap
# them by bytes (share of safe RAM) rather than trusting the slot count alone.
KV_CACHE_SLOTS = int(os.getenv("NOVA_KV_SLOTS", "8"))
KV_CACHE_MAX_BYTES = int(MAX_SAFE_RAM_MB * 0.25 * 1024 * 1024)

# Model & Neural Runtime (Resident, Never Unloaded)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.getenv(
    "NOVA_MODEL",
    "/Users/tk/.deepclaw/models/mlx-community/gemma-4-31B-it-The-DECKARD-HERETIC-UNCENSORED-Thinking-4.6bit-msq",
)
MLX_MODEL_PATH = os.getenv(
    "NOVA_MLX_MODEL",
    "/Users/tk/.deepclaw/models/mlx-community/gemma-4-31B-it-The-DECKARD-HERETIC-UNCENSORED-Thinking-4.6bit-msq",
)
# Avoid network lookups for local MLX models
os.environ.setdefault("HF_HUB_OFFLINE", "1")
MODEL_KEEP_ALIVE = 99           # -1 tells Ollama / engine NEVER to unload from RAM

# Voice & Speech
WAKE_WORDS = ["nova", "hey nova", "claw", "deepclaw"]
VOICE_NAME = "Samantha"         # Native macOS high-clarity voice (or Siri / custom)
SPEECH_INPUT_DEVICE = None      # Default microphone
WHISPER_MODEL = "base.en"       # Local Whisper model running on Apple Neural Engine / Metal

# Computer Control Safety
RESTRICTED_SYSTEM_PATHS = [
]
