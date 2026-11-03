#!/usr/bin/env python3
"""
DeepClaw Nova - Dynamic Skill & Plugin Registry
Allows hot-loading, listing, and dynamic execution of tools & autonomous plugins.
"""

import os
import sys
import importlib.util
import time
from pathlib import Path
from typing import Dict, Any, Callable, List, Optional
import config

class Skill:
    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        handler: Callable[..., Any],
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.handler = handler

    def to_ollama_definition(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }

class SkillRegistry:
    def __init__(self, skills_dir: Optional[Path] = None):
        self.skills_dir = skills_dir or config.SKILLS_DIR
        self._skills: Dict[str, Skill] = {}
        if config.ENABLE_EXTERNAL_SKILLS:
            self.load_all_skills()

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def list_definitions(self) -> List[Dict[str, Any]]:
        return [s.to_ollama_definition() for s in self._skills.values()]

    def execute(self, name: str, args: Dict[str, Any], observer: Optional[Callable[[Dict[str, Any]], None]] = None) -> str:
        started = time.monotonic()
        event = {"tool": name, "valid": False, "success": False}
        skill = self._skills.get(name)
        if not skill:
            result = f"Error: Tool '{name}' not found. Available tools: {list(self._skills.keys())}"
            event["error"] = result
            return self._finish_tool_event(event, result, started, observer)
        error = self._validate_args(skill, args)
        if error:
            event["error"] = error
            return self._finish_tool_event(event, error, started, observer)
        try:
            res = skill.handler(**args)
            result = str(res)
            event["valid"] = True
            event["success"] = not result.startswith("Error:")
            return self._finish_tool_event(event, result, started, observer)
        except Exception as e:
            result = f"Error executing tool '{name}': {e}"
            event["valid"] = True
            event["error"] = result
            return self._finish_tool_event(event, result, started, observer)

    @staticmethod
    def _validate_args(skill: Skill, args: Dict[str, Any]) -> Optional[str]:
        if not isinstance(args, dict):
            return f"Error: Tool '{skill.name}' arguments must be a JSON object."
        schema = skill.parameters or {}
        missing = [key for key in schema.get("required", []) if key not in args]
        if missing:
            return f"Error: Tool '{skill.name}' is missing required argument(s): {', '.join(missing)}."
        for key, value in args.items():
            definition = schema.get("properties", {}).get(key)
            if definition is None and schema.get("additionalProperties") is False:
                return f"Error: Tool '{skill.name}' received unknown argument '{key}'."
            definition = definition or {}
            expected = definition.get("type")
            if expected == "string" and not isinstance(value, str):
                return f"Error: Tool '{skill.name}' argument '{key}' must be a string."
            if expected == "integer" and (isinstance(value, bool) or not isinstance(value, int)):
                return f"Error: Tool '{skill.name}' argument '{key}' must be an integer."
            if expected == "object" and not isinstance(value, dict):
                return f"Error: Tool '{skill.name}' argument '{key}' must be an object."
            allowed = definition.get("enum")
            if allowed is not None and value not in allowed:
                return f"Error: Tool '{skill.name}' argument '{key}' must be one of: {', '.join(map(str, allowed))}."
        return None

    @staticmethod
    def _finish_tool_event(event, result, started, observer):
        event["duration_ms"] = round((time.monotonic() - started) * 1000, 2)
        if observer:
            observer({**event, "result": result[:4000]})
        return result

    def load_skill_file(self, file_path: Path) -> bool:
        if not file_path.suffix == ".py":
            return False
        module_name = f"nova_skill_{file_path.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, str(file_path))
            if not spec or not spec.loader:
                return False
            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)

            if hasattr(mod, "get_skill"):
                skill = mod.get_skill()
                if isinstance(skill, Skill):
                    self.register(skill)
                    return True
        except Exception as e:
            print(f"Warning: Failed to load skill from {file_path}: {e}")
        return False

    def load_all_skills(self) -> int:
        count = 0
        if self.skills_dir.exists():
            for p in self.skills_dir.glob("*.py"):
                if self.load_skill_file(p):
                    count += 1
        return count
