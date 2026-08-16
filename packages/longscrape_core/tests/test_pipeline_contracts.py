import asyncio
from collections.abc import AsyncIterable, AsyncIterator

from longscrape_core.domain import Document, InputUrl, Job, JobRequest, Record
from longscrape_core.ports import DISCARD_SUBMITTER, JobSubmitter


async def _collect(items: AsyncIterable[Record]) -> list[Record]:
    return [item async for item in items]


class CollectingSubmitter:
    def __init__(self) -> None:
        self.requests: list[JobRequest] = []

    async def submit(self, request: JobRequest) -> None:
        self.requests.append(request)


class ExampleFetcher:
    async def fetch(
        self, job: Job, submitter: JobSubmitter = DISCARD_SUBMITTER
    ) -> AsyncIterator[Document]:
        assert isinstance(job.input, InputUrl)
        await submitter.submit(
            JobRequest(
                kind="fetch-url",
                input=InputUrl("https://example.com/next"),
                context={"source": job.input.url},
            )
        )
        yield Document(url=job.input.url, content=b"<title>Example</title>")


class ExampleExtractor:
    async def extract(
        self,
        documents: AsyncIterable[Document],
        job: Job,
        submitter: JobSubmitter = DISCARD_SUBMITTER,
    ) -> AsyncIterator[Record]:
        async for document in documents:
            yield Record(kind=job.kind, data={"url": document.url})


class AddSourceTransformer:
    async def transform(
        self,
        records: AsyncIterable[Record],
        job: Job,
        submitter: JobSubmitter = DISCARD_SUBMITTER,
    ) -> AsyncIterator[Record]:
        async for record in records:
            yield Record(kind=record.kind, data={**record.data, "source": "core-test"})


def test_pipeline_stages_stream_records_and_submit_follow_up_jobs() -> None:
    async def run() -> tuple[list[Record], list[JobRequest]]:
        job = Job(kind="article", input=InputUrl("https://example.com/start"))
        submitter = CollectingSubmitter()
        documents = ExampleFetcher().fetch(job, submitter)
        records = ExampleExtractor().extract(documents, job, submitter)
        transformed = AddSourceTransformer().transform(records, job, submitter)
        return await _collect(transformed), submitter.requests

    records, submitted = asyncio.run(run())

    assert [(record.kind, record.data) for record in records] == [
        (
            "article",
            {"url": "https://example.com/start", "source": "core-test"},
        )
    ]
    assert submitted == [
        JobRequest(
            kind="fetch-url",
            input=InputUrl("https://example.com/next"),
            context={"source": "https://example.com/start"},
        )
    ]
