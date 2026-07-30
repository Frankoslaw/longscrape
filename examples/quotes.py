import asyncio
from logging import DEBUG
from urllib.parse import urljoin

from parsel.selector import Selector

from longscrape import (
    DefaultExtractor,
    ExtractionResult,
    InMemoryTaskQueue,
    RawEntry,
    RichEntry,
    ScraperWorker,
    Task,
    TaskQueue,
    configure_logging,
)
from longscrape.adapters import (
    PlaywrightManager,
    PlaywrightManagerPort,
    URLBlocklist,
    URLCacher,
)

Quote = dict[str, str]
Author = dict[str, str]
QUOTES_TASK_KIND = "quotes-page"
AUTHOR_TASK_KIND = "author-page"
START_URL = "https://quotes.toscrape.com/page/1/"


class QuotesFetcher:
    def __init__(self, playwright: PlaywrightManagerPort):
        self._playwright = playwright

    async def fetch(self, task: Task) -> RawEntry:
        if not isinstance(task.query, str):
            raise TypeError("QuotesFetcher requires a URL string query")
        page = await self._playwright.create_page()
        try:
            response = await page.goto(task.query)
            return RawEntry(
                url=page.url,
                content=await page.content(),
                status_code=response.status if response else 200,
            )
        finally:
            await page.close()


class AuthorFetcher:
    def __init__(self, playwright: PlaywrightManagerPort):
        self._playwright = playwright

    async def fetch(self, task: Task) -> RawEntry:
        if not isinstance(task.query, str):
            raise TypeError("AuthorFetcher requires a URL string query")
        page = await self._playwright.create_page()
        try:
            response = await page.goto(task.query)
            return RawEntry(
                url=page.url,
                content=await page.content(),
                status_code=response.status if response else 200,
            )
        finally:
            await page.close()


class QuotesExtractor(DefaultExtractor[Quote]):
    def __init__(self):
        super().__init__(allowed_domain="quotes.toscrape.com")

    async def extract(self, task: Task, raw_entry: RawEntry) -> ExtractionResult[Quote]:
        selector = Selector(text=raw_entry.content)
        items = [
            RichEntry(
                url=raw_entry.url,
                data={
                    "quote": quote.css(".text::text").get("").strip(),
                    "author": quote.css(".author::text").get("").strip(),
                },
            )
            for quote in selector.css(".quote")
        ]
        tasks = [
            task.spawn(kind=AUTHOR_TASK_KIND, query=urljoin(raw_entry.url, about_href))
            for about_href in selector.css(
                ".quote a[href*='/author/']::attr(href)"
            ).getall()
        ]
        if next_href := selector.css(".pager .next a::attr(href)").get():
            tasks.append(
                task.spawn(
                    kind=QUOTES_TASK_KIND, query=urljoin(raw_entry.url, next_href)
                )
            )
        return ExtractionResult(items=items, tasks=tasks)


class AuthorExtractor(DefaultExtractor[Author]):
    def __init__(self):
        super().__init__(allowed_domain="quotes.toscrape.com")

    async def extract(
        self, task: Task, raw_entry: RawEntry
    ) -> ExtractionResult[Author]:
        selector = Selector(text=raw_entry.content)
        return ExtractionResult(
            items=[
                RichEntry(
                    url=raw_entry.url,
                    data={
                        "name": selector.css(".author-title::text").get("").strip(),
                        "born_date": selector.css(".author-born-date::text")
                        .get("")
                        .strip(),
                        "born_location": selector.css(".author-born-location::text")
                        .get("")
                        .strip(),
                    },
                )
            ],
            tasks=[],
        )


async def main() -> None:
    configure_logging(level=DEBUG)
    playwright = PlaywrightManager()
    playwright.register_middleware(URLCacher(verbose=True))
    playwright.register_middleware(URLBlocklist())
    await playwright.start()

    try:
        workers = {
            QUOTES_TASK_KIND: ScraperWorker(
                QuotesFetcher(playwright),
                QuotesExtractor(),
                task_kind=QUOTES_TASK_KIND,
            ),
            AUTHOR_TASK_KIND: ScraperWorker(
                AuthorFetcher(playwright),
                AuthorExtractor(),
                task_kind=AUTHOR_TASK_KIND,
            ),
        }
        queue: TaskQueue = InMemoryTaskQueue()
        await queue.put(Task(kind=QUOTES_TASK_KIND, query=START_URL))

        while not queue.empty():
            task = await queue.get()
            result = await workers[task.kind].run(task)
            for child_task in result.tasks:
                await queue.put(child_task)
            for item in result.items:
                if task.kind == QUOTES_TASK_KIND:
                    print(
                        f"[{item.url}] {item.data['author']}: "
                        f"{item.data['quote'][:35]}..."
                    )
                else:
                    print(f"[{item.url}] author: {item.data['name']}")
    finally:
        await playwright.stop()


if __name__ == "__main__":
    asyncio.run(main())
