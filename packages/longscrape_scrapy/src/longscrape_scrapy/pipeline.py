from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from typing import Any, Protocol, cast

from itemadapter import ItemAdapter
from longscrape_core import Job, JsonValue, Record, RecordRef, RecordStore, Transformer
from scrapy.crawler import Crawler

from longscrape_scrapy.items import LongscrapeDocumentItem, LongscrapeRecordItem
from longscrape_scrapy.spider import JobSpider

logger = logging.getLogger(__name__)


class ItemExtractor(Protocol):
    """Adapt one Scrapy item into zero or more core records."""

    async def extract(
        self, item: Any, spider: JobSpider, job: Job
    ) -> Iterable[Record]: ...


class RecordSink(Protocol):
    """Accept core records emitted by a Scrapy item pipeline."""

    async def save(self, record: Record) -> RecordRef: ...


class ScrapyItemExtractor:
    """Convert native Scrapy items to core :class:`~longscrape_core.Record`s."""

    async def extract(self, item: Any, spider: JobSpider, job: Job) -> Iterable[Record]:
        metadata: dict[str, JsonValue] = {
            "producer": f"scrapy:{spider.name}",
            "job_id": str(job.id),
        }
        if isinstance(item, LongscrapeDocumentItem):
            return [
                item.to_record(
                    kind=getattr(spider, "record_kind", None) or spider.name,
                    metadata=metadata,
                )
            ]
        if isinstance(item, LongscrapeRecordItem):
            return [item.to_record()]
        data = dict(ItemAdapter(item).asdict())
        source_url = data.pop("source_url", None)
        if not isinstance(source_url, str) or not source_url:
            raise ValueError("LongscrapePipeline items need a non-empty source_url")
        return [
            Record(
                kind=getattr(spider, "record_kind", None) or spider.name,
                source_url=source_url,
                data=data,
                metadata=metadata,
            )
        ]


class RecordStoreSink:
    """Expose a core :class:`~longscrape_core.RecordStore` as a pipeline sink."""

    def __init__(self, store: RecordStore) -> None:
        self.store = store

    async def save(self, record: Record) -> RecordRef:
        return await self.store.save(record)


class LongscrapePipeline:
    """Extract core records from Scrapy items and send them to a record sink.

    By default, :class:`ScrapyItemExtractor` converts native items and
    :class:`RecordStoreSink` persists the resulting records.  Applications can
    replace either adapter to use their standalone extraction or sink logic in
    Scrapy's pipeline lifecycle.
    """

    def __init__(
        self,
        store: RecordStore | None = None,
        transformers: Sequence[Transformer] = (),
        *,
        extractor: ItemExtractor | None = None,
        sink: RecordSink | None = None,
        spider: JobSpider | None = None,
    ) -> None:
        if store is not None and sink is not None:
            raise ValueError("Pass either store or sink, not both")
        if store is None and sink is None:
            raise ValueError("LongscrapePipeline needs a store or sink")
        self.extractor = extractor or ScrapyItemExtractor()
        self.sink = sink or RecordStoreSink(cast(RecordStore, store))
        self.transformers = tuple(transformers)
        self.spider = spider
        self.crawler: Crawler | None = None

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> "LongscrapePipeline":
        store = crawler.settings.get("LONGSCRAPE_RECORD_STORE")
        sink = crawler.settings.get("LONGSCRAPE_RECORD_SINK")
        if sink is None and (
            store is None or not callable(getattr(store, "save", None))
        ):
            raise ValueError(
                "LONGSCRAPE_RECORD_STORE must provide async save(record), "
                "or set LONGSCRAPE_RECORD_SINK"
            )
        if sink is not None and not callable(getattr(sink, "save", None)):
            raise ValueError("LONGSCRAPE_RECORD_SINK must provide async save(record)")
        extractor = crawler.settings.get("LONGSCRAPE_ITEM_EXTRACTOR")
        if extractor is not None and not callable(getattr(extractor, "extract", None)):
            raise ValueError(
                "LONGSCRAPE_ITEM_EXTRACTOR must provide async "
                "extract(item, spider, job)"
            )
        transformers = crawler.settings.get("LONGSCRAPE_TRANSFORMERS", [])
        pipeline = cls(
            cast(RecordStore | None, store),
            list(transformers),
            extractor=cast(ItemExtractor | None, extractor),
            sink=cast(RecordSink | None, sink),
        )
        pipeline.crawler = crawler
        return pipeline

    async def process_item(self, item: Any) -> Any:
        spider = self.spider or (self.crawler.spider if self.crawler else None)
        if not isinstance(spider, JobSpider) or spider.job is None:
            return item
        records = list(await self.extractor.extract(item, spider, spider.job))
        for transformer in self.transformers:
            records = [
                output
                for record in records
                for output in await transformer.transform(spider.job, record)
            ]
        for record in records:
            ref = await self.sink.save(record)
            logger.info("Persisted record %s (%s)", ref, record.kind)
        return item
