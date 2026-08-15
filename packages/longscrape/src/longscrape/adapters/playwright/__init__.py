from importlib import import_module

__all__ = [
    "ContentTypeBlocklist",
    "DefaultFetcher",
    "PatchrightManager",
    "PlaywrightManager",
    "PlaywrightManagerPort",
    "PlaywrightMiddlewarePort",
    "PlaywrightRateLimiterMiddleware",
    "StealthPlaywrightManagerAdapter",
    "URLBlocklist",
    "URLCacher",
]

_ADAPTERS = {
    "ContentTypeBlocklist": "longscrape.adapters.playwright.middlewares",
    "DefaultFetcher": "longscrape.adapters.playwright.fetcher",
    "PatchrightManager": "longscrape.adapters.playwright.patchright",
    "PlaywrightManager": "longscrape.adapters.playwright.playwright",
    "PlaywrightManagerPort": "longscrape.core.ports.playwright",
    "PlaywrightMiddlewarePort": "longscrape.core.ports.playwright",
    "PlaywrightRateLimiterMiddleware": "longscrape.adapters.playwright.middlewares",
    "StealthPlaywrightManagerAdapter": "longscrape.adapters.playwright.stealth",
    "URLBlocklist": "longscrape.adapters.playwright.middlewares",
    "URLCacher": "longscrape.adapters.playwright.middlewares",
}


def __getattr__(name: str):
    try:
        module_name = _ADAPTERS[name]
    except KeyError as error:
        raise AttributeError(name) from error
    return getattr(import_module(module_name), name)
