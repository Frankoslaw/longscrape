import asyncio
import base64
import hashlib
import json
import os
from typing import Any, TypedDict, cast

from longscrape.browser._protocols import BrowserMiddleware
from longscrape.observability import get_logger
from longscrape.worker.rate_limit import RateLimiter

logger = get_logger(__name__)

CACHE_DIR = ".cache"


class CacheData(TypedDict):
    status: int
    headers: dict[str, str]
    body: str


def _read_cache(path: str) -> CacheData:
    with open(path, encoding="utf-8") as cache_file:
        return cast(CacheData, json.load(cache_file))


def _write_cache(path: str, data: CacheData) -> None:
    with open(path, "w", encoding="utf-8") as cache_file:
        json.dump(data, cache_file, ensure_ascii=False, indent=2)


class ContentTypeBlocklist(BrowserMiddleware):
    def __init__(self, blocked_types: list[str] | None = None, verbose: bool = False):
        self.blocked_types = blocked_types or ["stylesheet", "font"]
        self.verbose = verbose

    async def handle(self, route: Any) -> bool:
        resource_type = route.request.resource_type
        if resource_type in self.blocked_types:
            if self.verbose:
                logger.debug(
                    "blocked resource: type=%s url=%s", resource_type, route.request.url
                )
            await route.abort()
            return True
        return False


class URLBlocklist(BrowserMiddleware):
    def __init__(self, blocklist: list[str] | None = None, verbose: bool = False):
        self.blocklist = blocklist or [
            "google-analytics.com",
            "googletagmanager.com",
            "doubleclick.net",
            "facebook.net",
            "facebook.com",
            "hotjar.com",
            "segment.io",
            "favicon.ico",
        ]
        self.verbose = verbose

    async def handle(self, route: Any) -> bool:
        url = route.request.url

        if any(blocked in url for blocked in self.blocklist):
            if self.verbose:
                logger.debug("blocked URL: url=%s", url)
            await route.abort()
            return True

        return False


class URLCacher(BrowserMiddleware):
    def __init__(
        self,
        cache_dir: str = CACHE_DIR,
        cacheable_types: list[str] | None = None,
        verbose: bool = False,
    ):
        self.cache_dir = cache_dir
        self.cacheable_types = cacheable_types or ["all"]
        self.verbose = verbose
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_path(self, url: str) -> str:
        url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
        return os.path.join(self.cache_dir, f"{url_hash}.json")

    async def handle(self, route: Any) -> bool:
        request = route.request
        if request.method != "GET":
            return False
        if (
            "all" not in self.cacheable_types
            and request.resource_type not in self.cacheable_types
        ):
            return False

        cache_path = self._get_cache_path(request.url)

        if os.path.exists(cache_path):
            if self.verbose:
                logger.debug(
                    "cache hit: type=%s url=%s", request.resource_type, request.url
                )
            cached_data = await asyncio.to_thread(_read_cache, cache_path)

            body_bytes = base64.b64decode(cached_data["body"])
            await route.fulfill(
                status=cached_data["status"],
                headers=cached_data["headers"],
                body=body_bytes,
            )
            return True

        if self.verbose:
            logger.debug(
                "cache miss: type=%s url=%s", request.resource_type, request.url
            )
        try:
            response = await route.fetch()
            body_bytes = await response.body()

            cache_data: CacheData = {
                "status": response.status,
                "headers": response.headers,
                "body": base64.b64encode(body_bytes).decode("utf-8"),
            }
            await asyncio.to_thread(_write_cache, cache_path, cache_data)

            await route.fulfill(response=response)
            return True
        except Exception:
            logger.exception("cache fetch failed: url=%s", request.url)
            await route.abort()
            return True


class PlaywrightRateLimiterMiddleware(BrowserMiddleware):
    def __init__(self, rate_limiter: RateLimiter):
        self.rate_limiter = rate_limiter

    async def handle(self, route: Any) -> bool:
        await self.rate_limiter.acquire(route.request.url)
        return False
