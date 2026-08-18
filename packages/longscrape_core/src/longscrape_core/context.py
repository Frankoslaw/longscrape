from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, Protocol, TypeVar, cast

from longscrape_core.models import Job, JobRequest

T = TypeVar("T")
_MISSING = object()


@dataclass(frozen=True, eq=False)
class ContextKey(Generic[T]):
    """Identity-based key for a value stored in ``PipelineContext``."""

    name: str


class JobSubmitter(Protocol):
    async def submit_job(self, job: Job) -> None: ...


@dataclass
class PipelineContext:
    """Mutable, process-local capabilities shared by a pipeline.

    A context is deliberately separate from ``Job``. It may hold live objects
    such as a browser session or page lease, so it must never be serialized or
    persisted by a queue backend.
    """

    submitter: JobSubmitter | None = None
    _values: dict[ContextKey[object], object] = field(default_factory=dict)

    async def submit_child(self, parent: Job, request: JobRequest) -> None:
        if self.submitter is None:
            raise RuntimeError("PipelineContext has no job submitter")
        await self.submitter.submit_job(parent.spawn_child(request))

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
