import os

from longscrape import DocumentStore, RecordStore
from longscrape.stores import InMemoryDocumentStore, InMemoryRecordStore


def get_document_store() -> DocumentStore:
    if mongo_uri := os.getenv("MONGODB_URI"):
        from longscrape.stores import PyMongoDocumentStore

        print("Using MongoDB backed document store")
        return PyMongoDocumentStore(mongo_uri)

    print("Using in memory document store")
    return InMemoryDocumentStore()


def get_record_store(kind: str) -> RecordStore:
    if mongo_uri := os.getenv("MONGODB_URI"):
        from longscrape.stores import PyMongoRecordStore

        return PyMongoRecordStore(kind, mongo_uri)
    return InMemoryRecordStore()


async def close_store(store: DocumentStore | RecordStore) -> None:
    close = getattr(store, "close", None)
    if close is not None:
        await close()
