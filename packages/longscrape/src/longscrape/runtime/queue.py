import asyncio
from collections import deque

from longscrape_core import Job, JobRequest, JobSubmitter


class InMemoryJobQueue(JobSubmitter):
    def __init__(self):
        self._jobs: deque[Job] = deque()
        self._not_empty = asyncio.Condition()

    async def submit(self, request: JobRequest) -> None:
        job = Job(kind=request.kind, input=request.input, context=request.context)
        self._jobs.append(job)

    async def get(self, kind: str | None = None) -> Job:
        async with self._not_empty:
            while True:
                for index, job in enumerate(self._jobs):
                    if kind is None or job.kind == kind:
                        del self._jobs[index]
                        return job
                await self._not_empty.wait()
        raise AssertionError("unreachable")

    def empty(self, kind: str | None = None) -> bool:
        return not any(kind is None or job.kind == kind for job in self._jobs)
