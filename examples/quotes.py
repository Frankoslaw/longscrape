"""Direct browser scraping with kind-routed queue consumption."""

import asyncio
from urllib.parse import urljoin

from longscrape import (
    PatchrightFetcher,
    PatchrightManager,
    PlaywrightFetcher,
    URLBlocklist,
    URLCacher,
)
from longscrape_core import (
    Document,
    Extractor,
    InMemoryDocumentStore,
    InMemoryJobQueue,
    InMemoryRecordStore,
    InputUrl,
    Job,
    JobQueue,
    Record,
)
from parsel import Selector

QUOTES_KIND = "quotes-page"
AUTHOR_KIND = "author-page"
START_URL = "https://quotes.toscrape.com/page/1/"


class QuotesExtractor(Extractor):
    async def extract(
        self, job: Job, document: Document, queue: JobQueue
    ) -> list[Record]:
        selector = Selector(text=document.text)
        for href in selector.css(".quote a[href*='/author/']::attr(href)").getall():
            await queue.enqueue(
                Job(kind=AUTHOR_KIND, input=InputUrl(urljoin(document.url, href)))
            )
        if href := selector.css(".pager .next a::attr(href)").get():
            await queue.enqueue(
                Job(kind=QUOTES_KIND, input=InputUrl(urljoin(document.url, href)))
            )
        return [
            Record(
                kind="quote",
                source_url=document.url,
                document=document,
                data={
                    "quote": quote.css(".text::text").get("").strip(),
                    "author": quote.css(".author::text").get("").strip(),
                },
            )
            for quote in selector.css(".quote")
        ]


class AuthorExtractor(Extractor):
    async def extract(
        self, job: Job, document: Document, queue: JobQueue
    ) -> list[Record]:
        selector = Selector(text=document.text)
        return [
            Record(
                kind="author",
                source_url=document.url,
                document=document,
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
        ]


async def process_job(
    job: Job,
    *,
    fetcher: PlaywrightFetcher,
    queue: JobQueue,
    documents: InMemoryDocumentStore,
    records: InMemoryRecordStore,
) -> None:
    document = await fetcher.fetch(job)
    await documents.save(document)
    match job.kind:
        case "quotes-page":
            extracted = await QuotesExtractor().extract(job, document, queue)
        case "author-page":
            extracted = await AuthorExtractor().extract(job, document, queue)
        case _:
            raise ValueError(f"Unsupported job kind: {job.kind}")
    for record in extracted:
        await records.save(record)
        print(record.data)


async def main() -> None:
    queue = InMemoryJobQueue()
    documents = InMemoryDocumentStore()
    records = InMemoryRecordStore()
    await queue.enqueue(Job(kind=QUOTES_KIND, input=InputUrl(START_URL)))
    manager = PatchrightManager(
        headless=False,
        route_handlers=[
            URLBlocklist(["google-analytics.com", "googletagmanager.com"]),
            URLCacher(".cache/quotes"),
        ],
    )
    async with PatchrightFetcher(manager) as fetcher:
        while not queue.is_empty():
            for kind in (QUOTES_KIND, AUTHOR_KIND):
                while job := await queue.dequeue(kind):
                    try:
                        await process_job(
                            job,
                            fetcher=fetcher,
                            queue=queue,
                            documents=documents,
                            records=records,
                        )
                    except Exception as error:
                        await queue.mark_failed(job, error)
                    else:
                        await queue.mark_completed(job)


if __name__ == "__main__":
    asyncio.run(main())
