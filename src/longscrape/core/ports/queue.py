from typing import Protocol

from longscrape.core.domain.pipeline import PipelineInput


class TaskQueue(Protocol):
    async def put(self, task: PipelineInput) -> None: ...

    async def get(self, kind: str | None = None) -> PipelineInput: ...

    def empty(self, kind: str | None = None) -> bool: ...
