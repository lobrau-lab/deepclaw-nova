"""Deterministic harness benchmark; it does not load or alter a model."""

import tempfile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.harness import get_harness_profile
from skills.registry import Skill, SkillRegistry


def run_benchmark() -> dict:
    registry = SkillRegistry(skills_dir=Path(tempfile.mkdtemp(prefix="nova-bench-")))
    registry.register(Skill(
        name="echo",
        description="Returns value",
        parameters={"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]},
        handler=lambda value: value,
    ))
    events = []
    results = [
        registry.execute("echo", {"value": "ok"}, observer=events.append),
        registry.execute("echo", {}, observer=events.append),
        registry.execute("missing", {}, observer=events.append),
    ]
    checks = {
        "valid_call": results[0] == "ok" and events[0]["success"],
        "invalid_call_recoverable": results[1].startswith("Error:") and not events[1]["valid"],
        "unknown_tool_recoverable": results[2].startswith("Error:") and not events[2]["valid"],
        "profile_overlay": get_harness_profile("gemma-31b").edit_format == "str_replace",
        "trace_metadata": all("duration_ms" in event for event in events),
    }
    return {"passed": sum(checks.values()), "total": len(checks), "checks": checks}


if __name__ == "__main__":
    result = run_benchmark()
    print(f"Harness benchmark: {result['passed']}/{result['total']}")
    for name, passed in result["checks"].items():
        print(f"{'PASS' if passed else 'FAIL'} {name}")
    raise SystemExit(0 if result["passed"] == result["total"] else 1)
