from __future__ import annotations

import platform

import pytest

from bilimanga_dl.core import runtime
from bilimanga_dl.core.errors import BrowserTimeoutError
from bilimanga_dl.core.reader import PlaywrightReaderRenderer


class FakePage:
    def __init__(self) -> None:
        self.goto_calls: list[tuple[str, str, int]] = []
        self.wait_selectors: list[tuple[str, int]] = []
        self.closed = False

    async def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
        self.goto_calls.append((url, wait_until, timeout))

    async def wait_for_selector(self, selector: str, *, timeout: int) -> None:
        self.wait_selectors.append((selector, timeout))

    async def content(self) -> str:
        return "<html><body><div id='acontentz'><img class='imagecontent'></div></body></html>"

    async def close(self) -> None:
        self.closed = True


class FakeContext:
    def __init__(self, page: FakePage) -> None:
        self.page = page

    async def new_page(self) -> FakePage:
        return self.page


async def test_playwright_reader_renderer_waits_for_chapter_images() -> None:
    page = FakePage()
    renderer = PlaywrightReaderRenderer(context=FakeContext(page), timeout_ms=1234)

    html = await renderer.render("https://www.bilimanga.net/read/285/24327.html")

    assert "acontentz" in html
    assert page.goto_calls == [("https://www.bilimanga.net/read/285/24327.html", "domcontentloaded", 1234)]
    assert page.wait_selectors == [
        (
            "#acontentz img.imagecontent, "
            "#acontentz img[src*='motiezw.com'], "
            "#acontentz img[data-src*='motiezw.com']",
            1234,
        )
    ]
    assert page.closed is True


class FakeResponse:
    def __init__(self, url: str, body: bytes = b"image") -> None:
        self.url = url
        self._body = body

    async def body(self) -> bytes:
        return self._body


class FakeImagePage(FakePage):
    def __init__(self) -> None:
        super().__init__()
        self.handlers: dict[str, object] = {}
        self.evaluate_calls: list[str] = []

    def on(self, event: str, handler: object) -> None:
        self.handlers[event] = handler

    async def wait_for_load_state(self, state: str, *, timeout: int) -> None:
        return None

    async def evaluate(self, script: str, arg: object = None) -> None:
        self.evaluate_calls.append(script)
        await self.handlers["response"](FakeResponse("https://i.motiezw.com/0/285/24327/524971.avif"))


async def test_playwright_reader_renderer_can_fetch_image_response_body() -> None:
    page = FakeImagePage()
    renderer = PlaywrightReaderRenderer(context=FakeContext(page), timeout_ms=1234)

    body = await renderer.fetch_image(
        "https://i.motiezw.com/0/285/24327/524971.avif",
        referer="https://www.bilimanga.net/read/285/24327.html",
    )

    assert body == b"image"
    assert page.goto_calls == [("https://www.bilimanga.net/read/285/24327.html", "domcontentloaded", 1234)]
    assert page.closed is True


class TimeoutPage(FakePage):
    async def wait_for_selector(self, selector: str, *, timeout: int) -> None:
        raise TimeoutError("selector timeout")


async def test_playwright_reader_renderer_wraps_timeouts() -> None:
    page = TimeoutPage()
    renderer = PlaywrightReaderRenderer(context=FakeContext(page), timeout_ms=1234)

    with pytest.raises(BrowserTimeoutError, match="rendering reader page"):
        await renderer.render("https://www.bilimanga.net/read/285/24327.html")


def test_detect_chrome_path_uses_known_macos_path(monkeypatch) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr("bilimanga_dl.core.runtime.Path.exists", lambda self: str(self).startswith("/Applications"))

    assert runtime.detect_chrome_path() == "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def test_detect_chrome_path_uses_linux_path_from_path(monkeypatch) -> None:
    def fake_which(name: str) -> str | None:
        return f"/usr/bin/{name}" if name == "chromium" else None

    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(runtime.shutil, "which", fake_which)

    assert runtime.detect_chrome_path() == "/usr/bin/chromium"


def test_detect_chrome_path_uses_windows_default(monkeypatch) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.delenv("PROGRAMFILES", raising=False)
    monkeypatch.delenv("PROGRAMFILES(X86)", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(runtime.shutil, "which", lambda name: None)

    assert runtime.detect_chrome_path() == "chrome.exe"
