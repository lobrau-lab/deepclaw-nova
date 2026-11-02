#!/usr/bin/env python3
"""
DeepClaw Nova - Full macOS Computer Control Bridge
Gives Nova full voice-directed control over the Mac using AppleScript, JXA,
System Events accessibility, and terminal execution.
"""

import sys
import subprocess
import time
import re
from pathlib import Path
from typing import Tuple, List, Optional


def _escape_applescript_string(value: str) -> str:
    """Escape data embedded in an AppleScript string literal."""
    return (str(value)
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\r", "\\r")
            .replace("\n", "\\n"))


def _app_name(value: str) -> Optional[str]:
    name = str(value).strip()
    if not name or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._+()'-]{0,127}", name):
        return None
    return name

def run_applescript(script: str, timeout: float = 10.0) -> Tuple[bool, str]:
    """Executes an AppleScript snippet via osascript."""
    if sys.platform != "darwin":
        # Safe emulation on non-macOS test environments
        return True, f"[Simulated macOS AppleScript: {script.strip()}]"

    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        if proc.returncode == 0:
            return True, proc.stdout.strip()
        return False, proc.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "AppleScript command timed out."
    except Exception as e:
        return False, str(e)

class ComputerController:
    def __init__(self):
        pass

    def open_app(self, app_name: str) -> str:
        """Launches or brings an application to the foreground."""
        safe_name = _app_name(app_name)
        if safe_name is None:
            return "Error: invalid application name."
        script = f'tell application "{_escape_applescript_string(safe_name)}" to activate'
        ok, res = run_applescript(script)
        if ok:
            return f"Activated {safe_name}."
        # Fallback to 'open -a'
        try:
            subprocess.run(["open", "-a", safe_name], check=True, timeout=5)
            return f"Opened {safe_name} via open launcher."
        except Exception as e:
            return f"Failed to open {app_name}: {e}"

    def quit_app(self, app_name: str) -> str:
        """Gracefully quits an application."""
        safe_name = _app_name(app_name)
        if safe_name is None:
            return "Error: invalid application name."
        script = f'tell application "{_escape_applescript_string(safe_name)}" to quit'
        ok, res = run_applescript(script)
        return f"Quit {safe_name}." if ok else f"Could not quit {safe_name}: {res}"

    def set_system_volume(self, percent: int) -> str:
        """Sets the system speaker volume (0 to 100)."""
        clamped = max(0, min(100, percent))
        script = f"set volume output volume {clamped}"
        ok, res = run_applescript(script)
        return f"Volume set to {clamped}%." if ok else f"Error setting volume: {res}"

    def media_control(self, action: str) -> str:
        """Controls media playback ('play', 'pause', 'next', 'previous')."""
        actions = {
            "play": "play",
            "pause": "pause",
            "next": "next track",
            "previous": "previous track",
            "stop": "pause",
        }
        action = actions.get(action.lower().strip())
        if action is None:
            return "Unsupported media action. Use play, pause, next, previous, or stop."
        script = f"""
        if application "Spotify" is running then
            tell application "Spotify" to {action}
        else if application "Music" is running then
            tell application "Music" to {action}
        else
            tell application "System Events" to key code 49 -- space toggle
        end if
        """
        ok, res = run_applescript(script)
        return f"Executed media {action}." if ok else f"Media control error: {res}"

    def type_text(self, text: str) -> str:
        """Types text into the currently active macOS window."""
        escaped = _escape_applescript_string(text)
        script = f'tell application "System Events" to keystroke "{escaped}"'
        ok, res = run_applescript(script)
        return "Typed text successfully." if ok else f"Keystroke error: {res}"

    def press_key_combo(self, key: str, modifiers: Optional[List[str]] = None) -> str:
        """
        Presses key combinations (e.g. key='c', modifiers=['command down']).
        """
        mod_str = ""
        if modifiers:
            mod_str = " using {" + ", ".join(modifiers) + "}"
        script = f'tell application "System Events" to keystroke "{key}"{mod_str}'
        ok, res = run_applescript(script)
        return f"Pressed '{key}' {mod_str}." if ok else f"Key combo error: {res}"

    def show_notification(self, title: str, message: str) -> str:
        """Displays a native macOS banner notification."""
        script = (f'display notification "{_escape_applescript_string(message)}" '
                  f'with title "{_escape_applescript_string(title)}" sound name "Glass"')
        ok, res = run_applescript(script)
        return "Notification displayed." if ok else f"Notification error: {res}"

    def take_screenshot(self, output_path: Optional[str] = None) -> str:
        """Captures the current macOS screen."""
        target = output_path or f"/tmp/screenshot_{int(time.time())}.png"
        if sys.platform == "darwin":
            try:
                subprocess.run(["screencapture", "-x", target], check=True, timeout=5)
                return f"Screenshot saved to {target}"
            except Exception as e:
                return f"Failed to capture screen: {e}"
        return f"[Simulated screenshot saved to {target}]"
