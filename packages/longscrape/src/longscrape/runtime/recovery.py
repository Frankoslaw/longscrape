"""Optional retry decision contract for workers."""

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import Protocol

from longscrape_core.failures import Failure


class RecoveryAction(Enum):
    RETRY = "retry"
    FAIL = "fail"


@dataclass(frozen=True)
class Recovery:
    action: RecoveryAction
    delay: timedelta | None = None

    def __post_init__(self) -> None:
        if self.delay is not None and (
            self.delay < timedelta() or self.action is not RecoveryAction.RETRY
        ):
            raise ValueError("only non-negative retry delays are valid")


class RecoveryPolicy(Protocol):
    async def decide(self, failure: Failure) -> Recovery: ...
