from collections.abc import AsyncIterator, Callable

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
        fetcher: Fetcher,
        store: DocumentStore,
        *,
        cache_key: Callable[[Job], str] = _url_key,
    ) -> None:
        self._fetcher = fetcher
        self._store = store
        self._cache_key = cache_key

    async def fetch(
        self, job: Job, submitter: JobSubmitter = DISCARD_SUBMITTER
    ) -> AsyncIterator[Document]:
        cached = await self._store.load(self._cache_key(job))
        if cached is not None:
            yield cached
            return

        async for document in self._fetcher.fetch(job, submitter):
            await self._store.store(document)
            yield document
