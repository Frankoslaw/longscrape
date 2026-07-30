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

from longscrape.core.ports.playwright import (
    PlaywrightManagerPort,
    PlaywrightMiddlewarePort,
)

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
)


class PlaywrightManager(PlaywrightManagerPort):
    def __init__(self, headless: bool = False, proxy: str | None = None):
        self.headless = headless
        self.proxy = proxy
        self.middlewares: list[PlaywrightMiddlewarePort] = []

        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    # noinspection PyUnresolvedReferences
    async def start(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)

        context_options: Any = {"user_agent": USER_AGENT}
        if self.proxy:
            context_options.update(
                proxy=ProxySettings(server=self.proxy),
                ignore_https_errors=True,
            )
        self._context = await self._browser.new_context(**context_options)

        if self.middlewares:

            async def pipeline_runner(route: Route):
                for middleware in self.middlewares:
                    if await middleware.handle(route):
                        return
                await route.continue_()

            await self._context.route("**/*", pipeline_runner)

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
                "Browser context is not initialized. Ensure the context is created before calling 'create_page()'."
            )

        page = await self._context.new_page()
        return page

    def register_middleware(self, middleware: PlaywrightMiddlewarePort):
        self.middlewares.append(middleware)
