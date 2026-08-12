import asyncio

from longscrape_core import InMemoryJobQueue, InputUrl, Job


def test_queue_is_fifo_and_deduplicates_job_ids() -> None:
    async def check() -> None:
        queue = InMemoryJobQueue()
        first = Job(kind="url", input=InputUrl("https://example.com/one"))
        second = Job(kind="url", input=InputUrl("https://example.com/two"))

        assert await queue.enqueue(first)
        assert not await queue.enqueue(first)
        assert await queue.enqueue(second)
        assert await queue.dequeue("url") == first
        assert await queue.dequeue("url") == second
        assert await queue.dequeue("url") is None

    asyncio.run(check())


def test_queue_claims_only_the_requested_kind() -> None:
    async def check() -> None:
        queue = InMemoryJobQueue()
        quotes = Job(kind="quotes", input=InputUrl("https://example.com/quotes"))
        books = Job(kind="books", input=InputUrl("https://example.com/books"))
        await queue.enqueue(quotes)
        await queue.enqueue(books)

        assert await queue.dequeue("books") == books
        assert await queue.dequeue("books") is None
        assert await queue.dequeue("quotes") == quotes

    asyncio.run(check())
