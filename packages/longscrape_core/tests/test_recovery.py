from datetime import timedelta

import pytest
from longscrape_core.models import InputUrl, Job
from longscrape_core.recovery import (
    PipelineFailure,
    PipelineStage,
    Recovery,
    RecoveryAction,
)


def test_recovery_rejects_invalid_delays() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        Recovery(RecoveryAction.RETRY, delay=timedelta(seconds=-1))
    with pytest.raises(ValueError, match="only retry"):
        Recovery(RecoveryAction.HANDOFF, delay=timedelta(seconds=1))


def test_pipeline_failure_is_optional_context_for_direct_stage_calls() -> None:
    job = Job("article", InputUrl("https://example.com"))
    error = ValueError("bad document")
    failure = PipelineFailure(PipelineStage.EXTRACT, job, error)

    assert failure.job is job
    assert failure.error is error
