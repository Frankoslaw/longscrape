from importlib import import_module

__all__ = [
    "ContentTypeBlocklist",
    "DefaultFetcher",
    "HttpxFetcher",
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
    "HttpxFetcher": "longscrape.adapters.httpx",
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
    try:
        return getattr(import_module(module_name), name)
    except ModuleNotFoundError as error:
        extra = _OPTIONAL_EXTRAS.get(name)
        if extra is None:
            raise
        raise ModuleNotFoundError(
            f"{name} requires the optional '{extra}' extra. "
            f"Install it with: pip install longscrape[{extra}]"
        ) from error


_OPTIONAL_EXTRAS = {
    "ContentTypeBlocklist": "playwright",
    "DefaultFetcher": "playwright",
    "PatchrightManager": "patchright",
    "PlaywrightManager": "playwright",
    "PlaywrightManagerPort": "playwright",
    "PlaywrightMiddlewarePort": "playwright",
    "PlaywrightRateLimiterMiddleware": "playwright",
    "PyMongoRawEntryStore": "mongodb",
    "StealthPlaywrightManagerAdapter": "stealth",
    "URLBlocklist": "playwright",
    "URLCacher": "playwright",
}
