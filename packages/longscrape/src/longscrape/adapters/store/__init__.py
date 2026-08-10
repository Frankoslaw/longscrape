from importlib import import_module

__all__ = ["InMemoryRawEntryStore", "PyMongoRawEntryStore"]

_ADAPTERS = {
    "InMemoryRawEntryStore": "longscrape.adapters.store.in_memory",
    "PyMongoRawEntryStore": "longscrape.adapters.store.raw_entry",
}


def __getattr__(name: str):
    try:
        module_name = _ADAPTERS[name]
    except KeyError as error:
        raise AttributeError(name) from error
    return getattr(import_module(module_name), name)
