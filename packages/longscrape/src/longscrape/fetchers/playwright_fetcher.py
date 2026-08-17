from collections.abc import Awaitable, Callable
from typing import Any, AsyncIterable

from longscrape_core import (
    DISCARD_SUBMITTER,
    Document,
    Fetcher,
    InputUrl,
    Job,
    JobSubmitter,
)

from longscrape.browser._protocols import BrowserManagerProtocol

PageReady = Callable[[Any], Awaitable[None]]


class BrowserFetcher(Fetcher):
    """Fetch through any browser exposing the Playwright page API.

    ``page_ready`` runs after navigation and is the place to wait for dynamic
    content or apply a page-level integration such as ``playwright-stealth``.
    """

    def __init__(
        self,
        browser: BrowserManagerProtocol,
        *,
        page_ready: PageReady | None = None,
        goto_options: dict[str, Any] | None = None,
    ) -> None:
        self._browser = browser
        self._page_ready = page_ready
        self._goto_options = goto_options or {}

    async def fetch(
        self, job: Job, submitter: JobSubmitter = DISCARD_SUBMITTER
    ) -> AsyncIterable[Document]:
        if not isinstance(job.input, InputUrl):
            raise TypeError("BrowserFetcher requires a URL input")

        page = await self._browser.create_page()
        try:
            response = await page.goto(job.input.url, **self._goto_options)
            if self._page_ready:
                await self._page_ready(page)
            content = await page.content()

            yield Document(
                url=page.url,
                content=content.encode("utf-8"),
                status=response.status if response else 200,
            )
        finally:
            await page.close()
