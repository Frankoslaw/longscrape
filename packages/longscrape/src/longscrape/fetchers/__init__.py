from importlib import import_module
from typing import TYPE_CHECKING

from longscrape.fetchers.cache import CachedFetcher
from longscrape.fetchers.handoff import (
    HandoffDetector,
    HandoffFetcher,
    HandoffResolver,
)
from longscrape.fetchers.httpx_fetcher import HttpxFetcher
from longscrape.fetchers.rate_limit import RateLimitedFetcher
from longscrape.fetchers.retry import Backoff, RetryingFetcher

if TYPE_CHECKING:
    from longscrape.fetchers.playwright_fetcher import BrowserFetcher

DefaultFetcher = HttpxFetcher

__all__ = [
    "CachedFetcher",
    "BrowserFetcher",
    "DefaultFetcher",
    "HttpxFetcher",
    "HandoffFetcher",
    "HandoffDetector",
    "HandoffResolver",
    "RateLimitedFetcher",
    "RetryingFetcher",
    "Backoff",
]


def __getattr__(name: str):
    if name not in {"BrowserFetcher"}:
        raise AttributeError(name)
    return getattr(import_module("longscrape.fetchers.playwright_fetcher"), name)
