from __future__ import annotations

import re
from typing import Any

from longscrape_core import Document, Record
from pymongo import AsyncMongoClient
from pymongo.asynchronous.collection import AsyncCollection

_INVALID_COLLECTION_CHARS = re.compile(r"[^a-zA-Z0-9_-]+")


def _record_collection_name(kind: str, prefix: str) -> str:
    safe_kind = _INVALID_COLLECTION_CHARS.sub("_", kind).strip("_")
    if not safe_kind:
        raise ValueError("Record.kind must contain a collection-safe character")
    return f"{prefix}{safe_kind}"


class PyMongoDocumentStore:
    """Store every generic document in one MongoDB collection, keyed by URL."""

    def __init__(
        self,
        uri: str | None = None,
        *,
        database: str = "longscrape",
        collection: str = "documents",
        mongo_collection: AsyncCollection | None = None,
    ) -> None:
        if mongo_collection is not None:
            self._collection = mongo_collection
            self._client: AsyncMongoClient | None = None
        elif uri is None:
            raise ValueError("uri is required when mongo_collection is not provided")
        else:
            self._client = AsyncMongoClient(uri)
            self._collection = self._client[database][collection]

    async def save(self, document: Document) -> None:
        await self._collection.replace_one(
            {"_id": document.url},
            {
                "_id": document.url,
                "content": document.content,
                "content_type": document.content_type,
                "status": document.status,
                "headers": document.headers,
                "fetched_at": document.fetched_at,
                "metadata": document.metadata,
            },
            upsert=True,
        )

    async def get(self, key: str) -> Document | None:
        value = await self._collection.find_one({"_id": key})
        if value is None:
            return None
        return Document(
            url=value["_id"],
            content=bytes(value["content"]),
            content_type=value.get("content_type", "text/html"),
            status=value.get("status", 200),
            headers=dict(value.get("headers", {})),
            fetched_at=value["fetched_at"],
            metadata=dict(value.get("metadata", {})),
        )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()


class PyMongoRecordStore:
    """Store each record kind in its own MongoDB collection."""

    def __init__(
        self,
        uri: str | None = None,
        *,
        database: str = "longscrape",
        collection_prefix: str = "records_",
        mongo_database: Any | None = None,
    ) -> None:
        if mongo_database is not None:
            self._database = mongo_database
            self._client: AsyncMongoClient | None = None
        elif uri is None:
            raise ValueError("uri is required when mongo_database is not provided")
        else:
            self._client = AsyncMongoClient(uri)
            self._database = self._client[database]
        self._collection_prefix = collection_prefix

    def collection_for(self, kind: str) -> AsyncCollection:
        return self._database[_record_collection_name(kind, self._collection_prefix)]

    async def save(self, record: Record) -> None:
        await self.collection_for(record.kind).insert_one(
            {
                "kind": record.kind,
                "data": record.data,
                "source_url": record.source_url,
                "document_url": record.document.url if record.document else None,
                "metadata": record.metadata,
                "created_at": record.created_at,
            }
        )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
