"""A fully typed, jobless record flow."""

import asyncio
from collections.abc import AsyncIterable, AsyncIterator
from typing import TypedDict

from longscrape import (
    Context,
    Document,
    Extractor,
    InputUrl,
    Record,
    RecordSink,
    Transformer,
)
from longscrape.runtime import Flow
from longscrape.storage import InMemoryRecordStore


class Article(TypedDict):
    url: str
    title: str


class IndexedArticle(Article):
    slug: str


class OneDocumentFetcher:
    async def fetch(self, fetch_input: InputUrl | object, context: Context) -> Document:
        if not isinstance(fetch_input, InputUrl):
            raise TypeError("OneDocumentFetcher requires a URL")
        return Document(fetch_input.url, b"<title>Typed records</title>")


class ArticleExtractor(Extractor[Article]):
    async def _extract(self, document: Document) -> AsyncIterator[Record[Article]]:
        yield Record("article", {"url": document.url, "title": "Typed records"})

    def extract(
        self, document: Document, context: Context
    ) -> AsyncIterable[Record[Article]]:
        return self._extract(document)


class AddSlug(Transformer[Article, IndexedArticle]):
    async def transform(
        self, records: AsyncIterable[Record[Article]], context: Context
    ) -> AsyncIterator[Record[IndexedArticle]]:
        async for record in records:
            yield Record(
                "article",
                {**record.data, "slug": record.data["title"].lower().replace(" ", "-")},
            )


async def main() -> None:
    sink = RecordSink[IndexedArticle](
        InMemoryRecordStore(), key=lambda record: record.data["slug"]
    )
    flow = (
        Flow()
        .fetch(OneDocumentFetcher())
        .extract(ArticleExtractor())
        .transform(AddSlug())
        .transform(sink)
        .build()
    )
    async for _ in flow(
        InputUrl("https://example.com/articles/typed-records"), Context()
    ):
        pass


if __name__ == "__main__":
    asyncio.run(main())
