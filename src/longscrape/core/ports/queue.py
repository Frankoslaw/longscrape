from typing import Protocol

from longscrape.core.doamin.pipeline import ScraperTask


class TaskQueue(Protocol):
    async def put(self, task: ScraperTask) -> None: ...

    async def get(self, kind: str | None = None) -> ScraperTask: ...

    def empty(self, kind: str | None = None) -> bool: ...
