from uuid import UUID

from bson import ObjectId
from longscrape_core import Document, Record
from pymongo import AsyncMongoClient
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import DuplicateKeyError

from longscrape.storage.models import (
    CollisionPolicy,
    DocumentRef,
    RecordRef,
    merge_records,
)
from longscrape.storage.protocols import DocumentStore, RecordStore
from longscrape.worker.models import Job, JobStatus, StoredJob
from longscrape.worker.protocols import JobStore


class PyMongoDocumentStore(DocumentStore):
    """Mongo document revisions queried by key and fetch time."""

    def __init__(
        self,
        uri: str | None = None,
        *,
        database: str = "longscrape",
        collection: str = "documents",
        mongo_collection: AsyncCollection | None = None,
    ) -> None:
        self._store = f"mongo:{database}.{collection}"
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

    async def put(
        self,
        document: Document,
        *,
        key: str,
        policy: CollisionPolicy = CollisionPolicy.NEW,
    ) -> DocumentRef:
        current = await self.latest(key)
        if policy is CollisionPolicy.MERGE:
            raise ValueError("documents cannot be merged")
        if current is not None and policy is CollisionPolicy.OVERWRITE:
            await self._collection.delete_many({"key": key})
        result = await self._collection.insert_one(
            {
                "key": key,
                "url": document.url,
                "content": document.content,
                "content_type": document.content_type,
                "status": document.status,
                "headers": dict(document.headers),
                "fetched_at": document.fetched_at,
            }
        )
        ref = DocumentRef(self._store, str(result.inserted_id))
        return ref

    async def get(self, ref: DocumentRef) -> Document:
        self._check_ref(ref)
        try:
            object_id = ObjectId(ref.value)
        except Exception as error:
            raise LookupError(f"invalid document ref {ref.value!r}") from error
        document = await self._collection.find_one({"_id": object_id})
        if document is None:
            raise LookupError(f"document ref {ref.value!r} does not exist")
        return Document(
            url=document["url"],
            content=document["content"],
            content_type=document.get("content_type", "text/html"),
            status=document.get("status", 200),
            headers=document.get("headers", {}),
            fetched_at=document["fetched_at"],
        )

    async def latest(self, key: str) -> DocumentRef | None:
        document = await self._collection.find_one(
            {"key": key}, sort=[("fetched_at", -1), ("_id", -1)]
        )
        return DocumentRef(self._store, str(document["_id"])) if document else None

    async def iter_latest(self):
        for key in await self._collection.distinct("key"):
            ref = await self.latest(key)
            if ref is not None:
                yield ref

    def _check_ref(self, ref: DocumentRef) -> None:
        if ref.store != self._store:
            raise LookupError(f"document ref belongs to {ref.store!r}, not this store")

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()


class PyMongoRecordStore(RecordStore):
    """Mongo record revisions queried by key and creation time."""

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
        self._store = f"mongo:{database}.{kind}"
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

    async def put(
        self,
        record: Record,
        *,
        key: str | None = None,
        policy: CollisionPolicy = CollisionPolicy.NEW,
    ) -> RecordRef:
        record_key = record.hash if key is None else key
        current = await self.latest(record_key)
        if current is not None:
            if policy is CollisionPolicy.MERGE:
                record = merge_records(await self.get(current), record)
            if policy is not CollisionPolicy.NEW:
                await self._collection.delete_many({"key": record_key})
        result = await self._collection.insert_one(
            {
                "key": record_key,
                "kind": record.kind,
                "data": record.data,
                "created_at": record.created_at,
            }
        )
        ref = RecordRef(self._store, str(result.inserted_id))
        return ref

    async def get(self, ref: RecordRef) -> Record:
        self._check_ref(ref)
        try:
            object_id = ObjectId(ref.value)
        except Exception as error:
            raise LookupError(f"invalid record ref {ref.value!r}") from error
        record = await self._collection.find_one({"_id": object_id})
        if record is None:
            raise LookupError(f"record ref {ref.value!r} does not exist")
        return Record(
            kind=record["kind"], data=record["data"], created_at=record["created_at"]
        )

    async def latest(self, key: str) -> RecordRef | None:
        record = await self._collection.find_one(
            {"key": key}, sort=[("created_at", -1), ("_id", -1)]
        )
        return RecordRef(self._store, str(record["_id"])) if record else None

    def _check_ref(self, ref: RecordRef) -> None:
        if ref.store != self._store:
            raise LookupError(f"record ref belongs to {ref.store!r}, not this store")

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()


class PyMongoJobStore(JobStore):
    """Mongo job state keyed by the stable job admission key."""

    def __init__(
        self,
        uri: str | None = None,
        *,
        database: str = "longscrape",
        collection: str = "jobs",
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

    async def register(self, job: Job, *, key: str | None = None) -> bool:
        job_key = job.hash if key is None else key
        try:
            await self._collection.insert_one(
                {
                    "_id": job_key,
                    "job_id": str(job.id),
                    "job": job.to_dict(),
                    "status": JobStatus.QUEUED.value,
                    "attempts": 0,
                    "error": None,
                }
            )
        except DuplicateKeyError:
            return False
        return True

    async def get(self, job_id: UUID) -> StoredJob:
        stored = await self._collection.find_one({"job_id": str(job_id)})
        if stored is None:
            raise LookupError(f"job {job_id} does not exist")
        return StoredJob(
            Job.from_dict(stored["job"]),
            key=stored["_id"],
            status=JobStatus(stored["status"]),
            attempts=stored["attempts"],
            error=stored.get("error"),
        )

    async def start(self, job_id: UUID) -> None:
        await self._update(
            job_id,
            {
                "$set": {"status": JobStatus.RUNNING.value, "error": None},
                "$inc": {"attempts": 1},
            },
        )

    async def succeed(self, job_id: UUID) -> None:
        await self._update(
            job_id, {"$set": {"status": JobStatus.SUCCEEDED.value, "error": None}}
        )

    async def fail(self, job_id: UUID, error: Exception) -> None:
        await self._update(
            job_id,
            {"$set": {"status": JobStatus.FAILED.value, "error": str(error)}},
        )

    async def _update(self, job_id: UUID, update: dict[str, object]) -> None:
        result = await self._collection.update_one({"job_id": str(job_id)}, update)
        if not result.matched_count:
            raise LookupError(f"job {job_id} does not exist")

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
