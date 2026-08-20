"""Failure context and recovery decisions shared by pipeline integrations."""

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum

from longscrape_core.context import PipelineContext
from longscrape_core.models import Job


class RecoveryAction(Enum):
    """An action a recovery policy recommends for a pipeline failure."""

    RETRY = "retry"
    HANDOFF = "handoff"
    FAIL = "fail"


@dataclass(frozen=True)
class Recovery:
    """An execution-neutral recommendation for handling a failure."""

    action: RecoveryAction
    delay: timedelta | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.delay is not None and self.delay < timedelta():
            raise ValueError("recovery delay must be non-negative")
        if self.delay is not None and self.action is not RecoveryAction.RETRY:
            raise ValueError("only retry recoveries may specify a delay")


class PipelineStage(Enum):
    """The pipeline boundary from which an exception escaped."""

    FETCH = "fetch"
    EXTRACT = "extract"
    TRANSFORM = "transform"


@dataclass(frozen=True)
class PipelineFailure:
    """An exception plus the context of one failed stage invocation.

    This is a core recovery value, not a statement about how stages are
    composed. A caller can create or consume it while using one stage, a
    hand-written composition, or a higher-level runtime.
    """

    stage: PipelineStage
    job: Job
    error: Exception
    context: PipelineContext | None = None


class StageExecutionError(Exception):
    """A failed observed stage, preserving the original exception as a cause."""

    def __init__(self, failure: PipelineFailure) -> None:
        super().__init__(f"{failure.stage.value} failed for job {failure.job.id}")
        self.failure = failure

    @property
    def error(self) -> Exception:
        return self.failure.error


@dataclass(frozen=True)
class HttpStatusError(Exception):
    """An unsuccessful HTTP response returned by a fetcher."""

    url: str
    status: int
    retry_after: timedelta | None = None

    def __str__(self) -> str:
        return f"HTTP request to {self.url} failed with status {self.status}"
