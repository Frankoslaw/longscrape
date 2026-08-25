from dataclasses import dataclass, field
from datetime import timedelta
from typing import Protocol

from longscrape.core import Context
from longscrape.worker.models import Job, JobSpec


class JobSubmitter(Protocol):
    async def submit_job(self, job: Job, *, delay: timedelta | None = None) -> None: ...


@dataclass
class JobContext:
    """Worker-only execution state layered over generic stage capabilities."""

    job: Job
    context: Context = field(default_factory=Context)
    submitter: JobSubmitter | None = None
    worker_id: str | None = None

    async def submit_child(self, request: JobSpec) -> None:
        if self.submitter is None:
            raise RuntimeError("JobContext has no job submitter")
        await self.submitter.submit_job(self.job.spawn_child(request))

    def require_worker_id(self) -> str:
        if self.worker_id is None:
            raise RuntimeError("JobContext has no worker_id")
        return self.worker_id
