from collections.abc import AsyncIterable

import structlog
from longscrape import Job, PipelineContext, Record
from longscrape.stores import InMemoryRecordStore
from longscrape_scrapy import (
    LongscrapeSinkPipeline,
    LongscrapeTransformerPipeline,
)

logger = structlog.get_logger()


class AddJobIdPipeline(LongscrapeTransformerPipeline):
    async def transform(
        self,
        records: AsyncIterable[Record],
        job: Job,
        context: PipelineContext | None = None,
    ) -> AsyncIterable[Record]:
        async for record in records:
            yield Record(
                record.kind,
                {**record.data, "job_id": str(job.id)},
                created_at=record.created_at,
            )


record_store = InMemoryRecordStore()


class StoreLongscrapeRecordPipeline(LongscrapeSinkPipeline):
    async def sink(
        self,
        records: AsyncIterable[Record],
        job: Job,
        context: PipelineContext | None = None,
    ) -> None:
        async for record in records:
            await record_store.put(record)


class PrettyPrintQuotesPipeline:
    def process_item(self, item):
        """Pretty-prints scraped quote items to the terminal using structlog."""
        logger.info(
            "quote_scraped",
            author=item.get("author_name"),
            quote=item.get("quote_content"),
            tags=item.get("tags", []),
            birthday=item.get("author_birthday"),
            born_location=item.get("author_bornlocation"),
        )
        return item
