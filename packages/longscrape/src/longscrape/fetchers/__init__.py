from importlib import import_module
from typing import TYPE_CHECKING

from longscrape.fetchers.cached import CachedFetcher
from longscrape.fetchers.httpx_fetcher import HttpxFetcher
from longscrape.fetchers.ratelimited import RateLimitedFetcher

if TYPE_CHECKING:
    from longscrape.fetchers.playwright_fetcher import PlaywrightFetcher

DefaultFetcher = HttpxFetcher

__all__ = [
    "CachedFetcher",
    "DefaultFetcher",
    "HttpxFetcher",
    "PlaywrightFetcher",
    "RateLimitedFetcher",
]


def __getattr__(name: str):
    if name != "PlaywrightFetcher":
        raise AttributeError(name)
    return getattr(import_module("longscrape.fetchers.playwright_fetcher"), name)
