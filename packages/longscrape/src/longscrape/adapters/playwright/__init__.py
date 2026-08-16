from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from longscrape.adapters.fetchers.playwright_fetcher import PlaywrightFetcher
    from longscrape.adapters.playwright.patchright import PatchrightManager
    from longscrape.adapters.playwright.playwright import PlaywrightManager
    from longscrape.adapters.playwright.stealth import StealthPlaywrightManagerAdapter

__all__ = [
    "PatchrightManager",
    "PlaywrightFetcher",
    "PlaywrightManager",
    "StealthPlaywrightManagerAdapter",
]

_ADAPTERS = {
    "PatchrightManager": "longscrape.adapters.playwright.patchright",
    "PlaywrightFetcher": "longscrape.adapters.fetchers.playwright_fetcher",
    "PlaywrightManager": "longscrape.adapters.playwright.playwright",
    "StealthPlaywrightManagerAdapter": "longscrape.adapters.playwright.stealth",
}


def __getattr__(name: str):
    try:
        module_name = _ADAPTERS[name]
    except KeyError as error:
        raise AttributeError(name) from error
    return getattr(import_module(module_name), name)
