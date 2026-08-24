from collections.abc import Awaitable, Callable
from typing import Any, Literal

from longscrape_core import (
    Context,
    Document,
    Fetcher,
    HttpStatusError,
    InputUrl,
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
        page_mode: Literal["new", "reuse", "stored"] = "new",
        page_metadata_key: str = "browser_page_id",
    ) -> None:
        if page_mode not in {"new", "reuse", "stored"}:
            raise ValueError("page_mode must be 'new', 'reuse', or 'stored'")
        self._browser = browser
        self._page_ready = page_ready
        self._goto_options = goto_options or {}
        self._page_mode = page_mode
        self._page_metadata_key = page_metadata_key

    async def fetch(self, fetch_input, context: Context) -> Document:
        if not isinstance(fetch_input, InputUrl):
            raise TypeError("BrowserFetcher requires a URL input")

        if self._page_mode == "reuse":
            if context is None:
                raise RuntimeError("Reusable browser pages require a Context")
            page = context.require(CURRENT_PAGE)
            close_page = False
        elif self._page_mode == "stored":
            raise RuntimeError(
                "Stored browser pages are worker orchestration; restore the page "
                "and pass it with CURRENT_PAGE instead"
            )
        else:
            page = await self._browser.create_page()
            close_page = True
        try:
            response = await page.goto(fetch_input.url, **self._goto_options)
            if response is not None and response.status >= 400:
                raise HttpStatusError(page.url, response.status)
            if self._page_ready:
                await self._page_ready(page)
            content = await page.content()

            return Document(
                url=page.url,
                content=content.encode("utf-8"),
                status=response.status if response else 200,
            )
        finally:
            if close_page:
                await page.close()
