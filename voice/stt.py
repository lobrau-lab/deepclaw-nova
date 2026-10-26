#!/usr/bin/env python3
"""
DeepClaw Nova - Local Speech Recognition (STT)
Leverages Apple Neural Engine / Metal via Whisper (or mlx-whisper).
Transcribes microphone audio into text locally with zero cloud dependencies.
"""

import sys
import subprocess
import tempfile
import os
from pathlib import Path
from typing import Optional
import config

class LocalSpeechRecognizer:
    def __init__(self, model_name: str = config.WHISPER_MODEL):
        self.model_name = model_name
        self._model = None
        self._backend = self._detect_backend()

    def _detect_backend(self) -> str:
        try:
            import mlx_whisper
            return "mlx_whisper"
        except ImportError:
            pass
        try:
            import whisper
            return "openai_whisper"
        except ImportError:
            pass
        return "fallback_simulated"

    def transcribe_audio_file(self, audio_path: Path) -> str:
        """Transcribes a .wav or .m4a audio file to text."""
        if not audio_path.exists():
            return ""

        if self._backend == "mlx_whisper":
            import mlx_whisper
            res = mlx_whisper.transcribe(str(audio_path), path_or_hf_repo=f"mlx-community/whisper-{self.model_name}")
            return res.get("text", "").strip()

        elif self._backend == "openai_whisper":
            import whisper
            if self._model is None:
                self._model = whisper.load_model(self.model_name)
            res = self._model.transcribe(str(audio_path))
            return res.get("text", "").strip()

        else:
            # Fallback simulated response for test environment
            return "[Speech recognition ready: install mlx-whisper on macOS]"

    def record_microphone(self, duration_seconds: int = 5) -> Optional[Path]:
        """Records short audio snippet from system microphone."""
        temp_audio = Path(tempfile.gettempdir()) / f"nova_voice_{int(os.getpid())}.wav"
        if sys.platform == "darwin":
            try:
                # Use macOS built-in sox / rec if available, or ffmpeg
                cmd = ["ffmpeg", "-y", "-f", "avfoundation", "-i", ":0", "-t", str(duration_seconds), str(temp_audio)]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=duration_seconds + 3)
                if temp_audio.exists() and temp_audio.stat().st_size > 1000:
                    return temp_audio
            except Exception:
                pass
        return None
