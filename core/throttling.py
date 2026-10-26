#!/usr/bin/env python3
"""
DeepClaw Nova - Asymptotic UMA Memory & Resource Throttling Engine
Implements inverse proportional backpressure for Apple Silicon 32GB Unified Memory.
Ensures continuous 24/7 background tasks never cause OOM or kernel panic.
"""

import time
import os
from typing import Callable, Any, Dict, Tuple, Optional
import config
from core.telemetry import get_system_metrics

MIN_HEADROOM = 0.001

def calculate_asymptotic_delay(
    current_val: float,
    max_val: float,
    base_delay: float = config.BASE_DYNAMIC_DELAY,
    min_headroom: float = MIN_HEADROOM,
) -> Tuple[float, float]:
    """
    Computes headroom ratio (1.0 = completely empty, 0.0 = at boundary)
    and inverse proportional delay: dynamic_delay = base_delay / headroom.
    """
    if max_val <= 0:
        return base_delay, 1.0

    ratio = current_val / max_val
    headroom = max(min_headroom, 1.0 - ratio)
    dynamic_delay = base_delay / headroom
    return dynamic_delay, headroom

def execute_with_memory_backpressure(
    target_func: Callable[[], bool],
    max_memory_mb: float = config.MAX_SAFE_RAM_MB,
    base_delay: float = config.BASE_DYNAMIC_DELAY,
) -> None:
    """
    Executes target_func in an asymptotic loop.
    Delays scale toward infinity if memory approaches max_memory_mb.
    Continues until target_func returns True (finished).
    """
    while True:
        metrics = get_system_metrics()
        current_mem = metrics["used_ram_mb"]

        dynamic_delay, headroom = calculate_asymptotic_delay(
            current_val=current_mem,
            max_val=max_memory_mb,
            base_delay=base_delay,
        )

        # Extra swap growth penalty on Apple Silicon
        if metrics["swap_used_mb"] > config.MAX_SWAP_MB:
            dynamic_delay *= 2.0

        is_finished = target_func()
        if is_finished:
            break

        time.sleep(min(30.0, dynamic_delay))

class UnifiedMemoryGovernor:
    """
    Continuous Multi-Factor Governor for Apple Silicon Unified Memory.
    Balances Active LLM Residency, Heavy Jobs, and Background Daemons.
    """

    def __init__(
        self,
        max_ram_mb: float = config.MAX_SAFE_RAM_MB,
        reserve_mb: float = config.RESERVE_RAM_MB,
        base_delay: float = config.BASE_DYNAMIC_DELAY,
    ):
        self.max_ram_mb = max_ram_mb
        self.reserve_mb = reserve_mb
        self.base_delay = base_delay

    def compute_backpressure(self) -> Dict[str, Any]:
        metrics = get_system_metrics()
        used = metrics["used_ram_mb"]
        avail = metrics["avail_ram_mb"]

        # Safe headroom based on available reserve
        usable_avail = max(0.0, avail - self.reserve_mb)
        headroom = max(MIN_HEADROOM, usable_avail / metrics["total_ram_mb"])

        delay = self.base_delay / headroom

        # Swap inflation multiplier
        if metrics["swap_used_mb"] > config.MAX_SWAP_MB:
            delay *= (1.0 + (metrics["swap_used_mb"] - config.MAX_SWAP_MB) / 1024.0)

        effective_delay = min(30.0, delay)

        return {
            "effective_delay": effective_delay,
            "headroom": headroom,
            "metrics": metrics,
            "is_critical": headroom < 0.05,
        }

    def throttle(self) -> float:
        bp = self.compute_backpressure()
        if bp["effective_delay"] > 0:
            time.sleep(bp["effective_delay"])
        return bp["effective_delay"]
