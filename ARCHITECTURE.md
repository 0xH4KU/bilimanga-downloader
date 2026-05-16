# Architecture

`bilimanga-downloader` has a shared downloader core plus a bilimanga site adapter:

```text
src/bilimanga_dl/
  core/
    cli.py          command parsing and command dispatch
    client.py       orchestration for parsing, rendering fallback, and downloads
    cleanup.py      safe raw-image cleanup after conversion
    converters.py   PDF/CBZ/both conversion
    downloader.py   raw image file downloads
    history.py      JSON-backed download history
    http.py         mobile-shaped HTTP client
    models.py       shared data models
    reporting.py    shared summary/issue formatting
    reader.py       Playwright fallback for reader pages and protected images
    settings.py     JSON-backed user settings
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

`BilimangaClient` wires the parser, HTTP client, Playwright reader fallback, image downloader, chapter selection/filtering, and aggregate summary reporting. The framework `SiteAdapter` contract exists so future site support can move orchestration away from parser-specific imports.

`BilimangaHttpClient` is intentionally kept as the first transport because bilimanga reader pages often work with mobile-shaped HTTP headers and the `night=0` cookie. Playwright remains a fallback for pages or images that require browser behavior.

## Planned Direction

The remaining architecture work is deliberately narrow:

1. Keep the HTTP-first runtime unless real-site smoke tests prove a persistent browser profile is needed.
2. Move more orchestration behind `SiteAdapter` only when another site or a larger application use case appears.
3. Keep conversion and cleanup dependent on `.complete` and `chapter.state.json` semantics.

Do not move comix.to-specific Cloudflare or API signing assumptions into the framework. Add them only if bilimanga demonstrates the same need.
