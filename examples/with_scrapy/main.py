"""Run manually enqueued Scrapy jobs in one asyncio process."""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import ExampleStores, create_stores
from longscrape_core import (
    Document,
    InputDocument,
    InputQuery,
    InputUrl,
    Job,
)
from longscrape_scrapy import CrawlService
from longscrape_scrapy.runtime import discard, register
from scrapy.utils.project import get_project_settings


async def monitor_until_idle(stores: ExampleStores, poll_interval: float = 0.1) -> None:
    """Poll queue stats, log active progress, and notify when the service stalls."""
    print("\n--- Queue State Monitoring Started ---")

    # Brief delay to allow background workers to pick up initial jobs from queue
    await asyncio.sleep(0.1)

    while True:
        # Stalling condition: no jobs in pending or processing states
        if await stores.is_idle():
            print(
                "\n[Idle Alert] Service finished working on all current tasks "
                "and has begun to stall (waiting for new jobs)..."
            )
            print("[Idle Alert] No pending or leased jobs remain.\n")
            break

        await asyncio.sleep(poll_interval)


async def main() -> None:
    os.environ.setdefault("SCRAPY_SETTINGS_MODULE", "with_scrapy.settings")
    stores = create_stores()
    captured_ref = await stores.documents.save(
        Document(
            url="https://example.test/captured",
            content=b"<title>Captured without a request</title>",
        )
    )
    jobs = (
        # Traditional Scrapy parsing: QuotesSpider yields QuoteItem instances.
        Job(
            kind="quotes",
            input=InputUrl("https://quotes.toscrape.com/page/1/"),
        ),
        # Another native Scrapy parser; BookItem is persisted by the same
        # low-priority RecordStorePipeline.
        Job(
            kind="books",
            input=InputUrl("https://books.toscrape.com/"),
        ),
        # UrlCrawler fetches a Document; DocumentTitlePipeline extracts its title.
        Job(
            kind="url",
            input=InputUrl("https://quotes.toscrape.com/"),
        ),
        # IdentityCrawler passes already-acquired inputs through the pipelines.
        Job(
            kind="identity",
            input=InputDocument(captured_ref),
        ),
        Job(
            kind="identity",
            input=InputQuery({"source": "manual", "name": "Example"}),
        ),
    )

    for job in jobs:
        await stores.manager.submit(job)

    print(f"Enqueued {len(jobs)} jobs; starting service...")
    settings = get_project_settings().copy()
    document_store_key = register(stores.documents)
    record_store_key = register(stores.records)
    settings.set("LONGSCRAPE_DOCUMENT_STORE_KEY", document_store_key)
    settings.set("LONGSCRAPE_RECORD_STORE_KEY", record_store_key)
    service = CrawlService.from_project(
        stores.manager, settings=settings, concurrency=2
    )

    # Launch service in a background asyncio Task
    serve_task = asyncio.create_task(
        service.serve(("quotes", "books", "url", "identity"))
    )

    try:
        # Monitor progress until all current tasks complete and queue is empty
        await monitor_until_idle(stores, poll_interval=1.0)
    finally:
        # Gracefully halt workers once stalling is detected
        await service.shutdown()
        serve_task.cancel()
        await asyncio.gather(serve_task, return_exceptions=True)
        discard(document_store_key)
        discard(record_store_key)
        await stores.close()


if __name__ == "__main__":
    asyncio.run(main())
