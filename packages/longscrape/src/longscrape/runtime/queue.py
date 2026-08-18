import asyncio
from collections import deque

from longscrape_core.context import JobSubmitter
from longscrape_core.models import Job, JobRequest


class InMemoryJobQueue(JobSubmitter):
    def __init__(self):
        self._jobs: deque[Job] = deque()
        self._not_empty = asyncio.Condition()

    async def submit(self, request: JobRequest) -> None:
        await self.submit_job(Job.spawn_job(request))

    async def submit_job(self, job: Job) -> None:
        async with self._not_empty:
            self._jobs.append(job)
            self._not_empty.notify()

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
