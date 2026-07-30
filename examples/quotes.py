import asyncio
from urllib.parse import urljoin

from parsel.selector import Selector

from longscrape import (
    Crawler,
    DefaultExtractor,
    ExtractionResult,
    FetchRequest,
    LeakyBucketRateLimiter,
    RawEntry,
    RichEntry,
    ScraperWorker,
)
from longscrape.adapters import (
    DefaultFetcher,
    PatchrightManager,
    URLBlocklist,
)
from longscrape.adapters.playwright.middlewares import URLCacher
from longscrape.adapters.store.in_memory import InMemoryRawEntryStore

Quote = dict[str, str]
Author = dict[str, str]
QUOTES_TASK_KIND = "quotes-page"
AUTHOR_TASK_KIND = "author-page"
START_URL = "https://quotes.toscrape.com/page/1/"


class QuotesExtractor(DefaultExtractor[Quote]):
    def __init__(self):
        super().__init__(allowed_domain="quotes.toscrape.com")

    async def extract(
        self, request: FetchRequest, raw_entry: RawEntry
    ) -> ExtractionResult[Quote]:
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
            request.spawn(
                kind=AUTHOR_TASK_KIND, query=urljoin(raw_entry.url, about_href)
            )
            for about_href in selector.css(
                ".quote a[href*='/author/']::attr(href)"
            ).getall()
        ]
        if next_href := selector.css(".pager .next a::attr(href)").get():
            tasks.append(
                request.spawn(
                    kind=QUOTES_TASK_KIND, query=urljoin(raw_entry.url, next_href)
                )
            )
        return ExtractionResult(items=items, tasks=tasks)


class AuthorExtractor(DefaultExtractor[Author]):
    def __init__(self):
        super().__init__(allowed_domain="quotes.toscrape.com")

    async def extract(
        self, request: FetchRequest, raw_entry: RawEntry
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
    playwright = PatchrightManager(headless=False)
    playwright.register_middleware(URLBlocklist())
    playwright.register_middleware(URLCacher())

    fetcher = DefaultFetcher(playwright, "quotes.toscrape.com")
    raw_entries = InMemoryRawEntryStore()
    rate_limiter = LeakyBucketRateLimiter(requests_per_second=0.5)

    workers = {
        QUOTES_TASK_KIND: ScraperWorker(
            fetcher,
            QuotesExtractor(),
            task_kind=QUOTES_TASK_KIND,
            rate_limiter=rate_limiter,
            raw_entry_store=raw_entries,
        ),
        AUTHOR_TASK_KIND: ScraperWorker(
            fetcher,
            AuthorExtractor(),
            task_kind=AUTHOR_TASK_KIND,
            rate_limiter=rate_limiter,
            raw_entry_store=raw_entries,
        ),
    }

    async with Crawler(workers, resources=[playwright]) as crawler:
        async for item in crawler.stream_inputs(
            FetchRequest(kind=QUOTES_TASK_KIND, query=START_URL)
        ):
            if "quote" in item.data:
                print(
                    f"[{item.url}] {item.data['author']}: {item.data['quote'][:35]}..."
                )
            else:
                print(f"[{item.url}] author: {item.data['name']}")


if __name__ == "__main__":
    asyncio.run(main())
