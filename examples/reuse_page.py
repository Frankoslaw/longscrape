"""Reuse a Playwright page locally, then hand it to a second queued flow.

Run with ``uv run --extra browser python -m examples.reuse_page``.  The page
ID in job metadata is JSON-safe, but it works only while this BrowserManager
and its process stay alive; it is not a durable session-resume mechanism.
"""

import asyncio
from collections.abc import AsyncIterable, AsyncIterator
from typing import Any

from longscrape import (
    Document,
    Extractor,
    InputUrl,
    Job,
    JobRequest,
    PipelineContext,
    Record,
)
from longscrape.browser import (
    CURRENT_PAGE,
    BrowserConfig,
    BrowserManager,
    PlaywrightBrowserProvider,
)
from longscrape.fetchers import BrowserFetcher
from longscrape.runtime import Flow, FlowRouter, InMemoryJobQueue

FIRST_SCRAPE = "first-scrape"
SECOND_SCRAPE = "second-scrape"
PAGE_ID = "browser_page_id"
URL = "https://quotes.toscrape.com/"


class CountingPageFetcher(BrowserFetcher):
    """A browser fetcher that increments a counter on every scrape."""

    def __init__(self, browser: BrowserManager, *, page_mode: str) -> None:
        async def count(page: Any) -> None:
            count = await page.evaluate(
                "window.__longscrape_scrapes = (window.__longscrape_scrapes || 0) + 1; "
                "window.__longscrape_scrapes"
            )
            print(f"scrape #{count}: {page.url}")

        super().__init__(browser, page_mode=page_mode, page_ready=count)  # type: ignore[arg-type]


class QueueSecondScrape(Extractor):
    async def extract(
        self,
        documents: AsyncIterable[Document],
        job: Job,
        context: PipelineContext | None = None,
    ) -> AsyncIterator[Record]:
        if context is None:
            raise RuntimeError("QueueSecondScrape requires a PipelineContext")
        async for document in documents:
            # Context does not travel with a job.  Pass only the opaque page ID.
            await context.submit_child(
                job,
                JobRequest(
                    SECOND_SCRAPE,
                    InputUrl(document.url),
                    metadata={PAGE_ID: job.metadata[PAGE_ID]},
                    # Pin to the browser-owning worker: the page ID is valid
                    # only in that worker's process-local PageStore.
                    worker_id=context.require_worker_id(),
                ),
            )
            yield Record(FIRST_SCRAPE, {"url": document.url})


class PrintScrape(Extractor):
    async def extract(
        self,
        documents: AsyncIterable[Document],
        job: Job,
        context: PipelineContext | None = None,
    ) -> AsyncIterator[Record]:
        async for document in documents:
            print(f"second flow restored {job.metadata[PAGE_ID]} at {document.url}")
            yield Record(SECOND_SCRAPE, {"url": document.url})


async def main() -> None:
    config = BrowserConfig(launch_options={"headless": True})
    browser = BrowserManager(PlaywrightBrowserProvider(config), config)
    queue = InMemoryJobQueue()
    worker_id = "page-worker-1"
    context = PipelineContext(queue, worker_id=worker_id)

    await browser.start()
    page = await browser.create_page()
    page_id = browser.store_page(page)

    # Flow one receives the actual Playwright page via local context.  Its
    # reuse-mode fetcher never closes that page.
    context.set(CURRENT_PAGE, page)
    first_flow = (
        Flow(context)
        .fetch(CountingPageFetcher(browser, page_mode="reuse"))
        .extract(QueueSecondScrape())
        .build()
    )
    # Flow two runs as a distinct queued job and restores the same live page
    # from browser.page_store by reading the page ID from metadata.
    second_flow = (
        Flow(context)
        .fetch(CountingPageFetcher(browser, page_mode="stored"))
        .extract(PrintScrape())
        .build()
    )

    await queue.submit(
        JobRequest(FIRST_SCRAPE, InputUrl(URL), metadata={PAGE_ID: page_id})
    )
    try:
        await FlowRouter(
            {FIRST_SCRAPE: first_flow, SECOND_SCRAPE: second_flow},
            worker_id=worker_id,
        ).run(queue)
    finally:
        # BrowserManager.stop() closes every page left in its page store.
        await browser.stop()


if __name__ == "__main__":
    asyncio.run(main())
