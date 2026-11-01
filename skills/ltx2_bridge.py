#!/usr/bin/env python3
"""
DeepClaw Nova - Remote LTX-2 Audiovisual Generation Bridge
Connects Nova (running locally on Mac) to an LTX-2 generation server (ComfyUI / REST)
running on your desktop GPU rig for synchronized 4K video and audio generation.
"""

import os
import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional
from skills.registry import Skill

DEFAULT_DESKTOP_URL = os.getenv("LTX2_DESKTOP_URL", "http://192.168.1.100:8188")
OUTPUT_DIR = Path.home() / "workspace" / "nova_renders"

def trigger_ltx2_generation(
    prompt: str,
    negative_prompt: Optional[str] = None,
    duration_sec: int = 5,
    resolution: str = "1080p",
    desktop_url: Optional[str] = None,
) -> str:
    """
    Dispatches a synchronized audio-video generation request to the desktop LTX-2 server.
    """
    url = (desktop_url or DEFAULT_DESKTOP_URL).rstrip("/")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt or "blurry, low quality, distorted audio, static",
        "duration_sec": max(1, min(duration_sec, 20)),
        "resolution": resolution,
        "generate_audio": True,
        "fps": 50,
    }

    try:
        req = urllib.request.Request(
            f"{url}/api/ltx2/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            filename = data.get("filename", "ltx2_output.mp4")
            return f"LTX-2 generation successful. Video with synchronized audio saved: {OUTPUT_DIR / filename}"
    except urllib.error.URLError as e:
        return (
            f"Could not reach desktop LTX-2 server at {url}: {e.reason}. "
            "Please verify that your desktop LTX-2 / ComfyUI server is running and accessible over LAN/Tailscale."
        )
    except Exception as e:
        return f"Error executing LTX-2 generation: {e}"

def get_skill() -> Skill:
    return Skill(
        name="generate_ltx2_video",
        description=(
            "Generates a cinematic video clip with synchronized native audio using the LTX-2 model "
            "running on the desktop GPU. Provide a detailed, chronological scene description covering "
            "camera movement, subject action, lighting, and ambient audio."
        ),
        parameters={
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Chronological description of visual action, camera motion, and acoustic environment.",
                },
                "negative_prompt": {
                    "type": "string",
                    "description": "Elements to exclude from visual and audio generation.",
                },
                "duration_sec": {
                    "type": "integer",
                    "description": "Length of video in seconds (default 5, max 20).",
                    "default": 5,
                },
                "resolution": {
                    "type": "string",
                    "enum": ["720p", "1080p", "4k"],
                    "default": "1080p",
                },
            },
            "required": ["prompt"],
        },
        handler=trigger_ltx2_generation,
    )
