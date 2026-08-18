import asyncio

from longscrape.runtime import InMemoryJobQueue
from longscrape_core import InputUrl, Job, JobRequest, PipelineContext


def test_queue_wakes_waiting_consumer() -> None:
    async def run() -> None:
        queue = InMemoryJobQueue()
        waiter = asyncio.create_task(queue.get())
        await asyncio.sleep(0)

        request = JobRequest(kind="fetch", input=InputUrl("https://example.com"))
        await queue.submit(request)

        job = await asyncio.wait_for(waiter, timeout=0.1)
        assert job.kind == request.kind
        assert job.input == request.input

    asyncio.run(run())


def test_context_submits_child_jobs_with_lineage() -> None:
    async def run() -> tuple[Job, Job]:
        queue = InMemoryJobQueue()
        parent = Job.spawn_job(JobRequest("root", InputUrl("https://example.com")))
        context = PipelineContext(queue)
        await context.submit_child(
            parent,
            JobRequest("child", InputUrl("https://example.com/child")),
        )
        return parent, await queue.get()

    parent, child = asyncio.run(run())

    assert child.parent_id == parent.id
    assert child.root_id == parent.id
