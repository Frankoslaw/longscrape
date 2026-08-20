from collections.abc import AsyncIterable
from datetime import timedelta
from typing import Any, Callable, Never, Protocol
from uuid import UUID

from longscrape_core.context import JobSubmitter, PipelineContext
from longscrape_core.failures import PipelineFailure, Recovery
from longscrape_core.models import (
    CollisionPolicy,
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
    def fetch(
        self, job: Job, context: PipelineContext | None = None
    ) -> AsyncIterable[Document]: ...


class Extractor[Out](Protocol):
    def extract(
        self,
        documents: AsyncIterable[Document],
        job: Job,
        context: PipelineContext | None = None,
    ) -> AsyncIterable[Record[Out]]: ...


# NOTE: Earlier versions of api also exposed separate sink api with write method that
# sat at the end of pipelines. But transformer that emits 0 items at the end effectively
# provides same terminating behavior for both native longscrape usage and future
# longscrape-scrapy integration.
class Transformer[In, Out](Protocol):
    def transform(
        self,
        records: AsyncIterable[Record[In]],
        job: Job,
        context: PipelineContext | None = None,
    ) -> AsyncIterable[Record[Out]]: ...


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


class DocumentStore(Protocol):
    """Immutable document revisions addressed by opaque refs and stable keys."""

    async def put(
        self,
        document: Document,
        *,
        key: str,
        policy: CollisionPolicy = CollisionPolicy.NEW,
    ) -> DocumentRef: ...
    async def get(self, ref: DocumentRef) -> Document: ...
    async def latest(self, key: str) -> DocumentRef | None: ...
    def iter_latest(self) -> AsyncIterable[DocumentRef]: ...


class RecordStore(Protocol):
    """Records addressed by opaque refs and replaceable stable keys."""

    async def put(
        self,
        record: Record[Any],
        *,
        key: str | None = None,
        policy: CollisionPolicy = CollisionPolicy.NEW,
    ) -> RecordRef: ...
    async def get(self, ref: RecordRef) -> Record[Any]: ...
    async def latest(self, key: str) -> RecordRef | None: ...


# TODO: In future consider buffered sink to support batched writes instead of spamming
# the database with small records
class RecordSink[In](Transformer[In, Never]):
    def __init__(
        self,
        store: RecordStore,
        *,
        key: Callable[[Record[In], Job], str] | None = None,
        policy: CollisionPolicy = CollisionPolicy.NEW,
    ) -> None:
        self._store = store
        self._key = key
        self._policy = policy

    async def transform(
        self,
        records: AsyncIterable[Record[In]],
        job: Job,
        context: PipelineContext | None = None,
    ) -> AsyncIterable[Record[Never]]:
        async for record in records:
            await self._store.put(
                record,
                key=self._key(record, job) if self._key is not None else None,
                policy=self._policy,
            )

        if False:
            yield
