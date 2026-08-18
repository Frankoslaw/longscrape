"""Retry decorator for transient typed fetch failures."""

import asyncio
from collections.abc import AsyncIterator, Callable
from datetime import timedelta

from longscrape_core import (
    Document,
    Fetcher,
    Job,
    PipelineContext,
    RetryableFetchFailure,
)

type Backoff = Callable[[int, RetryableFetchFailure], timedelta | None]


class RetryingFetcher:
    """Retry a fetcher locally when it raises ``RetryableFetchFailure``.

    ``max_retries`` counts additional attempts after the initial fetch.
    A failure's ``retry_after`` takes precedence over the configured backoff.
    """

    def __init__(
        self,
        fetcher: Fetcher,
        *,
        max_retries: int = 0,
        backoff: Backoff | None = None,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        self._fetcher = fetcher
        self._max_retries = max_retries
        self._backoff = backoff

    async def fetch(
        self, job: Job, context: PipelineContext | None = None
    ) -> AsyncIterator[Document]:
        for retry in range(self._max_retries + 1):
            try:
                async for document in self._fetcher.fetch(job, context):
                    yield document
                return
            except RetryableFetchFailure as failure:
                if retry == self._max_retries:
                    raise
                await self._wait(retry + 1, failure)

        raise AssertionError("unreachable")

    async def _wait(self, retry: int, failure: RetryableFetchFailure) -> None:
        delay = failure.retry_after
        if delay is None and self._backoff is not None:
            delay = self._backoff(retry, failure)
        if delay is None:
            return
        if delay < timedelta():
            raise ValueError("retry delay must be non-negative")
        await asyncio.sleep(delay.total_seconds())
