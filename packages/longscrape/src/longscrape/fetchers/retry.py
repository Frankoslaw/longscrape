"""A local retry executor driven by a recovery policy."""

import asyncio
from collections.abc import AsyncIterator

from longscrape_core import (
    Document,
    Fetcher,
    Job,
    PipelineContext,
    PipelineFailure,
    PipelineStage,
    Recovery,
    RecoveryAction,
    RecoveryPolicy,
)


class RetryingFetcher:
    """Retry a wrapped fetcher, optionally using a recovery policy."""

    def __init__(
        self,
        fetcher: Fetcher,
        *,
        policy: RecoveryPolicy | None = None,
        max_retries: int = 0,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        self._fetcher = fetcher
        self._policy = policy
        self._max_retries = max_retries

    async def fetch(
        self, job: Job, context: PipelineContext | None = None
    ) -> AsyncIterator[Document]:
        for attempt in range(self._max_retries + 1):
            try:
                # Do not expose a partial attempt: a subsequent retry restarts
                # the wrapped fetcher and would otherwise duplicate documents
                # already consumed by downstream stages.
                documents: list[Document] = []
                async for document in self._fetcher.fetch(job, context):
                    documents.append(document)
                for document in documents:
                    yield document
                return
            except Exception as error:
                failure = PipelineFailure(PipelineStage.FETCH, job, error, context)
                recovery = (
                    await self._policy.decide(failure)
                    if self._policy is not None
                    else Recovery(RecoveryAction.RETRY)
                )
                if (
                    recovery.action is not RecoveryAction.RETRY
                    or attempt == self._max_retries
                ):
                    raise
                if recovery.delay:
                    await asyncio.sleep(recovery.delay.total_seconds())

        raise AssertionError("unreachable")
