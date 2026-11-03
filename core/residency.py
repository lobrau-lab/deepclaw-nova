#!/usr/bin/env python3
"""
DeepClaw Nova - Native Apple Silicon MLX Model Residency Engine
Loads and permanently pins MLX models (e.g. Qwen3-14B-4bit) in Unified Memory (Metal).
Zero HTTP overhead, zero-copy unified memory weight sharing, zero eviction.
"""

import sys
import os
import json
import re
import time
import html
import urllib.error
import urllib.request
from typing import Dict, Any, Optional, List, Tuple
import config

class ModelResidencyManager:
    _instance = None
    _model = None
    _tokenizer = None
    _processor = None
    _model_name = None
    _lru_cache = None
    _wired_limit_mb = 0.0

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ModelResidencyManager, cls).__new__(cls)
        return cls._instance

    def __init__(
        self,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.model_name = model_name or os.getenv("NOVA_MODEL", config.DEFAULT_MODEL)
        self.backend = config.MODEL_BACKEND
        # Embedded weights load on the first real inference, not when tools are inspected.
        if self.backend != "embedded":
            self._ensure_loaded()

    def is_model_loaded(self) -> bool:
        return ModelResidencyManager._model is not None

    def _ensure_loaded(self) -> bool:
        """Loads model into 32GB Unified Memory and pins it."""
        if self.backend == "omlx":
            ModelResidencyManager._model_name = self.model_name
            return True
        if self.backend == "embedded":
            return self._ensure_embedded_loaded()
        if self.is_model_loaded():
            return True

        print(f"⚡ [MLX Engine] Pinning '{self.model_name}' into Apple Silicon Unified RAM...")
        start_t = time.time()
        try:
            # Avoid triggering large network downloads during status/startup; use cached snapshot only.
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            import mlx.core as mx
            from mlx_lm import load
            from mlx_lm.models.cache import LRUPromptCache

            # Pin Metal working set to M5 hardware recommended limit for zero-eviction GPU neural acceleration
            dev_info = mx.device_info()
            rec_bytes = int(dev_info.get("max_recommended_working_set_size", 0))
            if rec_bytes > 0 and hasattr(mx, "set_wired_limit"):
                mx.set_wired_limit(rec_bytes)
                ModelResidencyManager._wired_limit_mb = rec_bytes / (1024 * 1024)

            ModelResidencyManager._model, ModelResidencyManager._tokenizer = load(self.model_name)
            ModelResidencyManager._model_name = self.model_name
            try:
                max_bytes = getattr(config, "KV_CACHE_MAX_BYTES", 1 << 63)
                max_slots = int(os.getenv("NOVA_KV_SLOTS", getattr(config, "KV_CACHE_SLOTS", 8)))
                ModelResidencyManager._lru_cache = LRUPromptCache(max_size=max_slots, max_bytes=max_bytes)
            except Exception:
                ModelResidencyManager._lru_cache = LRUPromptCache(max_size=8)
            load_dur = time.time() - start_t
            print(
                f"🟢 [MLX Engine] Model '{self.model_name}' locked in Unified RAM ({load_dur:.2f}s). "
                f"Zero-copy Metal + Wired Limit ({ModelResidencyManager._wired_limit_mb:.0f} MB) + KV Trie Cache active."
            )
            return True
        except ImportError:
            print("⚠️ [MLX Engine] 'mlx_lm' not installed in current Python environment. Running in emulation mode.")
            return False
        except Exception as e:
            print(f"⚠️ [MLX Engine] Could not load '{self.model_name}' via MLX: {e}")
            return False

    def _ensure_embedded_loaded(self) -> bool:
        if ModelResidencyManager._model is not None and ModelResidencyManager._processor is not None:
            return True
        print(f"⚡ [Embedded MLX] Loading '{self.model_name}' inside Nova...")
        start_t = time.time()
        try:
            from mlx_vlm import load
            model, processor = load(self.model_name)
            ModelResidencyManager._model = model
            ModelResidencyManager._processor = processor
            ModelResidencyManager._model_name = self.model_name
            print(f"🟢 [Embedded MLX] Model ready ({time.time() - start_t:.2f}s).")
            return True
        except ImportError as exc:
            print(f"⚠️ [Embedded MLX] mlx-vlm is unavailable in Nova's environment: {exc}")
        except Exception as exc:
            print(f"⚠️ [Embedded MLX] Could not load '{self.model_name}': {exc}")
        return False

    def ensure_resident(self) -> bool:
        return self._ensure_loaded()

    def start_residency_watchdog(self) -> None:
        """Keeps weights alive in process memory."""
        self._ensure_loaded()

    def stop_residency_watchdog(self) -> None:
        pass

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> Dict[str, Any]:
        """
        Executes native MLX inference with tool schema formatting and parsing.
        """
        if self.backend == "omlx":
            return self._chat_omlx(messages, tools, max_tokens, temperature)
        if self.backend == "embedded":
            return self._chat_embedded(messages, tools, max_tokens, temperature)

        self._ensure_loaded()

        if ModelResidencyManager._model is None or ModelResidencyManager._tokenizer is None:
            # Emulated inference response when mlx_lm is not available (e.g. CI/sandbox)
            return self._emulated_chat(messages, tools)

        from mlx_lm import generate

        tokenizer = ModelResidencyManager._tokenizer
        model = ModelResidencyManager._model

        # Augment system message with tool schemas if provided (deep-copy dicts to preserve KV prefix cache)
        formatted_messages = [dict(m) for m in messages]
        if tools:
            tools_json = json.dumps(tools, indent=2)
            tool_instruction = (
                f"\n\nAvailable tools (use strictly when needed):\n```json\n{tools_json}\n```\n"
                "To call a tool, respond with ONLY a JSON object in this format:\n"
                '{"tool": "<name>", "arguments": {<args>}}\n'
            )
            # Append to system message
            if formatted_messages and formatted_messages[0]["role"] == "system":
                formatted_messages[0]["content"] += tool_instruction
            else:
                formatted_messages.insert(0, {"role": "system", "content": tool_instruction})

        # Apply chat template
        if hasattr(tokenizer, "apply_chat_template"):
            prompt = tokenizer.apply_chat_template(
                formatted_messages,
                tokenize=False,
                add_generation_prompt=True
            )
        else:
            # Fallback simple prompt
            prompt = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in formatted_messages]) + "\nASSISTANT: "

        # Native Apple Metal Generation with Two-Level KV Prefix Trie Caching
        import copy
        import mlx.core as mx
        from mlx_lm.generate import stream_generate
        from mlx_lm.models.cache import make_prompt_cache
        try:
            from mlx_lm.sample_utils import make_sampler
            sampler = make_sampler(temp=temperature)
            gen_kwargs = {"sampler": sampler}
        except ImportError:
            gen_kwargs = {"temp": temperature}

        prompt_tokens = tokenizer.encode(prompt, add_special_tokens=False)
        lru = ModelResidencyManager._lru_cache
        cache = None
        rest_tokens = prompt_tokens
        cached_count = 0
        start_gen = time.time()

        if lru is not None:
            cache, rest_tokens = lru.fetch_nearest_cache(self.model_name, prompt_tokens)
            if not rest_tokens:
                rest_tokens = prompt_tokens[-1:]
            cached_count = max(0, len(prompt_tokens) - len(rest_tokens))
        if cache is None:
            cache = make_prompt_cache(model)

        # Prefill uncached prompt tokens in chunks and snapshot KV state into LRUPromptCache
        if len(rest_tokens) > 1:
            # Snapshot 1: system+tools boundary so every turn reuses the 2,000+ token tool schema
            sys_len = 0
            if formatted_messages and formatted_messages[0].get("role") == "system" and hasattr(tokenizer, "apply_chat_template"):
                sys_str = tokenizer.apply_chat_template(formatted_messages[:1], tokenize=False, add_generation_prompt=False)
                sys_len = len(tokenizer.encode(sys_str, add_special_tokens=False))

            prefill_target = len(rest_tokens) - 1
            sys_rel = sys_len - cached_count
            cursor = 0
            if lru is not None and 0 < sys_rel < prefill_target:
                while cursor < sys_rel:
                    step_end = min(cursor + 2048, sys_rel)
                    model(mx.array(rest_tokens[cursor:step_end])[None], cache=cache)
                    mx.eval([c.state for c in cache])
                    cursor = step_end
                lru.insert_cache(self.model_name, prompt_tokens[:sys_len], copy.deepcopy(cache), cache_type="system")

            while cursor < prefill_target:
                step_end = min(cursor + 2048, prefill_target)
                model(mx.array(rest_tokens[cursor:step_end])[None], cache=cache)
                mx.eval([c.state for c in cache])
                cursor = step_end

            if lru is not None:
                lru.insert_cache(self.model_name, prompt_tokens[:-1], copy.deepcopy(cache), cache_type="user")
            rest_tokens = rest_tokens[-1:]

        chunks = []
        gen_tokens = 0
        gen_tps = 0.0
        prompt_tps = 0.0
        peak_gb = 0.0
        for resp in stream_generate(
            model,
            tokenizer,
            prompt=rest_tokens,
            max_tokens=max_tokens,
            prompt_cache=cache,
            **gen_kwargs,
        ):
            chunks.append(resp.text)
            gen_tokens = getattr(resp, "generation_tokens", gen_tokens + 1)
            gen_tps = getattr(resp, "generation_tps", gen_tps)
            prompt_tps = getattr(resp, "prompt_tps", prompt_tps)
            peak_gb = getattr(resp, "peak_memory", peak_gb)

        raw_output = "".join(chunks)
        dur = max(1e-6, time.time() - start_gen)
        if not gen_tps and gen_tokens:
            gen_tps = gen_tokens / dur

        # Strip optional thinking blocks before extracting final response / tool calls
        cleaned = re.sub(r"(?:<think>.*?</think>|<\|channel>thought.*?<channel\|>)", "", raw_output, flags=re.DOTALL).strip()
        content = cleaned or raw_output.strip()
        tool_calls = self._extract_tool_calls(content)

        return {
            "message": {
                "role": "assistant",
                "content": content if not tool_calls else "",
                "tool_calls": tool_calls
            },
            "eval_count": gen_tokens or len(content.split()),
            "prompt_tokens": len(prompt_tokens),
            "cached_tokens": cached_count,
            "prompt_tps": round(prompt_tps, 1),
            "tokens_per_sec": round(gen_tps, 1),
            "peak_memory_gb": round(peak_gb, 2),
            "duration_sec": round(dur, 2),
        }

    def _chat_embedded(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]],
        max_tokens: int,
        temperature: float,
    ) -> Dict[str, Any]:
        """Run MLX-VLM directly in this process; no model server is used."""
        if not self._ensure_embedded_loaded():
            raise RuntimeError("embedded MLX runtime is unavailable")

        from mlx_vlm import stream_generate
        from mlx_vlm.prompt_utils import apply_chat_template

        formatted_messages = [dict(message) for message in messages]
        if tools:
            tool_instruction = (
                "\n\nAvailable tools (use strictly when needed):\n"
                f"```json\n{json.dumps(tools, indent=2)}\n```\n"
                'To call a tool, respond with ONLY a JSON object in this format:\n'
                '{"tool": "<name>", "arguments": {<args>}}\n'
            )
            if formatted_messages and formatted_messages[0].get("role") == "system":
                formatted_messages[0]["content"] += tool_instruction
            else:
                formatted_messages.insert(0, {"role": "system", "content": tool_instruction})

        prompt = apply_chat_template(
            ModelResidencyManager._processor,
            ModelResidencyManager._model.config,
            formatted_messages,
            num_images=0,
        )
        chunks = []
        last = None
        started = time.time()
        for result in stream_generate(
            ModelResidencyManager._model,
            ModelResidencyManager._processor,
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            enable_thinking=False,
        ):
            chunks.append(result.text)
            last = result

        raw_output = "".join(chunks)
        cleaned = re.sub(
            r"(?:<think>.*?</think>|<\|channel\>thought.*?<channel\|>)",
            "",
            raw_output,
            flags=re.DOTALL,
        ).strip()
        tool_calls = self._extract_tool_calls(cleaned or raw_output)
        return {
            "message": {
                "role": "assistant",
                "content": cleaned if not tool_calls else "",
                "tool_calls": tool_calls,
            },
            "eval_count": getattr(last, "generation_tokens", 0) if last else 0,
            "prompt_tokens": getattr(last, "prompt_tokens", 0) if last else 0,
            "cached_tokens": getattr(last, "cached_tokens", 0) if last else 0,
            "prompt_tps": getattr(last, "prompt_tps", 0.0) if last else 0.0,
            "tokens_per_sec": getattr(last, "generation_tps", 0.0) if last else 0.0,
            "peak_memory_gb": getattr(last, "peak_memory", 0.0) if last else 0.0,
            "duration_sec": round(time.time() - started, 2),
        }

    def _chat_omlx(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]],
        max_tokens: int,
        temperature: float,
    ) -> Dict[str, Any]:
        """Call oMLX without exposing its API key to prompts, logs, or traces."""
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if tools:
            payload["tools"] = tools

        request = urllib.request.Request(
            f"{config.OMLX_URL}/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {config.OMLX_API_KEY}"} if config.OMLX_API_KEY else {}),
            },
            method="POST",
        )
        started = time.time()
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise RuntimeError(f"oMLX request failed ({exc.code}): {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"oMLX is unavailable at {config.OMLX_URL}: {exc.reason}") from exc

        choice = (result.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        tool_calls = []
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            arguments = function.get("arguments", {})
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {}
            tool_calls.append({
                "id": call.get("id", ""),
                "type": "function",
                "function": {
                    "name": function.get("name", ""),
                    "arguments": arguments,
                },
            })

        usage = result.get("usage") or {}
        return {
            "message": {
                "role": message.get("role", "assistant"),
                "content": message.get("content", "") or "",
                "tool_calls": tool_calls,
            },
            "eval_count": usage.get("completion_tokens", 0),
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "cached_tokens": usage.get("prompt_tokens_details", {}).get("cached_tokens", 0),
            "tokens_per_sec": 0.0,
            "duration_sec": round(time.time() - started, 2),
        }

    def _extract_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        """Parses JSON tool call objects (including nested arguments) generated by local models."""
        tool_calls = []
        decoder = json.JSONDecoder()
        idx = 0
        while idx < len(text):
            brace = text.find("{", idx)
            if brace == -1:
                break
            try:
                obj, end_idx = decoder.raw_decode(text, brace)
                if isinstance(obj, dict):
                    name = obj.get("tool") or obj.get("name")
                    args = obj.get("arguments")
                    if isinstance(name, str) and isinstance(args, dict):
                        tool_calls.append({"function": {"name": name, "arguments": args}})
                idx = end_idx
            except Exception:
                idx = brace + 1

        # Qwen3.5 may emit its native XML function-call format instead of JSON.
        xml_call = re.compile(
            r"<tool_call>\s*<function=([A-Za-z0-9_]+)>(.*?)</function>\s*</tool_call>",
            re.DOTALL | re.IGNORECASE,
        )
        xml_param = re.compile(
            r"<parameter=([A-Za-z0-9_]+)>(.*?)</parameter>",
            re.DOTALL | re.IGNORECASE,
        )
        for name, body in xml_call.findall(text):
            arguments = {}
            for key, value in xml_param.findall(body):
                value = html.unescape(value.strip())
                try:
                    arguments[key] = json.loads(value)
                except json.JSONDecodeError:
                    arguments[key] = value
            tool_calls.append({"function": {"name": name, "arguments": arguments}})

        return tool_calls

    def _emulated_chat(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
        user_text = messages[-1].get("content", "")
        low = user_text.lower()
        if "safari" in low and ("open" in low or "volume" in low):
            return {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "function": {
                            "name": "computer_control",
                            "arguments": {"action": "open_app", "target": "Safari"}
                        }
                    }]
                }
            }
        return {
            "message": {
                "role": "assistant",
                "content": f"[Nova MLX Engine active for model {self.model_name}]"
            }
        }
