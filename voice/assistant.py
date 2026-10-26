#!/usr/bin/env python3
"""
DeepClaw Nova - 24/7 Live Voice Assistant & Multi-Modal Orchestrator
Listens, reasons with native MLX model, operates Mac computer, creates skills, and speaks.
"""

import os
import time
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
import config
from core.residency import ModelResidencyManager
from core.runner import ExecutionGovernor
from core.workspace import validate_workspace_path, is_path_in_approved_workspace
from memory.db import MemoryStore
from control.macos_bridge import ComputerController
from skills.registry import SkillRegistry, Skill
from skills.author import SkillAuthor
from tools.web_search import execute_web_search, should_search_online
from tools.system import clean_system_caches, get_system_health
from voice.stt import LocalSpeechRecognizer
from voice.tts import LocalSpeechSynthesizer

class NovaVoiceAssistant:
    def __init__(self):
        self.residency = ModelResidencyManager()
        self.governor = ExecutionGovernor()
        self.memory = MemoryStore()
        self.controller = ComputerController()
        self.registry = SkillRegistry()
        self.author = SkillAuthor(registry=self.registry, store=self.memory)
        self.stt = LocalSpeechRecognizer()
        self.tts = LocalSpeechSynthesizer()
        self.history: List[Dict[str, Any]] = []
        self.last_stats: Dict[str, Any] = {}

        # Register standard built-in skills
        self._register_default_skills()

    def reset_history(self) -> None:
        self.history = []

    def _register_default_skills(self) -> None:
        # 1. Computer Control Tool
        self.registry.register(Skill(
            name="computer_control",
            description="Controls macOS apps, volume, media playback, typing, and notifications.",
            parameters={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["open_app", "quit_app", "set_volume", "media", "type_text", "notify", "screenshot"]},
                    "target": {"type": "string", "description": "App name, text to type, or notification message"},
                    "value": {"type": "integer", "description": "Volume percentage (0-100) if setting volume"}
                },
                "required": ["action"]
            },
            handler=self._handle_computer_control
        ))

        # 2. Terminal Shell Tool (runs once, never twice)
        self.registry.register(Skill(
            name="run_terminal_command",
            description="Executes a safe bash shell command inside approved workspace boundaries.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Bash command to execute"},
                    "workdir": {"type": "string", "description": "Optional working directory inside approved workspaces"}
                },
                "required": ["command"]
            },
            handler=self._handle_terminal_command
        ))

        # 3. File Read Tool
        self.registry.register(Skill(
            name="read_file",
            description="Reads a file with line numbers (supports optional offset and limit).",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to read"},
                    "offset": {"type": "integer", "description": "1-based starting line (default 1)"},
                    "limit": {"type": "integer", "description": "Max lines to read (default 200)"}
                },
                "required": ["path"]
            },
            handler=self._handle_read_file
        ))

        # 4. File Write Tool
        self.registry.register(Skill(
            name="write_file",
            description="Creates or overwrites a file inside approved workspaces.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path inside approved workspace"},
                    "content": {"type": "string", "description": "Full text content to write"}
                },
                "required": ["path", "content"]
            },
            handler=self._handle_write_file
        ))

        # 5. File Edit Tool
        self.registry.register(Skill(
            name="edit_file",
            description="Replaces exact old_string with new_string in a file inside approved workspaces.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path inside approved workspace"},
                    "old_string": {"type": "string", "description": "Exact text to find"},
                    "new_string": {"type": "string", "description": "Replacement text"}
                },
                "required": ["path", "old_string", "new_string"]
            },
            handler=self._handle_edit_file
        ))

        # 6. Glob & Grep Tools
        self.registry.register(Skill(
            name="glob_files",
            description="Finds files matching a glob pattern inside a directory.",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern (e.g. '**/*.py')"},
                    "path": {"type": "string", "description": "Base directory (default: current directory)"}
                },
                "required": ["pattern"]
            },
            handler=self._handle_glob_files
        ))

        self.registry.register(Skill(
            name="grep_content",
            description="Searches file contents for a regex pattern inside a directory.",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern to search for"},
                    "path": {"type": "string", "description": "Directory or file to search"}
                },
                "required": ["pattern"]
            },
            handler=self._handle_grep_content
        ))

        # 7. Memory Search & Job Control Tools
        self.registry.register(Skill(
            name="memory_search",
            description="Searches long-term memories and compacted file summaries.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keyword or phrase"}
                },
                "required": ["query"]
            },
            handler=self._handle_memory_search
        ))

        self.registry.register(Skill(
            name="job_control",
            description="Lists recent or active governor jobs from JobStore.",
            parameters={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Optional status filter (RUNNING, COMPLETE, FAILED, BLOCKED)"}
                }
            },
            handler=lambda status=None: json.dumps(self.governor.store.list_jobs(limit=10, status=status), indent=2)
        ))

        # 8. Web Search Tool
        self.registry.register(Skill(
            name="search_online",
            description="Searches the live web for current news, facts, technical documentation, or pricing.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query string"}
                },
                "required": ["query"]
            },
            handler=lambda query: execute_web_search(query)
        ))

        # 9. System Maintenance Tool
        self.registry.register(Skill(
            name="maintain_system",
            description="Checks Mac M5 telemetry, frees unified RAM, and cleans developer/app caches.",
            parameters={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["health", "clean_caches"]}
                },
                "required": ["action"]
            },
            handler=lambda action: get_system_health() if action == "health" else clean_system_caches()
        ))

        # 10. Autonomous Skill Creator Tool
        self.registry.register(Skill(
            name="create_new_skill",
            description="Autonomously codes, compiles, and installs a brand new skill/plugin into Nova.",
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Unique function name for the skill"},
                    "description": {"type": "string", "description": "Clear explanation of what the skill does"},
                    "parameters": {"type": "object", "description": "JSON schema for tool parameters"},
                    "python_code": {"type": "string", "description": "Python implementation body"}
                },
                "required": ["name", "description", "parameters", "python_code"]
            },
            handler=lambda name, description, parameters, python_code: self.author.generate_and_install_skill(name, description, parameters, python_code)
        ))

    def _handle_terminal_command(self, command: str, workdir: Optional[str] = None) -> str:
        res = self.governor.run(command, working_directory=workdir)
        out = (res.stdout or "").strip()
        err = (res.stderr or "").strip()
        combined = f"{out}\n{err}".strip() if (out and err) else (out or err)
        if not res.success():
            return f"[Status: {res.status}, Exit: {res.exit_code}]\n{combined}"
        return combined or "[Command completed with no output]"

    def _handle_read_file(self, path: str, offset: int = 1, limit: int = 200) -> str:
        p = Path(path).expanduser().resolve()
        if not p.is_file():
            return f"Error: File not found: {p}"
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, int(offset)) - 1
        sliced = lines[start:start + int(limit)]
        return "\n".join(f"{start + i + 1}: {line}" for i, line in enumerate(sliced))

    def _handle_write_file(self, path: str, content: str) -> str:
        p = validate_workspace_path(Path(path).expanduser(), operation="write")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} bytes to {p}"

    def _handle_edit_file(self, path: str, old_string: str, new_string: str) -> str:
        p = validate_workspace_path(Path(path).expanduser(), operation="edit")
        if not p.is_file():
            return f"Error: File not found: {p}"
        text = p.read_text(encoding="utf-8")
        if old_string not in text:
            return f"Error: old_string not found in {p}"
        p.write_text(text.replace(old_string, new_string, 1), encoding="utf-8")
        return f"Updated {p}"

    def _handle_glob_files(self, pattern: str, path: str = ".") -> str:
        base = Path(path).expanduser().resolve()
        if not base.exists():
            return f"Error: Path not found: {base}"
        matches = [str(m) for m in list(base.glob(pattern))[:100]]
        return "\n".join(matches) if matches else "No matching files."

    def _handle_grep_content(self, pattern: str, path: str = ".") -> str:
        base = Path(path).expanduser().resolve()
        rx = re.compile(pattern, re.IGNORECASE)
        hits = []
        files = [base] if base.is_file() else base.rglob("*")
        for f in files:
            if not f.is_file() or any(part in (".git", "venv", "__pycache__", "node_modules") for part in f.parts):
                continue
            try:
                for idx, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                    if rx.search(line):
                        hits.append(f"{f}:{idx}: {line[:160]}")
                        if len(hits) >= 50:
                            return "\n".join(hits)
            except Exception:
                continue
        return "\n".join(hits) if hits else "No matches found."

    def _handle_memory_search(self, query: str) -> str:
        mems = self.memory.search_memories(query, limit=10)
        if not mems:
            return f"No memories matching '{query}'."
        return "\n".join(f"[{m['category']}] {m['content']}" for m in mems)

    def _handle_computer_control(self, action: str, target: str = "", value: int = 50) -> str:
        if action == "open_app":
            return self.controller.open_app(target)
        elif action == "quit_app":
            return self.controller.quit_app(target)
        elif action == "set_volume":
            return self.controller.set_system_volume(value)
        elif action == "media":
            return self.controller.media_control(target or "play")
        elif action == "type_text":
            return self.controller.type_text(target)
        elif action == "notify":
            return self.controller.show_notification("DeepClaw Nova", target)
        elif action == "screenshot":
            return self.controller.take_screenshot()
        return f"Unknown action {action}"

    def process_command(self, user_text: str, voice_output: bool = True, max_steps: int = 10) -> str:
        """
        Executes an end-to-end user request with multi-step autonomous tool loop:
        1. Recalls relevant memories.
        2. Queries resident MLX model with dynamic tools.
        3. Iteratively executes tool calls (coding, computer control, skills, search).
        4. Saves interaction trace for learning & self-training.
        5. Speaks answer back to user.
        """
        memories = self.memory.search_memories(user_text, limit=3)
        context_str = "\n".join([f"- {m['content']}" for m in memories]) if memories else "None"

        system_prompt = (
            "You are Nova (Claw), an autonomous live on-device intelligence and coding agent running on Apple Silicon (M5, 32GB Unified RAM). "
            "You have direct control over macOS apps, terminal, file reading/writing/editing, search, system maintenance, governor jobs, and self-extension. "
            "When asked to inspect files, run commands, control the computer, or build skills, use your provided tools.\n"
            f"Relevant User Memories:\n{context_str}"
        )

        # Keep bounded multi-turn history (last 12 messages)
        if len(self.history) > 12:
            self.history = self.history[-12:]

        messages = [{"role": "system", "content": system_prompt}] + list(self.history) + [
            {"role": "user", "content": user_text}
        ]
        tools = self.registry.list_definitions()
        final_content = ""

        for step in range(max_steps):
            try:
                resp = self.residency.chat(messages=messages, tools=tools if step < max_steps - 1 else None)
                self.last_stats = {
                    "eval_count": resp.get("eval_count", 0),
                    "tokens_per_sec": resp.get("tokens_per_sec", 0.0),
                    "duration_sec": resp.get("duration_sec", 0.0),
                }
            except Exception as e:
                low = user_text.lower()
                if "open" in low:
                    match = re.search(r"open\s+([a-zA-Z0-9\s]+?)(?:\s+and\s+|\.|$)", user_text, re.I)
                    app = match.group(1).strip() if match else "Safari"
                    ans = self.controller.open_app(app)
                elif "volume" in low:
                    match = re.search(r"(\d+)", user_text)
                    vol = int(match.group(1)) if match else 50
                    ans = self.controller.set_system_volume(vol)
                elif "search" in low:
                    ans = execute_web_search(user_text)
                elif "notification" in low or "banner" in low:
                    ans = self.controller.show_notification("DeepClaw Nova", user_text)
                else:
                    ans = f"Nova encountered an issue: {e}"
                if voice_output:
                    self.tts.speak(ans)
                return ans

            msg = resp.get("message", {})
            tool_calls = msg.get("tool_calls", [])

            if not tool_calls:
                final_content = msg.get("content", "").strip()
                break

            tool_outputs = []
            for tc in tool_calls:
                fn = tc.get("function", {})
                fn_name = fn.get("name", "")
                fn_args = fn.get("arguments", {})
                print(f"  \033[1;33m⚡ [Tool]\033[0m \033[1;36m{fn_name}\033[0m({json.dumps(fn_args)[:100]})")
                tool_res = self.registry.execute(fn_name, fn_args)

                self.memory.record_trace(
                    prompt=user_text,
                    completion=msg.get("content") or json.dumps({"tool": fn_name, "arguments": fn_args}),
                    tool_name=fn_name,
                    tool_args=json.dumps(fn_args),
                    tool_result=str(tool_res)[:4000],
                    success=not str(tool_res).startswith("Error:")
                )
                tool_outputs.append(f"[Tool '{fn_name}' result]:\n{str(tool_res)[:6000]}")

            messages.append({
                "role": "assistant",
                "content": json.dumps({"tool": tool_calls[0]["function"]["name"], "arguments": tool_calls[0]["function"]["arguments"]})
            })
            messages.append({
                "role": "user",
                "content": "\n\n".join(tool_outputs) + "\n\nUse the tool result above to answer the user's request concisely, or call another tool if needed."
            })

        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": final_content})

        self.memory.add_memory(f"User asked: {user_text}. Nova responded: {final_content[:150]}", category="conversation")

        if voice_output and final_content:
            self.tts.speak(final_content)

        return final_content
