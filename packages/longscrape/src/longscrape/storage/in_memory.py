import asyncio
import uuid
from dataclasses import replace
from uuid import UUID

from longscrape.core import Document, Record
from longscrape.storage.models import (
    CollisionPolicy,
    DocumentRef,
    RecordRef,
    merge_records,
)
from longscrape.storage.protocols import DocumentStore, RecordStore
from longscrape.worker.models import Job, JobStatus, StoredJob
from longscrape.worker.protocols import JobStore


class InMemoryDocumentStore(DocumentStore):
    def __init__(self) -> None:
        self._documents: dict[str, Document] = {}
        self._keys: dict[str, str] = {}

    async def put(
        self,
        document: Document,
        *,
        key: str,
        policy: CollisionPolicy = CollisionPolicy.NEW,
    ) -> DocumentRef:
        current = await self.latest(key)
        if policy is CollisionPolicy.MERGE:
            raise ValueError("documents cannot be merged")
        if current is not None and policy is CollisionPolicy.OVERWRITE:
            self._delete_key(key)
        ref = DocumentRef("memory-document", str(uuid.uuid4()))
        self._documents[ref.value] = document
        self._keys[ref.value] = key
        return ref

    async def get(self, ref: DocumentRef) -> Document:
        if ref.store != "memory-document":
            raise LookupError(f"document ref belongs to {ref.store!r}, not this store")
        try:
            return self._documents[ref.value]
        except KeyError as error:
            raise LookupError(f"document ref {ref.value!r} does not exist") from error

    async def latest(self, key: str) -> DocumentRef | None:
        for value in reversed(self._documents):
            if self._keys[value] == key:
                return DocumentRef("memory-document", value)
        return None

    async def iter_latest(self):
        keys = set(self._keys.values())
        for key in keys:
            ref = await self.latest(key)
            if ref is not None:
                yield ref

    def _delete_key(self, key: str) -> None:
        values = [
            value for value, stored_key in self._keys.items() if stored_key == key
        ]
        for value in values:
            del self._documents[value]
            del self._keys[value]


class InMemoryRecordStore(RecordStore):
    def __init__(self) -> None:
        self._records: dict[str, Record] = {}
        self._keys: dict[str, str] = {}

    async def put(
        self,
        record: Record,
        *,
        key: str | None = None,
        policy: CollisionPolicy = CollisionPolicy.NEW,
    ) -> RecordRef:
        record_key = record.hash if key is None else key
        current = await self.latest(record_key)
        if current is not None:
            if policy is CollisionPolicy.MERGE:
                record = merge_records(await self.get(current), record)
            if policy is not CollisionPolicy.NEW:
                self._delete_key(record_key)
        ref = RecordRef("memory-record", str(uuid.uuid4()))
        self._records[ref.value] = record
        self._keys[ref.value] = record_key
        return ref

    async def get(self, ref: RecordRef) -> Record:
        if ref.store != "memory-record":
            raise LookupError(f"record ref belongs to {ref.store!r}, not this store")
        try:
            return self._records[ref.value]
        except KeyError as error:
            raise LookupError(f"record ref {ref.value!r} does not exist") from error

    async def latest(self, key: str) -> RecordRef | None:
        for value in reversed(self._records):
            if self._keys[value] == key:
                return RecordRef("memory-record", value)
        return None

    def _delete_key(self, key: str) -> None:
        values = [
            value for value, stored_key in self._keys.items() if stored_key == key
        ]
        for value in values:
            del self._records[value]
            del self._keys[value]


class InMemoryJobStore(JobStore):
    """A process-local job store with first-writer-wins job keys."""

    def __init__(self) -> None:
        self._jobs: dict[UUID, StoredJob] = {}
        self._keys: dict[str, UUID] = {}
        self._lock = asyncio.Lock()

    async def register(self, job: Job, *, key: str | None = None) -> bool:
        job_key = job.hash if key is None else key
        async with self._lock:
            if job.id in self._jobs or job_key in self._keys:
                return False
            self._jobs[job.id] = StoredJob(job, job_key, JobStatus.QUEUED)
            self._keys[job_key] = job.id
            return True

    async def get(self, job_id: UUID) -> StoredJob:
        async with self._lock:
            try:
                return self._jobs[job_id]
            except KeyError as error:
                raise LookupError(f"job {job_id} does not exist") from error

    async def start(self, job_id: UUID) -> None:
        await self._update(job_id, status=JobStatus.RUNNING, attempts_delta=1)

    async def succeed(self, job_id: UUID) -> None:
        await self._update(job_id, status=JobStatus.SUCCEEDED, error=None)

    async def fail(self, job_id: UUID, error: Exception) -> None:
        await self._update(job_id, status=JobStatus.FAILED, error=str(error))

    async def _update(
        self,
        job_id: UUID,
        *,
        status: JobStatus,
        error: str | None = None,
        attempts_delta: int = 0,
    ) -> None:
        async with self._lock:
            try:
                current = self._jobs[job_id]
            except KeyError as missing:
                raise LookupError(f"job {job_id} does not exist") from missing
            self._jobs[job_id] = replace(
                current,
                status=status,
                attempts=current.attempts + attempts_delta,
                error=error,
            )
