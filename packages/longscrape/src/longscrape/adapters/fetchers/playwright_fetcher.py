from typing import AsyncIterable

from longscrape_core import (
    DISCARD_SUBMITTER,
    Document,
    Fetcher,
    InputUrl,
    Job,
    JobSubmitter,
)

from longscrape.core.ports.playwright import PlaywrightManagerPort


class PlaywrightFetcher(Fetcher):
    def __init__(self, playwright: PlaywrightManagerPort) -> None:
        self._playwright = playwright

    async def fetch(
        self, job: Job, submitter: JobSubmitter = DISCARD_SUBMITTER
    ) -> AsyncIterable[Document]:
        if not isinstance(job.input, InputUrl):
            raise TypeError("DefaultFetcher requires a URL input")

        page = await self._playwright.create_page()
        try:
            response = await page.goto(job.input.url)
            content = await page.content()

            yield Document(
                url=page.url,
                content=content.encode("utf-8"),
                status=response.status if response else 200,
            )
        finally:
            await page.close()
