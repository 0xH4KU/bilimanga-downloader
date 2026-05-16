# bilimanga-downloader 功能補全 TODO

這份清單用 `comix-downloader` 作為模板，但不直接照搬所有 comix.to 特例。目標是保留 `bilimanga.net` 解析器已經驗證過的站點邏輯，逐步補齊使用者功能、下載可靠性、轉檔、設定、工程配套與發布流程。

## 0. Repo 與品質門檻

- [x] 建立獨立 git repo，remote 指向 `https://github.com/0xH4KU/bilimanga-downloader.git`
- [x] 補 MIT `LICENSE`
- [x] 補 GitHub Actions CI：ruff、mypy、docs consistency、Python 3.11-3.14 測試矩陣、coverage gate
- [x] 補 release workflow：tag build sdist/wheel，PyPI token 存在時發布
- [x] 補 `scripts/check_docs_consistency.py`，檢查 README badge、`pyproject.toml`、`__init__.py` 版本一致
- [ ] 補 `CONTRIBUTING.md`，把本專案的本地品質門檻和 PR 規則寫清楚
- [ ] 補 `ARCHITECTURE.md`，記錄 bilimanga adapter 與共用 runtime 的邊界
- [ ] 補 `DEVELOPMENT.md`，記錄 venv、Playwright/Chrome、測試與真站 smoke test 流程
- [ ] 補 `.gitignore` 的 build/coverage/mypy/dist 產物忽略規則

## 1. 先搬共用框架，不急著改解析器

- [ ] 從 `comix-downloader` 移植站點無關的核心模型：`SearchResult`、`ChapterInfo`、`ChapterImages`、`SeriesInfo`、`DedupDecision`
- [ ] 移植 `sites/base.py` 的 `Engine` / `SiteAdapter` protocol，並調整 `chapter_id` 型別以兼容 bilimanga 的數字 ID
- [ ] 建立 `sites/__init__.py` registry，讓 CLI/application 只依賴 active adapter
- [ ] 把現有 `BilimangaParser` 包成 `BilimangaAdapter`，保留目前 detail/volume/read URL 支援
- [ ] 增加 adapter conformance tests，確保 bilimanga adapter 具備 search/get_series/get_chapter_images/deduplicate/probe_alive 的穩定契約
- [ ] 評估是否需要 search：如果 bilimanga 沒有可靠搜尋入口，先實作 URL/ID resolve，search command 回傳明確不支援訊息

## 2. 下載可靠性

- [ ] 移植 `core/fileio.py` 的 atomic write helper
- [ ] 升級 downloader：並發圖片下載、retry/backoff、bytes 統計、progress callback
- [ ] 加入圖片副檔名魔數判斷，避免只依 URL suffix 推測
- [ ] Resume 時驗證既有圖片有效性，壞檔/空檔自動刪除重抓
- [ ] 加入 partial semantics：部分失敗不寫 `.complete`，寫入 `chapter.state.json`
- [ ] 加入 path traversal 防護，確保 sanitize 後的輸出路徑不逃出 output dir
- [ ] 失敗摘要要能區分 missing images、all failed、partial failed、conversion failed
- [ ] 補 downloader 測試覆蓋 complete/skip/partial/retry/corrupt-file/path-escape

## 3. 瀏覽器與 HTTP runtime

- [ ] 把目前 `BilimangaHttpClient` 保留為第一優先 transport，因為 bilimanga 不一定需要 full CDP runtime
- [ ] 將 Playwright reader fallback 收斂成 Engine method：`fetch_page()` / `get_bytes()`
- [ ] 補明確 timeout 與 typed errors，避免 HTTP/render/image fetch 失敗只靠裸 `Exception`
- [ ] 增加 Chrome 路徑 autodetect：macOS、Linux、Windows
- [ ] 視真站阻擋情況決定是否需要 persistent browser profile、single-instance lock、stale Chrome cleanup
- [ ] 補 reader fallback 測試：HTTP 無圖片時 render，HTTP 圖片失敗時 browser fetch image

## 4. CLI 與使用者工作流

- [ ] 改成 `comix-dl` 類似命令面：`download`、`info`、`list`、`clean`、`history`、`doctor`、`settings`
- [ ] 支援裸 URL 快捷下載或明確提示，不要求永遠輸入 `download`
- [ ] 支援章節選擇：`all`、`1`、`1-5`、`1,3,5`
- [ ] 支援章節 filter：`+keyword`、`-keyword`、undo、reset
- [ ] 支援 `--format pdf|cbz|both`、`--output`、`--no-optimize`、`--quiet`、`--debug`
- [ ] 用 Rich table/panel 顯示 series metadata、chapter list、download progress、summary
- [ ] `doctor` 檢查 Python、依賴、Chrome/Playwright、output dir、bilimanga URL probe
- [ ] 補 CLI flow tests，避免互動流程和 non-interactive 流程分叉

## 5. 轉檔與清理

- [ ] 移植 `core/converters.py`：CBZ、PDF、both
- [ ] 支援 WebP optimization，並保留 `--no-optimize`
- [ ] 大 PDF 使用 batch merge，預設依賴 `pypdf`
- [ ] 只有完整 chapter 才能轉檔；partial chapter 保留 raw images 和 state file
- [ ] 移植 cleanup usecase：只刪除已成功轉檔且 `.complete` 存在的 raw image dir
- [ ] 補 converter tests：空目錄、壞圖、大批量 PDF、both、optimization

## 6. 設定、歷史、通知與報告

- [ ] 移植 `SettingsRepository`，預設 config path 改為 `~/.config/bilimanga-dl/settings.json`
- [ ] 支援 concurrency profile：`desktop`、`low_resource`、`ci`、`custom`
- [ ] 移植 `HistoryRepository`，記錄 completed/skipped/partial/failed、bytes、issues
- [ ] 移植 download report formatter，CLI/history/notification 共用同一份 summary
- [ ] 移植 best-effort desktop notification，名稱改為 `bilimanga-dl`
- [ ] 補 settings/history/report tests

## 7. 文件與發布

- [ ] README 補完整 features、平台支援、安裝、互動/非互動用法、設定、診斷、工作原理
- [ ] 補 install.sh / install.ps1，流程參考 `comix-downloader`
- [ ] 補 release checklist：版本 bump、docs consistency、full gate、tag、release
- [ ] 補 migration note：從目前 MVP CLI 到完整 CLI 的破壞性/兼容性變更
- [ ] 補真站 smoke test 手順，避免 CI 依賴外站但人工 release 前可驗證

## 8. 驗收標準

- [ ] `ruff check .` 通過
- [ ] `mypy src/bilimanga_dl --no-error-summary` 通過
- [ ] `pytest --cov=bilimanga_dl --cov-report=term-missing --cov-fail-under=70` 通過
- [ ] `bilimanga-dl doctor` 在本機能給出可理解診斷
- [ ] URL download 可下載 detail/volume/read 三種 URL
- [ ] 中斷或部分失敗後 rerun 能 resume，不轉檔 partial chapter
- [ ] 完整 chapter 可輸出 pdf/cbz/both
- [ ] README 中列出的每個命令都有對應測試或 smoke test 手順
