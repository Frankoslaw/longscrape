import asyncio

from longscrape_core.context import PipelineContext
from longscrape_core.models import InputQuery, Job, JobRequest


def test_context_without_submitter_rejects_follow_up_jobs() -> None:
    request = JobRequest(
        kind="search",
        input=InputQuery({"query": "longscrape", "page": 1}),
        metadata={"attempt": 0},
    )

    try:
        asyncio.run(
            PipelineContext().submit_child(
                Job.spawn_job(request),
                request,
            )
        )
    except RuntimeError as error:
        assert str(error) == "PipelineContext has no job submitter"
    else:
        raise AssertionError("expected submitting without a submitter to fail")
