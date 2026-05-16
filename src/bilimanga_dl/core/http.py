"""HTTP transport for bilimanga pages and image assets."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Self

import httpx

from bilimanga_dl.core.errors import HttpStatusError, HttpTimeoutError, HttpTransportError

if TYPE_CHECKING:
    from types import TracebackType

ANDROID_CHROME_UA = (
    "Mozilla/5.0 (Linux; Android 10; Pixel 5) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Mobile Safari/537.36"
)


class BilimangaHttpClient:
    """Small async HTTP client with headers accepted by bilimanga reader pages."""

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 0.5,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._max_retries = max(0, max_retries)
        self._retry_delay = max(0.0, retry_delay)
        self.headers = {
            "User-Agent": ANDROID_CHROME_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
            "sec-ch-ua": '"Chromium";v="125", "Not.A/Brand";v="24"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
        }
        self.cookies = {"night": "0"}
        self._client = httpx.AsyncClient(
            headers=self.headers,
            cookies=self.cookies,
            timeout=timeout,
            follow_redirects=True,
            transport=transport,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_text(self, url: str, *, referer: str | None = None) -> str:
        headers = {"Referer": referer} if referer else None
        response = await self._request(url, headers=headers)
        return response.text

    async def get_bytes(self, url: str, *, referer: str | None = None) -> bytes:
        headers = {"Referer": referer} if referer else None
        response = await self._request(url, headers=headers)
        return response.content

    async def _request(self, url: str, *, headers: dict[str, str] | None = None) -> httpx.Response:
        last_error: httpx.RequestError | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.get(url, headers=headers)
                response.raise_for_status()
                return response
            except httpx.TimeoutException as exc:
                last_error = exc
            except httpx.HTTPStatusError as exc:
                raise HttpStatusError(status_code=exc.response.status_code, url=url) from exc
            except httpx.RequestError as exc:
                last_error = exc

            if attempt < self._max_retries and self._retry_delay > 0:
                await asyncio.sleep(self._retry_delay * (2**attempt))

        if isinstance(last_error, httpx.TimeoutException):
            raise HttpTimeoutError(url=url, message=f"HTTP request timed out for {url}.") from last_error
        raise HttpTransportError(url=url, message=str(last_error) or None) from last_error
