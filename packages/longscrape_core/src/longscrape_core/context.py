from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, Protocol, TypeVar, cast

from longscrape_core._json import FrozenJsonObject, JsonObject, thaw_json_object
from longscrape_core.models import Job, JobLease, JobSpec

T = TypeVar("T")
_MISSING = object()


@dataclass(frozen=True, eq=False)
class ContextKey(Generic[T]):
    """Identity-based key for a value stored in ``PipelineContext``."""

    name: str


class WorkController(Protocol):
    """Work capabilities that a running pipeline may use.

    ``WorkStore`` extends this protocol with claiming, status, and event APIs.
    Keeping this smaller interface here avoids a context/protocol import cycle.
    """

    async def enqueue(
        self, spec: JobSpec, *, parent: Job | None = None
    ) -> tuple[Job, bool]: ...

    async def checkpoint(
        self,
        lease: JobLease,
        data: JsonObject,
        *,
        progress: float | None = None,
    ) -> None: ...


@dataclass
class PipelineContext:
    """Mutable process-local capabilities for one job execution.

    The context is never serialized. It can hold live browser objects while
    exposing a narrow durable-work interface for child jobs and checkpoints.
    """

    work: WorkController | None = None
    worker_id: str | None = None
    lease: JobLease | None = None
    _values: dict[ContextKey[object], object] = field(default_factory=dict)

    async def submit_child(self, parent: Job, spec: JobSpec) -> Job:
        if self.work is None:
            raise RuntimeError("PipelineContext has no work controller")
        job, _ = await self.work.enqueue(spec, parent=parent)
        return job

    def load_checkpoint(self) -> JsonObject | None:
        """Return a mutable copy of this attempt's persisted checkpoint."""

        if self.lease is None or self.lease.checkpoint is None:
            return None
        return thaw_json_object(cast(FrozenJsonObject, self.lease.checkpoint))

    async def save_checkpoint(
        self, data: JsonObject, *, progress: float | None = None
    ) -> None:
        if self.work is None or self.lease is None:
            raise RuntimeError("PipelineContext has no active work lease")
        await self.work.checkpoint(self.lease, data, progress=progress)

    def require_worker_id(self) -> str:
        if self.worker_id is None:
            raise RuntimeError("PipelineContext has no worker_id")
        return self.worker_id

    def set(self, key: ContextKey[T], value: T) -> None:
        self._values[cast(ContextKey[object], key)] = value

    def get(self, key: ContextKey[T]) -> T | None:
        return cast(T | None, self._values.get(cast(ContextKey[object], key)))

    def require(self, key: ContextKey[T]) -> T:
        value = self._values.get(cast(ContextKey[object], key), _MISSING)
        if value is _MISSING:
            raise LookupError(f"Pipeline context value is missing: {key.name}")
        return cast(T, value)

    def discard(self, key: ContextKey[T]) -> None:
        self._values.pop(cast(ContextKey[object], key), None)
