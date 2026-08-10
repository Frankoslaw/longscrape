from playwright.async_api import Page
from playwright_stealth import Stealth

from longscrape.adapters.playwright.playwright import USER_AGENT
from longscrape.core.ports.playwright import (
    PlaywrightManagerPort,
    PlaywrightMiddlewarePort,
)


class StealthPlaywrightManagerAdapter(PlaywrightManagerPort):
    def __init__(self, manager: PlaywrightManagerPort):
        self._manager = manager
        self._stealth = Stealth(navigator_user_agent_override=USER_AGENT)

    async def start(self) -> None:
        await self._manager.start()

    async def stop(self) -> None:
        await self._manager.stop()

    async def create_page(self) -> Page:
        page = await self._manager.create_page()
        try:
            await self._stealth.apply_stealth_async(page)
        except Exception:
            await page.close()
            raise
        return page

    def register_middleware(self, middleware: PlaywrightMiddlewarePort) -> None:
        self._manager.register_middleware(middleware)
