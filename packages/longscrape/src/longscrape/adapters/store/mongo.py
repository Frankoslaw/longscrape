from longscrape_core import Document
from longscrape_core.ports import DocumentStore
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

    async def store(self, document: Document) -> None:
        payload = {
            "_id": document.url,
            "url": document.url,
            "content": document.content,
            "content_type": document.content_type,
            "status": document.status,
            "headers": document.headers,
            "fetched_at": document.fetched_at,
        }
        await self._collection.replace_one({"_id": document.url}, payload, upsert=True)

    async def load(self, key: str) -> Document | None:
        doc = await self._collection.find_one({"_id": key})
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
