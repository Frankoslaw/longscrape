import asyncio
from datetime import timedelta

import pytest
from longscrape_core import (
    InMemoryJobQueue,
    InMemoryJobStore,
    InputUrl,
    Job,
    JobManager,
    JobState,
)


def test_manager_hides_store_queue_coordination_and_tracks_retries() -> None:
    async def check() -> None:
        manager = JobManager(InMemoryJobStore(), InMemoryJobQueue(), max_retries=1)
        ref = await manager.submit(
            Job(kind="url", input=InputUrl("https://example.com"))
        )
        lease = await manager.lease("url")
        assert lease is not None
        assert lease.job.id == ref
        await lease.retry("temporary")
        pending_status = await manager.status(ref)
        assert pending_status is not None
        assert pending_status.state == JobState.PENDING
        retry = await manager.lease("url")
        assert retry is not None
        await retry.retry("still broken")
        status = await manager.status(ref)
        assert status is not None
        assert status.state == JobState.RETRY_EXHAUSTED
        assert status.retry_count == 2

    asyncio.run(check())


def test_queue_rejects_stale_lease_and_reclaims_expired_one() -> None:
    async def check() -> None:
        queue = InMemoryJobQueue(lease_duration=timedelta(seconds=1))
        job = Job(kind="url", input=InputUrl("https://example.com"))
        assert await queue.enqueue(job.id, kind=job.kind)
        first = await queue.lease("url", duration=timedelta(microseconds=1))
        assert first is not None
        second = await queue.lease("url")
        assert second is not None
        assert second.ref == first.ref
        with pytest.raises(ValueError, match="invalid"):
            await queue.acknowledge(first)
        await queue.acknowledge(second)

    asyncio.run(check())
