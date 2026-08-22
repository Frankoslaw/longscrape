from datetime import UTC, datetime
from uuid import uuid4

import pytest
from longscrape_core.models import (
    DocumentRef,
    InputDocument,
    InputQuery,
    InputUrl,
    Job,
    JobInput,
)
from longscrape_core.serialization import job_from_json, job_to_json


@pytest.mark.parametrize(
    "input",
    [
        InputUrl("https://example.com"),
        InputQuery({"page": 2, "filters": {"ready": True}}),
        InputDocument(DocumentRef("archive", "revision-1")),
    ],
)
def test_job_json_round_trip_preserves_each_input(input: JobInput) -> None:
    job = Job(
        "article",
        input,
        {"source": "test"},
        id=uuid4(),
        root_id=uuid4(),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert job_from_json(job_to_json(job)) == job


def test_job_json_rejects_unknown_input_type() -> None:
    value = job_to_json(Job("article", InputUrl("https://example.com")))
    value["input"] = {"type": "unknown"}

    with pytest.raises(ValueError, match="unknown job input type"):
        job_from_json(value)
