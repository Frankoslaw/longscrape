"""Process-local storage for live browser pages.

Page IDs are safe to put in job metadata; the pages themselves are deliberately
not serializable.  A stored page is available only while the owning
``BrowserManager`` remains running.
"""

from typing import Any
from uuid import uuid4


class PageStore:
    """Keep live Playwright pages addressable by an opaque ID.

    The store does not close a page when it is retrieved or removed.  Call
    ``close_all`` during browser shutdown, or close a page yourself after
    removing it with ``pop``.
    """

    def __init__(self) -> None:
        self._pages: dict[str, Any] = {}

    def put(self, page: Any) -> str:
        """Store *page* and return a JSON-safe ID for job metadata."""
        page_id = str(uuid4())
        self._pages[page_id] = page
        return page_id

    def get(self, page_id: str) -> Any | None:
        """Return a stored page, if it is still live."""
        return self._pages.get(page_id)

    def require(self, page_id: str) -> Any:
        """Return a page or explain why the live-page handoff cannot resume."""
        page = self.get(page_id)
        if page is None:
            raise LookupError(
                f"No live browser page is stored under {page_id!r}. "
                "It may have been released or the browser process restarted."
            )
        return page

    def pop(self, page_id: str) -> Any:
        """Remove and return a page without closing it."""
        try:
            return self._pages.pop(page_id)
        except KeyError as error:
            raise LookupError(
                f"No live browser page is stored under {page_id!r}"
            ) from error

    async def close_all(self) -> None:
        """Close every still-stored page and clear the store."""
        pages = list(self._pages.values())
        self._pages.clear()
        for page in pages:
            await page.close()
