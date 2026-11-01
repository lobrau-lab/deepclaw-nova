"""Small, model-specific harness controls kept separate from model weights."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HarnessProfile:
    family: str
    edit_format: str
    prompt_suffix: str
    edit_guidance: str


_PROFILES = {
    "gemma": HarnessProfile(
        "gemma", "str_replace",
        "Prefer one tool call at a time. After every file edit, verify the result before continuing.",
        "Read the file first. Replace one exact, unique block; if it fails, re-read and retry with a smaller anchored block.",
    ),
    "qwen": HarnessProfile(
        "qwen", "str_replace",
        "Use tools deliberately and keep tool arguments valid JSON. Verify edits before reporting success.",
        "Read the file first and replace one exact, unique block. On failure, re-read instead of guessing the old text.",
    ),
    "llama": HarnessProfile(
        "llama", "str_replace",
        "Use the smallest tool call that can complete the task, then self-verify the observable result.",
        "Read before editing; old_string must be exact and unique. Re-read after an edit failure.",
    ),
    "default": HarnessProfile(
        "default", "str_replace",
        "Use tools only when needed, validate their results, and do not claim completion without verification.",
        "Read before editing and use one exact, unique old_string. If it is not found, re-read the file and retry.",
    ),
}


def get_harness_profile(model_name: str) -> HarnessProfile:
    """Select a stable overlay from a model path/name without changing the model."""
    name = Path(model_name or "").name.lower()
    for family in ("gemma", "qwen", "llama"):
        if family in name:
            return _PROFILES[family]
    return _PROFILES["default"]


def build_system_prompt(base_prompt: str, model_name: str) -> tuple[str, HarnessProfile]:
    profile = get_harness_profile(model_name)
    return f"{base_prompt}\n\nHarness profile ({profile.family}, {profile.edit_format}): {profile.prompt_suffix}", profile
