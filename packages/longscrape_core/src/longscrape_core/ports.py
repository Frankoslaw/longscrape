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
