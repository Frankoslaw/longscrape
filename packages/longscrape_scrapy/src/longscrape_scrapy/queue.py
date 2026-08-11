from __future__ import annotations

from collections import deque

from longscrape_core import CrawlJob


class InMemoryJobQueue:
    """Small FIFO queue for one-process workers and local development.

    Jobs are de-duplicated while queued by their stable CrawlJob fingerprint.
    This intentionally does not claim jobs or persist state; those belong in a
    future queue adapter backed by a database or message broker.
    """

    def __init__(self) -> None:
        self._jobs: deque[CrawlJob] = deque()
        self._fingerprints: set[str] = set()

    async def enqueue(self, job: CrawlJob) -> bool:
        job_fingerprint = job.fingerprint()
        if job_fingerprint in self._fingerprints:
            return False
        self._jobs.append(job)
        self._fingerprints.add(job_fingerprint)
        return True

    async def dequeue(self) -> CrawlJob | None:
        if not self._jobs:
            return None
        job = self._jobs.popleft()
        self._fingerprints.remove(job.fingerprint())
        return job
