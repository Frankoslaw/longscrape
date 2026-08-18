"""Small, reusable job flows built from the core stage protocols."""

from collections.abc import AsyncIterable, Callable
from typing import Self

from longscrape_core import (
    Extractor,
    Fetcher,
    Job,
    PipelineContext,
    Record,
    Transformer,
)

type RecordFlow = Callable[[Job], AsyncIterable[Record]]


class Flow:
    """Build a linear fetch/extract/transform flow bound to local context.

    A consumer such as ``RecordSink`` is a zero-output transformer, so built
    flows always return an ``AsyncIterable[Record]``.
    """

    def __init__(self, context: PipelineContext | None = None) -> None:
        self._context = context
        self._fetcher: Fetcher | None = None
        self._extractor: Extractor | None = None
        self._transformers: list[Transformer] = []

    def fetch(self, fetcher: Fetcher) -> Self:
        if self._fetcher is not None:
            raise ValueError("A flow can have only one fetcher")
        if self._extractor is not None:
            raise ValueError("fetch() must precede extract()")
        self._fetcher = fetcher
        return self

    def extract(self, extractor: Extractor) -> Self:
        if self._fetcher is None:
            raise ValueError("extract() requires fetch() first")
        if self._extractor is not None:
            raise ValueError("A flow can have only one extractor")
        self._extractor = extractor
        return self

    def transform(self, transformer: Transformer) -> Self:
        self._require_records()
        self._transformers.append(transformer)
        return self

    def consume(self, sink: Transformer) -> Self:
        return self.transform(sink)

    def build(self) -> RecordFlow:
        self._require_records()
        assert self._fetcher is not None
        assert self._extractor is not None
        fetcher = self._fetcher
        extractor = self._extractor
        transformers = tuple(self._transformers)
        context = self._context

        def run(job: Job) -> AsyncIterable[Record]:
            documents = fetcher.fetch(job, context)
            records = extractor.extract(documents, job, context)
            for transformer in transformers:
                records = transformer.transform(records, job, context)
            return records

        return run

    def _require_records(self) -> None:
        if self._fetcher is None or self._extractor is None:
            raise ValueError("A flow requires fetch() followed by extract()")
