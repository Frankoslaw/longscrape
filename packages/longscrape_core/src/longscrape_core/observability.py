"""Optional helpers for observing pipeline-stage execution.

These helpers decorate the core pipeline protocols; they do not prescribe a
runtime, logger, tracer, or retry implementation.
"""

import logging
from collections.abc import AsyncIterable, AsyncIterator, Iterable
from typing import Protocol, TypeVar

from longscrape_core.context import PipelineContext
from longscrape_core.failures import (
    PipelineFailure,
    PipelineStage,
    StageExecutionError,
)
from longscrape_core.models import Document, Job, Record
from longscrape_core.protocols import Extractor, Fetcher, Transformer


class StageObserver(Protocol):
    """An observer with any subset of the optional stage callbacks.

    Observers may implement ``on_stage_started``, ``on_stage_succeeded``,
    and/or ``on_stage_failed``. The dispatcher discovers each callback at
    runtime, so this marker protocol deliberately imposes no required method.
    """


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
    context: PipelineContext | None = None,
    *,
    observers: Iterable[StageObserver] = (),
) -> AsyncIterator[T]:
    """Add lifecycle callbacks and structured failure context to a stage."""
    observer_list = tuple(observers)
    await _notify(observer_list, "on_stage_started", stage, job, context)
    try:
        async for item in items:
            yield item
    except Exception as error:
        if isinstance(error, StageExecutionError):
            raise
        failure = PipelineFailure(stage, job, error, context)
        await _notify(observer_list, "on_stage_failed", failure)
        raise StageExecutionError(failure) from error
    else:
        await _notify(observer_list, "on_stage_succeeded", stage, job, context)


def observe_fetcher(fetcher: Fetcher, *observers: StageObserver) -> Fetcher:
    """Return a fetcher decorator that emits stage callbacks."""

    class ObservedFetcher:
        def fetch(
            self, job: Job, context: PipelineContext | None = None
        ) -> AsyncIterable[Document]:
            return observe_stage(
                fetcher.fetch(job, context),
                PipelineStage.FETCH,
                job,
                context,
                observers=observers,
            )

    return ObservedFetcher()


def observe_extractor(extractor: Extractor, *observers: StageObserver) -> Extractor:
    """Return an extractor decorator that emits stage callbacks."""

    class ObservedExtractor:
        def extract(
            self,
            documents: AsyncIterable[Document],
            job: Job,
            context: PipelineContext | None = None,
        ) -> AsyncIterable[Record]:
            return observe_stage(
                extractor.extract(documents, job, context),
                PipelineStage.EXTRACT,
                job,
                context,
                observers=observers,
            )

    return ObservedExtractor()


def observe_transformer(
    transformer: Transformer, *observers: StageObserver
) -> Transformer:
    """Return a transformer decorator that emits stage callbacks."""

    class ObservedTransformer:
        def transform(
            self,
            records: AsyncIterable[Record],
            job: Job,
            context: PipelineContext | None = None,
        ) -> AsyncIterable[Record]:
            return observe_stage(
                transformer.transform(records, job, context),
                PipelineStage.TRANSFORM,
                job,
                context,
                observers=observers,
            )

    return ObservedTransformer()
