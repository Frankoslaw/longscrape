"""A fully typed, JSON-compatible record pipeline.

Run with ``uv run python -m examples.typed_records`` from the repository root.
Type checkers reject wiring a transformer or sink for a different record shape
into this ``Flow``.
"""

import asyncio
from collections.abc import AsyncIterable, AsyncIterator
from typing import TypedDict

from longscrape import (
    Document,
    Extractor,
    InputUrl,
    Job,
    PipelineContext,
    Record,
    RecordSink,
    Transformer,
)
from longscrape.runtime import Flow
from longscrape.stores import InMemoryRecordStore


class Article(TypedDict):
    url: str
    title: str


class IndexedArticle(Article):
    slug: str


class OneDocumentFetcher:
    async def fetch(
        self, job: Job, context: PipelineContext | None = None
    ) -> AsyncIterator[Document]:
        assert isinstance(job.input, InputUrl)
        yield Document(
            url=job.input.url,
            content=b"<title>Typed records</title>",
        )


class ArticleExtractor(Extractor[Article]):
    async def extract(
        self,
        documents: AsyncIterable[Document],
        job: Job,
        context: PipelineContext | None = None,
    ) -> AsyncIterator[Record[Article]]:
        async for document in documents:
            data: Article = {"url": document.url, "title": "Typed records"}
            yield Record("article", data)


class AddSlug(Transformer[Article, IndexedArticle]):
    async def transform(
        self,
        records: AsyncIterable[Record[Article]],
        job: Job,
        context: PipelineContext | None = None,
    ) -> AsyncIterator[Record[IndexedArticle]]:
        async for record in records:
            data: IndexedArticle = {
                **record.data,
                "slug": record.data["title"].lower().replace(" ", "-"),
            }
            yield Record("article", data)


async def main() -> None:
    store = InMemoryRecordStore()
    sink = RecordSink[IndexedArticle](store, key=lambda record, _: record.data["slug"])

    flow = (
        Flow()
        .fetch(OneDocumentFetcher())
        .extract(ArticleExtractor())
        .transform(AddSlug())
        .sink(sink)
        .build()
    )

    job = Job("article", InputUrl("https://example.com/articles/typed-records"))
    async for _ in flow(job):
        pass


if __name__ == "__main__":
    asyncio.run(main())
