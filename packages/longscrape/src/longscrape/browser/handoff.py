"""Default interactive browser handoff support."""

import asyncio
from datetime import timedelta

from longscrape_core import Document, FetchFailure, Job

from longscrape.browser.manager import BrowserManager


class ManualHandoff:
    """Let a user resolve a browser block, then replace the managed session.

    A headed browser opens with the current storage state. The resolver waits
    for Enter or ``timeout`` before copying the updated state back to the
    managed browser, so the wrapped fetcher can retry with that session.
    """

    def __init__(
        self,
        browser: BrowserManager,
        *,
        timeout: timedelta = timedelta(minutes=2),
    ) -> None:
        if timeout <= timedelta():
            raise ValueError("timeout must be greater than zero")
        self._browser = browser
        self._timeout = timeout

    async def resolve(
        self, *, job: Job, document: Document, failure: FetchFailure
    ) -> None:
        storage_state = await self._browser.storage_state()
        manual_browser = await self._browser.launch_handoff_browser()
        manual_context = await manual_browser.new_context(storage_state=storage_state)
        manual_page = await manual_context.new_page()
        try:
            await manual_page.goto(document.url)
            await self._wait_for_user()
            updated_state = await manual_context.storage_state()
        finally:
            await manual_context.close()
            await manual_browser.close()

        await self._browser.replace_context(storage_state=updated_state)

    async def _wait_for_user(self) -> None:
        seconds = self._timeout.total_seconds()
        try:
            await asyncio.wait_for(
                asyncio.to_thread(
                    input,
                    "Resolve the browser issue, then press Enter "
                    f"(continuing in {seconds:g}s): ",
                ),
                timeout=seconds,
            )
        except TimeoutError:
            pass
