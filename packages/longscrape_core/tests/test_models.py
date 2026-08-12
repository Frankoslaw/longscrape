import asyncio
from typing import Any, cast

import pytest
from longscrape_core import (
    Document,
    InMemoryDocumentStore,
    InMemoryRecordStore,
    InputDocument,
    InputQuery,
    InputUrl,
    Job,
    Record,
)


def test_job_accepts_url_input_and_context() -> None:
    job = Job(
        kind="company",
        input=InputUrl("https://example.com/company/acme"),
        context={"requested_by": "cli"},
    )

    assert job.input == InputUrl("https://example.com/company/acme")
    assert job.context == {"requested_by": "cli"}


def test_job_accepts_document_input() -> None:
    document = Document(url="https://example.com", content=b"<h1>Example</h1>")
    job = Job(kind="company", input=InputDocument(document))

    assert isinstance(job.input, InputDocument)
    assert job.input.document is document


def test_blank_job_kind_is_rejected() -> None:
    with pytest.raises(ValueError, match="kind"):
        Job(kind=" ", input=InputQuery())


def test_document_decodes_content_as_text() -> None:
    document = Document(
        url="https://example.com",
        content="Łódź".encode(),
    )

    assert document.text == "Łódź"


def test_record_preserves_document_provenance() -> None:
    document = Document(url="https://example.com", content=b"<h1>Example</h1>")
    record = Record(
        kind="company",
        source_url="https://example.com/company/example",
        data={"name": "Example Sp. z o.o."},
        document=document,
    )

    assert record.document is document


def test_blank_url_is_rejected() -> None:
    with pytest.raises(ValueError, match="url"):
        InputUrl(" ")


def test_query_input_must_be_an_object() -> None:
    with pytest.raises(TypeError, match="object"):
        InputQuery(value=cast(Any, []))


def test_in_memory_document_store_uses_document_url_as_key() -> None:
    async def check() -> None:
        store = InMemoryDocumentStore()
        document = Document(url="https://example.com", content=b"example")
        await store.save(document)
        assert await store.get(document.url) is document

    asyncio.run(check())


def test_in_memory_record_store_groups_records_by_kind() -> None:
    async def check() -> None:
        store = InMemoryRecordStore()
        first = Record(kind="company", data={}, source_url="https://example.com/one")
        second = Record(kind="person", data={}, source_url="https://example.com/two")
        await store.save(first)
        await store.save(second)
        assert store.records("company") == (first,)
        assert store.records() == (first, second)

    asyncio.run(check())
