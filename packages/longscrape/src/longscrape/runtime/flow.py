"""Pure, reusable stage composition with no worker or job dependency."""

from collections.abc import AsyncIterable, AsyncIterator, Callable, Iterable
from typing import Any, cast

from longscrape_core import (
    Context,
    Extractor,
    Fetcher,
    FetchInput,
    Record,
    StageObserver,
    Transformer,
    observe_extractor,
    observe_fetcher,
    observe_transformer,
)

type RecordFlow[T] = Callable[[FetchInput, Context], AsyncIterable[Record[T]]]

__all__ = ["Flow", "RecordFlow"]


class Flow:
    def __init__(self, *, observers: Iterable[StageObserver] = ()) -> None:
        self._observers = tuple(observers)

    def fetch(self, fetcher: Fetcher) -> _FetchedFlow:
        return _FetchedFlow(fetcher, self._observers)


class _FetchedFlow:
    def __init__(self, fetcher: Fetcher, observers: tuple[StageObserver, ...]) -> None:
        self._fetcher = fetcher
        self._observers = observers

    def extract[Out](self, extractor: Extractor[Out]) -> _RecordFlow[Out]:
        return _RecordFlow(self._fetcher, extractor, (), self._observers)


class _RecordFlow[T]:
    def __init__(
        self,
        fetcher: Fetcher,
        extractor: Extractor[Any],
        transformers: tuple[Transformer[Any, Any], ...],
        observers: tuple[StageObserver, ...],
    ) -> None:
        self._fetcher, self._extractor, self._transformers, self._observers = (
            fetcher,
            extractor,
            transformers,
            observers,
        )

    def transform[Out](self, transformer: Transformer[T, Out]) -> _RecordFlow[Out]:
        return _RecordFlow(
            self._fetcher,
            self._extractor,
            (*self._transformers, transformer),
            self._observers,
        )

    def build(self) -> RecordFlow[T]:
        fetcher, extractor, transformers, observers = (
            self._fetcher,
            self._extractor,
            self._transformers,
            self._observers,
        )

        async def run(
            fetch_input: FetchInput, context: Context
        ) -> AsyncIterator[Record[T]]:
            document = await observe_fetcher(fetcher, *observers).fetch(
                fetch_input, context
            )
            records: AsyncIterable[Record[Any]] = observe_extractor(
                extractor, *observers
            ).extract(document, context)
            for transformer in transformers:
                records = observe_transformer(transformer, *observers).transform(
                    records, context
                )
            async for record in records:
                yield cast(Record[T], record)

        return run
