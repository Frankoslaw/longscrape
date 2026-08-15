from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TypeAlias, cast
from uuid import uuid4

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


def _json_object(value: object, name: str) -> None:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be an object")
    try:
        json.dumps(value)
    except (TypeError, ValueError) as error:
        raise TypeError(f"{name} must be JSON serializable") from error


@dataclass(frozen=True)
class JobRef:
    """Opaque, serializable identifier of a persisted job."""

    value: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("JobRef.value must not be blank")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class DocumentRef:
    """Opaque, serializable identifier of a persisted document."""

    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("DocumentRef.value must not be blank")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class RecordRef:
    """Opaque, serializable identifier of a persisted record."""

    value: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("RecordRef.value must not be blank")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class InputUrl:
    url: str

    def __post_init__(self) -> None:
        if not self.url.strip():
            raise ValueError("InputUrl.url must not be blank")


@dataclass(frozen=True)
class InputQuery:
    value: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _json_object(self.value, "InputQuery.value")


@dataclass(frozen=True)
class Document:
    url: str
    content: bytes
    content_type: str = "text/html"
    status: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.url.strip() or not self.content_type.strip():
            raise ValueError("Document.url and content_type must not be blank")
        _json_object(self.metadata, "Document.metadata")

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


@dataclass(frozen=True)
class InputDocument:
    """A reference to source content already persisted in a DocumentStore."""

    document_ref: DocumentRef


type JobInput = InputUrl | InputQuery | InputDocument


@dataclass(frozen=True)
class Job:
    """A JSON-safe unit of work. Documents are always addressed by reference."""

    kind: str
    input: JobInput
    context: dict[str, JsonValue] = field(default_factory=dict)
    id: JobRef = field(default_factory=JobRef)

    def __post_init__(self) -> None:
        if not self.kind.strip():
            raise ValueError("Job.kind must not be blank")
        _json_object(self.context, "Job.context")

    def to_dict(self) -> dict[str, JsonValue]:
        if isinstance(self.input, InputUrl):
            input_value: dict[str, JsonValue] = {"type": "url", "url": self.input.url}
        elif isinstance(self.input, InputQuery):
            input_value = {"type": "query", "value": self.input.value}
        else:
            input_value = {
                "type": "document",
                "document_ref": self.input.document_ref.value,
            }
        return {
            "id": self.id.value,
            "kind": self.kind,
            "input": input_value,
            "context": self.context,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"), sort_keys=True)

    @classmethod
    def from_dict(cls, value: dict[str, JsonValue]) -> "Job":
        raw_input = value.get("input")
        if not isinstance(raw_input, dict) or not isinstance(
            raw_input.get("type"), str
        ):
            raise ValueError("Job input must be an object with a type")
        input_type = raw_input["type"]
        if input_type == "url" and isinstance(raw_input.get("url"), str):
            job_input: JobInput = InputUrl(cast(str, raw_input["url"]))
        elif input_type == "query" and isinstance(raw_input.get("value"), dict):
            job_input = InputQuery(cast(dict[str, JsonValue], raw_input["value"]))
        elif input_type == "document" and isinstance(
            raw_input.get("document_ref"), str
        ):
            job_input = InputDocument(DocumentRef(cast(str, raw_input["document_ref"])))
        else:
            raise ValueError(f"Unsupported job input: {input_type!r}")
        if not isinstance(value.get("id"), str) or not isinstance(
            value.get("kind"), str
        ):
            raise ValueError("Job requires string id and kind")
        context = value.get("context", {})
        if not isinstance(context, dict):
            raise ValueError("Job context must be an object")
        return cls(
            kind=cast(str, value["kind"]),
            input=job_input,
            context=cast(dict[str, JsonValue], context),
            id=JobRef(cast(str, value["id"])),
        )

    @classmethod
    def from_json(cls, value: str) -> "Job":
        raw = json.loads(value)
        if not isinstance(raw, dict):
            raise ValueError("Job JSON must be an object")
        return cls.from_dict(raw)


class JobState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRY_EXHAUSTED = "retry_exhausted"


@dataclass(frozen=True)
class JobStatus:
    ref: JobRef
    state: JobState
    retry_count: int = 0
    error: str | None = None


@dataclass(frozen=True)
class Record:
    kind: str
    data: dict[str, JsonValue]
    source_url: str
    document_ref: DocumentRef | None = None
    metadata: dict[str, JsonValue] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.kind.strip() or not self.source_url.strip():
            raise ValueError("Record.kind and source_url must not be blank")
        _json_object(self.data, "Record.data")
        _json_object(self.metadata, "Record.metadata")
