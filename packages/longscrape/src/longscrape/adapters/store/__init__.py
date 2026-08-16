from importlib import import_module
from typing import TYPE_CHECKING

from longscrape.adapters.store.in_memory import (
    InMemoryDocumentStore,
    InMemoryRecordStore,
)

if TYPE_CHECKING:
    from longscrape.adapters.store.mongo import PyMongoDocumentStore, PyMongoRecordStore

__all__ = [
    "InMemoryDocumentStore",
    "InMemoryRecordStore",
    "PyMongoDocumentStore",
    "PyMongoRecordStore",
]


def __getattr__(name: str):
    if name not in {"PyMongoDocumentStore", "PyMongoRecordStore"}:
        raise AttributeError(name)
    return getattr(import_module("longscrape.adapters.store.mongo"), name)
