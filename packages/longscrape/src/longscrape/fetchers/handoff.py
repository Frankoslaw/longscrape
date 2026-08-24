"""A local recovery executor for fetch failures that require human handoff."""

import asyncio
from collections.abc import Callable
from typing import Protocol

from longscrape_core import (
    Context,
    Document,
    Fetcher,
    PipelineFailure,
    PipelineStage,
)

from longscrape.worker import Recovery, RecoveryAction, RecoveryPolicy


class HandoffResolver(Protocol):
    """Perform a handoff, then make its resulting state available to a retry."""

    async def resolve(self, failure: PipelineFailure) -> None: ...


type FailureDetector = Callable[[Document], Exception | None]


class HandoffFetcher:
    """Apply a recovery policy to failures from one wrapped fetcher.

    This decorator is intentionally local: it only retries the wrapped fetcher.
    An optional detector may turn an unsuccessful document (such as a login
    page returned with HTTP 200) into an ordinary exception. A ``HANDOFF``
    decision calls the resolver before retrying; a ``RETRY`` decision waits
    for its optional delay; ``FAIL`` re-raises the exception. Without a
    policy, only a failure reported by the detector triggers a handoff.
    """

    def __init__(
        self,
        fetcher: Fetcher,
        *,
        policy: RecoveryPolicy | None = None,
        handoff: HandoffResolver,
        detector: FailureDetector | None = None,
        max_recoveries: int = 1,
    ) -> None:
        if max_recoveries < 0:
            raise ValueError("max_recoveries must be non-negative")
        self._fetcher = fetcher
        self._policy = policy
        self._handoff = handoff
        self._detector = detector
        self._max_recoveries = max_recoveries

    async def fetch(self, fetch_input, context: Context) -> Document:
        for attempt in range(self._max_recoveries + 1):
            detected = False
            try:
                # As with ordinary retries, defer output until the attempt has
                # completed so a recovery cannot replay partial output.
                document = await self._fetcher.fetch(fetch_input, context)
                if self._detector is not None:
                    error = self._detector(document)
                    if error is not None:
                        detected = True
                        raise error
                return document
            except Exception as error:
                failure = PipelineFailure(PipelineStage.FETCH, error, context)
                recovery = (
                    await self._policy.decide(failure)
                    if self._policy is not None
                    else Recovery(
                        RecoveryAction.HANDOFF if detected else RecoveryAction.FAIL
                    )
                )
                if (
                    recovery.action is RecoveryAction.FAIL
                    or attempt == self._max_recoveries
                ):
                    raise
                if recovery.action is RecoveryAction.HANDOFF:
                    await self._handoff.resolve(failure)
                elif recovery.action is RecoveryAction.RETRY and recovery.delay:
                    await asyncio.sleep(recovery.delay.total_seconds())

        raise AssertionError("unreachable")
