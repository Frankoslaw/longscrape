from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import pytest
from longscrape_core._json import JsonInput, freeze_json_object, thaw_json_object
from longscrape_core.models import (
    Document,
    DocumentInput,
    DocumentRef,
    InputQuery,
    InputUrl,
    Job,
    JobEvent,
    JobEventType,
    JobLease,
    JobSpec,
    JobState,
    JobView,
    Record,
)


def test_job_spec_freezes_metadata_and_rejects_invalid_identity_values() -> None:
    spec = JobSpec(
        "search",
        InputQuery({"filters": {"published": True}, "page": 2}),
        metadata={"retry": 0, "tags": ["python"]},
        idempotency_key="search:python:2",
    )

    assert spec.metadata == {"retry": 0, "tags": ("python",)}
    assert spec.input == InputQuery({"filters": {"published": True}, "page": 2})

    with pytest.raises(ValueError, match="job kind"):
        JobSpec("", InputUrl("https://example.com"))
    with pytest.raises(ValueError, match="idempotency_key"):
        JobSpec("search", InputUrl("https://example.com"), idempotency_key="")


def test_json_object_helpers_freeze_copy_and_validate_values() -> None:
    source = {"nested": {"values": [1, True, None]}}
    frozen = freeze_json_object(source)
    source["nested"]["values"].append("later")

    assert thaw_json_object(frozen) == {"nested": {"values": [1, True, None]}}
    with pytest.raises(TypeError, match="not JSON-compatible"):
        freeze_json_object({"client": cast(JsonInput, object())})


def test_jobs_preserve_identity_lineage_and_json_round_trip() -> None:
    root = Job(JobSpec("root", InputUrl("https://example.com")))
    child = Job(
        JobSpec("child", InputUrl("https://example.com/child")),
        parent_id=root.id,
        root_id=root.root_id,
    )

    restored = Job.from_dict(child.to_dict())

    assert root.root_id == root.id
    assert child.parent_id == root.id
    assert child.root_id == root.id
    assert restored == child
    assert restored.kind == "child"
    assert restored.input == InputUrl("https://example.com/child")


def test_job_view_lease_and_events_validate_dashboard_state() -> None:
    job = Job(JobSpec("article", InputUrl("https://example.com")))
    checkpoint = {"next_page": 2}
    view = JobView(
        job,
        JobState.RUNNING,
        attempt=1,
        progress=0.5,
        checkpoint=checkpoint,
    )
    lease = JobLease(
        job,
        uuid4(),
        "worker-1",
        1,
        datetime.now(UTC),
        checkpoint,
    )
    event = JobEvent(job.id, JobEventType.CHECKPOINTED, data=checkpoint)

    assert view.checkpoint == lease.checkpoint == event.data == {"next_page": 2}

    with pytest.raises(ValueError, match="progress"):
        JobView(job, JobState.RUNNING, progress=1.1)
    with pytest.raises(ValueError, match="attempt"):
        JobLease(job, uuid4(), "worker-1", 0, datetime.now(UTC))


def test_document_and_record_defaults_are_utc_and_not_shared() -> None:
    first_document = Document(url="https://example.com", content=b"one")
    second_document = Document(url="https://example.org", content=b"two")
    first_record = Record(kind="article", data={"title": "One"})

    assert first_document.content_type == "text/html"
    assert first_document.status == 200
    assert first_document.fetched_at.tzinfo is UTC
    assert first_record.created_at.tzinfo is UTC
    assert first_document.headers is not second_document.headers


def test_document_input_keeps_its_archive_reference() -> None:
    ref = DocumentRef("archive", "revision-1")
    spec = JobSpec("extract", DocumentInput(ref))

    assert isinstance(spec.input, DocumentInput)
    assert spec.input.ref is ref
