import os

from longscrape import DocumentStore, JobStore, RecordStore
from longscrape.stores import (
    InMemoryDocumentStore,
    InMemoryJobStore,
    InMemoryRecordStore,
)


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

        print("Using MongoDB backed record store")
        return PyMongoRecordStore(kind, mongo_uri)

    print("Using in memory record store")
    return InMemoryRecordStore()


def get_job_store() -> JobStore:
    if mongo_uri := os.getenv("MONGODB_URI"):
        from longscrape.stores import PyMongoJobStore

        print("Using MongoDB backed job store")
        return PyMongoJobStore(mongo_uri)

    print("Using in memory job store")
    return InMemoryJobStore()


async def close_store(store: DocumentStore | JobStore | RecordStore) -> None:
    close = getattr(store, "close", None)
    if close is not None:
        await close()
