from typing import Any, Protocol

from longscrape.browser.config import BrowserConfig


class BrowserProvider(Protocol):
    """Starts a browser exposing the Playwright async browser API."""

    def __init__(self, config: BrowserConfig) -> None: ...

    async def start(self) -> None: ...
    async def launch_browser(self) -> Any: ...
    async def close(self) -> None: ...


class PlaywrightBrowserProvider:
    """The built-in provider for the optional ``playwright`` dependency."""

    def __init__(self, config: BrowserConfig) -> None:
        self.config = config
        self._playwright = None
        self._browser_type = None

    async def start(self) -> None:
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        self._browser_type = getattr(self._playwright, self.config.browser_type)

    async def launch_browser(self) -> Any:
        if self._browser_type is None:
            raise RuntimeError("Browser provider has not been started")
        return await self._browser_type.launch(**self.config.launch_options)

    async def close(self) -> None:
        if self._playwright:
            await self._playwright.stop()
