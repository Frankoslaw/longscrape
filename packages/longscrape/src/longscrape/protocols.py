from typing import AsyncIterable, Protocol

from longscrape.models import Document, Record


class Extractor[Out](Protocol):
    def extract(self, document: Document) -> AsyncIterable[Record[Out]]: ...
