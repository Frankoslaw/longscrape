from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from longscrape.core import Context, Document, Fetcher, FetchInput
from longscrape.storage import CollisionPolicy, DocumentStore


def _input_key(fetch_input: FetchInput) -> str:
    return repr(fetch_input)


class CachedFetcher:
    def __init__(
        self,
        fetcher: Fetcher | None,
        store: DocumentStore,
        *,
        cache_key: Callable[[FetchInput], str] = _input_key,
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

    async def fetch(self, fetch_input: FetchInput, context: Context) -> Document:
        ref = (
            await self._store.latest(self._cache_key(fetch_input))
            if self._read
            else None
        )
        cached = await self._store.get(ref) if ref is not None else None
        if cached is not None and self._is_fresh(cached):
            return cached

        if self._fetcher is None:
            raise RuntimeError("CachedFetcher has no fallback fetcher")

        document = await self._fetcher.fetch(fetch_input, context)
        if self._write:
            await self._store.put(
                document,
                key=self._cache_key(fetch_input),
                policy=CollisionPolicy.OVERWRITE,
            )
        return document

    def _is_fresh(self, document: Document) -> bool:
        if self._max_age is None:
            return True
        fetched_at = document.fetched_at
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=UTC)
        return datetime.now(UTC) - fetched_at <= self._max_age
