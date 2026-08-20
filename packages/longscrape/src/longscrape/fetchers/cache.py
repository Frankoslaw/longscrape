from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta

from longscrape_core import CollisionPolicy, Document, Fetcher, Job, PipelineContext
from longscrape_core.protocols import DocumentStore


def _job_key(job: Job) -> str:
    return job.hash


class CachedFetcher:
    def __init__(
        self,
        fetcher: Fetcher | None,
        store: DocumentStore,
        *,
        cache_key: Callable[[Job], str] = _job_key,
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
        self, job: Job, context: PipelineContext | None = None
    ) -> AsyncIterator[Document]:
        ref = await self._store.latest(self._cache_key(job)) if self._read else None
        cached = await self._store.get(ref) if ref is not None else None
        if cached is not None and self._is_fresh(cached):
            yield cached
            return

        if self._fetcher is None:
            return

        async for document in self._fetcher.fetch(job, context):
            if self._write:
                await self._store.put(
                    document,
                    key=self._cache_key(job),
                    policy=CollisionPolicy.OVERWRITE,
                )
            yield document

    def _is_fresh(self, document: Document) -> bool:
        if self._max_age is None:
            return True
        fetched_at = document.fetched_at
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=UTC)
        return datetime.now(UTC) - fetched_at <= self._max_age
