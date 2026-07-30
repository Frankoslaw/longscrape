from importlib import import_module

__all__ = [
    "ContentTypeBlocklist",
    "DefaultFetcher",
    "HttpxManager",
    "InMemoryRawEntryStore",
    "PatchrightManager",
    "PlaywrightManager",
    "PlaywrightManagerPort",
    "PlaywrightMiddlewarePort",
    "PlaywrightRateLimiterMiddleware",
    "PyMongoRawEntryStore",
    "StealthPlaywrightManagerAdapter",
    "URLBlocklist",
    "URLCacher",
]

_ADAPTERS = {
    "ContentTypeBlocklist": "longscrape.adapters.playwright.middlewares",
    "DefaultFetcher": "longscrape.adapters.playwright.fetcher",
    "HttpxManager": "longscrape.adapters.httpx",
    "InMemoryRawEntryStore": "longscrape.adapters.store.in_memory",
    "PatchrightManager": "longscrape.adapters.playwright.patchright",
    "PlaywrightManager": "longscrape.adapters.playwright.playwright",
    "PlaywrightManagerPort": "longscrape.core.ports.playwright",
    "PlaywrightMiddlewarePort": "longscrape.core.ports.playwright",
    "PlaywrightRateLimiterMiddleware": "longscrape.adapters.playwright.middlewares",
    "PyMongoRawEntryStore": "longscrape.adapters.store.raw_entry",
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
