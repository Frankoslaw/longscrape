"""Browser support for Playwright-compatible browser implementations.

Only the built-in ``PlaywrightBrowserProvider`` needs the optional Playwright
dependency. Third-party providers are supplied by the application and imported
only by that provider.
"""

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from longscrape.browser.config import BrowserConfig
    from longscrape.browser.context import CURRENT_PAGE
    from longscrape.browser.handoff import ManualHandoff
    from longscrape.browser.manager import BrowserManager
    from longscrape.browser.middlewares import (
        ContentTypeBlocklist,
        PlaywrightRateLimiterMiddleware,
        URLBlocklist,
        URLCacher,
    )
    from longscrape.browser.provider import BrowserProvider, PlaywrightBrowserProvider

__all__ = [
    "BrowserConfig",
    "BrowserManager",
    "BrowserProvider",
    "ContentTypeBlocklist",
    "CURRENT_PAGE",
    "PlaywrightBrowserProvider",
    "PlaywrightRateLimiterMiddleware",
    "ManualHandoff",
    "URLBlocklist",
    "URLCacher",
]

_MODULES = {
    "BrowserConfig": "longscrape.browser.config",
    "BrowserManager": "longscrape.browser.manager",
    "ManualHandoff": "longscrape.browser.handoff",
    "BrowserProvider": "longscrape.browser.provider",
    "ContentTypeBlocklist": "longscrape.browser.middlewares",
    "CURRENT_PAGE": "longscrape.browser.context",
    "PlaywrightBrowserProvider": "longscrape.browser.provider",
    "PlaywrightRateLimiterMiddleware": "longscrape.browser.middlewares",
    "URLBlocklist": "longscrape.browser.middlewares",
    "URLCacher": "longscrape.browser.middlewares",
}


def __getattr__(name: str):
    try:
        module_name = _MODULES[name]
    except KeyError as error:
        raise AttributeError(name) from error
    return getattr(import_module(module_name), name)
