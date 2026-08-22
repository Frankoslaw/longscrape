from collections.abc import Callable

from longscrape_core import (
    Document,
    Fetcher,
    InputUrl,
    Job,
    PipelineContext,
)

from longscrape.runtime.rate_limit import RateLimiter


def _url_key(job: Job) -> str:
    if not isinstance(job.input, InputUrl):
        raise TypeError(
            "RateLimitedFetcher requires an InputUrl input unless "
            "rate_limit_key is provided"
        )
    return job.input.url


class RateLimitedFetcher:
    def __init__(
        self,
        fetcher: Fetcher,
        rate_limiter: RateLimiter,
        *,
        rate_limit_key: Callable[[Job], str] = _url_key,
    ) -> None:
        self._fetcher = fetcher
        self._rate_limiter = rate_limiter
        self._rate_limit_key = rate_limit_key

    async def fetch(
        self, job: Job, context: PipelineContext | None = None
    ) -> Document:
        await self._rate_limiter.acquire(self._rate_limit_key(job))
        return await self._fetcher.fetch(job, context)
