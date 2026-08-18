# TODO: How should more generalized failures be handled for other parts of pipeline
# as currently all of them would result in abort. Also the notion of Recovery object
# is interesting to introduce Retry, Pause and Fail where Pause would be for example
# used for manual handoff after which it would become Fail if not synced.
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum


class FetchFailureKind(Enum):
    NETWORK = "network"
    TIMEOUT = "timeout"
    HTTP_STATUS = "http_status"
    RATE_LIMITED = "rate_limited"
    BLOCKED = "blocked"
    INVALID_INPUT = "invalid_input"


@dataclass(frozen=True)
class FetchFailure(Exception):
    kind: FetchFailureKind
    message: str
    url: str | None = None
    status: int | None = None
    retry_after: timedelta | None = None
    cause: Exception | None = None

    def __str__(self) -> str:
        return self.message


class RetryableFetchFailure(FetchFailure): ...


class BrowserHandoffRequired(FetchFailure): ...
