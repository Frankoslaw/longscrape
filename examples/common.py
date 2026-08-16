import os

from longscrape import DocumentStore, RecordStore
from longscrape.adapters import InMemoryDocumentStore, InMemoryRecordStore


def get_document_store() -> DocumentStore:
    if mongo_uri := os.getenv("MONGODB_URI"):
        from longscrape.adapters import PyMongoDocumentStore

        return PyMongoDocumentStore(mongo_uri)

    return InMemoryDocumentStore()


def get_record_store(kind: str) -> RecordStore:
    if mongo_uri := os.getenv("MONGODB_URI"):
        from longscrape.adapters import PyMongoRecordStore

        return PyMongoRecordStore(kind, mongo_uri)
    return InMemoryRecordStore()


async def close_store(store: DocumentStore | RecordStore) -> None:
    close = getattr(store, "close", None)
    if close is not None:
        await close()
