from collections.abc import AsyncIterator

from longscrape_core import Document
from longscrape_core.ports import DocumentStore

from longscrape.core.domain.pipeline import RawEntry


class InMemoryRawEntryStore:
    """Process-local raw entry store suitable as the default cache."""

    def __init__(self) -> None:
        self._entries: dict[str, RawEntry] = {}

    async def get(self, cache_key: str) -> RawEntry | None:
        return self._entries.get(cache_key)

    async def put(self, cache_key: str, raw_entry: RawEntry) -> None:
        self._entries[cache_key] = raw_entry

    async def entries(self) -> AsyncIterator[RawEntry]:
        # Snapshot values so a concurrent write cannot invalidate iteration.
        for raw_entry in tuple(self._entries.values()):
            yield raw_entry


class InMemoryDocumentStore(DocumentStore):
    def __init__(self) -> None:
        self._entries: dict[str, Document] = {}

    async def store(self, document: Document) -> None:
        # TODO: this is temporary
        key = document.url
        self._entries[key] = document

    async def load(self, key: str) -> Document | None:
        return self._entries.get(key)
