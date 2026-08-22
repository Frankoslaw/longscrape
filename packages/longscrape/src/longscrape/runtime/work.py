"""Optional durable work: enqueue a job, lease it, then finish it."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from longscrape_core.context import PipelineContext
from longscrape_core.models import Job


@dataclass(frozen=True)
class WorkRequest:
    job: Job
    key: str | None = None
    run_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.key == "":
            raise ValueError("work key must not be empty")


@dataclass(frozen=True)
class WorkLease:
    """One worker's temporary authority to execute a job."""

    job: Job
    token: UUID
    worker_id: str
    attempt: int
    expires_at: datetime

    def __post_init__(self) -> None:
        if not self.worker_id:
            raise ValueError("worker_id must not be empty")
        if self.attempt < 1:
            raise ValueError("attempt must be at least one")


class JobExecutor(Protocol):
    async def execute(self, job: Job, context: PipelineContext) -> None: ...


class WorkStore(Protocol):
    """Minimal durable queue contract.

    Mutating lease operations return ``False`` when the lease is stale. They
    never turn a normal duplicate delivery into an exception.
    """

    async def enqueue(self, request: WorkRequest) -> Job: ...
    async def claim(
        self,
        *,
        worker_id: str,
        lease_for: timedelta,
        job_id: UUID | None = None,
        kinds: set[str] | None = None,
    ) -> WorkLease | None: ...
    async def complete(self, lease: WorkLease) -> bool: ...
    async def retry(self, lease: WorkLease, *, run_at: datetime) -> bool: ...
    async def fail(self, lease: WorkLease, error: str) -> bool: ...
    async def cancel(self, job_id: UUID) -> bool: ...
    async def requeue_expired(self) -> int: ...
