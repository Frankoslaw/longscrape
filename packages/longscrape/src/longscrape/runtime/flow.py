"""Small, reusable job flows built from the core stage protocols."""

from collections.abc import AsyncIterable, AsyncIterator, Callable, Iterable
from typing import Any, Never, cast

from longscrape_core import (
    Extractor,
    Fetcher,
    Job,
    JobExecutionError,
    JobExecutor,
    PipelineContext,
    Record,
    Sink,
    StageExecutionError,
    StageObserver,
    Transformer,
    observe_extractor,
    observe_fetcher,
    observe_transformer,
)

type RecordFlow[T] = Callable[[Job], AsyncIterable[Record[T]]]

__all__ = ["Flow", "FlowExecutor", "RecordFlow"]


class FlowExecutor(JobExecutor):
    """Execute a linear core flow behind the common worker boundary."""

    def __init__(
        self,
        fetcher: Fetcher,
        extractor: Extractor[Any],
        *,
        transformers: Iterable[Transformer[Any, Any]] = (),
        sink: Sink[Any] | None = None,
    ) -> None:
        self._fetcher = fetcher
        self._extractor = extractor
        self._transformers = tuple(transformers)
        self._sink = sink

    async def execute(self, job: Job, context: PipelineContext) -> None:
        from longscrape_core import PipelineFailure, PipelineStage

        try:
            document = await self._fetcher.fetch(job, context)
        except StageExecutionError as error:
            raise JobExecutionError(error.failure) from error
        except Exception as error:
            raise JobExecutionError(
                PipelineFailure(PipelineStage.FETCH, job, error, context)
            ) from error
        try:
            records: AsyncIterable[Record[Any]] = self._extractor.extract(
                document, job, context
            )
            for transformer in self._transformers:
                records = transformer.transform(records, job, context)
            if self._sink is not None:
                await self._sink.sink(records, job, context)
            else:
                async for _ in records:
                    pass
        except StageExecutionError as error:
            raise JobExecutionError(error.failure) from error
        except Exception as error:
            raise JobExecutionError(
                PipelineFailure(PipelineStage.EXTRACT, job, error, context)
            ) from error


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

    def sink(self, sink: Sink[T]) -> _SinkFlow[T]:
        return _SinkFlow(
            self._fetcher,
            self._extractor,
            self._transformers,
            sink,
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
            documents = observe_fetcher(fetcher, *observers).fetch(job, context)
            records: AsyncIterable[Record[Any]] = observe_extractor(
                extractor, *observers
            ).extract(documents, job, context)
            for transformer in transformers:
                records = observe_transformer(transformer, *observers).transform(
                    records, job, context
                )
            async for record in records:
                yield cast(Record[T], record)

        return run


class _SinkFlow[T]:
    def __init__(
        self,
        fetcher: Fetcher,
        extractor: Extractor[Any],
        transformers: tuple[Transformer[Any, Any], ...],
        sink: Sink[T],
        context: PipelineContext | None,
        observers: tuple[StageObserver, ...],
    ) -> None:
        self._fetcher = fetcher
        self._extractor = extractor
        self._transformers = transformers
        self._sink = sink
        self._context = context
        self._observers = observers

    def build(self) -> RecordFlow[Never]:
        fetcher = self._fetcher
        extractor = self._extractor
        transformers = self._transformers
        sink = self._sink
        context = self._context
        observers = self._observers

        async def run(job: Job) -> AsyncIterator[Record[Never]]:
            documents = observe_fetcher(fetcher, *observers).fetch(job, context)
            records: AsyncIterable[Record[Any]] = observe_extractor(
                extractor, *observers
            ).extract(documents, job, context)
            for transformer in transformers:
                records = observe_transformer(transformer, *observers).transform(
                    records, job, context
                )
            await sink.sink(cast(AsyncIterable[Record[T]], records), job, context)
            if False:
                yield

        return run
