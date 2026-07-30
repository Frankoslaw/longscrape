from typing import Protocol

from playwright.async_api import Page, Route


class PlaywrightMiddlewarePort(Protocol):
    async def handle(self, route: Route) -> bool: ...


class PlaywrightManagerPort(Protocol):
    async def start(self): ...

    async def stop(self): ...

    async def create_page(self) -> Page: ...

    def register_middleware(self, middleware: PlaywrightMiddlewarePort): ...
