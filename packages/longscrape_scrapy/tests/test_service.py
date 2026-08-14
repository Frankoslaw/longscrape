import asyncio
from typing import cast

import scrapy
from longscrape_core import (
    Document,
    InMemoryJobQueue,
    InputDocument,
    InputQuery,
    InputUrl,
    Job,
    Record,
)
from longscrape_scrapy import (
    CrawlService,
    IdentityCrawler,
    JobSpider,
    LongscrapeDocumentItem,
    LongscrapePipeline,
    LongscrapeRecordItem,
    RecordStoreSink,
    UrlCrawler,
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


def test_from_project_preserves_project_pipelines() -> None:
    settings = Settings(
        {
            "ITEM_PIPELINES": {"example.ProjectPipeline": 100},
            "TWISTED_REACTOR_ENABLED": False,
        }
    )
    service = CrawlService.from_project(InMemoryJobQueue(), settings=settings)

    assert service.runner.settings.getdict("ITEM_PIPELINES") == {
        "example.ProjectPipeline": 100
    }


def test_longscrape_pipeline_converts_native_scrapy_items() -> None:
    class ExampleItem(scrapy.Item):
        title = scrapy.Field()
        source_url = scrapy.Field()

    async def check() -> None:
        store = FakeStore()
        job = Job(kind="example", input=InputUrl("https://x"))
        spider = ExampleSpider(job=job)
        pipeline = LongscrapePipeline(store, [], spider=spider)
        item = ExampleItem(title="Example", source_url="https://example.com")

        assert await pipeline.process_item(item) is item
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


def test_longscrape_pipeline_accepts_custom_extractor_and_sink() -> None:
    class CustomExtractor:
        async def extract(self, item, spider, job) -> list[Record]:
            return [
                Record(
                    kind="custom",
                    source_url=item["url"],
                    data={"job_kind": job.kind},
                )
            ]

    async def check() -> None:
        store = FakeStore()
        job = Job(kind="example", input=InputUrl("https://x"))
        pipeline = LongscrapePipeline(
            transformers=[],
            extractor=CustomExtractor(),
            sink=RecordStoreSink(store),
            spider=ExampleSpider(job=job),
        )

        item = {"url": "https://example.com"}
        assert await pipeline.process_item(item) is item
        assert len(store.records) == 1
        record = store.records[0]
        assert record.kind == "custom"
        assert record.source_url == "https://example.com"
        assert record.data == {"job_kind": "example"}

    asyncio.run(check())


def test_document_job_calls_parse_with_an_in_memory_response_and_tracks_urls() -> None:
    class DocumentSpider(JobSpider):
        name = "document"

        def parse(self, response):
            yield {"title": response.css("title::text").get()}

    async def check() -> None:
        document = Document(
            url="https://example.com/source", content=b"<title>Example</title>"
        )
        spider = DocumentSpider(job=Job(kind="document", input=InputDocument(document)))

        assert [item async for item in spider.start()] == [{"title": "Example"}]
        assert spider.initial_url == document.url
        assert spider.urls == [document.url]

    asyncio.run(check())


def test_basic_crawlers_return_native_scrapy_items() -> None:
    async def check() -> None:
        document = Document(url="https://example.com", content=b"body")
        document_job = Job(kind="identity", input=InputDocument(document))
        identity = IdentityCrawler(job=document_job)
        items = [item async for item in identity.start_job()]
        assert len(items) == 1
        assert isinstance(items[0], LongscrapeDocumentItem)
        assert items[0]["document"] is document
        assert items[0]["data"] == {}
        started_items = [item async for item in identity.start()]
        assert len(started_items) == 1
        assert started_items[0]["document"] is document

        query_job = Job(kind="identity", input=InputQuery({"name": "Example"}))
        query = IdentityCrawler(job=query_job)
        items = [item async for item in query.start_job()]
        assert isinstance(items[0], LongscrapeRecordItem)
        assert items[0]["data"] == {"name": "Example"}
        assert items[0]["source_url"] == f"longscrape://job/{query_job.id}"

        crawler = UrlCrawler(job=Job(kind="url", input=InputUrl(document.url)))
        request = anext(crawler.start_job())
        assert (await request).url == document.url

    asyncio.run(check())


def test_longscrape_record_item_round_trips_at_the_pipeline_boundary() -> None:
    async def check() -> None:
        store = FakeStore()
        job = Job(kind="example", input=InputQuery())
        pipeline = LongscrapePipeline(store, spider=ExampleSpider(job=job))
        record = Record(kind="example", source_url="longscrape://example", data={})
        item = LongscrapeRecordItem.from_record(record)

        assert await pipeline.process_item(item) is item
        assert store.records == [record]

    asyncio.run(check())
