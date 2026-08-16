import asyncio
import time
from typing import Protocol
from urllib.parse import urlparse


class RateLimiter(Protocol):
    async def acquire(self, key: str) -> None: ...


def _get_domain(url: str) -> str:
    parsed = urlparse(url)
    return (parsed.hostname or parsed.path.split("/", maxsplit=1)[0]).lower()


class LeakyBucketRateLimiter(RateLimiter):
    def __init__(self, requests_per_second: float, capacity: int = 1) -> None:
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be greater than zero")
        if capacity < 1:
            raise ValueError("capacity must be at least one")
        self.rate = requests_per_second
        self.capacity = capacity
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, url: str) -> None:
        domain = _get_domain(url)

        while True:
            async with self._lock:
                now = time.monotonic()
                water, last_check = self._buckets.get(domain, (0.0, now))

                elapsed = now - last_check
                water = max(0.0, water - elapsed * self.rate)

                if water + 1.0 <= self.capacity:
                    self._buckets[domain] = (water + 1.0, now)
                    return

                sleep_time = (water + 1.0 - self.capacity) / self.rate
                self._buckets[domain] = (water, now)
            await asyncio.sleep(max(0.02, sleep_time))
