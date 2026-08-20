import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from longscrape.browser._protocols import BrowserMiddleware
from longscrape.browser.config import BrowserConfig
from longscrape.browser.page_store import PageStore
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
        self._lock = asyncio.Lock()
        self.middlewares: list[BrowserMiddleware] = []
        self.page_store = PageStore()

    async def start(self) -> None:
        await self.provider.start()
        browser = await self.provider.launch_browser()
        self._browser = browser
        self._context = await self._new_context()

    async def _new_context(self, *, storage_state: Any | None = None) -> Any:
        if self._browser is None:
            raise RuntimeError("Browser is not initialized. Call start() first.")
        options = {
            "user_agent": USER_AGENT,
            **self.config.context_options,
        }
        if storage_state is not None:
            options["storage_state"] = storage_state
        if self.proxy:
            options["proxy"] = {"server": self.proxy}
            options["ignore_https_errors"] = True

        context = await self._browser.new_context(**options)

        if self.middlewares:

            async def pipeline_runner(route: Any) -> None:
                for middleware in self.middlewares:
                    if await middleware.handle(route):
                        return
                await route.continue_()

            await context.route("**/*", pipeline_runner)
        return context

    async def stop(self) -> None:
        await self.page_store.close_all()
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

    def store_page(self, page: Any) -> str:
        """Keep a live page available to a later job and return its opaque ID."""
        return self.page_store.put(page)

    def restore_page(self, page_id: str) -> Any:
        """Restore a live page previously stored by ``store_page``."""
        return self.page_store.require(page_id)

    async def storage_state(self) -> Any:
        if self._context is None:
            raise RuntimeError(
                "Browser context is not initialized. "
                "Call start() before storage_state()."
            )
        return await self._context.storage_state()

    async def replace_context(self, *, storage_state: Any) -> None:
        """Replace the active context while preserving manager configuration."""
        previous_context = self._context
        self._context = await self._new_context(storage_state=storage_state)
        if previous_context is not None:
            await previous_context.close()

    @asynccontextmanager
    async def locked(self) -> AsyncIterator[None]:
        """Serialize changes to this browser's active context."""
        async with self._lock:
            yield

    def register_middleware(self, middleware: BrowserMiddleware) -> None:
        self.middlewares.append(middleware)
