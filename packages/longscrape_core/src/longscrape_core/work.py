"""Optional durable-work contracts for resumable execution."""

from collections.abc import AsyncIterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Protocol
from uuid import UUID

from longscrape_core._json import (
    JsonInput,
    freeze_json_object,
)
from longscrape_core.context import ContextKey, PipelineContext
from longscrape_core.models import Job


@dataclass(frozen=True)
class WorkRequest:
    job: Job
    idempotency_key: str | None = None
    run_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.idempotency_key == "":
            raise ValueError("idempotency_key must not be empty")


class WorkState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkEventType(Enum):
    ENQUEUED = "enqueued"
    CLAIMED = "claimed"
    RETRIED = "retried"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LeaseLostError(RuntimeError):
    """The lease is expired, superseded, or no longer owned by its worker."""


@dataclass(frozen=True)
class WorkView:
    job: Job
    state: WorkState
    attempt: int = 0
    error: str | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if self.attempt < 0:
            raise ValueError("attempt must not be negative")


@dataclass(frozen=True)
class WorkLease:
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


@dataclass(frozen=True)
class WorkEvent:
    job_id: UUID
    type: WorkEventType
    at: datetime = field(default_factory=lambda: datetime.now(UTC))
    data: Mapping[str, JsonInput] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", freeze_json_object(self.data))


class JobExecutor(Protocol):
    async def execute(self, job: Job, context: PipelineContext) -> None: ...


class WorkController(Protocol):
    """The only durable-work capability available to a running pipeline."""

    # With an idempotency key, enqueue is atomic and returns the job created by
    # the first call. Without one, every call creates a new job.
    async def enqueue(self, request: WorkRequest) -> tuple[Job, bool]: ...


class WorkStore(WorkController, Protocol):
    """A durable job lifecycle: pending -> running -> terminal or pending.

    All lease-mutating methods raise ``LeaseLostError`` when their lease is no
    longer current. ``claim`` returns only runnable pending jobs. ``retry``
    returns its lease's job to pending at ``run_at``; ``complete`` and ``fail``
    are terminal. ``cancel`` prevents future claims.
    """

    async def claim(
        self, *, worker_id: str, lease_for: timedelta, kinds: set[str] | None = None
    ) -> WorkLease | None: ...
    async def heartbeat(
        self, lease: WorkLease, *, extend_for: timedelta
    ) -> WorkLease: ...
    async def complete(self, lease: WorkLease) -> None: ...
    async def retry(
        self, lease: WorkLease, error: Exception, *, run_at: datetime
    ) -> None: ...
    async def fail(self, lease: WorkLease, error: Exception) -> None: ...
    async def cancel(self, job_id: UUID) -> None: ...
    async def recover_expired_leases(self) -> int: ...
    async def get(self, job_id: UUID) -> WorkView: ...
    def events(self, job_id: UUID) -> AsyncIterable[WorkEvent]: ...


@dataclass(frozen=True)
class WorkExecution:
    """The optional durable-work capability attached to a running context."""

    store: WorkController
    lease: WorkLease

    async def submit(
        self,
        job: Job,
        *,
        idempotency_key: str | None = None,
        run_at: datetime | None = None,
    ) -> Job:
        child = Job(
            job.kind,
            job.input,
            job.metadata,
            parent_id=self.lease.job.id,
            root_id=self.lease.job.root_id,
        )
        accepted, _ = await self.store.enqueue(
            WorkRequest(child, idempotency_key, run_at)
        )
        return accepted


WORK_EXECUTION: ContextKey[WorkExecution] = ContextKey("work_execution")
