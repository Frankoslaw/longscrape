import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from longscrape_core.context import PipelineContext
from longscrape_core.models import InputQuery, Job
from longscrape_core.work import WORK_EXECUTION, WorkExecution, WorkLease, WorkRequest


class RecordingWorkStore:
    def __init__(self) -> None:
        self.requests: list[WorkRequest] = []

    async def enqueue(self, request: WorkRequest) -> tuple[Job, bool]:
        self.requests.append(request)
        return request.job, True


def test_durable_work_is_an_opt_in_context_capability() -> None:
    async def run() -> RecordingWorkStore:
        store = RecordingWorkStore()
        parent = Job("root", InputQuery({"page": 1}))
        lease = WorkLease(parent, uuid4(), "worker-1", 1, datetime.now(UTC))
        context = PipelineContext()
        execution = WorkExecution(store, lease)
        context.set(WORK_EXECUTION, execution)

        accepted = await context.require(WORK_EXECUTION).submit(
            Job("child", InputQuery({"page": 2}))
        )
        assert accepted.parent_id == parent.id
        assert accepted.root_id == parent.root_id
        return store

    store = asyncio.run(run())
    assert store.requests[0].job.kind == "child"
