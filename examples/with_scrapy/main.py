"""Run manually enqueued Scrapy jobs in one asyncio process."""

import asyncio
import os

from longscrape_core import InMemoryJobQueue, InputUrl, Job, Record
from longscrape_scrapy import CrawlService


class PrintStore:
    async def save(self, record: Record) -> None:
        # for record in records:
        #     print(record.data)
        pass


async def monitor_until_idle(
    queue: InMemoryJobQueue, poll_interval: float = 0.1
) -> None:
    """Poll queue stats, log active progress, and notify when the service stalls."""
    print("\n--- Queue State Monitoring Started ---")

    # Brief delay to allow background workers to pick up initial jobs from queue
    await asyncio.sleep(0.1)

    while True:
        stats = queue.stats
        print(
            f"[Queue State] Pending: {stats['pending']} | "
            f"Processing: {stats['processing']} | "
            f"Completed: {stats['completed']} | "
            f"Failed: {stats['failed']}"
        )

        # Stalling condition: no jobs in pending or processing states
        if queue.is_empty():
            print(
                "\n[Idle Alert] Service finished working on all current tasks "
                "and has begun to stall (waiting for new jobs)..."
            )
            print(f"[Final State Stats] {queue.stats}\n")
            break

        await asyncio.sleep(poll_interval)


async def main() -> None:
    os.environ.setdefault("SCRAPY_SETTINGS_MODULE", "with_scrapy.settings")
    queue = InMemoryJobQueue()
    jobs = (
        Job(
            kind="quotes",
            input=InputUrl("https://quotes.toscrape.com/page/1/"),
        ),
        Job(
            kind="books",
            input=InputUrl("https://books.toscrape.com/"),
        ),
    )

    for job in jobs:
        await queue.enqueue(job)

    print(f"Enqueued {len(jobs)} jobs; starting service...")
    service = CrawlService.from_project(queue, record_store=PrintStore(), concurrency=2)

    # Launch service in a background asyncio Task
    serve_task = asyncio.create_task(service.serve(("quotes", "books")))

    try:
        # Monitor progress until all current tasks complete and queue is empty
        await monitor_until_idle(queue, poll_interval=1.0)
    finally:
        # Gracefully halt workers once stalling is detected
        await service.shutdown()
        serve_task.cancel()
        await asyncio.gather(serve_task, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
