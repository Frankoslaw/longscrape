from __future__ import annotations

from collections import deque
from typing import Any

from longscrape_core import CrawlJob


class InMemoryJobQueue:
    """In-memory queue with state tracking and deduplication."""

    def __init__(self, *, max_retries: int = 0) -> None:
        self.max_retries = max_retries

        self._pending: deque[CrawlJob] = deque()
        self._processing: dict[str, CrawlJob] = {}
        self._completed: dict[str, CrawlJob] = {}
        self._failed: dict[str, tuple[CrawlJob, str | None]] = {}

        self._retry_counts: dict[str, int] = {}
        self._fingerprints: set[str] = set()

    async def enqueue(self, job: CrawlJob) -> bool:
        fp = job.fingerprint()
        if fp in self._fingerprints:
            return False

        self._fingerprints.add(fp)
        self._pending.append(job)
        return True

    async def dequeue(self) -> CrawlJob | None:
        if not self._pending:
            return None

        job = self._pending.popleft()
        fp = job.fingerprint()
        self._processing[fp] = job
        return job

    async def mark_completed(self, job: CrawlJob, result: Any | None = None) -> None:
        fp = job.fingerprint()
        self._processing.pop(fp, None)
        self._completed[fp] = job

    async def mark_failed(
        self,
        job: CrawlJob,
        error: Exception | str | None = None,
        *,
        can_retry: bool = True,
    ) -> None:
        fp = job.fingerprint()
        self._processing.pop(fp, None)

        err_msg = str(error) if error is not None else None
        current_retries = self._retry_counts.get(fp, 0)

        if can_retry and current_retries < self.max_retries:
            self._retry_counts[fp] = current_retries + 1
            self._pending.append(job)
        else:
            self._failed[fp] = (job, err_msg)

    # --- Inspection Helpers ---

    def is_empty(self) -> bool:
        return len(self._pending) == 0 and len(self._processing) == 0

    @property
    def stats(self) -> dict[str, int]:
        return {
            "pending": len(self._pending),
            "processing": len(self._processing),
            "completed": len(self._completed),
            "failed": len(self._failed),
            "total_fingerprints": len(self._fingerprints),
        }
