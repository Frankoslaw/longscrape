from datetime import UTC

from longscrape_core.models import (
    Document,
    DocumentInput,
    DocumentRef,
    InputQuery,
    InputUrl,
    Job,
    JobRequest,
    Record,
)


def test_jobs_receive_distinct_ids_and_immutable_metadata() -> None:
    first = Job(kind="article", input=InputUrl("https://example.com/one"))
    second = Job(kind="article", input=InputUrl("https://example.com/two"))

    assert first.id != second.id
    assert first.metadata == second.metadata == {}


def test_worker_pin_is_serialized_and_inherited_by_child_jobs() -> None:
    root = Job.spawn_job(
        JobRequest("root", InputUrl("https://example.com"), worker_id="worker-1")
    )
    child = root.spawn_child(JobRequest("child", InputUrl("https://example.com/child")))

    assert Job.from_dict(root.to_dict()).worker_id == "worker-1"
    assert child.worker_id == "worker-1"


def test_spawned_jobs_track_their_root_and_parent() -> None:
    root = Job.spawn_job(JobRequest("root", InputUrl("https://example.com")))
    child = root.spawn_child(JobRequest("child", InputUrl("https://example.com/1")))
    grandchild = child.spawn_child(
        JobRequest("grandchild", InputUrl("https://example.com/2"))
    )

    assert root.parent_id is None
    assert root.root_id == root.id
    assert child.parent_id == root.id
    assert child.root_id == root.id
    assert grandchild.parent_id == child.id
    assert grandchild.root_id == root.id


def test_document_and_record_defaults_are_utc_and_not_shared() -> None:
    first_document = Document(url="https://example.com", content=b"one")
    second_document = Document(url="https://example.org", content=b"two")
    first_record = Record(kind="article", data={"title": "One"})

    assert first_document.content_type == "text/html"
    assert first_document.status == 200
    assert first_document.fetched_at.tzinfo is UTC
    assert first_record.created_at.tzinfo is UTC
    assert first_document.headers is not second_document.headers


def test_job_inputs_preserve_structured_queue_payloads() -> None:
    document = Document(
        url="https://example.com/page",
        content=b"<html></html>",
        headers={"content-language": "en"},
    )
    query = {
        "filters": {"published": True, "tags": ["python", "async"]},
        "page": 2,
    }

    url_request = JobRequest(kind="fetch-url", input=InputUrl(document.url))
    query_request = JobRequest(
        kind="search",
        input=InputQuery(query),
        metadata={"retry": 0, "priority": "normal"},
    )
    document_ref = DocumentRef("test", "capture")
    document_request = JobRequest(
        kind="extract-capture", input=DocumentInput(document_ref)
    )

    assert url_request.input == InputUrl("https://example.com/page")
    assert query_request.input == InputQuery(query)
    assert query_request.metadata == {"retry": 0, "priority": "normal"}
    assert isinstance(document_request.input, DocumentInput)
    assert document_request.input.ref is document_ref


def test_job_hashes_are_stable_for_all_input_types() -> None:
    assert (
        Job(kind="fetch", input=InputUrl("https://example.com")).hash
        == Job(kind="fetch", input=InputUrl("https://example.com")).hash
    )
    assert (
        Job(kind="search", input=InputQuery({"page": 1})).hash
        == Job(kind="search", input=InputQuery({"page": 1})).hash
    )
    assert (
        Job(kind="extract", input=DocumentInput(DocumentRef("test", "capture"))).hash
        == Job(kind="extract", input=DocumentInput(DocumentRef("test", "capture"))).hash
    )
