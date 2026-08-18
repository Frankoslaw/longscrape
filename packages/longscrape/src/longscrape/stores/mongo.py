from longscrape_core import Document, Record
from longscrape_core.protocols import DocumentStore, RecordStore
from pymongo import AsyncMongoClient
from pymongo.asynchronous.collection import AsyncCollection


class PyMongoDocumentStore(DocumentStore):
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
        else:
            if uri is None:
                raise ValueError(
                    "uri is required when mongo_collection is not provided"
                )
            self._client = AsyncMongoClient(uri)
            self._collection = self._client[database][collection]

    async def start(self) -> None:
        """Match the lifecycle used by other crawler resources."""

    async def stop(self) -> None:
        await self.close()

    async def store(self, document: Document, *, key: str | None = None) -> None:
        cache_key = document.url if key is None else key
        payload = {
            "key": cache_key,
            "url": document.url,
            "content": document.content,
            "content_type": document.content_type,
            "status": document.status,
            "headers": document.headers,
            "fetched_at": document.fetched_at,
        }
        await self._collection.replace_one({"key": cache_key}, payload, upsert=True)

    async def load(self, key: str) -> Document | None:
        doc = await self._collection.find_one({"key": key})
        # Documents written before cache keys were introduced were addressed by
        # their final URL. Retain that read path so existing caches can be
        # re-extracted after URL canonicalization.
        if doc is None:
            doc = await self._collection.find_one({"url": key})
        if doc is None:
            return None
        return Document(
            url=doc["url"],
            content=doc["content"],
            content_type=doc.get("content_type", "text/html"),
            status=doc.get("status", 200),
            headers=doc.get("headers", {}),
            fetched_at=doc["fetched_at"],
        )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()


class PyMongoRecordStore(RecordStore):
    def __init__(
        self,
        kind: str,
        uri: str | None = None,
        *,
        database: str = "longscrape",
        mongo_collection: AsyncCollection | None = None,
    ) -> None:
        if not kind:
            raise ValueError("kind must not be empty")
        if mongo_collection is not None:
            self._collection = mongo_collection
            self._client: AsyncMongoClient | None = None
        else:
            if uri is None:
                raise ValueError(
                    "uri is required when mongo_collection is not provided"
                )
            self._client = AsyncMongoClient(uri)
            self._collection = self._client[database][kind]

    async def store(self, record: Record) -> None:
        await self._collection.replace_one(
            {"_id": record.hash},
            {
                "_id": record.hash,
                "kind": record.kind,
                "data": record.data,
                "created_at": record.created_at,
            },
            upsert=True,
        )

    async def get(self, key: str) -> Record | None:
        record = await self._collection.find_one({"_id": key})
        if record is None:
            return None
        return Record(
            kind=record["kind"], data=record["data"], created_at=record["created_at"]
        )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
