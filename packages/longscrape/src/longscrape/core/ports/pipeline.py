from collections.abc import AsyncIterator
from typing import Protocol
from urllib.parse import urlparse

from longscrape.core.domain.pipeline import (
    ExtractionResult,
    FetchRequest,
    PipelineInput,
    RawEntry,
)


class FetcherPort(Protocol):
    def get_base_domain(self) -> str: ...

    async def fetch(self, task: FetchRequest) -> RawEntry: ...


class ExtractorPort[T](Protocol):
    def is_compatible(self, raw_entry: RawEntry) -> bool: ...

    async def extract(
        self, input: PipelineInput, raw_entry: RawEntry
    ) -> ExtractionResult[T]: ...


class DefaultExtractor[T]:
    def __init__(self, allowed_domain: str):
        self.allowed_domain = allowed_domain

    def is_compatible(self, raw_entry: RawEntry) -> bool:
        netloc = urlparse(raw_entry.url).netloc.lower()
        target = self.allowed_domain.lower()
        return netloc == target or netloc.endswith(f".{target}")

    async def extract(
        self, input: PipelineInput, raw_entry: RawEntry
    ) -> ExtractionResult[T]:
        raise NotImplementedError(
            "Override extract() or implement ExtractorPort directly"
        )


class RawEntryStore(Protocol):
    async def get(self, cache_key: str) -> RawEntry | None: ...

    async def put(self, cache_key: str, raw_entry: RawEntry) -> None: ...

    def entries(self) -> AsyncIterator[RawEntry]: ...
