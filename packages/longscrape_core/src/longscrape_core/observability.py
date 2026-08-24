"""Execution-neutral observation helpers for core stage protocols."""

import logging
from collections.abc import AsyncIterable, AsyncIterator, Iterable
from typing import Protocol, TypeVar

from longscrape_core.context import Context
from longscrape_core.failures import PipelineFailure, PipelineStage, StageExecutionError
from longscrape_core.models import Document, FetchInput, Record
from longscrape_core.protocols import Extractor, Fetcher, Transformer


class StageObserver(Protocol):
    """Marker protocol; callbacks receive only generic stage information."""


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
    context: Context,
    *,
    observers: Iterable[StageObserver] = (),
) -> AsyncIterator[T]:
    await _notify(observers, "on_stage_started", stage, context)
    try:
        async for item in items:
            yield item
    except Exception as error:
        if isinstance(error, StageExecutionError):
            raise
        failure = PipelineFailure(stage, error, context)
        await _notify(observers, "on_stage_failed", failure)
        raise StageExecutionError(failure) from error
    else:
        await _notify(observers, "on_stage_succeeded", stage, context)


def observe_fetcher(fetcher: Fetcher, *observers: StageObserver) -> Fetcher:
    class ObservedFetcher:
        async def fetch(self, fetch_input: FetchInput, context: Context) -> Document:
            await _notify(observers, "on_stage_started", PipelineStage.FETCH, context)
            try:
                document = await fetcher.fetch(fetch_input, context)
            except Exception as error:
                failure = PipelineFailure(PipelineStage.FETCH, error, context)
                await _notify(observers, "on_stage_failed", failure)
                raise StageExecutionError(failure) from error
            await _notify(observers, "on_stage_succeeded", PipelineStage.FETCH, context)
            return document

    return ObservedFetcher()


def observe_extractor[Out](
    extractor: Extractor[Out], *observers: StageObserver
) -> Extractor[Out]:
    class ObservedExtractor:
        def extract(
            self, document: Document, context: Context
        ) -> AsyncIterable[Record[Out]]:
            return observe_stage(
                extractor.extract(document, context),
                PipelineStage.EXTRACT,
                context,
                observers=observers,
            )

    return ObservedExtractor()


def observe_transformer[In, Out](
    transformer: Transformer[In, Out], *observers: StageObserver
) -> Transformer[In, Out]:
    class ObservedTransformer:
        def transform(
            self, records: AsyncIterable[Record[In]], context: Context
        ) -> AsyncIterable[Record[Out]]:
            return observe_stage(
                transformer.transform(records, context),
                PipelineStage.TRANSFORM,
                context,
                observers=observers,
            )

    return ObservedTransformer()
