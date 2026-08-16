from datetime import UTC

from longscrape_core.domain import (
    Document,
    InputDocument,
    InputQuery,
    InputUrl,
    Job,
    JobRequest,
    Record,
)


def test_jobs_receive_distinct_ids_and_contexts() -> None:
    first = Job(kind="article", input=InputUrl("https://example.com/one"))
    second = Job(kind="article", input=InputUrl("https://example.com/two"))

    assert first.id != second.id
    assert first.context == second.context == {}
    assert first.context is not second.context


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
        context={"retry": 0, "priority": "normal"},
    )
    document_request = JobRequest(kind="extract-capture", input=InputDocument(document))

    assert url_request.input == InputUrl("https://example.com/page")
    assert query_request.input == InputQuery(query)
    assert query_request.context == {"retry": 0, "priority": "normal"}
    assert isinstance(document_request.input, InputDocument)
    assert document_request.input.document is document
