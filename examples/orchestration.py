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

from longscrape import Document, Extractor, InputUrl, Job, JobSpec, Record, Fetcher, Context, FetchInput, Transformer
from longscrape.worker.dramatiq import DramatiqApp
from longscrape.runtime import Flow

CATALOG = "catalog"
DETAIL = "detail"
SUMMARY = "summary"

app = DramatiqApp.redis(url=os.getenv("REDIS_URL", "redis://localhost:6379/0"))


class FakeFetcher(Fetcher):
    async def fetch(self, fetch_input: FetchInput, ctx=None) -> Document:
        if not isinstance(fetch_input, InputUrl):
            raise TypeError("example fetch_input require InputUrl")
        return Document(url=fetch_input.url, content=b"")


class PrintRecords(Transformer):
    async def transform(
        self, records: AsyncIterable[Record], ctx=None
    ) -> AsyncIterator[Record]:
        async for record in records:
            logging.info(
                f"{record.kind}: {record.data}; job={ctx.j.id}; "
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
                    job, JobSpec(DETAIL, InputUrl(f"{document.url}/{item}"))
                )
            yield Record("catalog", {"url": document.url})


class DetailExtractor(Extractor):
    async def extract(
        self, documents: AsyncIterable[Document], job: Job, context=None
    ) -> AsyncIterator[Record]:
        if context is None:
            raise RuntimeError("DetailExtractor requires a context")
        async for document in documents:
            await context.submit_child(job, JobSpec(SUMMARY, InputUrl(document.url)))
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
        Flow()
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
    await app.submit(JobSpec(CATALOG, InputUrl("https://example.test/catalog")))


if __name__ == "__main__":
    asyncio.run(main())
