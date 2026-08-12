from __future__ import annotations

from collections import deque

from longscrape_core.models import Job


class InMemoryJobQueue:
    """FIFO queue for initial jobs in a single process."""

    def __init__(self, *, max_retries: int = 0) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must not be negative")
        self.max_retries = max_retries
        self._pending: deque[Job] = deque()
        self._processing: dict[str, Job] = {}
        self._completed: dict[str, Job] = {}
        self._failed: dict[str, tuple[Job, str]] = {}
        self._retry_counts: dict[str, int] = {}
        self._job_ids: set[str] = set()

    async def enqueue(self, job: Job) -> bool:
        job_id = str(job.id)
        if job_id in self._job_ids:
            return False
        self._job_ids.add(job_id)
        self._pending.append(job)
        return True

    async def dequeue(self, kind: str) -> Job | None:
        """Claim the oldest pending job with ``kind``, if one exists."""
        if not kind.strip():
            raise ValueError("kind must not be blank")
        index = next(
            (index for index, job in enumerate(self._pending) if job.kind == kind),
            None,
        )
        if index is None:
            return None
        job = self._pending[index]
        del self._pending[index]
        self._processing[str(job.id)] = job
        return job

    async def mark_completed(self, job: Job) -> None:
        job_id = str(job.id)
        self._processing.pop(job_id, None)
        self._completed[job_id] = job

    async def mark_failed(self, job: Job, error: Exception) -> None:
        job_id = str(job.id)
        self._processing.pop(job_id, None)
        retries = self._retry_counts.get(job_id, 0)
        if retries < self.max_retries:
            self._retry_counts[job_id] = retries + 1
            self._pending.append(job)
            return
        self._failed[job_id] = (job, str(error))

    def is_empty(self) -> bool:
        return not self._pending and not self._processing

    @property
    def stats(self) -> dict[str, int]:
        return {
            "pending": len(self._pending),
            "processing": len(self._processing),
            "completed": len(self._completed),
            "failed": len(self._failed),
        }
