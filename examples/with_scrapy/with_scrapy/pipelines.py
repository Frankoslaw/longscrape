"""Project pipelines run before longscrape_scrapy.LongscrapePipeline."""

from typing import Any

import scrapy.signals
from longscrape.mongodb import PyMongoRecordStore
from longscrape_scrapy import JobSpider, LongscrapeDocumentItem, LongscrapePipeline
from parsel import Selector
from scrapy.crawler import Crawler


class DocumentTitlePipeline:
    """Extract from native items emitted by UrlCrawler without changing its spider.

    This is the longscrape-style option: UrlCrawler only fetches, while the
    pipeline turns its attached document item into application data. Core types
    are converted only by LongscrapePipeline, after this pipeline completes.
    """

    def process_item(self, item: Any) -> Any:
        if not isinstance(item, LongscrapeDocumentItem):
            return item
        title = Selector(text=item["document"].text).css("title::text").get()
        if title is None:
            return item
        item["data"] = {**item.get("data", {}), "title": title.strip()}
        return item


class UrlAuditPipeline:
    """Show the initial URL and every URL seen by a JobSpider."""

    def __init__(self) -> None:
        self.crawler: Crawler | None = None

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> "UrlAuditPipeline":
        pipeline = cls()
        pipeline.crawler = crawler
        return pipeline

    def process_item(self, item: Any) -> Any:
        if self.crawler is None:
            return item
        spider = self.crawler.spider
        if not isinstance(spider, JobSpider):
            return item
        spider.logger.info(
            "longscrape URLs: initial=%s seen=%s",
            spider.initial_url,
            spider.urls,
        )
        return item


class MongoRecordPipeline(LongscrapePipeline):
    """Convert the final native item to a record and persist it to MongoDB.

    The priority in ``settings.py`` places this wrapper after project item
    normalization, so ordinary Scrapy pipelines never need core record types.
    """

    def __init__(self, store: PyMongoRecordStore) -> None:
        super().__init__(store)
        self.store = store

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> "MongoRecordPipeline":
        uri = crawler.settings.get(
            "LONGSCRAPE_MONGODB_URI", "mongodb://localhost:27017"
        )
        pipeline = cls(PyMongoRecordStore(uri))
        pipeline.crawler = crawler
        crawler.signals.connect(pipeline.close, signal=scrapy.signals.spider_closed)
        return pipeline

    async def close(self, spider: Any) -> None:
        await self.store.close()
