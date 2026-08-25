from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import Protocol

from longscrape.core import PipelineFailure


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


class RecoveryPolicy(Protocol):
    async def decide(self, failure: PipelineFailure) -> Recovery: ...
