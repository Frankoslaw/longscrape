from typing import Protocol
from urllib.parse import urlparse

from longscrape.core.doamin.pipeline import (
    ExtractionResult,
    RawEntry,
    ScraperTask,
)


class FetcherPort(Protocol):
    def get_base_domain(self) -> str: ...

    async def fetch(self, task: ScraperTask) -> RawEntry: ...


class ExtractorPort[T](Protocol):
    def is_compatible(self, raw_entry: RawEntry) -> bool: ...

    async def extract(
        self, task: ScraperTask, raw_entry: RawEntry
    ) -> ExtractionResult[T]: ...


class DefaultExtractor[T]:
    def __init__(self, allowed_domain: str):
        self.allowed_domain = allowed_domain

    def is_compatible(self, raw_entry: RawEntry) -> bool:
        netloc = urlparse(raw_entry.url).netloc.lower()
        target = self.allowed_domain.lower()
        return netloc == target or netloc.endswith(f".{target}")

    async def extract(
        self, task: ScraperTask, raw_entry: RawEntry
    ) -> ExtractionResult[T]:
        raise NotImplementedError(
            "Override extract() or implement ExtractorPort directly"
        )
