from __future__ import annotations

import re
from typing import Any

from longscrape_core import (
    Document,
    DocumentRef,
    Job,
    JobRef,
    JobState,
    JobStatus,
    Record,
    RecordRef,
)
from pymongo import AsyncMongoClient, ReturnDocument
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

    async def save(self, document: Document) -> DocumentRef:
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
        return DocumentRef(document.url)

    async def get(self, ref: DocumentRef) -> Document | None:
        value = await self._collection.find_one({"_id": ref.value})
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

    async def save(self, record: Record) -> RecordRef:
        result = await self.collection_for(record.kind).insert_one(
            {
                "kind": record.kind,
                "data": record.data,
                "source_url": record.source_url,
                "document_ref": record.document_ref.value
                if record.document_ref
                else None,
                "metadata": record.metadata,
                "created_at": record.created_at,
            }
        )
        return RecordRef(str(result.inserted_id))

    async def get(self, ref: RecordRef) -> Record | None:
        from bson import ObjectId

        for collection in await self._database.list_collection_names():
            if not collection.startswith(self._collection_prefix):
                continue
            value = await self._database[collection].find_one(
                {"_id": ObjectId(ref.value)}
            )
            if value is not None:
                return Record(
                    kind=value["kind"],
                    data=dict(value["data"]),
                    source_url=value["source_url"],
                    document_ref=DocumentRef(value["document_ref"])
                    if value.get("document_ref")
                    else None,
                    metadata=dict(value.get("metadata", {})),
                    created_at=value["created_at"],
                )
        return None

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()


class PyMongoJobStore:
    """Durable job payload and lifecycle storage; it deliberately is not a queue."""

    def __init__(
        self,
        uri: str | None = None,
        *,
        database: str = "longscrape",
        collection: str = "jobs",
        mongo_collection: AsyncCollection | None = None,
    ) -> None:
        if mongo_collection is not None:
            self._collection, self._client = mongo_collection, None
        elif uri is None:
            raise ValueError("uri is required when mongo_collection is not provided")
        else:
            self._client = AsyncMongoClient(uri)
            self._collection = self._client[database][collection]

    async def save(self, job: Job) -> JobRef:
        await self._collection.update_one(
            {"_id": job.id.value},
            {
                "$setOnInsert": {
                    "job": job.to_dict(),
                    "state": JobState.PENDING.value,
                    "retry_count": 0,
                    "error": None,
                }
            },
            upsert=True,
        )
        return job.id

    async def get(self, ref: JobRef) -> Job | None:
        value = await self._collection.find_one({"_id": ref.value})
        return Job.from_dict(value["job"]) if value is not None else None

    async def get_status(self, ref: JobRef) -> JobStatus | None:
        value = await self._collection.find_one({"_id": ref.value})
        if value is None:
            return None
        return JobStatus(
            ref,
            JobState(value["state"]),
            value.get("retry_count", 0),
            value.get("error"),
        )

    async def set_status(
        self,
        ref: JobRef,
        state: JobState,
        *,
        retry_count: int | None = None,
        error: str | None = None,
    ) -> JobStatus:
        changes: dict[str, Any] = {"state": state.value, "error": error}
        if retry_count is not None:
            changes["retry_count"] = retry_count
        value = await self._collection.find_one_and_update(
            {"_id": ref.value}, {"$set": changes}, return_document=ReturnDocument.AFTER
        )
        if value is None:
            raise KeyError(f"Unknown job ref: {ref}")
        return JobStatus(
            ref,
            JobState(value["state"]),
            value.get("retry_count", 0),
            value.get("error"),
        )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
