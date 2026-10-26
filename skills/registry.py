#!/usr/bin/env python3
"""
DeepClaw Nova - Dynamic Skill & Plugin Registry
Allows hot-loading, listing, and dynamic execution of tools & autonomous plugins.
"""

import os
import sys
import importlib.util
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
        self.load_all_skills()

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def list_definitions(self) -> List[Dict[str, Any]]:
        return [s.to_ollama_definition() for s in self._skills.values()]

    def execute(self, name: str, args: Dict[str, Any]) -> str:
        skill = self._skills.get(name)
        if not skill:
            return f"Error: Tool '{name}' not found. Available tools: {list(self._skills.keys())}"
        try:
            res = skill.handler(**args)
            return str(res)
        except Exception as e:
            return f"Error executing tool '{name}': {e}"

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
