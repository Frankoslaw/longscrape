"""Canonical JSON representation for durable core values."""

from collections.abc import Mapping
from datetime import datetime
from typing import cast
from uuid import UUID

from longscrape_core._json import (
    FrozenJsonObject,
    JsonInput,
    JsonObject,
    JsonValue,
    thaw_json_object,
)
from longscrape_core.models import (
    DocumentRef,
    InputDocument,
    InputQuery,
    InputUrl,
    Job,
    JobInput,
)


def job_to_json(job: Job) -> JsonObject:
    """Encode a job in the format every durable work implementation must use."""
    return {
        "id": str(job.id),
        "kind": job.kind,
        "input": _input_to_json(job.input),
        "metadata": thaw_json_object(cast(FrozenJsonObject, job.metadata)),
        "parent_id": str(job.parent_id) if job.parent_id else None,
        "root_id": str(job.root_id),
        "created_at": job.created_at.isoformat(),
    }


def job_from_json(value: Mapping[str, JsonValue]) -> Job:
    """Decode a job previously returned by :func:`job_to_json`."""
    input_value = _object(value, "input")
    metadata = _object(value, "metadata")
    parent_id = value.get("parent_id")
    if parent_id is not None and not isinstance(parent_id, str):
        raise ValueError("job parent_id must be a string or null")
    return Job(
        kind=_string(value, "kind"),
        input=_input_from_json(input_value),
        metadata=cast(Mapping[str, JsonInput], metadata),
        id=UUID(_string(value, "id")),
        parent_id=UUID(parent_id) if parent_id else None,
        root_id=UUID(_string(value, "root_id")),
        created_at=datetime.fromisoformat(_string(value, "created_at")),
    )


def _input_to_json(input: JobInput) -> JsonObject:
    if isinstance(input, InputUrl):
        return {"type": "url", "url": input.url}
    if isinstance(input, InputQuery):
        return {
            "type": "query",
            "query": thaw_json_object(cast(FrozenJsonObject, input.query)),
        }
    return {
        "type": "document",
        "store": input.ref.store,
        "value": input.ref.value,
    }


def _input_from_json(value: Mapping[str, JsonValue]) -> JobInput:
    match _string(value, "type"):
        case "url":
            return InputUrl(_string(value, "url"))
        case "query":
            return InputQuery(cast(Mapping[str, JsonInput], _object(value, "query")))
        case "document":
            return InputDocument(
                DocumentRef(_string(value, "store"), _string(value, "value"))
            )
        case kind:
            raise ValueError(f"unknown job input type: {kind!r}")


def _object(value: Mapping[str, JsonValue], key: str) -> Mapping[str, JsonValue]:
    item = value.get(key)
    if not isinstance(item, Mapping):
        raise ValueError(f"job {key} must be an object")
    return cast(Mapping[str, JsonValue], item)


def _string(value: Mapping[str, JsonValue], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str):
        raise ValueError(f"job {key} must be a string")
    return item
