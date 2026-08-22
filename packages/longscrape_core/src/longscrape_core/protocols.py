from collections.abc import AsyncIterable, Awaitable, Callable
from datetime import timedelta
from typing import Any, Protocol
from uuid import UUID

from longscrape_core.context import JobSubmitter, PipelineContext
from longscrape_core.failures import PipelineFailure, Recovery
from longscrape_core.models import (
    Document,
    DocumentRef,
    Job,
    Record,
    RecordRef,
    StoredJob,
)


# Pipeline protocols
class JobQueue(JobSubmitter, Protocol):
    """Queue contract with optional worker-affinity delivery.

    ``get(worker_id=...)`` may return unpinned jobs and jobs pinned to that
    exact ID, but never jobs pinned to another worker. ``get()`` without an ID
    returns only unpinned jobs.
    """

    async def submit_job(self, job: Job, *, delay: timedelta | None = None) -> None: ...

    async def get(
        self, kind: str | None = None, *, worker_id: str | None = None
    ) -> Job: ...

    def empty(
        self, kind: str | None = None, *, worker_id: str | None = None
    ) -> bool: ...


class Fetcher(Protocol):
    async def fetch(self, job: Job, context: PipelineContext) -> Document: ...


class Extractor[Out](Protocol):
    def extract(
        self,
        document: Document,
        job: Job,
        context: PipelineContext,
    ) -> AsyncIterable[Record[Out]]: ...


class Transformer[In, Out](Protocol):
    def transform(
        self,
        records: AsyncIterable[Record[In]],
        job: Job,
        context: PipelineContext,
    ) -> AsyncIterable[Record[Out]]: ...


class Sink[Out](Protocol):
    """Terminal consumer of a stream of records."""

    async def sink(
        self,
        records: AsyncIterable[Record[Out]],
        job: Job,
        context: PipelineContext,
    ) -> None: ...


class RecoveryPolicy(Protocol):
    """Chooses a recovery recommendation for a failure."""

    async def decide(self, failure: PipelineFailure) -> Recovery: ...


class JobStore(Protocol):
    """Tracks durable job identity and execution state."""

    async def register(self, job: Job, *, key: str | None = None) -> bool: ...
    async def get(self, job_id: UUID) -> StoredJob: ...
    async def start(self, job_id: UUID) -> None: ...
    async def succeed(self, job_id: UUID) -> None: ...
    async def fail(self, job_id: UUID, error: Exception) -> None: ...


class DocumentCache(Protocol):
    async def get(self, key: str) -> Document | None: ...
    async def set(self, key: str, document: Document) -> None: ...
    async def delete(self, key: str) -> None: ...


class DocumentArchive(Protocol):
    async def save(self, document: Document, *, key: str) -> DocumentRef: ...
    async def get(self, ref: DocumentRef) -> Document: ...
    async def latest(self, key: str) -> DocumentRef | None: ...
    # TODO: Can this helper for reextraction be implemented in better way?
    async def iter_latest(self) -> AsyncIterable[DocumentRef]: ...
    async def prune(self, *, keep_last: int | None = None) -> int: ...


class RecordMerger(Protocol):
    """Combine the current keyed record with an incoming record."""

    def merge(self, existing: Record[Any], incoming: Record[Any]) -> Record[Any]: ...


class RecordStore(Protocol):
    async def add(self, record: Record) -> RecordRef: ...
    async def get(self, ref: RecordRef) -> Record: ...
    async def latest(self, key: str) -> RecordRef | None: ...

    async def create(self, key: str, record: Record) -> RecordRef: ...
    async def replace(self, key: str, record: Record) -> RecordRef: ...
    async def merge(
        self, key: str, record: Record, *, with_: RecordMerger
    ) -> RecordRef: ...


type RecordWriter[In] = Callable[[RecordStore, Record[In], Job], Awaitable[RecordRef]]


async def _add_record(store: RecordStore, record: Record[Any], _job: Job) -> RecordRef:
    return await store.add(record)


# TODO: In future consider buffered sink to support batched writes instead of spamming
# the database with small records
class RecordSink[In](Sink[In]):
    """Persist records through an explicit write strategy.

    The default strategy appends each record.  Supply ``write`` when a sink
    should create, replace, or merge records under an application-defined key.
    """

    def __init__(
        self,
        store: RecordStore,
        *,
        write: RecordWriter[In] | None = None,
    ) -> None:
        self._store = store
        self._write = write or _add_record

    async def sink(
        self,
        records: AsyncIterable[Record[In]],
        job: Job,
        context: PipelineContext,
    ) -> None:
        async for record in records:
            await self._write(self._store, record, job)
