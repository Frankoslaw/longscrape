import asyncio
from typing import cast

import scrapy
from longscrape_core import CrawlJob, RecordSink, SourceRecord
from longscrape_scrapy import (
    CrawlService,
    InMemoryJobQueue,
    JobSpider,
    RecordSinkPipeline,
)
from scrapy.crawler import AsyncCrawlerRunner, Crawler
from scrapy.settings import Settings


class ExampleSpider(JobSpider):
    name = "example"


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[FakeCrawler, CrawlJob]] = []

    def create_crawler(self, spider_name: str) -> "FakeCrawler":
        assert spider_name == ExampleSpider.name
        return FakeCrawler()

    async def crawl(self, crawler: "FakeCrawler", *, job: CrawlJob) -> None:
        self.calls.append((crawler, job))


class FakeCrawler:
    spidercls = ExampleSpider


class FakePipelineCrawler:
    class spider:
        name = "example"


class FakeSink:
    def __init__(self) -> None:
        self.records = []

    async def save(self, records: object) -> None:
        self.records.append(records)


def test_service_runs_a_job_with_the_project_spider() -> None:
    async def check() -> None:
        queue = InMemoryJobQueue()
        job = CrawlJob(kind="example", query={"url": "https://example.com"})
        assert await queue.enqueue(job)
        runner = FakeRunner()
        service = CrawlService(
            queue,
            cast(AsyncCrawlerRunner, runner),
        )

        assert await service.run_once()
        assert len(runner.calls) == 1
        assert runner.calls[0][0].spidercls is ExampleSpider
        assert runner.calls[0][1] == job
        assert not await service.run_once()

    asyncio.run(check())


def test_from_project_preserves_pipelines_and_adds_record_sink() -> None:
    settings = Settings(
        {
            "ITEM_PIPELINES": {"example.ProjectPipeline": 100},
            "TWISTED_REACTOR_ENABLED": False,
        }
    )
    sink = FakeSink()
    service = CrawlService.from_project(
        InMemoryJobQueue(), settings=settings, record_sink=cast(RecordSink, sink)
    )

    assert service.runner.settings.getdict("ITEM_PIPELINES") == {
        "example.ProjectPipeline": 100,
        "longscrape_scrapy.pipeline.RecordSinkPipeline": 300,
    }
    assert service.runner.settings.get("LONGSCRAPE_RECORD_SINK") is sink


def test_record_sink_pipeline_saves_source_records() -> None:

    async def check() -> None:
        sink = FakeSink()
        record = SourceRecord(
            id="record-1",
            kind="example",
            provider="test",
            source_url="https://example.com",
            data={},
        )
        pipeline = RecordSinkPipeline(cast(RecordSink, sink))
        assert await pipeline.process_item(record) == record
        assert sink.records == [(record,)]

    asyncio.run(check())


def test_record_sink_pipeline_converts_scrapy_items() -> None:
    class ExampleItem(scrapy.Item):
        title = scrapy.Field()
        source_url = scrapy.Field()

    async def check() -> None:
        sink = FakeSink()
        pipeline = RecordSinkPipeline(
            cast(RecordSink, sink), cast(Crawler, FakePipelineCrawler())
        )
        item = ExampleItem(title="Example", source_url="https://example.com")

        assert await pipeline.process_item(item) is item
        record = sink.records[0][0]
        assert record.kind == "ExampleItem"
        assert record.provider == "example"
        assert record.data == dict(item)

    asyncio.run(check())
