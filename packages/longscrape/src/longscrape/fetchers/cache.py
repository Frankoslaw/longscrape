from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta

from longscrape_core import (
    DISCARD_SUBMITTER,
    Document,
    Fetcher,
    InputUrl,
    Job,
    JobSubmitter,
)
from longscrape_core.ports import DocumentStore


def _url_key(job: Job) -> str:
    if not isinstance(job.input, InputUrl):
        raise TypeError(
            "CachedFetcher requires an InputUrl input unless cache_key is provided"
        )
    return job.input.url


class CachedFetcher:
    def __init__(
        self,
        fetcher: Fetcher | None,
        store: DocumentStore,
        *,
        cache_key: Callable[[Job], str] = _url_key,
        read: bool = True,
        write: bool = True,
        max_age: timedelta | None = None,
    ) -> None:
        if max_age is not None and max_age <= timedelta():
            raise ValueError("max_age must be greater than zero")
        self._fetcher = fetcher
        self._store = store
        self._cache_key = cache_key
        self._read = read
        self._write = write
        self._max_age = max_age

    async def fetch(
        self, job: Job, submitter: JobSubmitter = DISCARD_SUBMITTER
    ) -> AsyncIterator[Document]:
        cached = await self._store.load(self._cache_key(job)) if self._read else None
        if cached is not None and self._is_fresh(cached):
            yield cached
            return

        if self._fetcher is None:
            return

        async for document in self._fetcher.fetch(job, submitter):
            if self._write:
                await self._store.store(document)
            yield document

    def _is_fresh(self, document: Document) -> bool:
        if self._max_age is None:
            return True
        fetched_at = document.fetched_at
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=UTC)
        return datetime.now(UTC) - fetched_at <= self._max_age
