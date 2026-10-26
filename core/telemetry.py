#!/usr/bin/env python3
"""
DeepClaw Nova - Hardware & Unified Memory Telemetry
Platform-aware monitoring for Apple Silicon UMA (with POSIX fallbacks).
"""

import sys
import subprocess
import re
from typing import Dict, Any
import config

def get_system_metrics() -> Dict[str, float]:
    """
    Collects memory, swap, and CPU metrics.
    On macOS (Darwin), parses `vm_stat` and `sysctl vm.swapusage`.
    On Linux/POSIX, reads `/proc/meminfo`.
    """
    if sys.platform == "darwin":
        return _get_macos_metrics()
    else:
        return _get_posix_metrics()

def _get_macos_metrics() -> Dict[str, float]:
    total_ram_mb = config.TOTAL_RAM_MB
    try:
        # Get exact hardware memory size
        hw_mem = subprocess.check_output(["sysctl", "-n", "hw.memsize"], timeout=2).decode().strip()
        total_ram_mb = float(hw_mem) / (1024 * 1024)
    except Exception:
        pass

    page_size = 16384  # Standard Apple Silicon 16KB pages
    wired_bytes = 0
    active_bytes = 0
    inactive_bytes = 0
    free_bytes = 0
    compressed_bytes = 0

    try:
        vm_out = subprocess.check_output(["vm_stat"], timeout=2).decode("utf-8")
        for line in vm_out.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip()
                digits = re.sub(r"[^\d]", "", v)
                if digits:
                    val = int(digits)
                    if "Pages wired down" in k:
                        wired_bytes = val * page_size
                    elif "Pages active" in k:
                        active_bytes = val * page_size
                    elif "Pages inactive" in k:
                        inactive_bytes = val * page_size
                    elif "Pages free" in k or "Pages speculative" in k:
                        free_bytes += val * page_size
                    elif "Pages occupied by compressor" in k:
                        compressed_bytes = val * page_size
    except Exception:
        # Fallback simulation
        free_bytes = 8 * 1024 * 1024 * 1024
        active_bytes = 12 * 1024 * 1024 * 1024

    used_mb = (active_bytes + wired_bytes + compressed_bytes) / (1024 * 1024)
    avail_mb = (free_bytes + inactive_bytes) / (1024 * 1024)

    swap_used_mb = 0.0
    try:
        swap_out = subprocess.check_output(["sysctl", "vm.swapusage"], timeout=2).decode("utf-8")
        match = re.search(r"used\s*=\s*([\d\.]+)M", swap_out)
        if match:
            swap_used_mb = float(match.group(1))
    except Exception:
        pass

    return {
        "platform": "darwin",
        "total_ram_mb": total_ram_mb,
        "used_ram_mb": used_mb,
        "avail_ram_mb": avail_mb,
        "wired_ram_mb": wired_bytes / (1024 * 1024),
        "compressed_mb": compressed_bytes / (1024 * 1024),
        "swap_used_mb": swap_used_mb,
    }

def _get_posix_metrics() -> Dict[str, float]:
    total_ram_mb = config.TOTAL_RAM_MB
    avail_ram_mb = 16384.0
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    total_ram_mb = int(line.split()[1]) / 1024.0
                elif line.startswith("MemAvailable:"):
                    avail_ram_mb = int(line.split()[1]) / 1024.0
    except Exception:
        pass

    used_ram_mb = total_ram_mb - avail_ram_mb
    return {
        "platform": "posix",
        "total_ram_mb": total_ram_mb,
        "used_ram_mb": used_ram_mb,
        "avail_ram_mb": avail_ram_mb,
        "wired_ram_mb": 0.0,
        "compressed_mb": 0.0,
        "swap_used_mb": 0.0,
    }
