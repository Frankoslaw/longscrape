"""Failures from independently callable core stages."""

from dataclasses import dataclass
from enum import Enum


class Stage(Enum):
    FETCH = "fetch"
    EXTRACT = "extract"
    TRANSFORM = "transform"
    SINK = "sink"


@dataclass(frozen=True)
class StageFailure:
    stage: Stage
    error: Exception


class StageError(Exception):
    """A stage failed; no runtime/job assumptions are attached."""

    def __init__(self, failure: StageFailure) -> None:
        super().__init__(f"{failure.stage.value} failed: {failure.error}")
        self.failure = failure
