# Architecture

`bilimanga-downloader` currently has a small MVP core:

```text
src/bilimanga_dl/
  core/
    cli.py          command parsing and command dispatch
    client.py       orchestration for parsing, rendering fallback, and downloads
    downloader.py   raw image file downloads
    http.py         mobile-shaped HTTP client
    models.py       shared data models
    reader.py       Playwright fallback for reader pages and protected images
  sites/
    bilimanga.py    bilimanga.net URL and HTML parsing
```

The target architecture follows the `comix-downloader` split:

- `core/` remains site-agnostic runtime: configuration, file IO, downloader, conversion, CLI flows, history, reporting, and browser/HTTP engines.
- `sites/` owns site-specific behavior: URL matching, series/chapter parsing, image URL discovery, deduplication, and probes.
- CLI and application use cases should depend on a `SiteAdapter` contract rather than directly importing bilimanga parsing internals.

## Current Boundaries

`BilimangaParser` owns the known `bilimanga.net` URL shapes:

- `/detail/{manga}.html`
- `/detail/{manga}/vol_{volume}.html`
- `/read/{manga}/{chapter}.html`

`BilimangaClient` currently wires the parser, HTTP client, Playwright reader fallback, and image downloader directly. This is acceptable for the MVP but is the first boundary to unwind during the adapter migration.

`BilimangaHttpClient` is intentionally kept as the first transport because bilimanga reader pages often work with mobile-shaped HTTP headers and the `night=0` cookie. Playwright remains a fallback for pages or images that require browser behavior.

## Planned Direction

The migration should happen in this order:

1. Introduce framework models and `SiteAdapter` protocols without changing CLI behavior.
2. Wrap `BilimangaParser` in `BilimangaAdapter`.
3. Move orchestration from `BilimangaClient` toward application use cases.
4. Upgrade downloader reliability and conversion while keeping adapter behavior stable.
5. Expand CLI features once shared use cases exist.

Do not move comix.to-specific Cloudflare or API signing assumptions into the framework. Add them only if bilimanga demonstrates the same need.
