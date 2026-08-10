from collections.abc import AsyncIterator, Sequence
from typing import Any

from longscrape.core.domain.pipeline import (
    ExtractionResult,
    RawEntry,
    RawInput,
    RichEntry,
)
from longscrape.core.ports.pipeline import ExtractorPort, RawEntryStore
from longscrape.core.services.worker import ExtractionWorker


class ReExtractWorker[T]:
    def __init__(
        self, extractor: ExtractorPort[T], *, task_kind: str | None = None
    ) -> None:
        self.task_kind = task_kind
        self._worker = ExtractionWorker(extractor, task_kind=task_kind)

    def accepts(self, raw_entry: RawEntry) -> bool:
        return self.task_kind is None or self.task_kind == raw_entry.kind

    async def run(self, raw_entry: RawEntry) -> ExtractionResult[T]:
        return await self._worker.run(RawInput.from_raw_entry(raw_entry), raw_entry)


class ReExtractor:
    def __init__(
        self, raw_entry_store: RawEntryStore, workers: Sequence[ReExtractWorker[Any]]
    ) -> None:
        if not workers:
            raise ValueError("workers must not be empty")
        self.raw_entry_store = raw_entry_store
        self.workers = tuple(workers)

    def _worker_for(self, raw_entry: RawEntry) -> ReExtractWorker[Any]:
        for worker in self.workers:
            if worker.task_kind == raw_entry.kind:
                return worker
        for worker in self.workers:
            if worker.task_kind is None:
                return worker
        raise ValueError(
            f"No re-extraction worker registered for kind: {raw_entry.kind}"
        )

    async def stream(self) -> AsyncIterator[RichEntry[Any]]:
        async for raw_entry in self.raw_entry_store.entries():
            result = await self._worker_for(raw_entry).run(raw_entry)
            for item in result.items:
                yield item

    async def run(self) -> list[RichEntry[Any]]:
        return [item async for item in self.stream()]
