"""Optional persistence contracts for documents and records."""

from collections.abc import AsyncIterable, Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from longscrape_core.context import PipelineContext
from longscrape_core.models import Document, DocumentRef, Job, Record
from longscrape_core.pipeline import Sink


@dataclass(frozen=True)
class RecordRef:
    """Opaque reference returned by a record store."""

    store: str
    value: str


class DocumentCache(Protocol):
    async def get(self, key: str) -> Document | None: ...
    async def set(self, key: str, document: Document) -> None: ...
    async def delete(self, key: str) -> None: ...


class DocumentArchive(Protocol):
    async def save(self, key: str, document: Document) -> DocumentRef: ...
    async def get(self, ref: DocumentRef) -> Document: ...
    async def latest(self, key: str) -> DocumentRef | None: ...
    def iter_latest(self) -> AsyncIterable[DocumentRef]: ...
    async def prune(self, *, keep_last: int | None = None) -> int: ...


class RecordMerger(Protocol):
    def merge(self, existing: Record[Any], incoming: Record[Any]) -> Record[Any]: ...


class RecordStore(Protocol):
    """Persist append-only or stable-key records.

    ``append`` always creates a new entry and accepts keyed and unkeyed records.
    ``upsert`` requires a key and atomically creates or replaces its latest record.
    ``merge`` requires a key and atomically creates it when absent, otherwise merges
    it with the current record. Implementations must reject a kind change for an
    existing key and must not expose an intermediate value to concurrent writers.
    """

    async def append(self, record: Record[Any]) -> RecordRef: ...
    async def get(self, ref: RecordRef) -> Record[Any]: ...
    async def latest(self, key: str) -> RecordRef | None: ...
    async def upsert(self, record: Record[Any]) -> RecordRef: ...
    async def merge(self, record: Record[Any], *, with_: RecordMerger) -> RecordRef: ...


def require_record_key(record: Record[Any]) -> str:
    """Return a stable key or reject an operation that requires one."""
    if record.key is None:
        raise ValueError("record operation requires a stable record key")
    return record.key


type RecordWriter[In] = Callable[[RecordStore, Record[In], Job], Awaitable[RecordRef]]


async def append_record(
    store: RecordStore, record: Record[Any], _job: Job
) -> RecordRef:
    return await store.append(record)


class RecordSink[In](Sink[In]):
    """A storage adapter; direct sinks remain equally valid."""

    def __init__(
        self, store: RecordStore, *, write: RecordWriter[In] | None = None
    ) -> None:
        self._store = store
        self._write = write or append_record

    async def sink(
        self, records: AsyncIterable[Record[In]], job: Job, context: PipelineContext
    ) -> None:
        async for record in records:
            await self._write(self._store, record, job)
