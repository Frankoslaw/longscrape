from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from longscrape_core.models import Document, Job, Record


class JobQueue(Protocol):
    """Queue whose consumers explicitly claim only a supported job kind."""

    async def enqueue(self, job: Job) -> bool: ...

    async def dequeue(self, kind: str) -> Job | None: ...

    async def mark_completed(self, job: Job) -> None: ...

    async def mark_failed(self, job: Job, error: Exception) -> None: ...


class DocumentStore(Protocol):
    async def save(self, document: Document) -> None: ...

    async def get(self, key: str) -> Document | None: ...


class RecordStore(Protocol):
    async def save(self, record: Record) -> None: ...


class Fetcher(Protocol):
    """Acquires a document from a job whose input it understands."""

    async def fetch(self, job: Job) -> Document: ...


class Extractor(Protocol):
    """Turns a document into records and may enqueue discovered jobs."""

    async def extract(
        self,
        job: Job,
        document: Document,
        queue: JobQueue,
    ) -> Iterable[Record]: ...


class Transformer(Protocol):
    """Maps one record to zero or more records."""

    async def transform(self, job: Job, record: Record) -> Iterable[Record]: ...
