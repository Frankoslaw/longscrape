"""Optional failure values and recovery-policy contract."""

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import Protocol

from longscrape_core.context import PipelineContext
from longscrape_core.models import Job


class RecoveryAction(Enum):
    RETRY = "retry"
    HANDOFF = "handoff"
    FAIL = "fail"


@dataclass(frozen=True)
class Recovery:
    action: RecoveryAction
    delay: timedelta | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.delay is not None and self.delay < timedelta():
            raise ValueError("recovery delay must be non-negative")
        if self.delay is not None and self.action is not RecoveryAction.RETRY:
            raise ValueError("only retry recoveries may specify a delay")


class PipelineStage(Enum):
    FETCH = "fetch"
    EXTRACT = "extract"
    TRANSFORM = "transform"
    SINK = "sink"


@dataclass(frozen=True)
class PipelineFailure:
    stage: PipelineStage
    job: Job
    error: Exception
    context: PipelineContext | None = None


class RecoveryPolicy(Protocol):
    async def decide(self, failure: PipelineFailure) -> Recovery: ...


@dataclass(frozen=True)
class HttpStatusError(Exception):
    url: str
    status: int
    retry_after: timedelta | None = None

    def __str__(self) -> str:
        return f"HTTP request to {self.url} failed with status {self.status}"
