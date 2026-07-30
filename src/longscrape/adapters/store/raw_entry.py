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
        return RawEntry(
            id=UUID(document["id"]),
            task_hash=document.get("task_hash"),
            url=document["url"],
            content=document["content"],
            content_type=document["content_type"],
            status_code=document["status_code"],
            fetched_at=document["fetched_at"],
        )

    async def put(self, task_hash: str, raw_entry: RawEntry) -> None:
        document = {
            "_id": task_hash,
            "id": str(raw_entry.id),
            "task_hash": raw_entry.task_hash,
            "url": raw_entry.url,
            "content": raw_entry.content,
            "content_type": raw_entry.content_type,
            "status_code": raw_entry.status_code,
            "fetched_at": raw_entry.fetched_at,
        }
        await self._collection.replace_one({"_id": task_hash}, document, upsert=True)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
