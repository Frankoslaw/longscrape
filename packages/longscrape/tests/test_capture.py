import asyncio

import pytest
from longscrape import CaptureScraper, UnknownCaptureKind
from longscrape_core import (
    Document,
    InMemoryDocumentStore,
    InMemoryJobQueue,
    InMemoryRecordStore,
    InputDocument,
    Job,
    Record,
)


class ExampleExtractor:
    async def extract(self, job: Job, document: Document, queue) -> list[Record]:
        return [
            Record(
                kind=job.kind,
                source_url=document.url,
                document=document,
                data={"title": "Example"},
            )
        ]


def test_capture_scraper_routes_to_extractor_and_persists_output() -> None:
    async def check() -> None:
        documents = InMemoryDocumentStore()
        records = InMemoryRecordStore()
        scraper = CaptureScraper(
            {"example": ExampleExtractor()},
            queue=InMemoryJobQueue(),
            document_store=documents,
            record_store=records,
        )
        document = Document(url="https://example.com", content=b"<h1>Example</h1>")
        job = Job(kind="example", input=InputDocument(document))

        assert await scraper.scrape(job) == 1
        assert await documents.get(document.url) is document
        assert records.records("example")[0].data == {"title": "Example"}

    asyncio.run(check())


def test_capture_scraper_rejects_unknown_kind() -> None:
    async def check() -> None:
        scraper = CaptureScraper(
            {},
            queue=InMemoryJobQueue(),
            document_store=InMemoryDocumentStore(),
            record_store=InMemoryRecordStore(),
        )
        job = Job(
            kind="missing",
            input=InputDocument(Document(url="https://example.com", content=b"")),
        )
        with pytest.raises(UnknownCaptureKind, match="missing"):
            await scraper.scrape(job)

    asyncio.run(check())
