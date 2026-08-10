from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from longscrape_core.models import (
    CapturedDocument,
    CrawlJob,
    Extraction,
    FetchRequest,
    SourceRecord,
)


class Fetcher(Protocol):
    """Acquires a document from a framework-neutral fetch request."""

    async def fetch(self, request: FetchRequest) -> CapturedDocument: ...


class Extractor(Protocol):
    """Turns one captured document into records and optional follow-up jobs."""

    def extract(
        self,
        job: CrawlJob,
        document: CapturedDocument,
    ) -> Extraction: ...


class RecordSink(Protocol):
    """Persists or consumes source records."""

    async def save(self, records: Sequence[SourceRecord]) -> None: ...


class JobQueue(Protocol):
    """Minimal external job queue contract."""

    async def enqueue(self, job: CrawlJob) -> bool: ...

    async def dequeue(self) -> CrawlJob | None: ...
