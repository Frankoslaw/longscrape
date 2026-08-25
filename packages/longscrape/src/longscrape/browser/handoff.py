"""Default interactive browser handoff support."""

import asyncio
from datetime import timedelta

from longscrape.browser.manager import BrowserManager
from longscrape.core import PipelineFailure


class ManualHandoff:
    """Synchronize state through an explicitly configured headed browser."""

    def __init__(
        self,
        browser: BrowserManager,
        handoff_browser: BrowserManager,
        *,
        timeout: timedelta = timedelta(minutes=2),
    ) -> None:
        if timeout <= timedelta():
            raise ValueError("timeout must be greater than zero")
        self._browser = browser
        self._handoff_browser = handoff_browser
        self._timeout = timeout

    async def resolve(self, failure: PipelineFailure) -> None:
        # Core failures intentionally carry no job.  A worker-level handoff
        # adapter must attach its requested URL as a context capability.
        url = None
        if url is None:
            raise TypeError("ManualHandoff requires a URL job input")
        async with self._browser.locked():
            storage_state = await self._browser.storage_state()
            await self._handoff_browser.replace_context(storage_state=storage_state)
            page = await self._handoff_browser.create_page()
            try:
                await page.goto(url)
                await self._wait_for_user()
                updated_state = await self._handoff_browser.storage_state()
            finally:
                await page.close()

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
        except EOFError, TimeoutError:
            pass
