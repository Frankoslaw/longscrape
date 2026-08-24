from collections.abc import AsyncIterable
from typing import Protocol

from longscrape_core.context import Context
from longscrape_core.models import Document, FetchInput, Record


class Fetcher(Protocol):
    async def fetch(self, fetch_input: FetchInput, context: Context) -> Document: ...


class Extractor[Out](Protocol):
    def extract(
        self, document: Document, context: Context
    ) -> AsyncIterable[Record[Out]]: ...


class Transformer[In, Out](Protocol):
    def transform(
        self, records: AsyncIterable[Record[In]], context: Context
    ) -> AsyncIterable[Record[Out]]: ...
