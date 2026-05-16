"""Runtime environment helpers."""

from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path


def detect_chrome_path(system: str | None = None) -> str:
    """Return the best Chrome/Chromium executable candidate for the platform."""
    actual_system = system or platform.system()
    if actual_system == "Darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            str(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            "/opt/homebrew/bin/chromium",
        ]
        for candidate_path in candidates:
            if Path(candidate_path).exists():
                return candidate_path
        return candidates[0]

    if actual_system == "Linux":
        for name in ("google-chrome", "google-chrome-stable", "chromium-browser", "chromium"):
            found = shutil.which(name)
            if found:
                return found
        return "google-chrome"

    env_candidates: list[Path] = []
    for env_var in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        base = os.environ.get(env_var)
        if base:
            env_candidates.append(Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe")

    for env_candidate in env_candidates:
        if env_candidate.exists():
            return str(env_candidate)

    return shutil.which("chrome") or shutil.which("chrome.exe") or "chrome.exe"
