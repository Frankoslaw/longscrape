from importlib import import_module
from typing import TYPE_CHECKING

from longscrape.adapters.store.in_memory import InMemoryDocumentStore

if TYPE_CHECKING:
    from longscrape.adapters.store.mongo import PyMongoDocumentStore

__all__ = ["InMemoryDocumentStore", "PyMongoDocumentStore"]


def __getattr__(name: str):
    if name != "PyMongoDocumentStore":
        raise AttributeError(name)
    return import_module("longscrape.adapters.store.mongo").PyMongoDocumentStore
