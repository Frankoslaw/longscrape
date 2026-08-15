"""Project pipelines run before longscrape_scrapy.LongscrapePipeline."""

from typing import Any

from longscrape_core import RecordStore
from longscrape_scrapy import JobSpider, LongscrapeDocumentItem, LongscrapePipeline
from longscrape_scrapy.runtime import resolve
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


class RecordStorePipeline(LongscrapePipeline):
    """Convert the final native item to a record and persist it via core storage.

    The priority in ``settings.py`` places this wrapper after project item
    normalization, so ordinary Scrapy pipelines never need core record types.
    """

    def __init__(self, store: RecordStore) -> None:
        super().__init__(store)
        self.store = store

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> "RecordStorePipeline":
        store_key = crawler.settings.get("LONGSCRAPE_RECORD_STORE_KEY")
        if store_key is None:
            raise ValueError("LONGSCRAPE_RECORD_STORE_KEY must be configured")
        store = resolve(store_key)
        pipeline = cls(store)
        pipeline.crawler = crawler
        return pipeline
