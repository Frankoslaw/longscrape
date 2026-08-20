"""Coordinate a three-stage crawler with Dramatiq and Redis.

In separate terminals, from the repository root:

    docker run --rm -p 6379:6379 redis:7
    uv run --package longscrape --extra dramatiq dramatiq examples.orchestration
    uv run --package longscrape --extra dramatiq python -m examples.orchestration

``catalog`` submits one ``detail`` job per item.  Each detail flow submits a
``summary`` job.  The example uses an in-memory fake fetcher so the queueing
and parent/root lineage are visible without contacting a website.
"""

import asyncio
import logging
import os
from collections.abc import AsyncIterable, AsyncIterator

from longscrape import Document, Extractor, InputUrl, Job, JobRequest, Record
from longscrape.orchestration import DramatiqApp
from longscrape.runtime import Flow

CATALOG = "catalog"
DETAIL = "detail"
SUMMARY = "summary"

app = DramatiqApp.redis(url=os.getenv("REDIS_URL", "redis://localhost:6379/0"))


class FakeFetcher:
    async def fetch(self, job: Job, context=None) -> AsyncIterator[Document]:
        if not isinstance(job.input, InputUrl):
            raise TypeError("example jobs require InputUrl")
        yield Document(url=job.input.url, content=b"")


class PrintRecords:
    """A visible sink proving that the worker ran each flow."""

    async def transform(
        self, records: AsyncIterable[Record], job: Job, context=None
    ) -> AsyncIterator[Record]:
        async for record in records:
            logging.info(
                f"{record.kind}: {record.data}; job={job.id}; "
                f"parent={job.parent_id}; root={job.root_id}",
            )
            yield record


class CatalogExtractor(Extractor):
    async def extract(
        self, documents: AsyncIterable[Document], job: Job, context=None
    ) -> AsyncIterator[Record]:
        if context is None:
            raise RuntimeError("CatalogExtractor requires a context")
        async for document in documents:
            for item in ("alpha", "beta"):
                await context.submit_child(
                    job, JobRequest(DETAIL, InputUrl(f"{document.url}/{item}"))
                )
            yield Record("catalog", {"url": document.url})


class DetailExtractor(Extractor):
    async def extract(
        self, documents: AsyncIterable[Document], job: Job, context=None
    ) -> AsyncIterator[Record]:
        if context is None:
            raise RuntimeError("DetailExtractor requires a context")
        async for document in documents:
            await context.submit_child(job, JobRequest(SUMMARY, InputUrl(document.url)))
            yield Record("detail", {"url": document.url})


class SummaryExtractor(Extractor):
    async def extract(
        self, documents: AsyncIterable[Document], job: Job, context=None
    ) -> AsyncIterator[Record]:
        async for document in documents:
            yield Record("summary", {"url": document.url})


@app.flow(kind=CATALOG, queue="catalog")
def catalog(context):
    return (
        Flow(context)
        .fetch(FakeFetcher())
        .extract(CatalogExtractor())
        .transform(PrintRecords())
        .build()
    )


@app.flow(kind=DETAIL, queue="detail")
def detail(context):
    return (
        Flow(context)
        .fetch(FakeFetcher())
        .extract(DetailExtractor())
        .transform(PrintRecords())
        .build()
    )


@app.flow(kind=SUMMARY, queue="summary")
def summary(context):
    return (
        Flow(context)
        .fetch(FakeFetcher())
        .extract(SummaryExtractor())
        .transform(PrintRecords())
        .build()
    )


async def main() -> None:
    await app.submit(JobRequest(CATALOG, InputUrl("https://example.test/catalog")))


if __name__ == "__main__":
    asyncio.run(main())
