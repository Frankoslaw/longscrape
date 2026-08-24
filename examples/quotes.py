import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from urllib.parse import urljoin

import httpx
from longscrape import (
    Document,
    Extractor,
    InputUrl,
    JobRequest,
    Record,
)
from longscrape.fetchers import FetcherBuilder, HttpxFetcher
from longscrape.runtime import Flow
from longscrape.storage import RecordSink
from longscrape.worker import FlowRouter, InMemoryJobQueue, JobContext, StoredJobQueue
from parsel import Selector

from .common import close_store, get_document_store, get_job_store, get_record_store

QUOTES = "quotes-page"
AUTHOR = "author-page"
START_URL = "https://quotes.toscrape.com/page/1/"


class QuotesExtractor(Extractor):
    def __init__(self, submit_child: Callable[[JobRequest], Awaitable[None]]) -> None:
        self._submit_child = submit_child

    async def extract(self, document: Document, _) -> AsyncIterator[Record]:
        page = Selector(text=document.content.decode(errors="replace"))
        for quote in page.css(".quote"):
            yield Record(
                kind="quote",
                data={
                    "quote": quote.css(".text::text").get("").strip(),
                    "author": quote.css(".author::text").get("").strip(),
                },
            )
        for href in page.css(".quote a[href*='/author/']::attr(href)").getall():
            await self._submit_child(
                JobRequest(
                    AUTHOR,
                    InputUrl(urljoin(document.url, href.rstrip("/") + "/")),
                ),
            )
        if href := page.css(".pager .next a::attr(href)").get():
            await self._submit_child(
                JobRequest(QUOTES, InputUrl(urljoin(document.url, href)))
            )


class AuthorExtractor(Extractor):
    async def extract(self, document: Document, _) -> AsyncIterator[Record]:
        page = Selector(text=document.content.decode(errors="replace"))
        yield Record(
            kind="author",
            data={
                "name": page.css(".author-title::text").get("").strip(),
                "born_date": page.css(".author-born-date::text").get("").strip(),
                "born_location": page.css(".author-born-location::text")
                .get("")
                .strip(),
            },
        )


async def main() -> None:
    job_store = get_job_store()
    job_queue = StoredJobQueue(InMemoryJobQueue(), job_store)
    await job_queue.submit(JobRequest(QUOTES, InputUrl(START_URL)))

    quote_store = get_record_store("quotes")
    author_store = get_record_store("authors")
    quote_sink = RecordSink(quote_store)
    author_sink = RecordSink(author_store)

    async with httpx.AsyncClient(follow_redirects=True) as http:
        document_store = get_document_store()

        fetcher = (
            FetcherBuilder()
            .base(HttpxFetcher(http))
            .rate_limit(requests_per_second=2)
            .cache(document_store)
            .build()
        )

        def quotes_flow(context: JobContext):
            return (
                Flow()
                .fetch(fetcher)
                .extract(QuotesExtractor(context.submit_child))
                .transform(quote_sink)
                .build()
            )

        def author_flow(_: JobContext):
            return (
                Flow()
                .fetch(fetcher)
                .extract(AuthorExtractor())
                .transform(author_sink)
                .build()
            )

        flows = {
            QUOTES: quotes_flow,
            AUTHOR: author_flow,
        }

        try:
            await FlowRouter(flows, job_store=job_store).run(job_queue)
        finally:
            await close_store(document_store)
            await close_store(job_store)
            await close_store(quote_store)
            await close_store(author_store)


if __name__ == "__main__":
    asyncio.run(main())
