import asyncio
from collections.abc import AsyncIterable, AsyncIterator

import pytest
from longscrape import Document, InputUrl, Job, PipelineContext, Record
from longscrape_scrapy import (
    LongscrapeSinkPipeline,
    LongscrapeSpider,
    ScrapyJobRunner,
)
from longscrape_scrapy.http import document_to_response
from scrapy import Request
from scrapy.settings import Settings

seen: list[Record] = []


class OneDocumentFetcher:
    async def fetch(
        self, job: Job, context: PipelineContext | None = None
    ) -> AsyncIterator[Document]:
        yield Document("https://example.test/", b"<h1>Example</h1>")


class OneRecordExtractor:
    async def extract(self, documents, job, context=None):
        async for document in documents:
            yield Record("example", {"url": document.url})


class RecordingSinkPipeline(LongscrapeSinkPipeline):
    async def sink(
        self,
        records: AsyncIterable[Record],
        job: Job,
        context: PipelineContext | None = None,
    ) -> None:
        async for record in records:
            seen.append(record)


class ExampleSpider(LongscrapeSpider):
    name = "longscrape-example"
    fetcher = OneDocumentFetcher()
    extractor = OneRecordExtractor()


def test_runner_uses_spider_helpers_and_project_pipeline() -> None:
    seen.clear()

    async def run() -> None:
        runner = ScrapyJobRunner(
            Settings(
                {
                    "LOG_ENABLED": False,
                    "TWISTED_REACTOR_ENABLED": False,
                    "ITEM_PIPELINES": {
                        "test_integration.RecordingSinkPipeline": 100,
                    },
                }
            )
        )
        await runner.run(
            ExampleSpider,
            Job("example", InputUrl("https://example.test/")),
            PipelineContext(),
        )

    asyncio.run(run())

    assert [record.data for record in seen] == [{"url": "https://example.test/"}]


def test_runner_warns_before_disabling_the_twisted_reactor() -> None:
    with pytest.warns(RuntimeWarning, match="TWISTED_REACTOR_ENABLED=False"):
        runner = ScrapyJobRunner(Settings({"TWISTED_REACTOR_ENABLED": True}))

    assert not runner._settings.getbool("TWISTED_REACTOR_ENABLED")


def test_document_response_strips_decoded_compression_headers() -> None:
    response = document_to_response(
        Document(
            "https://example.test/",
            b"decoded body",
            headers={"content-encoding": "br", "content-length": "2"},
        ),
        Request("longscrape://fetch"),
    )

    assert b"content-encoding" not in response.headers
    assert b"content-length" not in response.headers
    assert response.body == b"decoded body"
