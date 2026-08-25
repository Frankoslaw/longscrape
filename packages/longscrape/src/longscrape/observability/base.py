"""Dependency-light observation scopes and stage wrappers."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Literal, Protocol, TypeVar

from longscrape.core import (
    Context,
    Document,
    Extractor,
    Fetcher,
    FetchInput,
    Record,
    Transformer,
)

type Scalar = str | int | float | bool
type EventKind = Literal[
    "scope.started", "scope.succeeded", "scope.failed", "scope.cancelled"
]


@dataclass(frozen=True)
class Event:
    kind: EventKind
    name: str
    scope_id: str
    parent_scope_id: str | None
    attributes: Mapping[str, Scalar]
    duration_ms: float | None = None
    error: BaseException | None = None


class EventSink(Protocol):
    def emit(self, event: Event) -> None: ...


@dataclass
class Scope:
    observer: Observer
    name: str
    scope_id: str
    parent_scope_id: str | None
    attributes: dict[str, Scalar]
    _started: float = field(default_factory=time.perf_counter)

    def bind(self, **attributes: Scalar) -> None:
        self.attributes.update(attributes)

    def set_input(self, **attributes: Scalar) -> None:
        self.bind(**{f"input.{key}": value for key, value in attributes.items()})

    def set_output(self, **attributes: Scalar) -> None:
        self.bind(**{f"output.{key}": value for key, value in attributes.items()})


_active_scope: ContextVar[Scope | None] = ContextVar(
    "longscrape_observation_scope", default=None
)


def current_scope() -> Scope | None:
    """Return the scope active in the current task, if any."""
    return _active_scope.get()


class Observer:
    """Dispatches lifecycle events and supplies inherited scope attributes."""

    def __init__(
        self,
        sinks: tuple[EventSink, ...] = (),
        attributes: Mapping[str, Scalar] = {},
    ) -> None:
        self._sinks = sinks
        self._attributes = dict(attributes)

    def bind(self, **attributes: Scalar) -> Observer:
        return type(self)(self._sinks, {**self._attributes, **attributes})

    @asynccontextmanager
    async def catch(self, name: str, /, **attributes: Scalar) -> AsyncIterator[Scope]:
        parent = current_scope()
        scope = Scope(
            self,
            name,
            str(uuid.uuid4()),
            parent.scope_id if parent else None,
            {**(parent.attributes if parent else {}), **self._attributes, **attributes},
        )
        token = _active_scope.set(scope)
        self._emit(
            Event(
                "scope.started",
                name,
                scope.scope_id,
                scope.parent_scope_id,
                dict(scope.attributes),
            )
        )
        try:
            yield scope
        except asyncio.CancelledError:
            self._terminal(scope, "scope.cancelled")
            raise
        except BaseException as error:
            self._terminal(scope, "scope.failed", error)
            raise
        else:
            self._terminal(scope, "scope.succeeded")
        finally:
            _active_scope.reset(token)

    def _terminal(
        self,
        scope: Scope,
        kind: EventKind,
        error: BaseException | None = None,
    ) -> None:
        self._emit(
            Event(
                kind,
                scope.name,
                scope.scope_id,
                scope.parent_scope_id,
                dict(scope.attributes),
                (time.perf_counter() - scope._started) * 1000,
                error,
            )
        )

    def _emit(self, event: Event) -> None:
        for sink in self._sinks:
            try:
                sink.emit(event)
            except Exception:
                logging.getLogger("longscrape.observability").exception(
                    "observation sink failed"
                )


NOOP = Observer()
_default_observer: Observer = NOOP


def get_observer() -> Observer:
    return _default_observer


def set_observer(observer: Observer) -> Observer:
    global _default_observer
    _default_observer = observer
    return observer


def observe_fetch(fetcher: Fetcher, *, observer: Observer | None = None) -> Fetcher:
    active = observer or get_observer()

    class ObservedFetcher:
        async def fetch(self, fetch_input: FetchInput, context: Context) -> Document:
            async with active.catch(
                "fetch", stage="fetch", input_type=type(fetch_input).__name__
            ) as scope:
                document = await fetcher.fetch(fetch_input, context)
                scope.set_output(
                    url=document.url,
                    status=document.status,
                    bytes=len(document.content),
                )
                return document

    return ObservedFetcher()


def observe_extractor[Out](
    extractor: Extractor[Out], *, observer: Observer | None = None
) -> Extractor[Out]:
    active = observer or get_observer()

    class ObservedExtractor:
        def extract(
            self, document: Document, context: Context
        ) -> AsyncIterable[Record[Out]]:
            async def records() -> AsyncIterator[Record[Out]]:
                count = 0
                async with active.catch(
                    "extract", stage="extract", document_url=document.url
                ) as scope:
                    async for record in extractor.extract(document, context):
                        count += 1
                        yield record
                    scope.set_output(record_count=count)

            return records()

    return ObservedExtractor()


def observe_transformer[In, Out](
    transformer: Transformer[In, Out], *, observer: Observer | None = None
) -> Transformer[In, Out]:
    active = observer or get_observer()

    class ObservedTransformer:
        def transform(
            self, records: AsyncIterable[Record[In]], context: Context
        ) -> AsyncIterable[Record[Out]]:
            async def transformed() -> AsyncIterator[Record[Out]]:
                count = 0
                async with active.catch("transform", stage="transform") as scope:
                    async for record in transformer.transform(records, context):
                        count += 1
                        yield record
                    scope.set_output(record_count=count)

            return transformed()

    return ObservedTransformer()


T = TypeVar("T")


def observe_flow[T](
    flow: Callable[[FetchInput, Context], AsyncIterable[Record[T]]],
    *,
    observer: Observer | None = None,
    name: str = "flow",
) -> Callable[[FetchInput, Context], AsyncIterable[Record[T]]]:
    active = observer or get_observer()

    def observed(fetch_input: FetchInput, context: Context) -> AsyncIterable[Record[T]]:
        async def records() -> AsyncIterator[Record[T]]:
            count = 0
            async with active.catch(
                name, flow=name, input_type=type(fetch_input).__name__
            ) as scope:
                async for record in flow(fetch_input, context):
                    count += 1
                    yield record
                scope.set_output(record_count=count)

        return records()

    return observed


def observe_job[JobT, ResultT](
    run: Callable[[JobT], Awaitable[ResultT]],
    *,
    observer: Observer | None = None,
    attributes: Callable[[JobT], Mapping[str, Scalar]] = lambda _job: {},
) -> Callable[[JobT], Awaitable[ResultT]]:
    active = observer or get_observer()

    async def observed(job: JobT) -> ResultT:
        async with active.catch("job", **dict(attributes(job))):
            return await run(job)

    return observed
