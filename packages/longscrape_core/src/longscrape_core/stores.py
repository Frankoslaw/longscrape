from __future__ import annotations

from longscrape_core.models import Document, Record


class InMemoryDocumentStore:
    """Process-local document store keyed by URL."""

    def __init__(self) -> None:
        self._documents: dict[str, Document] = {}

    async def save(self, document: Document) -> None:
        self._documents[document.url] = document

    async def get(self, key: str) -> Document | None:
        return self._documents.get(key)


class InMemoryRecordStore:
    """Process-local record store grouped by record kind."""

    def __init__(self) -> None:
        self._records: dict[str, list[Record]] = {}

    async def save(self, record: Record) -> None:
        self._records.setdefault(record.kind, []).append(record)

    def records(self, kind: str | None = None) -> tuple[Record, ...]:
        if kind is not None:
            return tuple(self._records.get(kind, ()))
        return tuple(record for records in self._records.values() for record in records)
