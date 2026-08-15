from typing import AsyncIterable, Protocol

from longscrape_core.domain import Document, Job, JobRequest, Record


# Job/Queue protocols
class JobSubmitter(Protocol):
    async def submit(self, request: JobRequest) -> None: ...


class NullJobSubmitter:
    async def submit(self, request: JobRequest) -> None:
        pass


DISCARD_SUBMITTER = NullJobSubmitter()


# Pipeline protocols
class Fetcher(Protocol):
    def fetch(
        self, job: Job, submitter: JobSubmitter = DISCARD_SUBMITTER
    ) -> AsyncIterable[Document]: ...


class Extractor(Protocol):
    def extract(
        self,
        documents: AsyncIterable[Document],
        job: Job,
        submitter: JobSubmitter = DISCARD_SUBMITTER,
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
        submitter: JobSubmitter = DISCARD_SUBMITTER,
    ) -> AsyncIterable[Record]: ...


# Store protocols
# TODO: in future modify stores to return handle/capability instead of random key to
# make it easier to pass around via job queue (drastiq only accepts JSON serializable
# data thus this will become a hard requirment at some point)
class DocumentStore(Protocol):
    async def store(self, document: Document) -> None: ...
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
        submitter: JobSubmitter = DISCARD_SUBMITTER,
    ) -> AsyncIterable[Record]:
        async for record in records:
            await self._store.store(record)

        if False:
            yield
