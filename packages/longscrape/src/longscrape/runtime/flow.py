"""Small, reusable job flows built from the core stage protocols."""

from collections.abc import AsyncIterable, AsyncIterator, Callable, Iterable
from typing import Self

from longscrape_core import (
    Extractor,
    Fetcher,
    Job,
    PipelineContext,
    Record,
    StageObserver,
    Transformer,
    observe_extractor,
    observe_fetcher,
    observe_transformer,
)

type RecordFlow = Callable[[Job], AsyncIterable[Record]]

__all__ = ["Flow", "RecordFlow"]


class Flow:
    """Build a linear fetch/extract/transform flow bound to local context.

    A consumer such as ``RecordSink`` is a zero-output transformer, so built
    flows always return an ``AsyncIterable[Record]``.
    """

    def __init__(
        self,
        context: PipelineContext | None = None,
        *,
        observers: Iterable[StageObserver] = (),
    ) -> None:
        self._context = context
        self._observers = tuple(observers)
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

    def build(self) -> RecordFlow:
        self._require_records()
        assert self._fetcher is not None
        assert self._extractor is not None
        fetcher = self._fetcher
        extractor = self._extractor
        transformers = tuple(self._transformers)
        context = self._context
        observers = self._observers

        async def run(job: Job) -> AsyncIterator[Record]:
            documents = observe_fetcher(fetcher, *observers).fetch(job, context)
            records = observe_extractor(extractor, *observers).extract(
                documents, job, context
            )
            for transformer in transformers:
                records = observe_transformer(transformer, *observers).transform(
                    records, job, context
                )
            async for record in records:
                yield record

        return run

    def _require_records(self) -> None:
        if self._fetcher is None or self._extractor is None:
            raise ValueError("A flow requires fetch() followed by extract()")
