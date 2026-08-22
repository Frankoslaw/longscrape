from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from types import MappingProxyType
from typing import Self, cast
from uuid import UUID, uuid4

from longscrape_core._json import (
    FrozenJsonObject,
    JsonInput,
    JsonObject,
    JsonValue,
    freeze_json_object,
    thaw_json_object,
)


@dataclass(frozen=True)
class InputUrl:
    url: str


@dataclass(frozen=True)
class InputQuery:
    query: Mapping[str, JsonInput]

    def __post_init__(self) -> None:
        object.__setattr__(self, "query", freeze_json_object(self.query))


@dataclass(frozen=True)
class DocumentRef:
    """Opaque reference to a document retained by an archive."""

    store: str
    value: str


@dataclass(frozen=True)
class RecordRef:
    """Opaque reference to a stored record."""

    store: str
    value: str


@dataclass(frozen=True)
class DocumentInput:
    """Job input for a document revision retained by an archive."""

    ref: DocumentRef


type JobInput = InputUrl | InputQuery | DocumentInput


@dataclass(frozen=True)
class JobSpec:
    """Immutable application request for work to be performed."""

    kind: str
    input: JobInput
    metadata: Mapping[str, JsonInput] = field(default_factory=dict)
    idempotency_key: str | None = None
    run_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.kind:
            raise ValueError("job kind must not be empty")
        if self.idempotency_key == "":
            raise ValueError("idempotency_key must not be empty")
        object.__setattr__(self, "metadata", freeze_json_object(self.metadata))


@dataclass(frozen=True)
class Job:
    """A durable job identity and its immutable lineage."""

    spec: JobSpec
    id: UUID = field(default_factory=uuid4)
    parent_id: UUID | None = None
    root_id: UUID | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if self.root_id is None:
            object.__setattr__(self, "root_id", self.id)

    @property
    def kind(self) -> str:
        return self.spec.kind

    @property
    def input(self) -> JobInput:
        return self.spec.input

    @property
    def metadata(self) -> FrozenJsonObject:
        return cast(FrozenJsonObject, self.spec.metadata)

    def to_dict(self) -> JsonObject:
        """Return the JSON payload used by durable work implementations."""

        return {
            "id": str(self.id),
            "parent_id": str(self.parent_id) if self.parent_id else None,
            "root_id": str(self.root_id),
            "created_at": self.created_at.isoformat(),
            "spec": {
                "kind": self.spec.kind,
                "input": _input_to_dict(self.spec.input),
                "metadata": thaw_json_object(
                    cast(FrozenJsonObject, self.spec.metadata)
                ),
                "idempotency_key": self.spec.idempotency_key,
                "run_at": self.spec.run_at.isoformat() if self.spec.run_at else None,
            },
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, JsonValue]) -> Self:
        spec_value = cast(Mapping[str, JsonValue], value["spec"])
        run_at = cast(str | None, spec_value.get("run_at"))
        parent_id = cast(str | None, value.get("parent_id"))
        return cls(
            id=UUID(cast(str, value["id"])),
            parent_id=UUID(parent_id) if parent_id else None,
            root_id=UUID(cast(str, value["root_id"])),
            created_at=datetime.fromisoformat(cast(str, value["created_at"])),
            spec=JobSpec(
                kind=cast(str, spec_value["kind"]),
                input=_input_from_dict(
                    cast(Mapping[str, JsonValue], spec_value["input"])
                ),
                metadata=cast(Mapping[str, JsonInput], spec_value.get("metadata", {})),
                idempotency_key=cast(str | None, spec_value.get("idempotency_key")),
                run_at=datetime.fromisoformat(run_at) if run_at else None,
            ),
        )


class JobState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobEventType(Enum):
    ENQUEUED = "enqueued"
    CLAIMED = "claimed"
    CHECKPOINTED = "checkpointed"
    RETRIED = "retried"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class JobView:
    """Current durable state of a job, suitable for status displays."""

    job: Job
    state: JobState
    attempt: int = 0
    progress: float | None = None
    checkpoint: Mapping[str, JsonInput] | None = None
    error: str | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if self.attempt < 0:
            raise ValueError("attempt must not be negative")
        if self.progress is not None and not 0 <= self.progress <= 1:
            raise ValueError("progress must be between zero and one")
        if self.checkpoint is not None:
            object.__setattr__(self, "checkpoint", freeze_json_object(self.checkpoint))


@dataclass(frozen=True)
class JobLease:
    """Exclusive, expiring authority to execute one job attempt."""

    job: Job
    token: UUID
    worker_id: str
    attempt: int
    expires_at: datetime
    checkpoint: Mapping[str, JsonInput] | None = None

    def __post_init__(self) -> None:
        if not self.worker_id:
            raise ValueError("worker_id must not be empty")
        if self.attempt < 1:
            raise ValueError("attempt must be at least one")
        if self.checkpoint is not None:
            object.__setattr__(self, "checkpoint", freeze_json_object(self.checkpoint))


@dataclass(frozen=True)
class JobEvent:
    """An append-only durable job event for audit and dashboard views."""

    job_id: UUID
    type: JobEventType
    at: datetime = field(default_factory=lambda: datetime.now(UTC))
    data: Mapping[str, JsonInput] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", freeze_json_object(self.data))


@dataclass(frozen=True)
class Document:
    url: str
    content: bytes
    content_type: str = "text/html"
    status: int = 200
    headers: Mapping[str, str] = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))


@dataclass(frozen=True)
class Record[T]:
    kind: str
    data: T
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def hash(self) -> str:
        payload = json.dumps(
            {"kind": self.kind, "data": self.data},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def merge_records(
    existing: Record[dict[str, JsonValue]], incoming: Record[dict[str, JsonValue]]
) -> Record[dict[str, JsonValue]]:
    """Fill missing or ``None`` fields without replacing known values."""

    if existing.kind != incoming.kind:
        raise ValueError("cannot merge records with different kinds")
    data = dict(existing.data)
    for key, value in incoming.data.items():
        if data.get(key) is None:
            data[key] = value
    return Record(existing.kind, data, created_at=incoming.created_at)


def _input_to_dict(input: JobInput) -> JsonObject:
    match input:
        case InputUrl(url):
            return {"type": "url", "url": url}
        case InputQuery(query):
            return {
                "type": "query",
                "query": thaw_json_object(cast(FrozenJsonObject, query)),
            }
        case DocumentInput(DocumentRef(store, value)):
            return {"type": "document-ref", "store": store, "ref": value}


def _input_from_dict(value: Mapping[str, JsonValue]) -> JobInput:
    match value["type"]:
        case "url":
            return InputUrl(cast(str, value["url"]))
        case "query":
            return InputQuery(cast(Mapping[str, JsonInput], value["query"]))
        case "document-ref":
            return DocumentInput(
                DocumentRef(cast(str, value["store"]), cast(str, value["ref"]))
            )
        case input_type:
            raise ValueError(f"unknown job input type: {input_type!r}")
