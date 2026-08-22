import asyncio
from collections.abc import AsyncIterable, AsyncIterator

from longscrape_core._json import JsonObject
from longscrape_core.context import PipelineContext
from longscrape_core.models import (
    Document,
    InputUrl,
    Job,
    JobLease,
    JobSpec,
    Record,
)


class RecordingWorkController:
    def __init__(self) -> None:
        self.jobs: list[Job] = []
        self.checkpoints: list[tuple[JobLease, JsonObject, float | None]] = []

    async def enqueue(
        self, spec: JobSpec, *, parent: Job | None = None
    ) -> tuple[Job, bool]:
        job = Job(
            spec,
            parent_id=parent.id if parent else None,
            root_id=parent.root_id if parent else None,
        )
        self.jobs.append(job)
        return job, True

    async def checkpoint(
        self,
        lease: JobLease,
        data: JsonObject,
        *,
        progress: float | None = None,
    ) -> None:
        self.checkpoints.append((lease, data, progress))


class ExampleFetcher:
    async def fetch(self, job: Job, context: PipelineContext) -> Document:
        assert isinstance(job.input, InputUrl)
        await context.submit_child(
            job,
            JobSpec(
                "fetch-url",
                InputUrl("https://example.com/next"),
                metadata={"source": job.input.url},
            ),
        )
        return Document(url=job.input.url, content=b"<title>Example</title>")


class ExampleExtractor:
    async def extract(
        self, document: Document, job: Job, context: PipelineContext
    ) -> AsyncIterator[Record[dict[str, str]]]:
        yield Record(kind=job.kind, data={"url": document.url})


class AddSourceTransformer:
    def transform(
        self,
        records: AsyncIterable[Record[dict[str, str]]],
        job: Job,
        context: PipelineContext,
    ) -> AsyncIterator[Record[dict[str, str]]]:
        async def transformed() -> AsyncIterator[Record[dict[str, str]]]:
            async for record in records:
                yield Record(
                    kind=record.kind,
                    data={**record.data, "source": "core-test"},
                )

        return transformed()


def test_pipeline_contracts_support_one_document_and_child_jobs() -> None:
    async def run() -> tuple[list[Record[dict[str, str]]], list[Job]]:
        root = Job(JobSpec("article", InputUrl("https://example.com/start")))
        work = RecordingWorkController()
        context = PipelineContext(work=work)
        document = await ExampleFetcher().fetch(root, context)
        records = ExampleExtractor().extract(document, root, context)
        transformed = AddSourceTransformer().transform(records, root, context)
        return [record async for record in transformed], work.jobs

    records, submitted = asyncio.run(run())

    assert [(record.kind, record.data) for record in records] == [
        ("article", {"url": "https://example.com/start", "source": "core-test"})
    ]
    assert len(submitted) == 1
    assert submitted[0].parent_id is not None
    assert submitted[0].root_id == submitted[0].parent_id
