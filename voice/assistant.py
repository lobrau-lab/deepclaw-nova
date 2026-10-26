#!/usr/bin/env python3
"""
DeepClaw Nova - 24/7 Live Voice Assistant & Multi-Modal Orchestrator
Listens, reasons with native MLX model, operates Mac computer, creates skills, and speaks.
"""

import time
import json
import re
from typing import Dict, Any, List, Optional
import config
from core.residency import ModelResidencyManager
from core.runner import ExecutionGovernor
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

        # Register standard built-in skills
        self._register_default_skills()

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

        # 2. Terminal Shell Tool
        self.registry.register(Skill(
            name="run_terminal_command",
            description="Executes a safe bash shell command inside approved workspace boundaries.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Bash command to execute"}
                },
                "required": ["command"]
            },
            handler=lambda command: self.governor.run(command).stdout or self.governor.run(command).stderr
        ))

        # 3. Web Search Tool
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

        # 4. System Maintenance Tool
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

        # 5. Autonomous Skill Creator Tool
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

    def process_command(self, user_text: str, voice_output: bool = True) -> str:
        """
        Executes an end-to-end user request:
        1. Recalls relevant memories.
        2. Queries resident MLX model with dynamic tools.
        3. Executes tool calls (computer control, skills, search).
        4. Saves interaction trace for learning & self-training.
        5. Speaks answer back to user.
        """
        start_time = time.time()
        # Retrieve relevant episodic context
        memories = self.memory.search_memories(user_text, limit=3)
        context_str = "\n".join([f"- {m['content']}" for m in memories]) if memories else "None"

        system_prompt = (
            "You are Nova, an autonomous live on-device intelligence running on Apple Silicon (M5, 32GB RAM). "
            "You have direct control over macOS apps, terminal, web search, system maintenance, and self-extension. "
            "When asked to control the computer or build skills, use your provided tools.\n"
            f"Relevant User Memories:\n{context_str}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text}
        ]

        tools = self.registry.list_definitions()
        resp = {}
        try:
            resp = self.residency.chat(messages=messages, tools=tools)
        except Exception as e:
            # Safe, resilient fallback for direct user intents
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

        # Process Tool Calls if generated
        if tool_calls:
            for tc in tool_calls:
                fn = tc.get("function", {})
                fn_name = fn.get("name", "")
                fn_args = fn.get("arguments", {})
                tool_res = self.registry.execute(fn_name, fn_args)

                # Record training trace for on-device learning
                self.memory.record_trace(
                    prompt=user_text,
                    completion=msg.get("content") or f"Executed tool {fn_name}",
                    tool_name=fn_name,
                    tool_args=json.dumps(fn_args),
                    tool_result=tool_res,
                    success=True
                )

                messages.append(msg)
                messages.append({
                    "role": "tool",
                    "name": fn_name,
                    "content": str(tool_res)
                })

            # Get final conversational synthesis after tool execution
            final_resp = self.residency.chat(messages=messages)
            final_content = final_resp.get("message", {}).get("content", "").strip()
        else:
            final_content = msg.get("content", "").strip()

        # Retain new interaction memory
        self.memory.add_memory(f"User asked: {user_text}. Nova responded: {final_content[:150]}", category="conversation")

        if voice_output and final_content:
            self.tts.speak(final_content)

        return final_content
