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


def test_queue_only_delivers_a_pinned_job_to_its_worker() -> None:
    async def run() -> tuple[Job, Job]:
        queue = InMemoryJobQueue()
        pinned = Job.spawn_job(
            JobRequest(
                "pinned",
                InputUrl("https://example.com/pinned"),
                worker_id="browser-a",
            )
        )
        unpinned = Job.spawn_job(JobRequest("open", InputUrl("https://example.com")))
        await queue.submit_job(pinned)
        await queue.submit_job(unpinned)
        first = await queue.get(worker_id="browser-b")
        second = await queue.get(worker_id="browser-a")
        return first, second

    first, second = asyncio.run(run())

    assert first.kind == "open"
    assert second.kind == "pinned"
    assert second.worker_id == "browser-a"


def test_queue_wakes_the_matching_filtered_consumer() -> None:
    async def run() -> Job:
        queue = InMemoryJobQueue()
        other = asyncio.create_task(queue.get(kind="other"))
        await asyncio.sleep(0)
        matching = asyncio.create_task(queue.get(kind="article"))
        await asyncio.sleep(0)
        await queue.submit(JobRequest("article", InputUrl("https://example.com")))
        try:
            return await asyncio.wait_for(matching, timeout=0.1)
        finally:
            other.cancel()

    assert asyncio.run(run()).kind == "article"
