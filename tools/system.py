#!/usr/bin/env python3
"""
DeepClaw Nova - System Maintenance & Hygiene Tool
Monitors Apple Silicon health, prunes bloated caches, and maintains system stability.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any
from core.telemetry import get_system_metrics

def clean_system_caches() -> Dict[str, Any]:
    """
    Cleans harmless developer and application caches to reclaim storage.
    Targets Xcode DerivedData, Homebrew cache, pip cache, and user temp logs.
    """
    reclaimed_bytes = 0
    targets = [
        Path.home() / "Library" / "Caches" / "Homebrew",
        Path.home() / "Library" / "Developer" / "Xcode" / "DerivedData",
        Path.home() / ".cache" / "pip",
        Path("/tmp/deepclaw-locks"),
    ]

    pruned = []
    for t in targets:
        if t.exists():
            try:
                size = sum(f.stat().st_size for f in t.glob("**/*") if f.is_file())
                if t.is_dir():
                    shutil.rmtree(t, ignore_errors=True)
                    t.mkdir(parents=True, exist_ok=True)
                reclaimed_bytes += size
                pruned.append(f"{t.name} ({size / (1024*1024):.1f} MB)")
            except Exception:
                pass

    return {
        "status": "SUCCESS",
        "reclaimed_mb": reclaimed_bytes / (1024 * 1024),
        "cleaned_targets": pruned,
    }

def get_system_health() -> Dict[str, Any]:
    """Provides consolidated telemetry for the M5 workstation."""
    metrics = get_system_metrics()
    # Check disk space on user root
    stat = os.statvfs(Path.home())
    free_disk_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
    total_disk_gb = (stat.f_blocks * stat.f_frsize) / (1024 ** 3)

    return {
        "unified_ram_used_mb": round(metrics["used_ram_mb"], 1),
        "unified_ram_free_mb": round(metrics["avail_ram_mb"], 1),
        "swap_used_mb": round(metrics["swap_used_mb"], 1),
        "disk_free_gb": round(free_disk_gb, 1),
        "disk_total_gb": round(total_disk_gb, 1),
        "platform": metrics["platform"],
    }
