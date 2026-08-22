from datetime import UTC
from typing import cast

import pytest
from longscrape_core._json import (
    JsonInput,
    freeze_json_object,
    thaw_json_object,
)
from longscrape_core.models import (
    DocumentRef,
    InputDocument,
    InputQuery,
    InputUrl,
    Job,
    Record,
)
from longscrape_core.storage import require_record_key


def test_json_values_are_frozen_copied_and_validated() -> None:
    source = {"nested": {"values": [1, True, None]}}
    frozen = freeze_json_object(source)
    source["nested"]["values"].append("later")

    assert thaw_json_object(frozen) == {"nested": {"values": [1, True, None]}}
    with pytest.raises(TypeError, match="not JSON-compatible"):
        freeze_json_object({"client": cast(JsonInput, object())})


def test_job_is_usable_without_a_work_runtime_and_preserves_lineage() -> None:
    root = Job("root", InputUrl("https://example.com"), {"source": "test"})
    child = root.child("child", InputQuery({"page": 2}), page=2)

    assert root.root_id == root.id
    assert child.parent_id == root.id
    assert child.root_id == root.id
    assert child.metadata == {"page": 2}
    with pytest.raises(ValueError, match="job kind"):
        Job("", InputUrl("https://example.com"))


def test_job_can_start_from_a_referenced_document() -> None:
    ref = DocumentRef("archive", "revision-1")
    job = Job("extract", InputDocument(ref))

    assert isinstance(job.input, InputDocument)
    assert job.input.ref is ref

    with pytest.raises(ValueError, match="reference store"):
        DocumentRef("", "revision-1")
    with pytest.raises(ValueError, match="reference value"):
        DocumentRef("archive", "")


def test_document_and_record_values_validate_stable_identity() -> None:
    record = Record("article", {"title": "One"}, key="article:1")
    assert record.created_at.tzinfo is UTC
    with pytest.raises(ValueError, match="record key"):
        Record("article", {}, key="")
    with pytest.raises(ValueError, match="stable record key"):
        require_record_key(Record("article", {}))
