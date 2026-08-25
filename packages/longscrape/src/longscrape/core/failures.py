from dataclasses import dataclass
from datetime import timedelta
from enum import Enum

from longscrape.core.context import Context


class PipelineStage(Enum):
    FETCH = "fetch"
    EXTRACT = "extract"
    TRANSFORM = "transform"


@dataclass(frozen=True)
class PipelineFailure:
    """A stage exception, independent of a particular execution model."""

    stage: PipelineStage
    error: Exception
    context: Context | None = None


class StageExecutionError(Exception):
    def __init__(self, failure: PipelineFailure) -> None:
        super().__init__(f"{failure.stage.value} failed")
        self.failure = failure

    @property
    def error(self) -> Exception:
        return self.failure.error


@dataclass(frozen=True)
class HttpStatusError(Exception):
    url: str
    status: int
    retry_after: timedelta | None = None

    def __str__(self) -> str:
        return f"HTTP request to {self.url} failed with status {self.status}"
