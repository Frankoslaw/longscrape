"""Shared, selectable storage wiring for runnable examples.

By default examples connect to the MongoDB and Redis services from
``compose.dev.yml``. Set ``LONGSCRAPE_EXAMPLE_BACKEND=memory`` for a fully
process-local run.
"""

from __future__ import annotations

import inspect
import os
from dataclasses import dataclass

from longscrape.mongodb import PyMongoDocumentStore, PyMongoJobStore, PyMongoRecordStore
from longscrape.redis import RedisJobQueue
from longscrape_core import (
    DocumentStore,
    InMemoryDocumentStore,
    InMemoryJobQueue,
    InMemoryJobStore,
    InMemoryRecordStore,
    JobManager,
    JobStore,
    RecordStore,
)


@dataclass
class ExampleStores:
    jobs: JobStore
    queue: InMemoryJobQueue | RedisJobQueue
    documents: DocumentStore
    records: RecordStore
    manager: JobManager

    async def close(self) -> None:
        for store in (self.jobs, self.queue, self.documents, self.records):
            close = getattr(store, "close", None)
            if close is not None:
                await close()

    async def is_idle(self) -> bool:
        value = self.queue.is_empty()
        return await value if inspect.isawaitable(value) else value


def create_stores(*, max_retries: int = 2) -> ExampleStores:
    """Build the stores used by examples, defaulting to Compose services."""
    if os.getenv("LONGSCRAPE_EXAMPLE_BACKEND", "mongo") == "memory":
        jobs, queue = InMemoryJobStore(), InMemoryJobQueue()
        documents, records = InMemoryDocumentStore(), InMemoryRecordStore()
    else:
        mongo_url = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        jobs, queue = PyMongoJobStore(mongo_url), RedisJobQueue(redis_url)
        documents, records = (
            PyMongoDocumentStore(mongo_url),
            PyMongoRecordStore(mongo_url),
        )
    return ExampleStores(
        jobs,
        queue,
        documents,
        records,
        JobManager(jobs, queue, max_retries=max_retries),
    )
