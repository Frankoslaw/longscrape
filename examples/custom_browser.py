"""Fetch a JavaScript-rendered page through a custom Patchright provider.

Run from the repository root:

    uv run --with patchright python -m examples.custom_browser

For an application, install ``longscrape`` and ``patchright`` independently;
Longscrape does not own Patchright's version.
"""

import asyncio
from collections.abc import AsyncIterable, AsyncIterator
from contextlib import AsyncExitStack
from typing import Any

from longscrape import Document, Extractor, InputUrl, Job, PipelineContext, Record
from longscrape.browser import BrowserConfig, BrowserManager
from longscrape.fetchers import BrowserFetcher, FetcherBuilder
from longscrape.runtime import Flow
from parsel import Selector


class PatchrightBrowserProvider:
    """A provider belongs in the application that selected Patchright."""

    def __init__(self, config: BrowserConfig) -> None:
        self.config = config
        self._stack = AsyncExitStack()
        self._browser_type: Any | None = None

    async def start(self) -> None:
        # This optional dependency is imported only when this provider is used.
        from patchright.async_api import async_playwright

        playwright = await self._stack.enter_async_context(async_playwright())
        self._browser_type = getattr(playwright, self.config.browser_type)

    async def launch_browser(self) -> Any:
        if self._browser_type is None:
            raise RuntimeError("Patchright provider has not been started")
        return await self._browser_type.launch(**self.config.launch_options)

    async def close(self) -> None:
        await self._stack.aclose()


async def wait_for_quotes(page: Any) -> None:
    # js-delayed starts empty. Waiting for a quote, rather than network-idle,
    # proves that the content needed by the scraper has actually rendered.
    await page.wait_for_selector(".quote")

    # playwright-stealth is a page integration, not a browser provider. With a
    # compatible browser, it can be applied here before the wait, for example:
    # from playwright_stealth import Stealth
    # await Stealth().apply_stealth_async(page)


class QuotesExtractor(Extractor):
    async def extract(
        self,
        documents: AsyncIterable[Document],
        job: Job,
        context: PipelineContext | None = None,
    ) -> AsyncIterator[Record]:
        async for document in documents:
            page = Selector(text=document.content.decode(errors="replace"))
            for quote in page.css(".quote"):
                yield Record(
                    kind="quote",
                    data={
                        "quote": quote.css(".text::text").get("").strip(),
                        "author": quote.css(".author::text").get("").strip(),
                    },
                )


async def main() -> None:
    config = BrowserConfig(launch_options={"headless": True})
    provider = PatchrightBrowserProvider(config)
    browser = BrowserManager(provider, config)
    fetcher = (
        FetcherBuilder()
        .base(BrowserFetcher(browser, page_ready=wait_for_quotes))
        .build()
    )
    extractor = QuotesExtractor()

    await browser.start()
    try:
        job = Job("quotes", InputUrl("https://quotes.toscrape.com/js-delayed/"))
        records = Flow().fetch(fetcher).extract(extractor).build()(job)
        quote_count = 0
        async for record in records:
            quote_count += 1
            print(f"{record.data['author']}: {record.data['quote']}")
        if not quote_count:
            raise RuntimeError("Quotes were not rendered before the page was read")
        print(f"extracted quote records: {quote_count}")
    finally:
        await browser.stop()


if __name__ == "__main__":
    asyncio.run(main())
