"""Executor-neutral durable worker."""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

from longscrape_core import (
    JobExecutionError,
    JobExecutor,
    PipelineContext,
    RecoveryAction,
    RecoveryPolicy,
    WorkStore,
)

from longscrape.runtime.context import JOB_CONTEXT, JobContext, WorkSubmitter


class Worker:
    def __init__(
        self,
        store: WorkStore,
        executors: Mapping[str, JobExecutor],
        recovery: RecoveryPolicy | None,
        worker_id: str,
        *,
        lease_for: timedelta = timedelta(minutes=5),
    ) -> None:
        self._store = store
        self._executors = executors
        self._recovery = recovery
        self._worker_id = worker_id
        self._lease_for = lease_for

    @property
    def worker_id(self) -> str:
        return self._worker_id

    async def run_once(self) -> bool:
        lease = await self._store.claim(
            worker_id=self._worker_id, lease_for=self._lease_for
        )
        if lease is None:
            return False
        await self.run_lease(lease)
        return True

    async def run_lease(self, lease) -> None:
        try:
            executor = self._executors[lease.job.kind]
        except KeyError as error:
            await self._store.fail(lease, str(error))
            return
        try:
            context = PipelineContext()
            context.set(JOB_CONTEXT, JobContext(lease.job, WorkSubmitter(self._store)))
            await executor.execute(lease.job, context)
        except JobExecutionError as error:
            if self._recovery is not None:
                decision = await self._recovery.decide(error.failure)
                if decision.action is RecoveryAction.RETRY:
                    await self._store.retry(
                        lease,
                        run_at=datetime.now(UTC) + (decision.delay or timedelta()),
                    )
                    return
            await self._store.fail(lease, str(error))
        except Exception as error:
            await self._store.fail(lease, str(error))
        else:
            await self._store.complete(lease)
