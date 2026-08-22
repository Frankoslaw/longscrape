from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator
from typing import Any

from longscrape import Job, PipelineContext, Record, Sink
from scrapy.exceptions import DropItem

from longscrape_scrapy.items import item_from_record, record_from_item


class PipelineCardinalityError(RuntimeError):
    """A core stage did not satisfy Scrapy's one-item pipeline contract."""


class LongscrapeTransformerPipeline:
    """Adapt one-item Scrapy pipeline calls to a core record transformer.

    Subclasses implement ``transform`` over the familiar longscrape record
    stream.  This class consistently handles token filtering, item conversion,
    and Scrapy's zero-or-one output requirement.
    """

    token_only = True

    def __init__(self, crawler) -> None:
        self._crawler = crawler

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def transform(
        self,
        records: AsyncIterable[Record[Any]],
        job: Job,
        context: PipelineContext | None = None,
    ) -> AsyncIterable[Record[Any]]:
        raise NotImplementedError

    async def process_item(self, item: Any) -> Any:
        spider = self._crawler.spider
        record = record_from_item(item, token_only=self.token_only)
        if record is None:
            return item

        async def one_record() -> AsyncIterator[Record[Any]]:
            yield record

        transformed = aiter(self.transform(one_record(), spider.job, spider.context))
        try:
            output = await anext(transformed)
        except StopAsyncIteration as error:
            raise DropItem("longscrape transformer emitted no record") from error
        try:
            await anext(transformed)
        except StopAsyncIteration:
            return item_from_record(output)
        raise PipelineCardinalityError(
            "Scrapy transformers must emit at most one record per input item"
        )


class LongscrapeSinkPipeline(Sink[Any]):
    """Adapt a terminal record stream operation to a Scrapy item pipeline.

    Subclasses implement ``sink`` and may use a ``RecordSink`` internally or
    perform additional record-level work.
    """

    token_only = True

    def __init__(self, crawler) -> None:
        self._crawler = crawler

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    async def sink(
        self,
        records: AsyncIterable[Record[Any]],
        job: Job,
        context: PipelineContext | None = None,
    ) -> None:
        raise NotImplementedError

    async def process_item(self, item: Any) -> Any:
        spider = self._crawler.spider
        record = record_from_item(item, token_only=self.token_only)
        if record is None:
            return item

        async def one_record() -> AsyncIterator[Record[Any]]:
            yield record

        await self.sink(one_record(), spider.job, spider.context)
        return item
