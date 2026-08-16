import asyncio

from longscrape_core.domain import InputQuery, JobRequest
from longscrape_core.ports import DISCARD_SUBMITTER, NullJobSubmitter


def test_discard_submitter_accepts_json_safe_job_requests() -> None:
    request = JobRequest(
        kind="search",
        input=InputQuery({"query": "longscrape", "page": 1}),
        context={"attempt": 0},
    )

    assert asyncio.run(DISCARD_SUBMITTER.submit(request)) is None
    assert asyncio.run(NullJobSubmitter().submit(request)) is None
