from typing import Any

from longscrape.browser._protocols import BrowserMiddleware
from longscrape.browser.config import BrowserConfig
from longscrape.browser.provider import BrowserProvider

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
)


class BrowserManager:
    def __init__(
        self,
        provider: BrowserProvider,
        config: BrowserConfig,
        *,
        proxy: str | None = None,
    ) -> None:
        self.provider = provider
        self.config = config
        self.proxy = proxy
        self._browser: Any | None = None
        self._context: Any | None = None
        self.middlewares: list[BrowserMiddleware] = []

    async def start(self) -> None:
        await self.provider.start()
        browser = await self.provider.launch_browser()
        self._browser = browser

        options = {
            "user_agent": USER_AGENT,
            **self.config.context_options,
        }
        if self.proxy:
            options["proxy"] = {"server": self.proxy}
            options["ignore_https_errors"] = True

        context = await browser.new_context(**options)
        self._context = context

        if self.middlewares:

            async def pipeline_runner(route: Any) -> None:
                for middleware in self.middlewares:
                    if await middleware.handle(route):
                        return
                await route.continue_()

            await context.route("**/*", pipeline_runner)

    async def stop(self) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        await self.provider.close()

    async def create_page(self) -> Any:
        if self._context is None:
            raise RuntimeError(
                "Browser context is not initialized. Call start() before create_page()."
            )
        return await self._context.new_page()

    def register_middleware(self, middleware: BrowserMiddleware) -> None:
        self.middlewares.append(middleware)
