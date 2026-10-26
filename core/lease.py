#!/usr/bin/env python3
"""
DeepClaw Nova - Atomic POSIX Resource Lease Engine
Guarantees exclusive resource ownership (Metal compute, camera, mic)
using kernel-level fcntl.flock semantics. Automatically cleans up stale locks.
"""

import os
import time
import json
import fcntl
from pathlib import Path
from typing import Optional, Dict, Any
import config
from core.telemetry import get_system_metrics

DEFAULT_LOCK_DIR = Path("/tmp/deepclaw-locks")
DEFAULT_LOCK_DIR.mkdir(parents=True, exist_ok=True)

class ResourceLeaseError(Exception):
    pass

class MemoryPressureError(ResourceLeaseError):
    pass

class ResourceLease:
    def __init__(
        self,
        resource_name: str = "compute",
        owner: str = "nova",
        timeout: float = 10.0,
        retry_interval: float = 0.5,
    ):
        self.resource_name = resource_name
        self.owner = owner
        self.timeout = timeout
        self.retry_interval = retry_interval
        self.lock_path = DEFAULT_LOCK_DIR / f"{resource_name}.lock"
        self._handle = None
        self._acquired = False

    def acquire(self, blocking: bool = True) -> bool:
        # 1. Pre-flight memory verification
        metrics = get_system_metrics()
        if metrics["avail_ram_mb"] < config.RESERVE_RAM_MB:
            raise MemoryPressureError(
                f"Cannot acquire lease '{self.resource_name}': Available RAM {metrics['avail_ram_mb']:.1f}MB is below safe reserve {config.RESERVE_RAM_MB:.1f}MB."
            )

        start_time = time.time()
        while True:
            self._handle = self.lock_path.open("a+", encoding="utf-8")
            try:
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Successfully acquired kernel lock
                self._handle.seek(0)
                self._handle.truncate()
                payload = {
                    "pid": os.getpid(),
                    "owner": self.owner,
                    "resource": self.resource_name,
                    "acquired_at": time.time(),
                }
                self._handle.write(json.dumps(payload, indent=2))
                self._handle.flush()
                self._acquired = True
                return True
            except BlockingIOError:
                self._handle.close()
                self._handle = None

                if not blocking or (time.time() - start_time) >= self.timeout:
                    return False
                time.sleep(self.retry_interval)

    def release(self) -> None:
        if self._handle and self._acquired:
            try:
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
                self._handle.close()
            except Exception:
                pass
            finally:
                self._handle = None
                self._acquired = False

    @classmethod
    def current_owner(cls, resource_name: str) -> Optional[str]:
        """Returns the active process owner of the lease, or None if unlocked or stale."""
        path = DEFAULT_LOCK_DIR / f"{resource_name}.lock"
        if not path.exists():
            return None

        try:
            handle = path.open("a+", encoding="utf-8")
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                # If we succeeded, nobody owns the lock
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                return None
            except BlockingIOError:
                # Active lock held by live process
                handle.seek(0)
                try:
                    data = json.loads(handle.read() or "{}")
                    return data.get("owner", f"PID {data.get('pid')}")
                except Exception:
                    return "active process"
            finally:
                handle.close()
        except Exception:
            return None

    def __enter__(self):
        if not self.acquire(blocking=True):
            raise ResourceLeaseError(f"Failed to acquire lease for '{self.resource_name}' within {self.timeout}s.")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
