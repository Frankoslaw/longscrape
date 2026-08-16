import asyncio

from longscrape.runtime import InMemoryJobQueue
from longscrape_core import InputUrl, JobRequest


def test_queue_wakes_waiting_consumer() -> None:
    async def run() -> None:
        queue = InMemoryJobQueue()
        waiter = asyncio.create_task(queue.get())
        await asyncio.sleep(0)

        request = JobRequest(kind="fetch", input=InputUrl("https://example.com"))
        await queue.submit(request)

        job = await asyncio.wait_for(waiter, timeout=0.1)
        assert job.kind == request.kind
        assert job.input == request.input

    asyncio.run(run())
