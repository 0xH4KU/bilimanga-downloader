from __future__ import annotations

import httpx

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
