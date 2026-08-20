from importlib import import_module
from typing import TYPE_CHECKING

from longscrape.stores.in_memory import (
    InMemoryDocumentStore,
    InMemoryJobStore,
    InMemoryRecordStore,
)

if TYPE_CHECKING:
    from longscrape.stores.mongo import (
        PyMongoDocumentStore,
        PyMongoJobStore,
        PyMongoRecordStore,
    )

__all__ = [
    "InMemoryDocumentStore",
    "InMemoryJobStore",
    "InMemoryRecordStore",
    "PyMongoDocumentStore",
    "PyMongoJobStore",
    "PyMongoRecordStore",
]


def __getattr__(name: str):
    if name not in {"PyMongoDocumentStore", "PyMongoJobStore", "PyMongoRecordStore"}:
        raise AttributeError(name)
    return getattr(import_module("longscrape.stores.mongo"), name)
