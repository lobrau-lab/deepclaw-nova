#!/usr/bin/env python3
"""
DeepClaw Nova - Local Neural Voice Synthesizer (TTS)
Speaks responses aloud on macOS with zero latency using native Apple Speech or neural TTS.
"""

import sys
import subprocess
import shutil
from typing import Optional
import config

class LocalSpeechSynthesizer:
    def __init__(self, voice_name: str = config.VOICE_NAME):
        self.voice_name = voice_name
        self.say_bin = shutil.which("say")

    def speak(self, text: str, block: bool = True) -> bool:
        """Speaks text using native macOS voice engine."""
        if not text.strip():
            return False

        clean_text = text.replace('"', '\\"').replace('$', '\\$')
        if sys.platform == "darwin" and self.say_bin:
            try:
                cmd = [self.say_bin, "-v", self.voice_name, clean_text]
                if block:
                    subprocess.run(cmd, check=True, timeout=30)
                else:
                    subprocess.Popen(cmd)
                return True
            except Exception as e:
                print(f"TTS warning: {e}")
                return False
        else:
            # Emulated voice output for non-macOS test environment
            print(f"🔊 [Nova Speaks]: {text}")
            return True
