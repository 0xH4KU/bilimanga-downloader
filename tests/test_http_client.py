from __future__ import annotations

import httpx
import pytest

from bilimanga_dl.core.errors import HttpStatusError, HttpTimeoutError
from bilimanga_dl.core.http import BilimangaHttpClient


def test_client_uses_android_chrome_user_agent() -> None:
    client = BilimangaHttpClient()

    assert "Android" in client.headers["User-Agent"]
    assert "Chrome" in client.headers["User-Agent"]
    assert client.headers["sec-ch-ua-mobile"] == "?1"
    assert client.cookies["night"] == "0"


async def test_get_text_sends_default_headers() -> None:
    seen_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(request.headers)
        return httpx.Response(200, text="<html>ok</html>")

    transport = httpx.MockTransport(handler)
    async with BilimangaHttpClient(transport=transport) as client:
        text = await client.get_text("https://www.bilimanga.net/detail/285.html")

    assert text == "<html>ok</html>"
    assert "Android" in seen_headers["user-agent"]
    assert "night=0" in seen_headers["cookie"]


async def test_get_bytes_sends_referer_when_provided() -> None:
    seen_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(request.headers)
        return httpx.Response(200, content=b"image")

    transport = httpx.MockTransport(handler)
    async with BilimangaHttpClient(transport=transport) as client:
        body = await client.get_bytes(
            "https://i.motiezw.com/0/285/24327/524971.avif",
            referer="https://www.bilimanga.net/read/285/24327.html",
        )

    assert body == b"image"
    assert seen_headers["referer"] == "https://www.bilimanga.net/read/285/24327.html"


async def test_get_text_wraps_http_status_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, request=request, text="forbidden")

    transport = httpx.MockTransport(handler)
    async with BilimangaHttpClient(transport=transport) as client:
        with pytest.raises(HttpStatusError) as exc_info:
            await client.get_text("https://www.bilimanga.net/detail/285.html")

    assert exc_info.value.status_code == 403
    assert exc_info.value.url == "https://www.bilimanga.net/detail/285.html"


async def test_get_bytes_wraps_http_timeouts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    transport = httpx.MockTransport(handler)
    async with BilimangaHttpClient(transport=transport) as client:
        with pytest.raises(HttpTimeoutError, match="timed out"):
            await client.get_bytes("https://i.motiezw.com/0/285/24327/524971.avif")


async def test_get_text_retries_transient_transport_errors() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("temporary connect failure", request=request)
        return httpx.Response(200, text="<html>ok</html>")

    transport = httpx.MockTransport(handler)
    async with BilimangaHttpClient(transport=transport, retry_delay=0) as client:
        text = await client.get_text("https://www.bilimanga.net/read/285/24328.html")

    assert text == "<html>ok</html>"
    assert attempts == 2
