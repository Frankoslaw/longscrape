"""Direct browser scraping with kind-routed queue consumption."""

import asyncio
from dataclasses import replace
from urllib.parse import urljoin

from common import create_stores
from longscrape import (
    PatchrightFetcher,
    PatchrightManager,
    PlaywrightFetcher,
    URLBlocklist,
    URLCacher,
)
from longscrape_core import (
    Document,
    DocumentStore,
    Extractor,
    InputUrl,
    Job,
    JobManager,
    JobSubmitter,
    Record,
    RecordStore,
    Transformer,
)
from parsel import Selector

QUOTES_KIND = "quotes-page"
AUTHOR_KIND = "author-page"
START_URL = "https://quotes.toscrape.com/page/1/"


class QuotesExtractor(Extractor):
    async def extract(
        self,
        job: Job,
        document: Document,
        jobs: JobSubmitter,
    ) -> list[Record]:
        selector = Selector(text=document.text)
        for href in selector.css(".quote a[href*='/author/']::attr(href)").getall():
            await jobs.submit(
                Job(kind=AUTHOR_KIND, input=InputUrl(urljoin(document.url, href)))
            )
        if href := selector.css(".pager .next a::attr(href)").get():
            await jobs.submit(
                Job(kind=QUOTES_KIND, input=InputUrl(urljoin(document.url, href)))
            )
        return [
            Record(
                kind="quote",
                source_url=document.url,
                data={
                    "quote": quote.css(".text::text").get("").strip(),
                    "author": quote.css(".author::text").get("").strip(),
                },
            )
            for quote in selector.css(".quote")
        ]


class AuthorExtractor(Extractor):
    async def extract(
        self,
        job: Job,
        document: Document,
        jobs: JobSubmitter,
    ) -> list[Record]:
        selector = Selector(text=document.text)
        return [
            Record(
                kind="author",
                source_url=document.url,
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


class StripTextFields(Transformer):
    """A reusable transformation stage applied before records are persisted."""

    async def transform(self, job: Job, record: Record) -> list[Record]:
        return [
            replace(
                record,
                data={
                    key: value.strip() if isinstance(value, str) else value
                    for key, value in record.data.items()
                },
            )
        ]


async def process_job(
    job: Job,
    *,
    fetcher: PlaywrightFetcher,
    jobs: JobManager,
    documents: DocumentStore,
    records: RecordStore,
) -> None:
    document = await fetcher.fetch(job)
    document_ref = await documents.save(document)
    match job.kind:
        case "quotes-page":
            extracted = await QuotesExtractor().extract(job, document, jobs)
        case "author-page":
            extracted = await AuthorExtractor().extract(job, document, jobs)
        case _:
            raise ValueError(f"Unsupported job kind: {job.kind}")
    transformer = StripTextFields()
    for extracted_record in extracted:
        for record in await transformer.transform(job, extracted_record):
            record = replace(record, document_ref=document_ref)
            await records.save(record)
            print(record.data)


async def main() -> None:
    stores = create_stores()
    await stores.manager.submit(Job(kind=QUOTES_KIND, input=InputUrl(START_URL)))
    manager = PatchrightManager(
        headless=False,
        route_handlers=[
            URLBlocklist(["google-analytics.com", "googletagmanager.com"]),
            URLCacher(".cache/quotes"),
        ],
    )
    async with PatchrightFetcher(manager) as fetcher:
        while not await stores.is_idle():
            for kind in (QUOTES_KIND, AUTHOR_KIND):
                while lease := await stores.manager.lease(kind):
                    try:
                        await process_job(
                            lease.job,
                            fetcher=fetcher,
                            jobs=stores.manager,
                            documents=stores.documents,
                            records=stores.records,
                        )
                    except Exception as error:
                        await lease.retry(error)
                    else:
                        await lease.acknowledge()
    await stores.close()


if __name__ == "__main__":
    asyncio.run(main())
