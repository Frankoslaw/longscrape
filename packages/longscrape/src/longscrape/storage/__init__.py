from importlib import import_module
from typing import TYPE_CHECKING

from longscrape.storage.in_memory import (
    InMemoryDocumentStore,
    InMemoryJobStore,
    InMemoryRecordStore,
)
from longscrape.storage.models import CollisionPolicy, DocumentRef, RecordRef
from longscrape.storage.protocols import DocumentStore, RecordSink, RecordStore

if TYPE_CHECKING:
    from longscrape.storage.mongo import (
        PyMongoDocumentStore,
        PyMongoJobStore,
        PyMongoRecordStore,
    )

__all__ = [
    "InMemoryDocumentStore",
    "InMemoryJobStore",
    "InMemoryRecordStore",
    "CollisionPolicy",
    "DocumentRef",
    "DocumentStore",
    "PyMongoDocumentStore",
    "PyMongoJobStore",
    "PyMongoRecordStore",
    "RecordRef",
    "RecordSink",
    "RecordStore",
]


def __getattr__(name: str):
    if name not in {"PyMongoDocumentStore", "PyMongoJobStore", "PyMongoRecordStore"}:
        raise AttributeError(name)
    return getattr(import_module("longscrape.storage.mongo"), name)
