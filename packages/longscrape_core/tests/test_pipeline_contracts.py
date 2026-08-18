import asyncio
from collections.abc import AsyncIterable, AsyncIterator

from longscrape_core.context import PipelineContext
from longscrape_core.models import Document, InputUrl, Job, JobRequest, Record


async def _collect(items: AsyncIterable[Record]) -> list[Record]:
    return [item async for item in items]


class CollectingSubmitter:
    def __init__(self) -> None:
        self.jobs: list[Job] = []

    async def submit_job(self, job: Job) -> None:
        self.jobs.append(job)


class ExampleFetcher:
    async def fetch(
        self, job: Job, context: PipelineContext | None = None
    ) -> AsyncIterator[Document]:
        assert isinstance(job.input, InputUrl)
        if context is None:
            raise RuntimeError("ExampleFetcher requires a PipelineContext")
        await context.submit_child(
            job,
            JobRequest(
                kind="fetch-url",
                input=InputUrl("https://example.com/next"),
                metadata={"source": job.input.url},
            ),
        )
        yield Document(url=job.input.url, content=b"<title>Example</title>")


class ExampleExtractor:
    async def extract(
        self,
        documents: AsyncIterable[Document],
        job: Job,
        context: PipelineContext | None = None,
    ) -> AsyncIterator[Record]:
        async for document in documents:
            yield Record(kind=job.kind, data={"url": document.url})


class AddSourceTransformer:
    async def transform(
        self,
        records: AsyncIterable[Record],
        job: Job,
        context: PipelineContext | None = None,
    ) -> AsyncIterator[Record]:
        async for record in records:
            yield Record(kind=record.kind, data={**record.data, "source": "core-test"})


def test_pipeline_stages_stream_records_and_submit_follow_up_jobs() -> None:
    async def run() -> tuple[list[Record], list[Job]]:
        job = Job(kind="article", input=InputUrl("https://example.com/start"))
        submitter = CollectingSubmitter()
        context = PipelineContext(submitter)
        documents = ExampleFetcher().fetch(job, context)
        records = ExampleExtractor().extract(documents, job, context)
        transformed = AddSourceTransformer().transform(records, job, context)
        return await _collect(transformed), submitter.jobs

    records, submitted = asyncio.run(run())

    assert [(record.kind, record.data) for record in records] == [
        (
            "article",
            {"url": "https://example.com/start", "source": "core-test"},
        )
    ]
    assert len(submitted) == 1
    child = submitted[0]
    assert child.kind == "fetch-url"
    assert child.input == InputUrl("https://example.com/next")
    assert child.metadata == {"source": "https://example.com/start"}
    assert child.parent_id is not None
    assert child.root_id == child.parent_id
