from collections.abc import AsyncIterable
from typing import Protocol

from longscrape.core.context import Context
from longscrape.core.models import Document, FetchInput, Record


class Fetcher(Protocol):
    async def fetch(self, fetch_input: FetchInput, ctx: Context) -> Document: ...


class Extractor[Out](Protocol):
    def extract(
        self, document: Document, ctx: Context
    ) -> AsyncIterable[Record[Out]]: ...


class Transformer[In, Out](Protocol):
    def transform(
        self, records: AsyncIterable[Record[In]], ctx: Context
    ) -> AsyncIterable[Record[Out]]: ...


class Sink[In](Protocol):
    async def sink(self, records: AsyncIterable[Record[In]], ctx: Context) -> None: ...
