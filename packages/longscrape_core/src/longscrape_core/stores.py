from __future__ import annotations

from longscrape_core.models import (
    Document,
    DocumentRef,
    Job,
    JobRef,
    JobState,
    JobStatus,
    Record,
    RecordRef,
)


class InMemoryJobStore:
    """Process-local job persistence, deliberately independent of queueing."""

    def __init__(self) -> None:
        self._jobs: dict[JobRef, Job] = {}
        self._statuses: dict[JobRef, JobStatus] = {}

    async def save(self, job: Job) -> JobRef:
        if job.id in self._jobs:
            return job.id
        self._jobs[job.id] = job
        self._statuses[job.id] = JobStatus(job.id, JobState.PENDING)
        return job.id

    async def get(self, ref: JobRef) -> Job | None:
        return self._jobs.get(ref)

    async def get_status(self, ref: JobRef) -> JobStatus | None:
        return self._statuses.get(ref)

    async def set_status(
        self,
        ref: JobRef,
        state: JobState,
        *,
        retry_count: int | None = None,
        error: str | None = None,
    ) -> JobStatus:
        previous = self._statuses.get(ref)
        if previous is None:
            raise KeyError(f"Unknown job ref: {ref}")
        status = JobStatus(
            ref=ref,
            state=state,
            retry_count=previous.retry_count if retry_count is None else retry_count,
            error=error,
        )
        self._statuses[ref] = status
        return status


class InMemoryDocumentStore:
    """Process-local document store returning an opaque reference on save."""

    def __init__(self) -> None:
        self._documents: dict[DocumentRef, Document] = {}

    async def save(self, document: Document) -> DocumentRef:
        ref = DocumentRef(document.url)
        self._documents[ref] = document
        return ref

    async def get(self, ref: DocumentRef) -> Document | None:
        return self._documents.get(ref)


class InMemoryRecordStore:
    """Process-local record store returning an opaque reference on save."""

    def __init__(self) -> None:
        self._records: dict[RecordRef, Record] = {}
        self._by_kind: dict[str, list[RecordRef]] = {}

    async def save(self, record: Record) -> RecordRef:
        ref = RecordRef()
        self._records[ref] = record
        self._by_kind.setdefault(record.kind, []).append(ref)
        return ref

    async def get(self, ref: RecordRef) -> Record | None:
        return self._records.get(ref)

    def records(self, kind: str | None = None) -> tuple[Record, ...]:
        refs = self._by_kind.get(kind, ()) if kind is not None else self._records
        return tuple(self._records[ref] for ref in refs)
