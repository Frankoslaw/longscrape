from longscrape_core import Document, Record
from longscrape_core.protocols import DocumentStore, RecordStore


class InMemoryDocumentStore(DocumentStore):
    def __init__(self) -> None:
        self._entries: dict[str, Document] = {}

    async def store(self, document: Document, *, key: str | None = None) -> None:
        self._entries[document.url if key is None else key] = document

    async def load(self, key: str) -> Document | None:
        return self._entries.get(key)


class InMemoryRecordStore(RecordStore):
    def __init__(self) -> None:
        self._records: dict[str, Record] = {}

    async def store(self, record: Record) -> None:
        self._records[record.hash] = record

    async def get(self, key: str) -> Record | None:
        return self._records.get(key)
