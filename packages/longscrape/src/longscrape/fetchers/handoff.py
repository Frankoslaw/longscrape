"""Document-detected browser or human handoff fetcher decorator."""

from collections.abc import AsyncIterator, Callable
from typing import Protocol

from longscrape_core import (
    Document,
    Fetcher,
    FetchFailure,
    Job,
    PipelineContext,
)

type HandoffDetector = Callable[[Document, Job], FetchFailure | None]


class HandoffResolver(Protocol):
    """Resolve a detected fetch block so the wrapped fetcher can be retried."""

    async def resolve(
        self,
        *,
        job: Job,
        document: Document,
        failure: FetchFailure,
    ) -> None: ...


class HandoffFetcher:
    """Retry the wrapped fetcher after a resolver handles a blocked document.

    The resolver must make state available to the wrapped fetcher (for example,
    by updating shared cookies). A manual resolver may instead raise a typed
    ``FetchFailure`` to hand control to the application.
    """

    def __init__(
        self,
        fetcher: Fetcher,
        *,
        detector: HandoffDetector,
        handoff: HandoffResolver,
        max_handoffs: int = 1,
    ) -> None:
        if max_handoffs < 0:
            raise ValueError("max_handoffs must be non-negative")
        self._fetcher = fetcher
        self._detector = detector
        self._handoff = handoff
        self._max_handoffs = max_handoffs

    async def fetch(
        self, job: Job, context: PipelineContext | None = None
    ) -> AsyncIterator[Document]:
        for handoff_attempt in range(self._max_handoffs + 1):
            detected: tuple[Document, FetchFailure] | None = None

            async for document in self._fetcher.fetch(job, context):
                failure = self._detector(document, job)
                if failure is None:
                    yield document
                    continue
                detected = document, failure
                break

            if detected is None:
                return

            document, failure = detected
            if handoff_attempt == self._max_handoffs:
                raise failure
            await self._handoff.resolve(
                job=job,
                document=document,
                failure=failure,
            )

        raise AssertionError("unreachable")
