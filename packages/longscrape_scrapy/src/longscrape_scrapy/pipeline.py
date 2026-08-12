from __future__ import annotations

from typing import Any, cast

import scrapy
from itemadapter import ItemAdapter
from longscrape_core import Job, Record, RecordStore, Transformer
from scrapy.crawler import Crawler

from longscrape_scrapy.spider import JobSpider


class LongscrapePipeline:
    """Convert native Scrapy items to records and persist transformed output."""

    def __init__(self, store: RecordStore, transformers: list[Transformer]) -> None:
        self.store = store
        self.transformers = transformers

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> "LongscrapePipeline":
        store = crawler.settings.get("LONGSCRAPE_RECORD_STORE")
        if store is None or not callable(getattr(store, "save", None)):
            raise ValueError("LONGSCRAPE_RECORD_STORE must provide async save(record)")
        transformers = crawler.settings.get("LONGSCRAPE_TRANSFORMERS", [])
        return cls(cast(RecordStore, store), list(transformers))

    async def process_item(self, item: Any, spider: scrapy.Spider) -> Any:
        if not isinstance(spider, JobSpider) or spider.job is None:
            return item
        records = [self._to_record(item, spider, spider.job)]
        for transformer in self.transformers:
            records = [
                output
                for record in records
                for output in await transformer.transform(spider.job, record)
            ]
        for record in records:
            await self.store.save(record)
        return item

    @staticmethod
    def _to_record(item: Any, spider: JobSpider, job: Job) -> Record:
        data = dict(ItemAdapter(item).asdict())
        source_url = data.pop("source_url", None)
        if not isinstance(source_url, str) or not source_url:
            raise ValueError("LongscrapePipeline items need a non-empty source_url")
        return Record(
            kind=getattr(spider, "record_kind", None) or spider.name,
            source_url=source_url,
            data=data,
            metadata={"producer": f"scrapy:{spider.name}", "job_id": str(job.id)},
        )
