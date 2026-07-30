from typing import Any

from patchright.async_api import async_playwright

from longscrape.adapters.playwright.playwright import PlaywrightManager


class PatchrightManager(PlaywrightManager):
    def _create_playwright(self) -> Any:
        return async_playwright()
