from collections.abc import Mapping
from typing import Any, Literal

from longscrape_core import JobQueue, JobStore

from longscrape.runtime.flow import RecordFlow


class FlowRouter:
    """Drain a local queue through flows selected by job kind."""

    def __init__(
        self,
        flows: Mapping[str, RecordFlow[Any]],
        *,
        job_store: JobStore | None = None,
        on_unknown: Literal["skip", "error"] = "skip",
        worker_id: str | None = None,
    ) -> None:
        self._flows = dict(flows)
        self._job_store = job_store
        self._on_unknown = on_unknown
        self._worker_id = worker_id

    async def run(self, queue: JobQueue) -> None:
        while not queue.empty(worker_id=self._worker_id):
            job = await queue.get(worker_id=self._worker_id)
            if self._job_store is not None:
                await self._job_store.start(job.id)
            try:
                flow = self._flows.get(job.kind)
                if flow is None:
                    if self._on_unknown == "error":
                        raise LookupError(f"no flow is registered for {job.kind!r}")
                else:
                    async for _ in flow(job):
                        pass
            except Exception as error:
                if self._job_store is not None:
                    await self._job_store.fail(job.id, error)
                raise
            else:
                if self._job_store is not None:
                    await self._job_store.succeed(job.id)
