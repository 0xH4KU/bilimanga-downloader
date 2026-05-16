from __future__ import annotations

import subprocess

from bilimanga_dl.core import notify


def test_send_notification_uses_macos_osascript(monkeypatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(notify.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(notify.subprocess, "run", lambda args, **kwargs: calls.append(args))

    notify.send_notification("bilimanga-dl", 'Finished "Title"')

    assert calls
    assert calls[0][0:2] == ["osascript", "-e"]
    assert '\\"Title\\"' in calls[0][2]


def test_send_notification_uses_linux_notify_send_when_available(monkeypatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(notify.platform, "system", lambda: "Linux")
    monkeypatch.setattr(notify.shutil, "which", lambda name: "/usr/bin/notify-send")
    monkeypatch.setattr(notify.subprocess, "run", lambda args, **kwargs: calls.append(args))

    notify.send_notification("bilimanga-dl", "Finished")

    assert calls == [["notify-send", "bilimanga-dl", "Finished"]]


def test_send_notification_is_best_effort(monkeypatch) -> None:
    def fail_run(*args: object, **kwargs: object) -> None:
        raise subprocess.SubprocessError("notification failed")

    monkeypatch.setattr(notify.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(notify.subprocess, "run", fail_run)

    notify.send_notification("bilimanga-dl", "Finished")
