import asyncio

from longscrape_core import CrawlJob
from longscrape_scrapy import InMemoryJobQueue


def test_queue_is_fifo_and_deduplicates_pending_jobs() -> None:
    async def check() -> None:
        queue = InMemoryJobQueue()
        first = CrawlJob(kind="url", query={"url": "https://example.com/one"})
        duplicate = CrawlJob(kind="url", query={"url": "https://example.com/one"})
        second = CrawlJob(kind="url", query={"url": "https://example.com/two"})

        assert await queue.enqueue(first)
        assert not await queue.enqueue(duplicate)
        assert await queue.enqueue(second)
        assert await queue.dequeue() == first
        assert await queue.dequeue() == second
        assert await queue.dequeue() is None

    asyncio.run(check())
