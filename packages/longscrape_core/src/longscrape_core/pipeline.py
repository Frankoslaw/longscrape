"""The seven fundamental pipeline contracts."""

from collections.abc import AsyncIterable
from typing import Protocol

from longscrape_core.context import PipelineContext
from longscrape_core.models import Document, JobInput, Record


class Fetcher(Protocol):
    async def fetch(self, input: JobInput, context: PipelineContext) -> Document: ...


class Extractor[Out](Protocol):
    def extract(
        self, document: Document, context: PipelineContext
    ) -> AsyncIterable[Record[Out]]: ...


class Transformer[In, Out](Protocol):
    def transform(
        self,
        records: AsyncIterable[Record[In]],
        context: PipelineContext,
    ) -> AsyncIterable[Record[Out]]: ...


class Sink[In](Protocol):
    async def sink(
        self,
        records: AsyncIterable[Record[In]],
        context: PipelineContext,
    ) -> None: ...
