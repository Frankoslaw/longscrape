from __future__ import annotations

from typing import Any, cast

from itemadapter import ItemAdapter
from longscrape_core import RecordSink, SourceRecord, fingerprint
from scrapy.crawler import Crawler


class RecordSinkPipeline:
    """Send Scrapy items to the configured core ``RecordSink``.

    Configure an application-owned sink instance under
    ``LONGSCRAPE_RECORD_SINK`` and this pipeline under ``ITEM_PIPELINES``.
    The sink is intentionally not serialized into spider arguments: it is a
    process resource shared by all concurrent crawlers.
    """

    def __init__(self, sink: RecordSink, crawler: Crawler | None = None) -> None:
        self.sink = sink
        self.crawler = crawler

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> "RecordSinkPipeline":
        sink = crawler.settings.get("LONGSCRAPE_RECORD_SINK")
        if sink is None or not callable(getattr(sink, "save", None)):
            raise ValueError("LONGSCRAPE_RECORD_SINK must provide async save(records)")
        return cls(cast(RecordSink, sink), crawler)

    async def process_item(self, item: Any) -> Any:
        record = item if isinstance(item, SourceRecord) else self._to_record(item)
        await self.sink.save((record,))
        return item

    def _to_record(self, item: Any) -> SourceRecord:
        if self.crawler is None:
            raise RuntimeError("RecordSinkPipeline requires a Scrapy crawler")
        spider = self.crawler.spider
        if spider is None:
            raise RuntimeError("Cannot persist an item before its spider starts")
        data = dict(ItemAdapter(item).asdict())
        source_url = data.get("source_url")
        if not isinstance(source_url, str) or not source_url:
            raise ValueError("Scrapy items sent to RecordSinkPipeline need source_url")
        kind = type(item).__name__
        return SourceRecord(
            id=fingerprint({"kind": kind, "source_url": source_url, "data": data}),
            kind=kind,
            provider=spider.name,
            source_url=source_url,
            data=data,
        )
