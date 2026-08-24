from collections.abc import Callable, Mapping
from typing import Any, Literal

from longscrape.runtime.flow import RecordFlow
from longscrape.worker.context import JobContext
from longscrape.worker.models import DocumentRefInput
from longscrape.worker.protocols import JobQueue, JobStore

type FlowFactory = Callable[[JobContext], RecordFlow[Any]]


class FlowRouter:
    """Drain worker jobs through jobless flows selected by job kind."""

    def __init__(
        self,
        flows: Mapping[str, FlowFactory],
        *,
        job_store: JobStore | None = None,
        on_unknown: Literal["skip", "error"] = "skip",
        worker_id: str | None = None,
    ) -> None:
        self._flows, self._job_store, self._on_unknown, self._worker_id = (
            dict(flows),
            job_store,
            on_unknown,
            worker_id,
        )

    async def run(self, queue: JobQueue) -> None:
        while not queue.empty(worker_id=self._worker_id):
            job = await queue.get(worker_id=self._worker_id)
            if self._job_store:
                await self._job_store.start(job.id)
            try:
                factory = self._flows.get(job.kind)
                if factory is None:
                    if self._on_unknown == "error":
                        raise LookupError(f"no flow is registered for {job.kind!r}")
                    continue
                if isinstance(job.input, DocumentRefInput):
                    raise TypeError(
                        "DocumentRefInput requires a worker adapter before "
                        "running a Flow"
                    )
                context = JobContext(job, submitter=queue, worker_id=self._worker_id)
                async for _ in factory(context)(job.input, context.context):
                    pass
            except Exception as error:
                if self._job_store:
                    await self._job_store.fail(job.id, error)
                raise
            else:
                if self._job_store:
                    await self._job_store.succeed(job.id)
