from typing import Any, AsyncIterable, Protocol

from longscrape.models import Document, InputQuery, InputUrl, Record


class Fetcher[In: (InputUrl, InputQuery[Any])](Protocol):
    async def fetch(self, fetch_input: In) -> Document: ...


class Extractor[Out](Protocol):
    def extract(self, document: Document) -> AsyncIterable[Record[Out]]: ...
