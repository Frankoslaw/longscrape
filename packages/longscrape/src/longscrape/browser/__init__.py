"""Browser support for Playwright-compatible browser implementations.

Only the built-in ``PlaywrightBrowserProvider`` needs the optional Playwright
dependency. Third-party providers are supplied by the application and imported
only by that provider.
"""

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from longscrape.browser.config import BrowserConfig
    from longscrape.browser.manager import BrowserManager
    from longscrape.browser.middlewares import (
        ContentTypeBlocklist,
        PlaywrightRateLimiterMiddleware,
        URLBlocklist,
        URLCacher,
    )
    from longscrape.browser.provider import BrowserProvider, PlaywrightBrowserProvider

    PlaywrightManager = BrowserManager

__all__ = [
    "BrowserConfig",
    "BrowserManager",
    "BrowserProvider",
    "ContentTypeBlocklist",
    "PlaywrightBrowserProvider",
    "PlaywrightManager",
    "PlaywrightRateLimiterMiddleware",
    "URLBlocklist",
    "URLCacher",
]

_MODULES = {
    "BrowserConfig": "longscrape.browser.config",
    "BrowserManager": "longscrape.browser.manager",
    "BrowserProvider": "longscrape.browser.provider",
    "ContentTypeBlocklist": "longscrape.browser.middlewares",
    "PlaywrightBrowserProvider": "longscrape.browser.provider",
    "PlaywrightRateLimiterMiddleware": "longscrape.browser.middlewares",
    "URLBlocklist": "longscrape.browser.middlewares",
    "URLCacher": "longscrape.browser.middlewares",
}


def __getattr__(name: str):
    if name == "PlaywrightManager":
        # Deprecated spelling retained for source compatibility.
        return getattr(import_module("longscrape.browser.manager"), "BrowserManager")
    try:
        module_name = _MODULES[name]
    except KeyError as error:
        raise AttributeError(name) from error
    return getattr(import_module(module_name), name)
