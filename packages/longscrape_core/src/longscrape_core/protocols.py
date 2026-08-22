from collections.abc import AsyncIterable, Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

from longscrape_core.context import PipelineContext, WorkController
from longscrape_core.failures import PipelineFailure, Recovery
from longscrape_core.models import (
    Document,
    DocumentRef,
    Job,
    JobEvent,
    JobLease,
    JobView,
    Record,
    RecordRef,
)


class Fetcher(Protocol):
    async def fetch(self, job: Job, context: PipelineContext) -> Document: ...


class Extractor[Out](Protocol):
    def extract(
        self, document: Document, job: Job, context: PipelineContext
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


class JobExecutor(Protocol):
    """Execute one claimed job using the supplied process-local context."""

    async def execute(self, job: Job, context: PipelineContext) -> None: ...


class RecoveryPolicy(Protocol):
    """Choose a recovery recommendation for an execution failure."""

    async def decide(self, failure: PipelineFailure) -> Recovery: ...


class WorkStore(WorkController, Protocol):
    """Durable work persistence, claiming, progress, and event history."""

    async def claim(
        self,
        *,
        worker_id: str,
        lease_for: timedelta,
        kinds: set[str] | None = None,
        job_id: UUID | None = None,
    ) -> JobLease | None: ...

    async def heartbeat(
        self, lease: JobLease, *, extend_for: timedelta
    ) -> JobLease: ...

    async def complete(self, lease: JobLease) -> None: ...

    async def retry(
        self, lease: JobLease, error: Exception, *, run_at: datetime
    ) -> None: ...

    async def fail(self, lease: JobLease, error: Exception) -> None: ...

    async def cancel(self, job_id: UUID) -> None: ...

    async def recover_expired_leases(self) -> int: ...

    async def get(self, job_id: UUID) -> JobView: ...

    def events(self, job_id: UUID) -> AsyncIterable[JobEvent]: ...


class DocumentCache(Protocol):
    async def get(self, key: str) -> Document | None: ...
    async def set(self, key: str, document: Document) -> None: ...
    async def delete(self, key: str) -> None: ...


class DocumentArchive(Protocol):
    async def save(self, document: Document, *, key: str) -> DocumentRef: ...
    async def get(self, ref: DocumentRef) -> Document: ...
    async def latest(self, key: str) -> DocumentRef | None: ...
    def iter_latest(self) -> AsyncIterable[DocumentRef]: ...
    async def prune(self, *, keep_last: int | None = None) -> int: ...


class RecordMerger(Protocol):
    """Combine the current keyed record with an incoming record."""

    def merge(self, existing: Record[Any], incoming: Record[Any]) -> Record[Any]: ...


class RecordStore(Protocol):
    async def add(self, record: Record[Any]) -> RecordRef: ...
    async def get(self, ref: RecordRef) -> Record[Any]: ...
    async def latest(self, key: str) -> RecordRef | None: ...
    async def create(self, key: str, record: Record[Any]) -> RecordRef: ...
    async def replace(self, key: str, record: Record[Any]) -> RecordRef: ...
    async def merge(
        self, key: str, record: Record[Any], *, with_: RecordMerger
    ) -> RecordRef: ...


type RecordWriter[In] = Callable[[RecordStore, Record[In], Job], Awaitable[RecordRef]]


async def _add_record(store: RecordStore, record: Record[Any], _job: Job) -> RecordRef:
    return await store.add(record)


class RecordSink[In](Sink[In]):
    """Persist records through an explicit write strategy.

    The default strategy appends each record. Supply ``write`` when a sink
    should create, replace, or merge records under an application-defined key.
    """

    def __init__(
        self, store: RecordStore, *, write: RecordWriter[In] | None = None
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
