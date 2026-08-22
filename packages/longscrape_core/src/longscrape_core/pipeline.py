"""The seven fundamental pipeline contracts."""

from collections.abc import AsyncIterable
from typing import Protocol

from longscrape_core.context import PipelineContext
from longscrape_core.models import Document, Job, Record


class Fetcher(Protocol):
    async def fetch(self, job: Job, context: PipelineContext) -> Document: ...


class Extractor[Out](Protocol):
    def extract(
        self, document: Document, job: Job, context: PipelineContext
    ) -> AsyncIterable[Record[Out]]: ...


class Transformer[In, Out](Protocol):
    def transform(
        self,
        records: AsyncIterable[Record[In]],
        job: Job,
        context: PipelineContext,
    ) -> AsyncIterable[Record[Out]]: ...


class Sink[In](Protocol):
    async def sink(
        self,
        records: AsyncIterable[Record[In]],
        job: Job,
        context: PipelineContext,
    ) -> None: ...
