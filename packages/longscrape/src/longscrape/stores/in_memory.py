from longscrape_core import Document, Record
from longscrape_core.ports import DocumentStore, RecordStore


class InMemoryDocumentStore(DocumentStore):
    def __init__(self) -> None:
        self._entries: dict[str, Document] = {}

    async def store(self, document: Document) -> None:
        key = document.url
        self._entries[key] = document

    async def load(self, key: str) -> Document | None:
        return self._entries.get(key)


class InMemoryRecordStore(RecordStore):
    def __init__(self) -> None:
        self._records: dict[str, Record] = {}

    async def store(self, record: Record) -> None:
        self._records[record.hash] = record

    async def get(self, key: str) -> Record | None:
        return self._records.get(key)
