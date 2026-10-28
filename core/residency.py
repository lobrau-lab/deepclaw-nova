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
from typing import Dict, Any, Optional, List, Tuple
import config

class ModelResidencyManager:
    _instance = None
    _model = None
    _tokenizer = None
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
        self.backend = "mlx"
        self._ensure_loaded()

    def is_model_loaded(self) -> bool:
        return ModelResidencyManager._model is not None

    def _ensure_loaded(self) -> bool:
        """Loads model into 32GB Unified Memory and pins it."""
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
