#!/usr/bin/env python3
"""
DeepClaw Nova - Autonomous Self-Authoring Skill & Plugin Engine
Empowers Nova to create, test, and register new tools and capabilities dynamically.
"""

import time
import re
import py_compile
from pathlib import Path
from typing import Dict, Any, Optional
import config
from memory.db import MemoryStore
from skills.registry import Skill, SkillRegistry

TEMPLATE = '''#!/usr/bin/env python3
"""
Autonomously Generated Skill: {name}
Description: {description}
"""

from skills.registry import Skill

def execute_{name}(**kwargs):
{indented_body}

def get_skill():
    return Skill(
        name="{name}",
        description="{description}",
        parameters={parameters_repr},
        handler=execute_{name}
    )
'''

class SkillAuthor:
    def __init__(self, registry: Optional[SkillRegistry] = None, store: Optional[MemoryStore] = None):
        self.registry = registry or SkillRegistry()
        self.store = store or MemoryStore()

    def generate_and_install_skill(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        implementation_code: str,
    ) -> Dict[str, Any]:
        """
        Validates, persists, compiles, and registers a brand-new skill.
        """
        clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", name.lower()).strip("_")
        skill_file = config.SKILLS_DIR / f"{clean_name}.py"

        # Indent implementation code
        indented = "\n".join(["    " + line for line in implementation_code.strip().splitlines()])
        full_code = TEMPLATE.format(
            name=clean_name,
            description=description,
            parameters_repr=repr(parameters),
            indented_body=indented,
        )

        # Write to file
        with open(skill_file, "w", encoding="utf-8") as f:
            f.write(full_code)

        # Step 2: Pre-flight syntax validation
        try:
            py_compile.compile(str(skill_file), doraise=True)
        except Exception as e:
            skill_file.unlink(missing_ok=True)
            return {
                "success": False,
                "error": f"Generated skill failed Python compilation: {e}"
            }

        # Step 3: Hot-load into registry
        loaded = self.registry.load_skill_file(skill_file)
        if not loaded:
            return {
                "success": False,
                "error": "Skill compiled but get_skill() returned invalid object."
            }

        # Step 4: Record in database ledger
        with self.store.get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO skills_ledger (name, description, code, enabled, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (clean_name, description, full_code, 1, time.time() if "time" in globals() else 0.0)
            )

        return {
            "success": True,
            "skill_name": clean_name,
            "file_path": str(skill_file),
            "message": f"Skill '{clean_name}' successfully authored, verified, and activated."
        }
