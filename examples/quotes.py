import asyncio
from collections.abc import AsyncIterable, AsyncIterator
from urllib.parse import urljoin

import httpx
from common import close_store, get_document_store, get_record_store
from longscrape import (
    Document,
    Extractor,
    InputUrl,
    Job,
    JobRequest,
    JobSubmitter,
    Record,
    RecordSink,
)
from longscrape.fetchers import CachedFetcher, HttpxFetcher, RateLimitedFetcher
from longscrape.runtime import Flow, InMemoryJobQueue, LeakyBucketRateLimiter
from longscrape_core import DISCARD_SUBMITTER
from parsel import Selector

QUOTES = "quotes-page"
AUTHOR = "author-page"
START_URL = "https://quotes.toscrape.com/page/1/"


class QuotesExtractor(Extractor):
    async def extract(
        self,
        documents: AsyncIterable[Document],
        job: Job,
        submitter: JobSubmitter = DISCARD_SUBMITTER,
    ) -> AsyncIterator[Record]:
        async for document in documents:
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
                await submitter.submit(
                    JobRequest(AUTHOR, InputUrl(urljoin(document.url, href)))
                )
            if href := page.css(".pager .next a::attr(href)").get():
                await submitter.submit(
                    JobRequest(QUOTES, InputUrl(urljoin(document.url, href)))
                )


class AuthorExtractor(Extractor):
    async def extract(
        self,
        documents: AsyncIterable[Document],
        job: Job,
        submitter: JobSubmitter = DISCARD_SUBMITTER,
    ) -> AsyncIterator[Record]:
        async for document in documents:
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
    job_queue = InMemoryJobQueue()
    await job_queue.submit(JobRequest(QUOTES, InputUrl(START_URL)))

    quote_store = get_record_store("quotes")
    author_store = get_record_store("authors")
    quote_sink = RecordSink(quote_store)
    author_sink = RecordSink(author_store)

    async with httpx.AsyncClient(follow_redirects=True) as http:
        document_store = get_document_store()

        fetcher = CachedFetcher(
            RateLimitedFetcher(
                HttpxFetcher(http),
                LeakyBucketRateLimiter(requests_per_second=2),
            ),
            document_store,
        )
        flows = {
            QUOTES: (
                Flow(job_queue)
                .fetch(fetcher)
                .extract(QuotesExtractor())
                .consume(quote_sink)
                .build()
            ),
            AUTHOR: (
                Flow(job_queue)
                .fetch(fetcher)
                .extract(AuthorExtractor())
                .consume(author_sink)
                .build()
            ),
        }

        try:
            while not job_queue.empty():
                job = await job_queue.get()
                flow = flows.get(job.kind)
                if flow is None:
                    continue
                async for _ in flow(job):
                    pass

        finally:
            await close_store(document_store)
            await close_store(quote_store)
            await close_store(author_store)


if __name__ == "__main__":
    asyncio.run(main())
