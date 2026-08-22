"""Attach observation to individual stages without choosing a runtime."""

import logging
from collections.abc import AsyncIterable, AsyncIterator, Iterable
from typing import Protocol, TypeVar

from longscrape_core.context import PipelineContext
from longscrape_core.models import Document, Job, Record
from longscrape_core.pipeline import Extractor, Fetcher, Sink, Transformer

from longscrape.runtime.work import JobExecutor


class StageObserver(Protocol):
    """Marker protocol; callbacks are discovered independently at runtime."""


T = TypeVar("T")
logger = logging.getLogger("longscrape_core.observability")


async def _notify(
    observers: Iterable[StageObserver], method: str, *args: object
) -> None:
    for observer in observers:
        callback = getattr(observer, method, None)
        if callback is None:
            continue
        try:
            await callback(*args)
        except Exception:
            logger.exception("stage observer callback failed: callback=%s", method)


async def observe_stage(
    items: AsyncIterable[T],
    stage: PipelineStage,
    job: Job,
    context: PipelineContext,
    *,
    observers: Iterable[StageObserver] = (),
) -> AsyncIterator[T]:
    """Observe a stream while preserving its original exceptions."""
    observer_list = tuple(observers)
    await _notify(observer_list, "on_stage_started", stage, job, context)
    try:
        async for item in items:
            yield item
    except Exception as error:
        await _notify(
            observer_list,
            "on_stage_failed",
            PipelineFailure(stage, job, error, context),
        )
        raise StageExecutionError(
            PipelineFailure(stage, job, error, context)
        ) from error
    else:
        await _notify(observer_list, "on_stage_succeeded", stage, job, context)


def observe_fetcher(fetcher: Fetcher, *observers: StageObserver) -> Fetcher:
    class ObservedFetcher:
        async def fetch(self, job: Job, context: PipelineContext) -> Document:
            observer_list = tuple(observers)
            await _notify(
                observer_list, "on_stage_started", PipelineStage.FETCH, job, context
            )
            try:
                document = await fetcher.fetch(job, context)
            except Exception as error:
                await _notify(
                    observer_list,
                    "on_stage_failed",
                    PipelineFailure(PipelineStage.FETCH, job, error, context),
                )
                raise StageExecutionError(
                    PipelineFailure(PipelineStage.FETCH, job, error, context)
                ) from error
            await _notify(
                observer_list, "on_stage_succeeded", PipelineStage.FETCH, job, context
            )
            return document

    return ObservedFetcher()


def observe_extractor[Out](
    extractor: Extractor[Out], *observers: StageObserver
) -> Extractor[Out]:
    class ObservedExtractor:
        def extract(
            self, document: Document, job: Job, context: PipelineContext
        ) -> AsyncIterable[Record[Out]]:
            return observe_stage(
                extractor.extract(document, job, context),
                PipelineStage.EXTRACT,
                job,
                context,
                observers=observers,
            )

    return ObservedExtractor()


def observe_transformer[In, Out](
    transformer: Transformer[In, Out], *observers: StageObserver
) -> Transformer[In, Out]:
    class ObservedTransformer:
        def transform(
            self, records: AsyncIterable[Record[In]], job: Job, context: PipelineContext
        ) -> AsyncIterable[Record[Out]]:
            return observe_stage(
                transformer.transform(records, job, context),
                PipelineStage.TRANSFORM,
                job,
                context,
                observers=observers,
            )

    return ObservedTransformer()


def observe_sink[In](sink: Sink[In], *observers: StageObserver) -> Sink[In]:
    class ObservedSink:
        async def sink(
            self, records: AsyncIterable[Record[In]], job: Job, context: PipelineContext
        ) -> None:
            observer_list = tuple(observers)
            await _notify(
                observer_list, "on_stage_started", PipelineStage.SINK, job, context
            )
            try:
                await sink.sink(records, job, context)
            except Exception as error:
                await _notify(
                    observer_list,
                    "on_stage_failed",
                    PipelineFailure(PipelineStage.SINK, job, error, context),
                )
                raise
            await _notify(
                observer_list, "on_stage_succeeded", PipelineStage.SINK, job, context
            )

    return ObservedSink()


def observe_executor(executor: JobExecutor, *observers: StageObserver) -> JobExecutor:
    """Attach a job lifecycle boundary to any executor."""

    class ObservedExecutor:
        async def execute(self, job: Job, context: PipelineContext) -> None:
            observer_list = tuple(observers)
            await _notify(observer_list, "on_job_started", job, context)
            try:
                await executor.execute(job, context)
            except JobExecutionError as error:
                await _notify(observer_list, "on_job_failed", error.failure)
                raise
            except Exception as error:
                failure = PipelineFailure(PipelineStage.EXTRACT, job, error, context)
                await _notify(observer_list, "on_job_failed", failure)
                raise JobExecutionError(failure) from error
            await _notify(observer_list, "on_job_succeeded", job, context)

    return ObservedExecutor()
