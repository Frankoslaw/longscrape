import asyncio
from collections import deque

from longscrape.core.domain.pipeline import PipelineInput


class InMemoryTaskQueue:
    def __init__(self):
        self._tasks: deque[PipelineInput] = deque()
        self._not_empty = asyncio.Condition()

    async def put(self, task: PipelineInput) -> None:
        async with self._not_empty:
            self._tasks.append(task)
            self._not_empty.notify_all()

    async def get(self, kind: str | None = None) -> PipelineInput:
        async with self._not_empty:
            while True:
                for index, task in enumerate(self._tasks):
                    if kind is None or task.kind == kind:
                        del self._tasks[index]
                        return task
                await self._not_empty.wait()
        raise AssertionError("unreachable")

    def empty(self, kind: str | None = None) -> bool:
        return not any(kind is None or task.kind == kind for task in self._tasks)
