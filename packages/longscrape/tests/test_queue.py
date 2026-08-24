import asyncio

from longscrape import InputUrl
from longscrape.worker import InMemoryJobQueue, Job, JobContext, JobRequest


def test_worker_context_submits_child_job() -> None:
    async def run() -> Job:
        queue = InMemoryJobQueue()
        parent = Job.spawn_job(JobRequest("root", InputUrl("https://example.com")))
        await JobContext(parent, submitter=queue).submit_child(
            JobRequest("child", InputUrl("https://example.com/child"))
        )
        return await queue.get()

    child = asyncio.run(run())
    assert child.parent_id is not None
    assert child.kind == "child"
