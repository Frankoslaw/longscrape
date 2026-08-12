import asyncio
from typing import cast

import scrapy
from longscrape_core import InMemoryJobQueue, InputUrl, Job, Record
from longscrape_scrapy import (
    CrawlService,
    JobSpider,
    LongscrapePipeline,
)
from scrapy.crawler import AsyncCrawlerRunner
from scrapy.settings import Settings


class ExampleSpider(JobSpider):
    name = "example"


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[FakeCrawler, Job]] = []

    def create_crawler(self, spider_name: str) -> "FakeCrawler":
        assert spider_name == ExampleSpider.name
        return FakeCrawler()

    async def crawl(self, crawler: "FakeCrawler", *, job: Job) -> None:
        self.calls.append((crawler, job))


class FakeCrawler:
    spidercls = ExampleSpider

    class signals:
        @staticmethod
        def connect(*_: object, **__: object) -> None:
            pass


class FakeStore:
    def __init__(self) -> None:
        self.records: list[Record] = []

    async def save(self, record: Record) -> None:
        self.records.append(record)


def test_service_runs_a_job_with_the_project_spider() -> None:
    async def check() -> None:
        queue = InMemoryJobQueue()
        job = Job(kind="example", input=InputUrl("https://example.com"))
        assert await queue.enqueue(job)
        runner = FakeRunner()
        service = CrawlService(queue, cast(AsyncCrawlerRunner, runner))

        assert await service.run_once("example")
        assert len(runner.calls) == 1
        assert runner.calls[0][0].spidercls is ExampleSpider
        assert runner.calls[0][1] == job
        assert not await service.run_once("example")

    asyncio.run(check())


def test_from_project_preserves_pipelines_and_adds_longscrape_pipeline() -> None:
    settings = Settings(
        {
            "ITEM_PIPELINES": {"example.ProjectPipeline": 100},
            "TWISTED_REACTOR_ENABLED": False,
        }
    )
    store = FakeStore()
    service = CrawlService.from_project(
        InMemoryJobQueue(), settings=settings, record_store=store
    )

    assert service.runner.settings.getdict("ITEM_PIPELINES") == {
        "example.ProjectPipeline": 100,
        "longscrape_scrapy.pipeline.LongscrapePipeline": 300,
    }
    assert service.runner.settings.get("LONGSCRAPE_RECORD_STORE") is store


def test_longscrape_pipeline_converts_native_scrapy_items() -> None:
    class ExampleItem(scrapy.Item):
        title = scrapy.Field()
        source_url = scrapy.Field()

    async def check() -> None:
        store = FakeStore()
        pipeline = LongscrapePipeline(store, [])
        job = Job(kind="example", input=InputUrl("https://x"))
        spider = ExampleSpider(job=job)
        item = ExampleItem(title="Example", source_url="https://example.com")

        assert await pipeline.process_item(item, spider) is item
        assert len(store.records) == 1
        record = store.records[0]
        assert record.kind == "example"
        assert record.source_url == "https://example.com"
        assert record.data == {"title": "Example"}
        assert record.metadata == {
            "producer": "scrapy:example",
            "job_id": str(job.id),
        }

    asyncio.run(check())
