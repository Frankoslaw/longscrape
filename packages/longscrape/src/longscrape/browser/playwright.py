from typing import Any

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    ProxySettings,
    Route,
    async_playwright,
)

from longscrape.browser._protocols import PlaywrightManager as PlaywrightManagerProtocol
from longscrape.browser._protocols import PlaywrightMiddleware

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
)


class PlaywrightManager(PlaywrightManagerProtocol):
    def __init__(self, headless: bool = True, proxy: str | None = None):
        self.headless = headless
        self.proxy = proxy
        self.middlewares: list[PlaywrightMiddleware] = []

        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    def _create_playwright(self) -> Any:
        return async_playwright()

    # noinspection PyUnresolvedReferences
    async def start(self):
        playwright = await self._create_playwright().start()
        self._playwright = playwright
        browser = await playwright.chromium.launch(headless=self.headless)
        self._browser = browser

        context_options: Any = {"user_agent": USER_AGENT}
        if self.proxy:
            context_options.update(
                proxy=ProxySettings(server=self.proxy),
                ignore_https_errors=True,
            )
        context = await browser.new_context(**context_options)
        self._context = context

        if self.middlewares:

            async def pipeline_runner(route: Route):
                for middleware in self.middlewares:
                    if await middleware.handle(route):
                        return
                await route.continue_()

            await context.route("**/*", pipeline_runner)

    async def stop(self):
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def create_page(self) -> Page:
        if self._context is None:
            raise RuntimeError(
                "Browser context is not initialized. Ensure the context is created "
                "before calling 'create_page()'."
            )

        page = await self._context.new_page()
        return page

    def register_middleware(self, middleware: PlaywrightMiddleware) -> None:
        self.middlewares.append(middleware)
