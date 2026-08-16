from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from longscrape.browser.middlewares import (
        ContentTypeBlocklist,
        PlaywrightRateLimiterMiddleware,
        URLBlocklist,
        URLCacher,
    )
    from longscrape.browser.patchright import PatchrightManager
    from longscrape.browser.playwright import PlaywrightManager
    from longscrape.browser.stealth import StealthPlaywrightManagerAdapter
    from longscrape.fetchers.playwright_fetcher import PlaywrightFetcher

__all__ = [
    "ContentTypeBlocklist",
    "PatchrightManager",
    "PlaywrightFetcher",
    "PlaywrightManager",
    "PlaywrightRateLimiterMiddleware",
    "StealthPlaywrightManagerAdapter",
    "URLBlocklist",
    "URLCacher",
]

_MODULES = {
    "ContentTypeBlocklist": "longscrape.browser.middlewares",
    "PatchrightManager": "longscrape.browser.patchright",
    "PlaywrightFetcher": "longscrape.fetchers.playwright_fetcher",
    "PlaywrightManager": "longscrape.browser.playwright",
    "PlaywrightRateLimiterMiddleware": "longscrape.browser.middlewares",
    "StealthPlaywrightManagerAdapter": "longscrape.browser.stealth",
    "URLBlocklist": "longscrape.browser.middlewares",
    "URLCacher": "longscrape.browser.middlewares",
}


def __getattr__(name: str):
    try:
        module_name = _MODULES[name]
    except KeyError as error:
        raise AttributeError(name) from error
    return getattr(import_module(module_name), name)
