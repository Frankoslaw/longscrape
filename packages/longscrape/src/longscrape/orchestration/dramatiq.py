"""Dramatiq transport for durable work IDs; it never carries job payloads."""

from datetime import timedelta
from uuid import UUID

try:
    import dramatiq
except ImportError as error:  # pragma: no cover
    raise ImportError("Dramatiq requires the 'longscrape[dramatiq]' extra") from error

from longscrape_core import WorkStore

from longscrape.runtime.worker import Worker


class DramatiqTransport:
    def __init__(
        self, store: WorkStore, worker: Worker, *, queue: str = "default"
    ) -> None:
        self._store = store
        self._worker = worker

        @dramatiq.actor(queue_name=queue)
        async def run_job(job_id: str) -> None:
            lease = await store.claim(
                worker_id=worker.worker_id,
                lease_for=timedelta(minutes=5),
                job_id=UUID(job_id),
            )
            if lease is None:
                return
            await worker.run_lease(lease)

        self._actor = run_job

    def send(self, job_id: UUID, *, delay: timedelta | None = None) -> None:
        if delay is None:
            self._actor.send(str(job_id))
        else:
            self._actor.send_with_options(
                args=(str(job_id),), delay=round(delay.total_seconds() * 1000)
            )
