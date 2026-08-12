from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence

from longscrape_core import (
    DocumentStore,
    Extractor,
    InputDocument,
    Job,
    JobQueue,
    Record,
    RecordStore,
    Transformer,
)


class UnknownCaptureKind(ValueError):
    """Raised when no extractor was registered for a browser capture kind."""


class CaptureScraper:
    """Extract and persist browser-captured documents by job kind.

    This is a direct composition helper for FastAPI/browser-extension capture
    flows. It does not fetch documents, manage a queue, or run background
    workers.
    """

    def __init__(
        self,
        extractors: Mapping[str, Extractor],
        *,
        queue: JobQueue,
        document_store: DocumentStore,
        record_store: RecordStore,
        transformers: Sequence[Transformer] = (),
        on_record: Callable[[Record], Awaitable[None]] | None = None,
    ) -> None:
        self.extractors = dict(extractors)
        self.queue = queue
        self.document_store = document_store
        self.record_store = record_store
        self.transformers = tuple(transformers)
        self.on_record = on_record

    async def scrape(self, job: Job) -> int:
        if not isinstance(job.input, InputDocument):
            raise TypeError("CaptureScraper requires Job.input to be InputDocument")
        try:
            extractor = self.extractors[job.kind]
        except KeyError as error:
            raise UnknownCaptureKind(
                f"No extractor registered for {job.kind!r}"
            ) from error

        document = job.input.document
        await self.document_store.save(document)
        count = 0
        for extracted in await extractor.extract(job, document, self.queue):
            records = [extracted]
            for transformer in self.transformers:
                records = [
                    output
                    for record in records
                    for output in await transformer.transform(job, record)
                ]
            for record in records:
                await self.record_store.save(record)
                if self.on_record is not None:
                    await self.on_record(record)
                count += 1
        return count
