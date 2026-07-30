from collections.abc import AsyncIterator, Mapping
from typing import Any
from uuid import UUID

from pymongo import AsyncMongoClient
from pymongo.asynchronous.collection import AsyncCollection

from longscrape.core.domain.pipeline import RawEntry


class PyMongoRawEntryStore:
    def __init__(
        self,
        uri: str | None = None,
        *,
        database: str = "longscrape",
        collection: str = "raw_entries",
        mongo_collection: AsyncCollection | None = None,
    ) -> None:
        if mongo_collection is not None:
            self._collection = mongo_collection
            self._client: AsyncMongoClient | None = None
        else:
            if uri is None:
                raise ValueError(
                    "uri is required when mongo_collection is not provided"
                )
            self._client = AsyncMongoClient(uri)
            self._collection = self._client[database][collection]

    async def start(self) -> None:
        """Match the lifecycle used by other crawler resources.

        PyMongo connects lazily, so there is nothing to open here.
        """

    async def stop(self) -> None:
        await self.close()

    async def get(self, task_hash: str) -> RawEntry | None:
        document = await self._collection.find_one({"_id": task_hash})
        if document is None:
            return None
        return self._raw_entry(document)

    async def entries(self) -> AsyncIterator[RawEntry]:
        async for document in self._collection.find({}):
            yield self._raw_entry(document)

    @staticmethod
    def _raw_entry(document: Mapping[str, Any]) -> RawEntry:
        return RawEntry(
            id=UUID(document["id"]),
            url=document["url"],
            content=document["content"],
            content_type=document["content_type"],
            status_code=document["status_code"],
            fetched_at=document["fetched_at"],
            kind=document.get("kind", "default"),
            query=document.get("query"),
        )

    async def put(self, cache_key: str, raw_entry: RawEntry) -> None:
        document = {
            "_id": cache_key,
            "id": str(raw_entry.id),
            "url": raw_entry.url,
            "content": raw_entry.content,
            "content_type": raw_entry.content_type,
            "status_code": raw_entry.status_code,
            "fetched_at": raw_entry.fetched_at,
            "kind": raw_entry.kind,
            "query": raw_entry.query,
        }
        await self._collection.replace_one({"_id": cache_key}, document, upsert=True)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
