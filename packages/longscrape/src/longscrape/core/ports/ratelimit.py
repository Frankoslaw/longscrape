from typing import Protocol

class RateLimiter(Protocol):
    async def acquire(self, url: str) -> None: ...
