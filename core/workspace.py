#!/usr/bin/env python3
"""
DeepClaw Nova - Workspace Boundary Guard
Ensures autonomous modifications stay inside approved writable roots.
"""

import os
from pathlib import Path
from typing import List, Union
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config


class WorkspaceViolationError(PermissionError):
    """Raised when an operation targets a path outside approved roots."""
    pass


def get_approved_roots() -> List[Path]:
    return [Path(p).resolve() for p in config.WORKSPACE_ROOTS]


def is_path_in_approved_workspace(path: Union[str, Path]) -> bool:
    try:
        target = Path(path).resolve()
        for root in get_approved_roots():
            try:
                target.relative_to(root)
                return True
            except ValueError:
                continue
    except Exception:
        return False
    return False


def validate_workspace_path(path: Union[str, Path], operation: str = "write") -> Path:
    target = Path(path).resolve()
    # Restricted system paths
    for restricted in config.RESTRICTED_SYSTEM_PATHS:
        if str(target).startswith(restricted):
            raise WorkspaceViolationError(
                f"Invariant 3 Violation: Autonomous {operation} denied on path '{target}'. "
                f"Path is under restricted system root '{restricted}'."
            )
    if not is_path_in_approved_workspace(target):
        roots = "\n  - ".join(str(r) for r in get_approved_roots())
        raise WorkspaceViolationError(
            f"Invariant 3 Violation: Autonomous {operation} denied on path '{target}'.\n"
            f"Target is outside approved writable workspaces:\n  - {roots}"
        )
    return target


if __name__ == "__main__":
    # self-check
    assert is_path_in_approved_workspace("/tmp/x")
    try:
        validate_workspace_path("/System/Library/x")
        raise SystemExit("FAIL: restricted not blocked")
    except WorkspaceViolationError:
        pass
    print("workspace self-check ok")
