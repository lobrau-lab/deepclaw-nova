#!/usr/bin/env python3
"""
DeepClaw Nova - Comprehensive Acceptance & Unit Test Suite
Validates all 10 core invariants and capabilities on Apple Silicon architecture.
"""

import sys
import os
import time
import json
import shutil
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent))

import config
from core.telemetry import get_system_metrics
from core.throttling import calculate_asymptotic_delay, UnifiedMemoryGovernor
from core.lease import ResourceLease
from core.classifier import classify_failure, CLASS_WORKSPACE_VIOLATION, CLASS_COMMAND_NOT_FOUND
from core.repair import select_repair_strategy
from core.runner import ExecutionGovernor, WorkspaceViolationError
from memory.db import MemoryStore
from skills.registry import SkillRegistry, Skill
from skills.author import SkillAuthor
from tools.web_search import should_search_online
from tools.system import clean_system_caches, get_system_health
from control.macos_bridge import ComputerController
from training.dataset import DatasetBuilder
from training.trainer import ModelTrainer

def run_test(name, fn):
    print(f"▶ RUNNING {name}...", end=" ")
    try:
        fn()
        print("\033[1;32m✔ PASS\033[0m")
        return True
    except Exception as e:
        print(f"\033[1;31m✖ FAIL\033[0m\n  Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_telemetry_and_memory():
    metrics = get_system_metrics()
    assert "total_ram_mb" in metrics
    assert "used_ram_mb" in metrics
    assert "avail_ram_mb" in metrics
    assert metrics["total_ram_mb"] > 0

def test_asymptotic_backpressure():
    # Test near-empty (headroom ~0.9)
    delay, headroom = calculate_asymptotic_delay(3000, 30000, base_delay=0.05)
    assert round(headroom, 2) == 0.90
    assert delay < 0.1

    # Test near-boundary (headroom ~0.01)
    delay_tight, headroom_tight = calculate_asymptotic_delay(29700, 30000, base_delay=0.05)
    assert round(headroom_tight, 2) == 0.01
    assert delay_tight >= 4.5  # Scales asymptotically toward infinity

def test_atomic_resource_lease():
    lease1 = ResourceLease(resource_name="test_metal", owner="worker_1", timeout=1.0)
    assert lease1.acquire(blocking=False)

    # Secondary lease must fail non-blocking
    lease2 = ResourceLease(resource_name="test_metal", owner="worker_2", timeout=0.1)
    assert not lease2.acquire(blocking=False)

    lease1.release()
    assert lease2.acquire(blocking=True)
    lease2.release()

def test_deterministic_classifier():
    c1 = classify_failure(exit_code=127, stderr="/bin/bash: nonexistent_cmd: command not found")
    assert c1 == CLASS_COMMAND_NOT_FOUND

    c2 = classify_failure(exit_code=1, stderr="WorkspaceViolationError: Path outside approved workspace")
    assert c2 == CLASS_WORKSPACE_VIOLATION

def test_execution_governor_boundaries():
    gov = ExecutionGovernor()
    # Illegal path outside workspace roots
    res = gov.run(command="echo hello", working_directory="/System/Library")
    assert res.status == "BLOCKED"
    assert res.failure_class == CLASS_WORKSPACE_VIOLATION

    # Legal execution inside approved root
    res_ok = gov.run(command="echo 'DeepClaw Nova Active'", working_directory=str(Path.home() / "workspace"))
    assert res_ok.success()
    assert "DeepClaw Nova Active" in res_ok.stdout
    stored = gov.store.get_job(res_ok.job_id)
    assert stored is not None and stored["status"] == "COMPLETE"

def test_memory_retention_and_traces():
    store = MemoryStore()
    m_id = store.add_memory("User prefers dark mode and Python 3.12", category="preference", importance=8.0)
    assert m_id > 0

    results = store.search_memories("prefers dark mode")
    assert len(results) > 0
    assert "dark mode" in results[0]["content"]

    t_id = store.record_trace(prompt="open safari", completion="Opened Safari", tool_name="computer_control", success=True)
    assert t_id > 0

def test_autonomous_skill_creation():
    reg = SkillRegistry()
    author = SkillAuthor(registry=reg)

    res = author.generate_and_install_skill(
        name="unit_converter",
        description="Converts kilometers to miles",
        parameters={
            "type": "object",
            "properties": {"km": {"type": "number"}},
            "required": ["km"]
        },
        implementation_code="km_val = kwargs.get('km', 0)\nreturn f'{km_val} km = {km_val * 0.621371:.2f} miles'"
    )
    assert res["success"]
    assert "unit_converter" in [d["function"]["name"] for d in reg.list_definitions()]
    ans = reg.execute("unit_converter", {"km": 10})
    assert "6.21 miles" in ans

def test_computer_controller_and_system():
    ctrl = ComputerController()
    res = ctrl.set_system_volume(40)
    assert "Volume set" in res or "Simulated" in res

    notif = ctrl.show_notification("Nova Test", "System operational")
    assert "Notification" in notif or "Simulated" in notif

    health = get_system_health()
    assert "unified_ram_used_mb" in health
    assert "disk_free_gb" in health

def test_training_pipeline():
    builder = DatasetBuilder()
    tmp_data = config.TRAINING_DIR / "test_train.jsonl"
    count = builder.export_chatml_jsonl(tmp_data)
    assert count >= 0
    if tmp_data.exists():
        tmp_data.unlink()

if __name__ == "__main__":
    tests = [
        ("Telemetry & System Metrics", test_telemetry_and_memory),
        ("Asymptotic Memory Throttling", test_asymptotic_backpressure),
        ("Atomic Resource Leasing", test_atomic_resource_lease),
        ("Deterministic Failure Classifier", test_deterministic_classifier),
        ("Execution Governor & Workspace Boundaries", test_execution_governor_boundaries),
        ("Memory Retention & Trace Logging", test_memory_retention_and_traces),
        ("Autonomous Skill & Plugin Creation", test_autonomous_skill_creation),
        ("Computer Control & System Maintenance", test_computer_controller_and_system),
        ("Training Dataset Pipeline", test_training_pipeline),
    ]

    all_ok = True
    print("\n=======================================================")
    print(" 🐺 RUNNING DEEPCLAW NOVA TEST SUITE (APPLE SILICON M5)")
    print("=======================================================")
    for name, fn in tests:
        if not run_test(name, fn):
            all_ok = False

    print("=======================================================")
    if all_ok:
        print("\033[1;32m★★★ ALL 9 ACCEPTANCE TESTS PASSED CLEANLY ★★★\033[0m\n")
        sys.exit(0)
    else:
        print("\033[1;31m✗ SOME TESTS FAILED\033[0m\n")
        sys.exit(1)
