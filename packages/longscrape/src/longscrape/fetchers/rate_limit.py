from collections.abc import Callable

from longscrape_core import (
    Context,
    Document,
    Fetcher,
    FetchInput,
    InputUrl,
)

from longscrape.worker.rate_limit import RateLimiter


def _url_key(fetch_input: FetchInput) -> str:
    if not isinstance(fetch_input, InputUrl):
        raise TypeError(
            "RateLimitedFetcher requires an InputUrl input unless "
            "rate_limit_key is provided"
        )
    return fetch_input.url


class RateLimitedFetcher:
    def __init__(
        self,
        fetcher: Fetcher,
        rate_limiter: RateLimiter,
        *,
        rate_limit_key: Callable[[FetchInput], str] = _url_key,
    ) -> None:
        self._fetcher = fetcher
        self._rate_limiter = rate_limiter
        self._rate_limit_key = rate_limit_key

    async def fetch(self, fetch_input: FetchInput, context: Context) -> Document:
        await self._rate_limiter.acquire(self._rate_limit_key(fetch_input))
        return await self._fetcher.fetch(fetch_input, context)
