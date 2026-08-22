from datetime import UTC, datetime
from uuid import uuid4

import pytest
from longscrape_core.models import InputUrl, Job
from longscrape_core.work import WorkLease, WorkRequest


def test_work_request_and_lease_validate_identity() -> None:
    job = Job("article", InputUrl("https://example.com"))
    assert WorkRequest(job).job is job
    with pytest.raises(ValueError, match="work key"):
        WorkRequest(job, key="")
    with pytest.raises(ValueError, match="worker_id"):
        WorkLease(job, uuid4(), "", 1, datetime.now(UTC))
