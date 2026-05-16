"""Desktop notifications, best effort."""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess

logger = logging.getLogger(__name__)


def send_notification(title: str, body: str) -> None:
    """Send a desktop notification when supported, never raising to callers."""
    try:
        system = platform.system()
        if system == "Darwin":
            _notify_macos(title, body)
        elif system == "Linux":
            _notify_linux(title, body)
        else:
            logger.debug("Notifications not supported on %s", system)
    except Exception as exc:
        logger.debug("Notification failed: %s", exc)


def _notify_macos(title: str, body: str) -> None:
    safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
    safe_body = body.replace("\\", "\\\\").replace('"', '\\"')
    script = f'display notification "{safe_body}" with title "{safe_title}"'
    subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)


def _notify_linux(title: str, body: str) -> None:
    if not shutil.which("notify-send"):
        return
    subprocess.run(["notify-send", title, body], capture_output=True, timeout=5)
