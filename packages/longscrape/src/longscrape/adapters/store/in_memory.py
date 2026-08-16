from longscrape_core import Document
from longscrape_core.ports import DocumentStore

class InMemoryDocumentStore(DocumentStore):
    def __init__(self) -> None:
        self._entries: dict[str, Document] = {}

    async def store(self, document: Document) -> None:
        # TODO: this is temporary
        key = document.url
        self._entries[key] = document

    async def load(self, key: str) -> Document | None:
        return self._entries.get(key)
