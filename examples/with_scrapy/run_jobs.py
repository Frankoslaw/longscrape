"""Run manually enqueued Scrapy jobs in one asyncio process."""

import asyncio
import os

from longscrape_core import CrawlJob, RecordSink, SourceRecord
from longscrape_scrapy import CrawlService, InMemoryJobQueue


class PrintSink(RecordSink):
    async def save(self, records: tuple[SourceRecord, ...]) -> None:
        for record in records:
            print(record.data)


async def main() -> None:
    os.environ.setdefault("SCRAPY_SETTINGS_MODULE", "with_scrapy.settings")
    queue = InMemoryJobQueue()
    jobs = (
        CrawlJob(
            kind="quotes",
            query={"url": "https://quotes.toscrape.com/page/1/"},
        ),
        CrawlJob(
            kind="books",
            query={"url": "https://books.toscrape.com/"},
        ),
    )
    for job in jobs:
        await queue.enqueue(job)
    print(f"Enqueued {len(jobs)} jobs; waiting for more jobs after the initial crawl.")
    service = CrawlService.from_project(queue, record_sink=PrintSink(), concurrency=2)
    await service.serve()


if __name__ == "__main__":
    asyncio.run(main())
