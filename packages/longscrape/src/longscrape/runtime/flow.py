"""Small, reusable job flows built from the core stage protocols."""

from collections.abc import AsyncIterable, AsyncIterator, Callable, Iterable
from typing import Any, cast

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

type RecordFlow[T] = Callable[[Job], AsyncIterable[Record[T]]]

__all__ = ["Flow", "RecordFlow"]


class Flow:
    """Start an immutable, optionally typed linear pipeline builder.

    Record types are inferred from the extractor and carried through each
    transformer. Untyped stages remain supported as ``Any``-typed stages.
    """

    def __init__(
        self,
        context: PipelineContext | None = None,
        *,
        observers: Iterable[StageObserver] = (),
    ) -> None:
        self._context = context
        self._observers = tuple(observers)

    def fetch(self, fetcher: Fetcher) -> _FetchedFlow:
        return _FetchedFlow(fetcher, self._context, self._observers)


class _FetchedFlow:
    def __init__(
        self,
        fetcher: Fetcher,
        context: PipelineContext | None,
        observers: tuple[StageObserver, ...],
    ) -> None:
        self._fetcher = fetcher
        self._context = context
        self._observers = observers

    def extract[Out](self, extractor: Extractor[Out]) -> _RecordFlow[Out]:
        return _RecordFlow(self._fetcher, extractor, (), self._context, self._observers)


class _RecordFlow[T]:
    def __init__(
        self,
        fetcher: Fetcher,
        extractor: Extractor[Any],
        transformers: tuple[Transformer[Any, Any], ...],
        context: PipelineContext | None,
        observers: tuple[StageObserver, ...],
    ) -> None:
        self._fetcher = fetcher
        self._extractor = extractor
        self._transformers = transformers
        self._context = context
        self._observers = observers

    def transform[Out](self, transformer: Transformer[T, Out]) -> _RecordFlow[Out]:
        return _RecordFlow(
            self._fetcher,
            self._extractor,
            (*self._transformers, transformer),
            self._context,
            self._observers,
        )

    def build(self) -> RecordFlow[T]:
        fetcher = self._fetcher
        extractor = self._extractor
        transformers = self._transformers
        context = self._context
        observers = self._observers

        async def run(job: Job) -> AsyncIterator[Record[T]]:
            pipeline_context = context or PipelineContext(job)
            pipeline_context.job = job
            document = await observe_fetcher(fetcher, *observers).fetch(
                job.input, pipeline_context
            )
            records: AsyncIterable[Record[Any]] = observe_extractor(
                extractor, *observers
            ).extract(document, pipeline_context)
            for transformer in transformers:
                records = observe_transformer(transformer, *observers).transform(
                    records, pipeline_context
                )
            async for record in records:
                yield cast(Record[T], record)

        return run
