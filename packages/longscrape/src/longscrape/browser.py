from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any

from longscrape_core import Document, InputUrl, Job

RouteHandler = Callable[[Any], Awaitable[bool]]

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
)


class PlaywrightManager:
    """Own a Playwright browser and optional route handlers."""

    def __init__(
        self,
        *,
        headless: bool = True,
        proxy: str | None = None,
        route_handlers: Sequence[RouteHandler] = (),
    ) -> None:
        self.headless = headless
        self.proxy = proxy
        self.route_handlers = list(route_handlers)
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None

    def _playwright_factory(self) -> Any:
        try:
            from playwright.async_api import async_playwright
        except ImportError as error:
            raise RuntimeError(
                "Install longscrape[playwright] to use Playwright"
            ) from error
        return async_playwright()

    async def start(self) -> None:
        if self._context is not None:
            return
        self._playwright = await self._playwright_factory().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        options: dict[str, Any] = {"user_agent": USER_AGENT}
        if self.proxy:
            options["proxy"] = {"server": self.proxy}
            options["ignore_https_errors"] = True
        self._context = await self._browser.new_context(**options)
        if self.route_handlers:
            await self._context.route("**/*", self._route)

    async def _route(self, route: Any) -> None:
        for handler in self.route_handlers:
            if await handler(route):
                return
        await route.continue_()

    async def stop(self) -> None:
        if self._context is not None:
            await self._context.close()
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()
        self._context = self._browser = self._playwright = None

    async def __aenter__(self) -> "PlaywrightManager":
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.stop()

    async def new_page(self) -> Any:
        await self.start()
        if self._context is None:
            raise RuntimeError("Playwright browser failed to start")
        return await self._context.new_page()


class PatchrightManager(PlaywrightManager):
    """PlaywrightManager using Patchright's browser driver."""

    def _playwright_factory(self) -> Any:
        try:
            from patchright.async_api import async_playwright
        except ImportError as error:
            raise RuntimeError(
                "Install longscrape[patchright] to use Patchright"
            ) from error
        return async_playwright()


class StealthPlaywrightManager(PlaywrightManager):
    """PlaywrightManager that applies playwright-stealth to every new page."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        try:
            from playwright_stealth import Stealth
        except ImportError as error:
            raise RuntimeError("Install longscrape[stealth] to use stealth") from error
        self._stealth = Stealth(navigator_user_agent_override=USER_AGENT)

    async def new_page(self) -> Any:
        page = await super().new_page()
        try:
            await self._stealth.apply_stealth_async(page)
        except Exception:
            await page.close()
            raise
        return page


class PlaywrightFetcher:
    """Fetch :class:`InputUrl` jobs through a Playwright-compatible manager."""

    manager_class = PlaywrightManager

    def __init__(self, manager: PlaywrightManager | None = None) -> None:
        self.manager = manager or self.manager_class()

    async def start(self) -> None:
        await self.manager.start()

    async def stop(self) -> None:
        await self.manager.stop()

    async def __aenter__(self) -> "PlaywrightFetcher":
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.stop()

    async def fetch(self, job: Job) -> Document:
        if not isinstance(job.input, InputUrl):
            raise TypeError("PlaywrightFetcher requires Job.input to be InputUrl")
        page = await self.manager.new_page()
        try:
            response = await page.goto(job.input.url)
            return Document(
                url=page.url,
                content=(await page.content()).encode(),
                status=response.status if response else 200,
                headers=dict(response.headers) if response else {},
            )
        finally:
            await page.close()


class PatchrightFetcher(PlaywrightFetcher):
    manager_class = PatchrightManager


class StealthFetcher(PlaywrightFetcher):
    manager_class = StealthPlaywrightManager


class ContentTypeBlocklist:
    def __init__(self, blocked_types: Sequence[str] = ("stylesheet", "font")) -> None:
        self.blocked_types = frozenset(blocked_types)

    async def __call__(self, route: Any) -> bool:
        if route.request.resource_type not in self.blocked_types:
            return False
        await route.abort()
        return True


class URLBlocklist:
    def __init__(self, blocklist: Sequence[str]) -> None:
        self.blocklist = tuple(blocklist)

    async def __call__(self, route: Any) -> bool:
        if not any(value in route.request.url for value in self.blocklist):
            return False
        await route.abort()
        return True


class URLCacher:
    """Small GET-response disk cache implemented as a route handler."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, url: str) -> Path:
        return self.directory / f"{hashlib.sha256(url.encode()).hexdigest()}.json"

    async def __call__(self, route: Any) -> bool:
        if route.request.method != "GET":
            return False
        path = self._path(route.request.url)
        if path.exists():
            data = json.loads(await asyncio.to_thread(path.read_text, encoding="utf-8"))
            await route.fulfill(
                status=data["status"],
                headers=data["headers"],
                body=base64.b64decode(data["body"]),
            )
            return True
        response = await route.fetch()
        body = await response.body()
        payload = {
            "status": response.status,
            "headers": response.headers,
            "body": base64.b64encode(body).decode(),
        }
        await asyncio.to_thread(path.write_text, json.dumps(payload), encoding="utf-8")
        await route.fulfill(response=response)
        return True
