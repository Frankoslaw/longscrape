import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from longscrape_core._json import JsonObject
from longscrape_core.context import PipelineContext
from longscrape_core.models import InputQuery, Job, JobLease, JobSpec


class RecordingWorkController:
    def __init__(self) -> None:
        self.enqueued: list[tuple[JobSpec, Job | None]] = []
        self.saved: list[tuple[JobLease, JsonObject, float | None]] = []

    async def enqueue(
        self, spec: JobSpec, *, parent: Job | None = None
    ) -> tuple[Job, bool]:
        self.enqueued.append((spec, parent))
        return (
            Job(
                spec,
                parent_id=parent.id if parent else None,
                root_id=parent.root_id if parent else None,
            ),
            True,
        )

    async def checkpoint(
        self,
        lease: JobLease,
        data: JsonObject,
        *,
        progress: float | None = None,
    ) -> None:
        self.saved.append((lease, data, progress))


def test_context_requires_a_work_controller_for_child_jobs() -> None:
    async def run() -> None:
        parent = Job(JobSpec("root", InputQuery({"page": 1})))
        with pytest.raises(RuntimeError, match="no work controller"):
            await PipelineContext().submit_child(
                parent, JobSpec("child", InputQuery({"page": 2}))
            )

    asyncio.run(run())


def test_context_submits_children_and_persists_checkpoints() -> None:
    async def run() -> RecordingWorkController:
        work = RecordingWorkController()
        parent = Job(JobSpec("root", InputQuery({"page": 1})))
        lease = JobLease(
            parent,
            uuid4(),
            "worker-1",
            1,
            datetime.now(UTC),
            {"page": 1},
        )
        context = PipelineContext(work=work, worker_id="worker-1", lease=lease)

        child = await context.submit_child(
            parent,
            JobSpec("child", InputQuery({"page": 2})),
        )
        await context.save_checkpoint({"page": 2}, progress=0.5)

        assert context.load_checkpoint() == {"page": 1}
        assert child.parent_id == parent.id
        assert context.require_worker_id() == "worker-1"
        return work

    work = asyncio.run(run())
    assert work.enqueued[0][0].kind == "child"
    assert work.saved[0][1:] == ({"page": 2}, 0.5)
