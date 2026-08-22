"""Typed runtime capabilities installed into a core pipeline context."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from longscrape_core import ContextKey, Job, JobInput

from longscrape.runtime.work import WorkRequest, WorkStore


class JobSubmitter(Protocol):
    async def submit(
        self, job: Job, *, key: str | None = None, run_at: datetime | None = None
    ) -> Job: ...


@dataclass(frozen=True)
class WorkSubmitter(JobSubmitter):
    store: WorkStore

    async def submit(
        self, job: Job, *, key: str | None = None, run_at: datetime | None = None
    ) -> Job:
        return await self.store.enqueue(WorkRequest(job, key, run_at))


@dataclass(frozen=True)
class JobContext:
    job: Job
    submitter: JobSubmitter | None = None

    async def submit(
        self, kind: str, input: JobInput, *, key: str | None = None
    ) -> Job:
        if self.submitter is None:
            raise RuntimeError("this execution cannot enqueue child jobs")
        return await self.submitter.submit(self.job.child(kind, input), key=key)


JOB_CONTEXT: ContextKey[JobContext] = ContextKey("job_context")
