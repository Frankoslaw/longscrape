import asyncio
from collections.abc import AsyncIterable, AsyncIterator
from urllib.parse import urljoin

import httpx
from longscrape import (
    Document,
    Extractor,
    InputUrl,
    Job,
    JobRequest,
    PipelineContext,
    Record,
    RecordSink,
)
from longscrape.fetchers import FetcherBuilder, HttpxFetcher
from longscrape.runtime import (
    Flow,
    FlowRouter,
    InMemoryJobQueue,
    StoredJobQueue,
)
from parsel import Selector

from .common import close_store, get_document_store, get_job_store, get_record_store

QUOTES = "quotes-page"
AUTHOR = "author-page"
START_URL = "https://quotes.toscrape.com/page/1/"


class QuotesExtractor(Extractor):
    async def extract(
        self,
        documents: AsyncIterable[Document],
        job: Job,
        context: PipelineContext | None = None,
    ) -> AsyncIterator[Record]:
        if context is None:
            raise RuntimeError("QuotesExtractor requires a PipelineContext")
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
                await context.submit_child(
                    job,
                    JobRequest(
                        AUTHOR,
                        InputUrl(urljoin(document.url, href.rstrip("/") + "/")),
                    ),
                )
            if href := page.css(".pager .next a::attr(href)").get():
                await context.submit_child(
                    job, JobRequest(QUOTES, InputUrl(urljoin(document.url, href)))
                )


class AuthorExtractor(Extractor):
    async def extract(
        self,
        documents: AsyncIterable[Document],
        job: Job,
        context: PipelineContext | None = None,
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
    job_store = get_job_store()
    job_queue = StoredJobQueue(InMemoryJobQueue(), job_store)
    context = PipelineContext(job_queue)
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

        quotes_flow = (
            Flow(context)
            .fetch(fetcher)
            .extract(QuotesExtractor())
            .sink(quote_sink)
            .build()
        )
        author_flow = (
            Flow(context)
            .fetch(fetcher)
            .extract(AuthorExtractor())
            .sink(author_sink)
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
