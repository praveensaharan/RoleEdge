"""Headless Chromium for turning HTML into PNGs (cards, video frames, mocks)."""

from __future__ import annotations

from pathlib import Path
from types import TracebackType

from playwright.sync_api import sync_playwright


class HtmlRenderer:
    """``with HtmlRenderer() as r: r.screenshot(html, path, 1080, 1350)`` - one browser per run."""

    def __enter__(self) -> HtmlRenderer:
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        self._page = self._browser.new_page()
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None,
                 tb: TracebackType | None) -> None:
        self._browser.close()
        self._pw.stop()

    def screenshot(self, html: str, path: Path, width: int, height: int) -> Path:
        self._page.set_viewport_size({"width": width, "height": height})
        self._page.set_content(html, wait_until="networkidle")
        self._page.evaluate("document.fonts.ready")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._page.screenshot(path=str(path))
        return path

    def screenshot_file(self, html_file: Path, path: Path, width: int, height: int, full_page: bool = True) -> Path:
        """Render a file on disk (so relative image paths in it resolve)."""
        self._page.set_viewport_size({"width": width, "height": height})
        self._page.goto(html_file.as_uri(), wait_until="networkidle")
        self._page.evaluate("document.fonts.ready")
        self._page.screenshot(path=str(path), full_page=full_page)
        return path
