from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from types import MappingProxyType
from typing import Self, cast

from longscrape_core._json import FrozenJsonValue, JsonValue, _freeze_json, _thaw_json


@dataclass(frozen=True)
class InputUrl:
    url: str


@dataclass(frozen=True)
class InputQuery:
    query: Mapping[str, FrozenJsonValue]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "query",
            MappingProxyType(
                {key: _freeze_json(value) for key, value in self.query.items()}
            ),
        )


@dataclass(frozen=True)
class DocumentRef:
    """Opaque capability for one immutable document revision."""

    store: str
    value: str


@dataclass(frozen=True)
class RecordRef:
    """Opaque capability for one stored record."""

    store: str
    value: str


class CollisionPolicy(Enum):
    """How a store handles a write when a stable key already exists."""

    NEW = "new"
    OVERWRITE = "overwrite"
    MERGE = "merge"


class JobStatus(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class DocumentInput:
    """Durable job input for an exact document revision."""

    ref: DocumentRef


type JobInput = InputUrl | InputQuery | DocumentInput


@dataclass(frozen=True)
class JobRequest:
    """A durable request; ``worker_id`` optionally pins execution to one worker."""

    kind: str
    input: JobInput
    metadata: Mapping[str, FrozenJsonValue] = field(default_factory=dict)
    worker_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "metadata",
            MappingProxyType(
                {key: _freeze_json(value) for key, value in self.metadata.items()}
            ),
        )
        if self.worker_id == "":
            raise ValueError("worker_id must not be empty")


@dataclass(frozen=True)
class Job:
    """A queued job whose optional ``worker_id`` is enforced by queue backends."""

    kind: str
    input: JobInput
    metadata: Mapping[str, FrozenJsonValue] = field(default_factory=dict)
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    parent_id: uuid.UUID | None = None
    root_id: uuid.UUID | None = None
    worker_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "metadata",
            MappingProxyType(
                {key: _freeze_json(value) for key, value in self.metadata.items()}
            ),
        )
        if self.root_id is None:
            object.__setattr__(self, "root_id", self.id)
        if self.worker_id == "":
            raise ValueError("worker_id must not be empty")

    @classmethod
    def spawn_job(cls, request: JobRequest) -> Job:
        return cls(
            kind=request.kind,
            input=request.input,
            metadata=request.metadata,
            worker_id=request.worker_id,
        )

    def spawn_child(self, request: JobRequest) -> Job:
        return type(self)(
            kind=request.kind,
            input=request.input,
            metadata=cast(
                Mapping[str, FrozenJsonValue],
                {
                    **{key: _thaw_json(value) for key, value in self.metadata.items()},
                    **{
                        key: _thaw_json(value)
                        for key, value in request.metadata.items()
                    },
                },
            ),
            parent_id=self.id,
            root_id=self.root_id,
            worker_id=request.worker_id or self.worker_id,
        )

    def to_dict(self) -> dict[str, JsonValue]:
        """Return the small JSON payload sent through a durable job queue."""

        return {
            "id": str(self.id),
            "parent_id": str(self.parent_id) if self.parent_id else None,
            "root_id": str(self.root_id),
            "kind": self.kind,
            "input": _input_to_dict(self.input),
            "metadata": {key: _thaw_json(item) for key, item in self.metadata.items()},
            "worker_id": self.worker_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, JsonValue]) -> Self:
        parent_id = cast(str | None, value["parent_id"])
        return cls(
            id=uuid.UUID(cast(str, value["id"])),
            parent_id=uuid.UUID(parent_id) if parent_id else None,
            root_id=uuid.UUID(cast(str, value["root_id"])),
            kind=cast(str, value["kind"]),
            input=_input_from_dict(cast(dict[str, JsonValue], value["input"])),
            metadata=cast(Mapping[str, FrozenJsonValue], value["metadata"]),
            worker_id=cast(str | None, value.get("worker_id")),
        )

    @property
    def hash(self) -> str:
        payload = json.dumps(
            {"kind": self.kind, "input": _input_to_dict(self.input)},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class StoredJob:
    job: Job
    key: str
    status: JobStatus
    attempts: int = 0
    error: str | None = None


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


# NOTE: T is no longer of type dict[str, JsonValue] as it would make usage with
# TypedDict awkward but it doesn't mean that it does no longer need to be JSON
# serializable
# TODO: enforce in type system or in code this requirment in cleaner manner
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


def _input_to_dict(input: JobInput) -> dict[str, JsonValue]:
    match input:
        case InputUrl(url):
            return {"type": "url", "url": url}
        case InputQuery(query):
            return {"type": "query", "query": _thaw_json(query)}
        case DocumentInput(DocumentRef(store, value)):
            return {"type": "document-ref", "store": store, "ref": value}


def _input_from_dict(value: dict[str, JsonValue]) -> JobInput:
    match value["type"]:
        case "url":
            return InputUrl(cast(str, value["url"]))
        case "query":
            return InputQuery(cast(Mapping[str, FrozenJsonValue], value["query"]))
        case "document-ref":
            return DocumentInput(
                DocumentRef(cast(str, value["store"]), cast(str, value["ref"]))
            )
        case input_type:
            raise ValueError(f"unknown job input type: {input_type!r}")
