from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta
from typing import Protocol

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


class JobStore(Protocol):
    async def save(self, job: Job) -> JobRef: ...
    async def get(self, ref: JobRef) -> Job | None: ...
    async def get_status(self, ref: JobRef) -> JobStatus | None: ...
    async def set_status(
        self,
        ref: JobRef,
        state: JobState,
        *,
        retry_count: int | None = None,
        error: str | None = None,
    ) -> JobStatus: ...


class JobSubmitter(Protocol):
    """Narrow dependency exposed to extractors for discovered work."""

    async def submit(self, job: Job) -> JobRef: ...


class JobQueue(Protocol):
    async def enqueue(self, ref: JobRef, *, kind: str) -> bool: ...
    async def lease(
        self, kind: str, *, duration: timedelta | None = None
    ) -> JobLease | None: ...
    async def acknowledge(self, lease: JobLease) -> None: ...
    async def retry(self, lease: JobLease) -> None: ...
    async def extend(self, lease: JobLease, *, duration: timedelta) -> JobLease: ...


class JobLease(Protocol):
    @property
    def ref(self) -> JobRef: ...


class DocumentStore(Protocol):
    async def save(self, document: Document) -> DocumentRef: ...
    async def get(self, ref: DocumentRef) -> Document | None: ...


class RecordStore(Protocol):
    async def save(self, record: Record) -> RecordRef: ...
    async def get(self, ref: RecordRef) -> Record | None: ...


class Fetcher(Protocol):
    async def fetch(self, job: Job) -> Document: ...


class Extractor(Protocol):
    async def extract(
        self, job: Job, document: Document, queue: JobSubmitter
    ) -> Iterable[Record]: ...


class Transformer(Protocol):
    async def transform(self, job: Job, record: Record) -> Iterable[Record]: ...
