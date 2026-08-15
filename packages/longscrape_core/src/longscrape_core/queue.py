from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from longscrape_core.models import JobRef
from longscrape_core.protocols import JobLease


@dataclass(frozen=True)
class Lease:
    """Capability to settle exactly one temporary claim of a queued job."""

    ref: JobRef
    token: str
    expires_at: datetime


class InMemoryJobQueue:
    """FIFO reference queue with expiring, token-bound leases.

    It intentionally has no job data or lifecycle state; those belong in a
    JobStore and are commonly coordinated through JobManager.
    """

    def __init__(self, *, lease_duration: timedelta = timedelta(minutes=5)) -> None:
        if lease_duration <= timedelta():
            raise ValueError("lease_duration must be greater than zero")
        self.lease_duration = lease_duration
        self._pending: deque[tuple[str, JobRef]] = deque()
        self._leased: dict[str, Lease] = {}
        self._enqueued: set[JobRef] = set()
        self._kinds: dict[JobRef, str] = {}

    async def enqueue(self, ref: JobRef, *, kind: str | None = None) -> bool:
        """Enqueue a ref once. ``kind`` is required because queues do not load jobs."""
        if not kind or not kind.strip():
            raise ValueError("kind must be supplied when enqueueing a job ref")
        if ref in self._enqueued:
            return False
        self._enqueued.add(ref)
        self._kinds[ref] = kind
        self._pending.append((kind, ref))
        return True

    def _reclaim_expired(self) -> None:
        now = datetime.now(UTC)
        for token, lease in tuple(self._leased.items()):
            if lease.expires_at <= now:
                self._leased.pop(token)
                self._pending.appendleft((self._kinds[lease.ref], lease.ref))

    async def lease(
        self, kind: str, *, duration: timedelta | None = None
    ) -> Lease | None:
        if not kind.strip():
            raise ValueError("kind must not be blank")
        self._reclaim_expired()
        duration = duration or self.lease_duration
        if duration <= timedelta():
            raise ValueError("duration must be greater than zero")
        index = next(
            (
                i
                for i, (queued_kind, _) in enumerate(self._pending)
                if queued_kind == kind
            ),
            None,
        )
        if index is None:
            return None
        _, ref = self._pending[index]
        del self._pending[index]
        lease = Lease(ref, str(uuid4()), datetime.now(UTC) + duration)
        self._leased[lease.token] = lease
        return lease

    def _require_active(self, lease: JobLease) -> Lease:
        if not isinstance(lease, Lease):
            raise ValueError("Lease was not issued by this queue")
        self._reclaim_expired()
        if self._leased.get(lease.token) != lease:
            raise ValueError("Lease is invalid, already settled, or expired")
        return lease

    async def acknowledge(self, lease: JobLease) -> None:
        lease = self._require_active(lease)
        self._leased.pop(lease.token)

    async def retry(self, lease: JobLease) -> None:
        lease = self._require_active(lease)
        self._leased.pop(lease.token)
        self._pending.append((self._kinds[lease.ref], lease.ref))

    async def extend(self, lease: JobLease, *, duration: timedelta) -> Lease:
        if duration <= timedelta():
            raise ValueError("duration must be greater than zero")
        lease = self._require_active(lease)
        extended = Lease(lease.ref, lease.token, datetime.now(UTC) + duration)
        self._leased[lease.token] = extended
        return extended

    def is_empty(self) -> bool:
        self._reclaim_expired()
        return not self._pending and not self._leased
