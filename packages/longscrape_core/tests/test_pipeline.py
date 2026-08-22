import asyncio
from collections.abc import AsyncIterable, AsyncIterator

from longscrape_core.context import PipelineContext
from longscrape_core.models import Document, InputUrl, Job, Record


class ExampleFetcher:
    async def fetch(self, job: Job, context: PipelineContext) -> Document:
        assert isinstance(job.input, InputUrl)
        return Document(url=job.input.url, content=b"<title>Example</title>")


class ExampleExtractor:
    def extract(
        self, document: Document, job: Job, context: PipelineContext
    ) -> AsyncIterator[Record[dict[str, str]]]:
        async def extracted() -> AsyncIterator[Record[dict[str, str]]]:
            yield Record(job.kind, {"url": document.url})

        return extracted()


class AddSourceTransformer:
    def transform(
        self,
        records: AsyncIterable[Record[dict[str, str]]],
        job: Job,
        context: PipelineContext,
    ) -> AsyncIterator[Record[dict[str, str]]]:
        async def transformed() -> AsyncIterator[Record[dict[str, str]]]:
            async for record in records:
                yield Record(record.kind, {**record.data, "source": "core-test"})

        return transformed()


def test_stages_support_manual_composition_without_work_or_flow() -> None:
    async def run() -> list[Record[dict[str, str]]]:
        job = Job("article", InputUrl("https://example.com/start"))
        context = PipelineContext()
        document = await ExampleFetcher().fetch(job, context)
        records = ExampleExtractor().extract(document, job, context)
        transformed = AddSourceTransformer().transform(records, job, context)
        return [record async for record in transformed]

    records = asyncio.run(run())
    assert [(record.kind, record.data) for record in records] == [
        ("article", {"url": "https://example.com/start", "source": "core-test"})
    ]
