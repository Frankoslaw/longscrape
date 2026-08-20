from importlib import import_module
from typing import TYPE_CHECKING

from longscrape.fetchers.builder import FetcherBuilder
from longscrape.fetchers.cache import CachedFetcher
from longscrape.fetchers.handoff import FailureDetector, HandoffFetcher, HandoffResolver
from longscrape.fetchers.httpx_fetcher import HttpxFetcher
from longscrape.fetchers.rate_limit import RateLimitedFetcher
from longscrape.fetchers.retry import RetryingFetcher

if TYPE_CHECKING:
    from longscrape.fetchers.playwright_fetcher import BrowserFetcher

DefaultFetcher = HttpxFetcher

__all__ = [
    "CachedFetcher",
    "FetcherBuilder",
    "BrowserFetcher",
    "DefaultFetcher",
    "HttpxFetcher",
    "HandoffFetcher",
    "FailureDetector",
    "HandoffResolver",
    "RateLimitedFetcher",
    "RetryingFetcher",
]


def __getattr__(name: str):
    if name not in {"BrowserFetcher"}:
        raise AttributeError(name)
    return getattr(import_module("longscrape.fetchers.playwright_fetcher"), name)
