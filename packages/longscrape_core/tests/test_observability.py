import asyncio

import pytest
from longscrape_core.context import PipelineContext
from longscrape_core.models import Document, InputUrl, Job
from longscrape_core.observability import observe_fetcher
from longscrape_core.recovery import PipelineFailure, StageExecutionError


class FailingFetcher:
    async def fetch(self, job: Job, context: PipelineContext) -> Document:
        raise ValueError("unavailable")


class RecordingObserver:
    def __init__(self) -> None:
        self.failures: list[PipelineFailure] = []

    async def on_stage_failed(self, failure: PipelineFailure) -> None:
        self.failures.append(failure)


def test_observation_reports_failure_without_wrapping_the_original_error() -> None:
    async def run() -> RecordingObserver:
        observer = RecordingObserver()
        fetcher = observe_fetcher(FailingFetcher(), observer)
        with pytest.raises(StageExecutionError, match="fetch failed"):
            await fetcher.fetch(
                Job("article", InputUrl("https://example.com")),
                PipelineContext(),
            )
        return observer

    observer = asyncio.run(run())
    assert len(observer.failures) == 1
    assert isinstance(observer.failures[0].error, ValueError)
