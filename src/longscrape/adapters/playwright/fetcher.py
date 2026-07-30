from longscrape.core.domain.pipeline import RawEntry, ScraperTask
from longscrape.core.ports.playwright import PlaywrightManagerPort


class DefaultFetcher:
    """Fetch a URL task through a Playwright-compatible browser manager."""

    def __init__(self, playwright: PlaywrightManagerPort, base_domain: str) -> None:
        self._playwright = playwright
        self._base_domain = base_domain

    def get_base_domain(self) -> str:
        return self._base_domain

    async def fetch(self, task: ScraperTask) -> RawEntry:
        if not isinstance(task.query, str):
            raise TypeError("DefaultFetcher requires a URL string query")
        page = await self._playwright.create_page()
        try:
            response = await page.goto(task.query)
            return RawEntry(
                task_hash=task.hash,
                url=page.url,
                content=await page.content(),
                status_code=response.status if response else 200,
            )
        finally:
            await page.close()
