"""Dramatiq/Redis execution for flows registered by job kind.

Install with ``longscrape[dramatiq]``.  Worker modules create an app, register
flows at import time, and are then run using the normal ``dramatiq`` command.

Pass a stable ``worker_id`` to ``DramatiqApp.redis`` on every worker to enable
worker-pinned jobs.  They are routed to worker-specific queues while ordinary
jobs continue to use the shared queue.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

try:
    import dramatiq
    from dramatiq.brokers.redis import RedisBroker
    from dramatiq.middleware import AsyncIO
except ImportError as error:  # pragma: no cover - depends on an optional extra
    raise ImportError(
        "Dramatiq orchestration requires the 'longscrape[dramatiq]' extra"
    ) from error

from longscrape_core import StageExecutionError

from longscrape.runtime.flow import RecordFlow
from longscrape.utils import JsonValue
from longscrape.worker.context import JobContext
from longscrape.worker.models import DocumentRefInput, Job, JobRequest
from longscrape.worker.recovery import RecoveryAction, RecoveryPolicy

type FlowFactory = Callable[[JobContext], RecordFlow]


@dataclass(frozen=True)
class _DramatiqRetries:
    policy: RecoveryPolicy
    max_retries: int
    min_backoff: int = 15_000
    max_backoff: int = 604_800_000

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if self.min_backoff <= 0:
            raise ValueError("min_backoff must be positive")
        if self.max_backoff < self.min_backoff:
            raise ValueError("max_backoff must be at least min_backoff")

    def __call__(self, factory: FlowFactory) -> _RetryingFlowFactory:
        return _RetryingFlowFactory(factory, self)


@dataclass(frozen=True)
class _RetryingFlowFactory:
    factory: FlowFactory
    retries: _DramatiqRetries

    def __call__(self, context: JobContext) -> RecordFlow:
        return self.factory(context)


def dramatiq_retries(
    *,
    policy: RecoveryPolicy,
    max_retries: int,
    min_backoff: int = 15_000,
    max_backoff: int = 604_800_000,
) -> _DramatiqRetries:
    """Attach Dramatiq retry policy to a flow factory.

    Keep recovery decisions separate from ``DramatiqApp.flow`` registration;
    the application decorator remains concerned only with routing a job kind to
    its queue and factory.
    """
    return _DramatiqRetries(policy, max_retries, min_backoff, max_backoff)


class _TerminalFlowError(Exception):
    """Marks a policy decision as terminal for Dramatiq's retry middleware."""


class DramatiqJobSubmitter:
    def __init__(self, app: DramatiqApp) -> None:
        self._app = app

    async def submit_job(self, job: Job, *, delay: timedelta | None = None) -> None:
        await self._app.submit(job, delay=delay)


class DramatiqApp:
    def __init__(self, broker: RedisBroker, *, worker_id: str | None = None) -> None:
        if worker_id == "":
            raise ValueError("worker_id must not be empty")
        self._broker = broker
        self._worker_id = worker_id
        self._actors: dict[str, Any] = {}
        self._queues: dict[str, str] = {}

    @classmethod
    def redis(
        cls, *, url: str, namespace: str = "dramatiq", worker_id: str | None = None
    ) -> DramatiqApp:
        broker = RedisBroker(url=url, namespace=namespace)
        broker.add_middleware(AsyncIO())
        dramatiq.set_broker(broker)
        return cls(broker, worker_id=worker_id)

    def flow(
        self,
        *,
        kind: str,
        queue: str = "default",
    ) -> Callable[[FlowFactory], FlowFactory]:
        if not kind:
            raise ValueError("flow kind must not be empty")
        if kind in self._actors:
            raise ValueError(f"a flow is already registered for {kind!r}")

        def register(factory: FlowFactory) -> FlowFactory:
            retries = (
                factory.retries if isinstance(factory, _RetryingFlowFactory) else None
            )

            async def run(payload: Mapping[str, JsonValue]) -> None:
                job = Job.from_dict(payload)
                if job.worker_id not in {None, self._worker_id}:
                    raise _TerminalFlowError(
                        f"job is pinned to worker {job.worker_id!r}, not "
                        f"{self._worker_id!r}"
                    )
                if isinstance(job.input, DocumentRefInput):
                    raise _TerminalFlowError(
                        "DocumentRefInput requires a worker adapter"
                    )
                context = JobContext(
                    job, submitter=DramatiqJobSubmitter(self), worker_id=self._worker_id
                )
                flow = factory(context)
                try:
                    async for _ in flow(job.input, context.context):
                        pass
                except StageExecutionError as error:
                    await self._recover(error, retries)

            actor = dramatiq.actor(
                actor_name=f"longscrape.{kind}",
                queue_name=queue,
                broker=self._broker,
                max_retries=retries.max_retries if retries is not None else 0,
                min_backoff=retries.min_backoff if retries is not None else 15_000,
                max_backoff=(
                    retries.max_backoff if retries is not None else 604_800_000
                ),
                throws=(_TerminalFlowError,),
            )(run)
            self._actors[kind] = actor
            self._queues[kind] = queue
            if self._worker_id is not None:
                # Each worker consumes its own affinity queue.  A producer can
                # target it without registering that remote queue locally.
                dramatiq.actor(
                    actor_name=f"longscrape.{kind}.worker.{self._worker_id}",
                    queue_name=_affinity_queue(queue, self._worker_id),
                    broker=self._broker,
                    max_retries=retries.max_retries if retries is not None else 0,
                    min_backoff=retries.min_backoff if retries is not None else 15_000,
                    max_backoff=(
                        retries.max_backoff if retries is not None else 604_800_000
                    ),
                    throws=(_TerminalFlowError,),
                )(run)
            return factory

        return register

    async def submit(
        self, job: Job | JobRequest, *, delay: timedelta | None = None
    ) -> None:
        if isinstance(job, JobRequest):
            job = Job.spawn_job(job)
        try:
            actor = self._actors[job.kind]
        except KeyError as error:
            raise LookupError(
                f"no Dramatiq flow is registered for {job.kind!r}"
            ) from error

        payload = job.to_dict()
        if delay is None:
            if job.worker_id is None:
                actor.send(payload)
            else:
                self._send_to_worker(actor, job.kind, job.worker_id, payload)
        else:
            if job.worker_id is None:
                actor.send_with_options(
                    args=(payload,), delay=round(delay.total_seconds() * 1000)
                )
            else:
                self._send_to_worker(
                    actor,
                    job.kind,
                    job.worker_id,
                    payload,
                    delay=round(delay.total_seconds() * 1000),
                )

    def _send_to_worker(
        self,
        actor: Any,
        kind: str,
        worker_id: str,
        payload: Mapping[str, JsonValue],
        *,
        delay: int | None = None,
    ) -> None:
        """Send to a worker-specific queue without consuming it locally."""
        message = actor.message_with_options(args=(payload,)).copy(
            actor_name=f"longscrape.{kind}.worker.{worker_id}",
            queue_name=_affinity_queue(self._queues[kind], worker_id),
        )
        self._broker.enqueue(message, delay=delay)

    @staticmethod
    async def _recover(
        error: StageExecutionError, retries: _DramatiqRetries | None
    ) -> None:
        if retries is None:
            raise _TerminalFlowError("flow retries are not configured") from error

        recovery = await retries.policy.decide(error.failure)
        if recovery.action is RecoveryAction.RETRY:
            delay = (
                round(recovery.delay.total_seconds() * 1000)
                if recovery.delay is not None
                else None
            )
            raise dramatiq.Retry(
                recovery.reason or "longscrape retry", delay=delay
            ) from error

        raise _TerminalFlowError(recovery.reason or "longscrape flow failed") from error


def _affinity_queue(queue: str, worker_id: str) -> str:
    return f"{queue}.worker.{worker_id}"
