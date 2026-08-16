from longscrape.adapters.fetchers.cached import CachedFetcher
from longscrape.adapters.fetchers.httpx_fetcher import HttpxFetcher
from longscrape.adapters.fetchers.playwright_fetcher import PlaywrightFetcher
from longscrape.adapters.fetchers.ratelimited import RateLimitedFetcher

DefaultFetcher = HttpxFetcher

__all__ = [
    "CachedFetcher",
    "DefaultFetcher",
    "HttpxFetcher",
    "PlaywrightFetcher",
    "RateLimitedFetcher",
]
