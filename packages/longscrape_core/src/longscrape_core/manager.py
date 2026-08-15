from __future__ import annotations

from datetime import timedelta

from longscrape_core.models import Job, JobRef, JobState, JobStatus
from longscrape_core.protocols import JobLease, JobQueue, JobStore


class JobManager:
    """Small application-facing facade over independent job store and queue.

    Consumers normally only submit a Job, lease one supported kind, and settle
    the returned managed lease. Infrastructure remains replaceable behind the
    two protocols.
    """

    def __init__(
        self, jobs: JobStore, queue: JobQueue, *, max_retries: int = 0
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must not be negative")
        self.jobs, self.queue, self.max_retries = jobs, queue, max_retries

    async def submit(self, job: Job) -> JobRef:
        ref = await self.jobs.save(job)
        await self.queue.enqueue(ref, kind=job.kind)
        return ref

    async def lease(
        self, kind: str, *, duration: timedelta | None = None
    ) -> ManagedLease | None:
        # Queues and stores are independent durable systems. A queue can retain
        # an old ref after its store was manually cleared; discard such orphaned
        # refs instead of letting one poison a worker forever.
        while lease := await self.queue.lease(kind, duration=duration):
            job = await self.jobs.get(lease.ref)
            if job is None:
                await self.queue.acknowledge(lease)
                continue
            await self.jobs.set_status(lease.ref, JobState.RUNNING)
            return ManagedLease(job, lease, self)
        return None

    async def status(self, ref: JobRef) -> JobStatus | None:
        return await self.jobs.get_status(ref)


class ManagedLease:
    def __init__(self, job: Job, lease: JobLease, manager: JobManager) -> None:
        self.job, self._lease, self._manager = job, lease, manager

    async def acknowledge(self) -> None:
        await self._manager.queue.acknowledge(self._lease)
        await self._manager.jobs.set_status(self.job.id, JobState.SUCCEEDED)

    async def retry(self, error: Exception | str) -> None:
        status = await self._manager.jobs.get_status(self.job.id)
        retries = (status.retry_count if status else 0) + 1
        error_text = str(error)
        if retries > self._manager.max_retries:
            await self._manager.queue.acknowledge(self._lease)
            await self._manager.jobs.set_status(
                self.job.id,
                JobState.RETRY_EXHAUSTED,
                retry_count=retries,
                error=error_text,
            )
            return
        await self._manager.queue.retry(self._lease)
        await self._manager.jobs.set_status(
            self.job.id,
            JobState.PENDING,
            retry_count=retries,
            error=error_text,
        )

    async def fail(self, error: Exception | str) -> None:
        """Terminally fail a lease without scheduling another attempt."""
        await self._manager.queue.acknowledge(self._lease)
        status = await self._manager.jobs.get_status(self.job.id)
        await self._manager.jobs.set_status(
            self.job.id,
            JobState.FAILED,
            retry_count=status.retry_count if status else 0,
            error=str(error),
        )

    async def extend(self, *, duration: timedelta) -> None:
        self._lease = await self._manager.queue.extend(self._lease, duration=duration)
