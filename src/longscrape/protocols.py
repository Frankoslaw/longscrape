from typing import Protocol, AsyncIterable

from longscrape.models import Document, Record


class Extractor[Out](Protocol):
    def extract(self, document: Document) -> AsyncIterable[Record[Out]]: ...