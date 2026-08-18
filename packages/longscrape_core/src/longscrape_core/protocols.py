from collections.abc import AsyncIterable
from typing import Protocol

from longscrape_core.context import PipelineContext
from longscrape_core.models import Document, Job, Record


# Pipeline protocols
class Fetcher(Protocol):
    def fetch(
        self, job: Job, context: PipelineContext | None = None
    ) -> AsyncIterable[Document]: ...


class Extractor(Protocol):
    def extract(
        self,
        documents: AsyncIterable[Document],
        job: Job,
        context: PipelineContext | None = None,
    ) -> AsyncIterable[Record]: ...


# NOTE: Earlier versions of api also exposed separate sink api with write method that
# sat at the end of pipelines. But transformer that emits 0 items at the end effectively
# provides same terminating behavior for both native longscrape usage and future
# longscrape-scrapy integration.
class Transformer(Protocol):
    def transform(
        self,
        records: AsyncIterable[Record],
        job: Job,
        context: PipelineContext | None = None,
    ) -> AsyncIterable[Record]: ...


# Store protocols
# TODO: in future modify stores to return handle/capability instead of random key to
# make it easier to pass around via job queue (drastiq only accepts JSON serializable
# data thus this will become a hard requirment at some point)
# TODO: to better support reextract functionality in the future separate protocol
# for reading would be preferable as it could fetch all of the documents by kind
# and provide AsyncIterable which could simply plug into existing pipeline
# existing downstream of fetchers
class DocumentStore(Protocol):
    async def store(self, document: Document, *, key: str | None = None) -> None: ...
    async def load(self, key: str) -> Document | None: ...


class RecordStore(Protocol):
    async def store(self, record: Record) -> None: ...
    async def get(self, key: str) -> Record | None: ...


# TODO: In future consider buffered sink to support batched writes instead of spamming
# the database with small records
class RecordSink(Transformer):
    def __init__(self, store: RecordStore) -> None:
        self._store = store

    async def transform(
        self,
        records: AsyncIterable[Record],
        job: Job,
        context: PipelineContext | None = None,
    ) -> AsyncIterable[Record]:
        async for record in records:
            await self._store.store(record)

        if False:
            yield
