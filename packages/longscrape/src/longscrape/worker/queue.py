import asyncio
from collections import deque
from collections.abc import Callable
from datetime import timedelta

from longscrape.worker.models import Job, JobSpec
from longscrape.worker.protocols import JobQueue, JobStore


class InMemoryJobQueue(JobQueue):
    def __init__(self) -> None:
        self._jobs: deque[Job] = deque()
        self._not_empty = asyncio.Condition()

    async def submit(self, request: JobSpec) -> None:
        await self.submit_job(Job.spawn_job(request))

    async def submit_job(self, job: Job, *, delay: timedelta | None = None) -> None:
        if delay is not None:
            await asyncio.sleep(delay.total_seconds())
        async with self._not_empty:
            self._jobs.append(job)
            self._not_empty.notify_all()

    async def get(
        self, kind: str | None = None, *, worker_id: str | None = None
    ) -> Job:
        async with self._not_empty:
            while True:
                for index, job in enumerate(self._jobs):
                    if (kind is None or job.kind == kind) and (
                        job.worker_id is None or job.worker_id == worker_id
                    ):
                        del self._jobs[index]
                        return job
                await self._not_empty.wait()

    def empty(self, kind: str | None = None, *, worker_id: str | None = None) -> bool:
        return not any(
            (kind is None or job.kind == kind)
            and (job.worker_id is None or job.worker_id == worker_id)
            for job in self._jobs
        )


class StoredJobQueue(JobQueue):
    def __init__(
        self,
        queue: JobQueue,
        store: JobStore,
        *,
        key: Callable[[Job], str] | None = None,
    ) -> None:
        self._queue, self._store, self._key = queue, store, key

    async def submit(self, request: JobSpec) -> None:
        await self.submit_job(Job.spawn_job(request))

    async def submit_job(self, job: Job, *, delay: timedelta | None = None) -> None:
        if await self._store.register(job, key=self._key(job) if self._key else None):
            await self._queue.submit_job(job, delay=delay)

    async def get(
        self, kind: str | None = None, *, worker_id: str | None = None
    ) -> Job:
        return await self._queue.get(kind, worker_id=worker_id)

    def empty(self, kind: str | None = None, *, worker_id: str | None = None) -> bool:
        return self._queue.empty(kind, worker_id=worker_id)
