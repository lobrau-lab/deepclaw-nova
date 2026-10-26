#!/usr/bin/env python3
"""
DeepClaw Nova - Invariant-Driven Execution Governor
Executes commands with workspace sandboxing, macOS taskpolicy QoS scheduling,
atomic lease governance, and deterministic self-healing loops.
"""

import os
import sys
import time
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import config
from core.lease import ResourceLease, ResourceLeaseError
from core.classifier import classify_failure, CLASS_WORKSPACE_VIOLATION
from core.repair import select_repair_strategy
from core.workspace import validate_workspace_path, WorkspaceViolationError
from core.job_store import JobStore

class ExecutionResult:
    def __init__(
        self,
        job_id: str,
        status: str,
        exit_code: int,
        stdout: str,
        stderr: str,
        retries_used: int = 0,
        failure_class: Optional[str] = None,
        duration: float = 0.0,
    ):
        self.job_id = job_id
        self.status = status
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.retries_used = retries_used
        self.failure_class = failure_class
        self.duration = duration

    def success(self) -> bool:
        return self.status == "COMPLETE" and self.exit_code == 0

class ExecutionGovernor:
    def __init__(self, job_store: Optional[JobStore] = None):
        self.store = job_store or JobStore()

    def run(
        self,
        command: str,
        working_directory: Optional[str] = None,
        resource_class: str = "general",
        timeout: float = 120.0,
        env: Optional[Dict[str, str]] = None,
    ) -> ExecutionResult:
        cwd = Path(working_directory or os.getcwd())
        start_time = time.time()
        created = self.store.create_job(command=command, resource_class=resource_class, working_directory=str(cwd))
        job_id = created["job_id"]

        # Step 1: Validate Workspace Boundary
        try:
            cwd = validate_workspace_path(cwd)
        except WorkspaceViolationError as wve:
            self.store.update_status(job_id, "BLOCKED", failure_class=CLASS_WORKSPACE_VIOLATION)
            return ExecutionResult(
                job_id=job_id,
                status="BLOCKED",
                exit_code=1,
                stdout="",
                stderr=str(wve),
                failure_class=CLASS_WORKSPACE_VIOLATION,
                duration=time.time() - start_time,
            )

        # Step 2: Retry Loop with Surgical Self-Healing
        retry_count = 0
        last_failure_class = None
        merged_env = dict(os.environ)
        if env:
            merged_env.update(env)

        while True:
            # Acquire Resource Lease if heavy
            lease = None
            if resource_class in ("heavy", "metal", "training", "diffusion"):
                lease = ResourceLease(resource_name="metal_compute", owner=f"nova-{job_id}", timeout=15.0)
                try:
                    lease.acquire(blocking=True)
                except ResourceLeaseError as rle:
                    self.store.update_status(job_id, "BLOCKED", failure_class="GPU_CONTENTION")
                    return ExecutionResult(
                        job_id=job_id,
                        status="BLOCKED",
                        exit_code=1,
                        stdout="",
                        stderr=str(rle),
                        failure_class="GPU_CONTENTION",
                        duration=time.time() - start_time,
                    )

            self.store.update_status(job_id, "RUNNING")
            # Build command execution list (macOS QoS taskpolicy wrapper)
            cmd_args = self._build_exec_command(command, resource_class)

            exit_code = 0
            stdout = ""
            stderr = ""
            try:
                proc = subprocess.Popen(
                    cmd_args,
                    cwd=str(cwd),
                    env=merged_env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                stdout, stderr = proc.communicate(timeout=timeout)
                exit_code = proc.returncode
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
                exit_code = 124
                stderr += f"\nProcess timed out after {timeout} seconds."
            except Exception as e:
                exit_code = 1
                stderr = str(e)
            finally:
                if lease:
                    lease.release()

            # Step 3: Validate Outcome
            if exit_code == 0:
                self.store.update_status(job_id, "COMPLETE")
                return ExecutionResult(
                    job_id=job_id,
                    status="COMPLETE",
                    exit_code=0,
                    stdout=stdout,
                    stderr=stderr,
                    retries_used=retry_count,
                    duration=time.time() - start_time,
                )

            # Step 4: Classify Failure & Execute Bounded Repair
            last_failure_class = classify_failure(exit_code=exit_code, stderr=stderr, stdout=stdout)
            repair_strategy = select_repair_strategy(last_failure_class, retry_count)

            if repair_strategy.can_retry and retry_count < 2:
                retry_count += 1
                self.store.update_status(job_id, "RECOVERING", failure_class=last_failure_class, repair_action=repair_strategy.name, increment_retry=True)
                repair_strategy.execute({"job_id": job_id, "stderr": stderr, "stdout": stdout})
                continue
            else:
                final_st = "BLOCKED" if retry_count >= 2 else "FAILED"
                self.store.update_status(job_id, final_st, failure_class=last_failure_class, repair_action=repair_strategy.name)
                return ExecutionResult(
                    job_id=job_id,
                    status=final_st,
                    exit_code=exit_code,
                    stdout=stdout,
                    stderr=stderr,
                    retries_used=retry_count,
                    failure_class=last_failure_class,
                    duration=time.time() - start_time,
                )

    def _build_exec_command(self, command: str, resource_class: str) -> list:
        if sys.platform == "darwin":
            # Use taskpolicy on macOS for QoS enforcement
            if resource_class in ("background", "compactor"):
                return ["taskpolicy", "-b", "bash", "-c", command]
            else:
                return ["taskpolicy", "-c", "utility", "bash", "-c", command]
        return ["bash", "-c", command]
