from collections.abc import AsyncIterable, AsyncIterator

import httpx
from longscrape import Document, Extractor, Job, PipelineContext, Record
from longscrape.fetchers import HttpxFetcher
from longscrape_scrapy import LongscrapeSpider, job_only


class QuotesExtractor(Extractor[dict[str, object]]):
    """The same extraction logic can run from an HTTP fetch or a stored page."""

    async def extract(
        self,
        documents: AsyncIterable[Document],
        job: Job,
        context: PipelineContext | None = None,
    ) -> AsyncIterator[Record[dict[str, object]]]:
        async for document in documents:
            response = document.content.decode(errors="replace")
            # Scrapy is intentionally still available at the parse boundary;
            # this extractor uses its selector-compatible response content.
            from parsel import Selector

            for quote in Selector(text=response).css("div.quote"):
                yield Record(
                    "quote",
                    {
                        "quote_content": quote.css(".text::text").get("").strip("“”"),
                        "author_name": quote.css("small.author::text").get(""),
                        "tags": quote.css(".tag::text").getall(),
                        "source_url": document.url,
                    },
                )


class QuotesFetcher:
    async def fetch(self, job, context=None):
        async with httpx.AsyncClient() as client:
            async for document in HttpxFetcher(client).fetch(job, context):
                yield document


class QuotesLongscrapeSpider(LongscrapeSpider):
    """A job-driven sibling of ``QuotesSpider``; the vanilla spider remains."""

    name = "quotes_longscrape"

    @job_only
    async def start(self):
        self.fetcher = QuotesFetcher()
        async for request in super().start():
            yield request

    @job_only
    async def parse(self, response):
        self.extractor = QuotesExtractor()
        async for item in super().parse(response):
            yield item
