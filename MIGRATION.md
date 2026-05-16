# Migration Notes

This project started as a minimal parser/downloader. The current CLI and runtime are broader and closer to `comix-downloader`.

## CLI Changes

- The old required form still works:

```bash
bilimanga-dl download URL
```

- Bare URLs now download directly:

```bash
bilimanga-dl URL
```

- `--limit` and `--image-limit` remain as smoke-test shortcuts, but normal chapter selection should use `--chapters all`, `--chapters 1`, `--chapters 1-5`, or `--chapters 1,3,5`.
- Output format is now controlled with `--format pdf|cbz|both`.
- WebP optimization is enabled by default during conversion; use `--no-optimize` to preserve original downloaded image formats before packaging.

## Runtime Changes

- Downloads are resumable and validate existing files by magic bytes.
- Partial or failed chapters write `chapter.state.json` and do not write `.complete`.
- Only complete chapters can be converted to PDF or CBZ.
- Cleanup removes raw image directories only when converted output exists and `.complete` is present.
- Settings and history live under `~/.config/bilimanga-dl/`.

## Maintainer Notes

- `BilimangaHttpClient` is still the first transport. Playwright is a fallback for reader pages or images that HTTP cannot access.
- Do not import comix.to Cloudflare assumptions unless bilimanga needs the same behavior.
- Use `todo.md` as the project completion map; only check items that have tests or documented smoke steps.
