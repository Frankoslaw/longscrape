from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from longscrape.adapters.browser_capture import BrowserCapture, BrowserCaptureServer
    from longscrape.adapters.fetchers import (
        CachedFetcher,
        HttpxFetcher,
        PlaywrightFetcher,
        RateLimitedFetcher,
    )
    from longscrape.adapters.ratelimit import LeakyBucketRateLimiter, RateLimiter
    from longscrape.adapters.store import InMemoryDocumentStore, PyMongoDocumentStore

__all__ = [
    "BrowserCapture",
    "BrowserCaptureServer",
    "CachedFetcher",
    "HttpxFetcher",
    "InMemoryDocumentStore",
    "LeakyBucketRateLimiter",
    "PyMongoDocumentStore",
    "PlaywrightFetcher",
    "RateLimitedFetcher",
    "RateLimiter",
]

_ADAPTERS = {
    "BrowserCapture": "longscrape.adapters.browser_capture",
    "BrowserCaptureServer": "longscrape.adapters.browser_capture",
    "CachedFetcher": "longscrape.adapters.fetchers",
    "HttpxFetcher": "longscrape.adapters.fetchers",
    "InMemoryDocumentStore": "longscrape.adapters.store.in_memory",
    "LeakyBucketRateLimiter": "longscrape.adapters.ratelimit",
    "PyMongoDocumentStore": "longscrape.adapters.store.mongo",
    "PlaywrightFetcher": "longscrape.adapters.fetchers",
    "RateLimitedFetcher": "longscrape.adapters.fetchers",
    "RateLimiter": "longscrape.adapters.ratelimit",
}


def __getattr__(name: str):
    try:
        module_name = _ADAPTERS[name]
    except KeyError as error:
        raise AttributeError(name) from error
    return getattr(import_module(module_name), name)
