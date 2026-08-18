from collections.abc import Awaitable, Callable
from typing import Any, AsyncIterable, Literal

from longscrape_core import (
    Document,
    Fetcher,
    InputUrl,
    Job,
    PipelineContext,
)

from longscrape.browser._protocols import BrowserManagerProtocol
from longscrape.browser.context import CURRENT_PAGE

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
        page_mode: Literal["new", "reuse"] = "new",
    ) -> None:
        if page_mode not in {"new", "reuse"}:
            raise ValueError("page_mode must be 'new' or 'reuse'")
        self._browser = browser
        self._page_ready = page_ready
        self._goto_options = goto_options or {}
        self._page_mode = page_mode

    async def fetch(
        self, job: Job, context: PipelineContext | None = None
    ) -> AsyncIterable[Document]:
        if not isinstance(job.input, InputUrl):
            raise TypeError("BrowserFetcher requires a URL input")

        if self._page_mode == "reuse":
            if context is None:
                raise RuntimeError("Reusable browser pages require a PipelineContext")
            page = context.require(CURRENT_PAGE)
            close_page = False
        else:
            page = await self._browser.create_page()
            close_page = True
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
            if close_page:
                await page.close()
