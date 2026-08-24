"""Pure, reusable stage composition with no worker or job dependency."""

from collections.abc import AsyncIterable, AsyncIterator, Callable
from typing import Any, cast

from longscrape_core import (
    Context,
    Extractor,
    Fetcher,
    FetchInput,
    Record,
    Transformer,
)

type RecordFlow[T] = Callable[[FetchInput, Context], AsyncIterable[Record[T]]]

__all__ = ["Flow", "RecordFlow"]


class Flow:
    def fetch(self, fetcher: Fetcher) -> _FetchedFlow:
        return _FetchedFlow(fetcher)


class _FetchedFlow:
    def __init__(self, fetcher: Fetcher) -> None:
        self._fetcher = fetcher

    def extract[Out](self, extractor: Extractor[Out]) -> _RecordFlow[Out]:
        return _RecordFlow(self._fetcher, extractor, ())


class _RecordFlow[T]:
    def __init__(
        self,
        fetcher: Fetcher,
        extractor: Extractor[Any],
        transformers: tuple[Transformer[Any, Any], ...],
    ) -> None:
        self._fetcher, self._extractor, self._transformers = (
            fetcher,
            extractor,
            transformers,
        )

    def transform[Out](self, transformer: Transformer[T, Out]) -> _RecordFlow[Out]:
        return _RecordFlow(
            self._fetcher,
            self._extractor,
            (*self._transformers, transformer),
        )

    def build(self) -> RecordFlow[T]:
        fetcher, extractor, transformers = (
            self._fetcher,
            self._extractor,
            self._transformers,
        )

        async def run(
            fetch_input: FetchInput, context: Context
        ) -> AsyncIterator[Record[T]]:
            document = await fetcher.fetch(fetch_input, context)
            records: AsyncIterable[Record[Any]] = extractor.extract(document, context)
            for transformer in transformers:
                records = transformer.transform(records, context)
            async for record in records:
                yield cast(Record[T], record)

        return run
