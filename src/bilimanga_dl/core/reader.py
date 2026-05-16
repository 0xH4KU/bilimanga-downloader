"""Rendered reader-page access for bilimanga chapters."""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bilimanga_dl.core.errors import BrowserTimeoutError
from bilimanga_dl.core.http import ANDROID_CHROME_UA
from bilimanga_dl.core.runtime import detect_chrome_path

if TYPE_CHECKING:
    from types import TracebackType

    from playwright.async_api import Browser, BrowserContext, Playwright, Response

DEFAULT_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
IMAGE_SELECTOR = (
    "#acontentz img.imagecontent, "
    "#acontentz img[src*='motiezw.com'], "
    "#acontentz img[data-src*='motiezw.com']"
)


class PlaywrightReaderRenderer:
    """Render a bilimanga reader page and return the populated HTML."""

    def __init__(self, *, context: BrowserContext, timeout_ms: int = 30_000) -> None:
        self._context = context
        self._timeout_ms = timeout_ms

    async def render(self, url: str) -> str:
        page = await self._context.new_page()
        try:
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=self._timeout_ms)
                await page.wait_for_selector(IMAGE_SELECTOR, timeout=self._timeout_ms)
            except TimeoutError as exc:
                raise BrowserTimeoutError(f"Timed out rendering reader page: {url}") from exc
            return await page.content()
        finally:
            await page.close()

    async def fetch_image(self, url: str, *, referer: str | None = None) -> bytes:
        """Load one image in the browser and return its response body."""
        page = await self._context.new_page()
        response_task: asyncio.Task[bytes] | None = None

        async def capture_response(response: Response) -> None:
            nonlocal response_task
            if response_task is not None:
                return
            if response.url == url:
                response_task = asyncio.create_task(response.body())

        page.on("response", capture_response)
        try:
            await page.goto(
                referer or "https://www.bilimanga.net/",
                wait_until="domcontentloaded",
                timeout=self._timeout_ms,
            )
            await page.evaluate(
                """(imageUrl) => {
                    const img = document.createElement('img');
                    img.src = imageUrl;
                    img.style.position = 'fixed';
                    img.style.left = '-10000px';
                    document.body.appendChild(img);
                }""",
                url,
            )
            deadline = asyncio.get_running_loop().time() + (self._timeout_ms / 1000)
            while response_task is None and asyncio.get_running_loop().time() < deadline:
                await asyncio.sleep(0.05)
            if response_task is None:
                raise TimeoutError(f"Timed out waiting for image response: {url}")
            try:
                return await asyncio.wait_for(response_task, timeout=self._timeout_ms / 1000)
            except TimeoutError as exc:
                raise BrowserTimeoutError(f"Timed out loading image response: {url}") from exc
        finally:
            await page.close()


class PlaywrightBrowser:
    """Own Playwright and a mobile Chromium context for reader rendering."""

    def __init__(
        self,
        *,
        headless: bool = True,
        chrome_path: str | None = None,
        timeout_ms: int = 30_000,
    ) -> None:
        self._headless = headless
        self._chrome_path = chrome_path or detect_chrome_path()
        self._timeout_ms = timeout_ms
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._renderer: PlaywrightReaderRenderer | None = None

    async def __aenter__(self) -> PlaywrightReaderRenderer:
        return await self.start()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def start(self) -> PlaywrightReaderRenderer:
        if self._renderer is not None:
            return self._renderer
        try:
            from playwright.async_api import async_playwright
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Playwright is required to render bilimanga reader pages. "
                "Install project dependencies with `python -m pip install -e .`."
            ) from exc

        self._playwright = await async_playwright().start()
        launch_options: dict[str, Any] = {
            "headless": self._headless,
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        if self._chrome_path and Path(self._chrome_path).exists():
            launch_options["executable_path"] = self._chrome_path

        self._browser = await self._playwright.chromium.launch(**launch_options)
        self._context = await self._browser.new_context(
            user_agent=ANDROID_CHROME_UA,
            viewport={"width": 412, "height": 915},
            is_mobile=True,
            has_touch=True,
            locale="zh-TW",
            extra_http_headers={
                "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
                "sec-ch-ua-mobile": "?1",
                "sec-ch-ua-platform": '"Android"',
            },
        )
        await self._context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            """
        )
        self._renderer = PlaywrightReaderRenderer(context=self._context, timeout_ms=self._timeout_ms)
        return self._renderer

    async def aclose(self) -> None:
        context = self._context
        browser = self._browser
        playwright = self._playwright
        self._renderer = None
        self._context = None
        self._browser = None
        self._playwright = None

        if context is not None:
            with contextlib.suppress(Exception):
                await context.close()
        if browser is not None:
            with contextlib.suppress(Exception):
                await browser.close()
        if playwright is not None:
            with contextlib.suppress(Exception):
                await playwright.stop()


async def render_reader_html(
    url: str,
    *,
    headless: bool = True,
    chrome_path: str | None = None,
    timeout_ms: int = 30_000,
) -> str:
    """Convenience helper for one-off rendered reader fetches."""
    async with PlaywrightBrowser(headless=headless, chrome_path=chrome_path, timeout_ms=timeout_ms) as reader:
        return await reader.render(url)
