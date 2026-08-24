from collections.abc import AsyncIterable
from typing import Any, Callable, Never, Protocol

from longscrape_core.context import Context
from longscrape_core.models import (
    CollisionPolicy,
    Document,
    DocumentRef,
    FetchInput,
    Record,
    RecordRef,
)


class Fetcher(Protocol):
    async def fetch(self, fetch_input: FetchInput, context: Context) -> Document: ...


class Extractor[Out](Protocol):
    def extract(
        self, document: Document, context: Context
    ) -> AsyncIterable[Record[Out]]: ...


class Transformer[In, Out](Protocol):
    def transform(
        self, records: AsyncIterable[Record[In]], context: Context
    ) -> AsyncIterable[Record[Out]]: ...


class DocumentStore(Protocol):
    async def put(
        self,
        document: Document,
        *,
        key: str,
        policy: CollisionPolicy = CollisionPolicy.NEW,
    ) -> DocumentRef: ...
    async def get(self, ref: DocumentRef) -> Document: ...
    async def latest(self, key: str) -> DocumentRef | None: ...
    def iter_latest(self) -> AsyncIterable[DocumentRef]: ...


class RecordStore(Protocol):
    async def put(
        self,
        record: Record[Any],
        *,
        key: str | None = None,
        policy: CollisionPolicy = CollisionPolicy.NEW,
    ) -> RecordRef: ...
    async def get(self, ref: RecordRef) -> Record[Any]: ...
    async def latest(self, key: str) -> RecordRef | None: ...


class RecordSink[In](Transformer[In, Never]):
    """Persist records without depending on any worker/job identity."""

    def __init__(
        self,
        store: RecordStore,
        *,
        key: Callable[[Record[In]], str] | None = None,
        policy: CollisionPolicy = CollisionPolicy.NEW,
    ) -> None:
        self._store = store
        self._key = key
        self._policy = policy

    async def transform(
        self, records: AsyncIterable[Record[In]], context: Context
    ) -> AsyncIterable[Record[Never]]:
        async for record in records:
            await self._store.put(
                record,
                key=self._key(record) if self._key is not None else None,
                policy=self._policy,
            )
        if False:
            yield
